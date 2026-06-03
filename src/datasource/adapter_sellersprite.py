"""
卖家精灵 MCP 适配器
42 工具, Amazon 全站点, MCP SSE 协议

原始字段 → 标准化模型映射
"""

from __future__ import annotations

import time
from datetime import datetime

from .base import BaseAdapter
from .models import (
    InventorySnapshot, SalesData, AdMetrics, CompetitorSnapshot,
    ProfitData, ProductInfo, CompetitorProfile,
)


class SellerSpriteAdapter(BaseAdapter):
    """卖家精灵适配器"""

    source_name = "sellersprite"

    def _source_type(self) -> str:
        return "mcp_sse"

    # ──── 各数据获取 ────

    async def fetch_inventory(self, params: dict) -> list[InventorySnapshot]:
        """库存 → asin_detail + keepa_info (BSR/销量趋势估算库存)"""
        if not self.client:
            return []
        asin_list = params.get("asin_list", [])
        results = []
        for asin in asin_list:
            start = time.time()
            resp = await self.client.call("asin_detail", {"asin": asin})
            raw = resp.get("result", resp)
            prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))
            results.append(InventorySnapshot(
                sku=raw.get("asin", asin),
                asin=asin,
                product_name=raw.get("title", ""),
                fba_stock=raw.get("stock_quantity", 0),
                daily_sales=round(raw.get("sales_30d", 0) / 30, 1),
                provenance=prov,
            ))
        return results

    async def fetch_sales(self, params: dict) -> list[SalesData]:
        """销量 → competitor_lookup 获取销量数据"""
        if not self.client:
            return []
        asin_list = params.get("asin_list", [])
        results = []
        for asin in asin_list:
            start = time.time()
            resp = await self.client.call("competitor_lookup", {"asin": asin})
            raw = resp.get("result", resp)
            prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))
            results.append(SalesData(
                sku=raw.get("asin", asin),
                asin=asin,
                daily_avg_7d=round(raw.get("sales_7d", 0) / 7, 1),
                daily_avg_30d=round(raw.get("sales_30d", 0) / 30, 1),
                trend="up" if raw.get("sales_trend", "") == "up" else "down" if raw.get("sales_trend") == "down" else "stable",
                change_pct=raw.get("sales_change_pct", 0),
                provenance=prov,
            ))
        return results

    async def fetch_advertising(self, params: dict) -> list[AdMetrics]:
        """卖家精灵不直接提供广告数据, 返回空"""
        return []

    async def fetch_competitor(self, params: dict) -> list[CompetitorSnapshot]:
        """竞品 → get_buy_box + get_new_sellers + get_price_comparison"""
        if not self.client:
            return []
        asin_list = params.get("asin_list", [])
        results = []
        for asin in asin_list:
            start = time.time()
            prov = self._make_provenance(duration_ms=0)

            # 并行拉 Buy Box + 新卖家 + 价格
            bb_resp = await self.client.call("get_buy_box", {"asin_list": [asin]})
            ns_resp = await self.client.call("get_new_sellers", {"asin_list": [asin]})
            price_resp = await self.client.call("get_price_comparison", {"asin_list": [asin]})

            bb_data = bb_resp.get("result", {}).get("buy_boxes", [{}])
            ns_data = ns_resp.get("result", {}).get("new_sellers", [])
            price_data = price_resp.get("result", {}).get("price_comparisons", [{}])

            bb_info = bb_data[0] if bb_data else {}
            price_info = price_data[0] if price_data else {}
            prov.query_duration_ms = resp.get("duration_ms", 0) if (resp := bb_resp) else 0

            results.append(CompetitorSnapshot(
                asin=asin,
                buy_box_owner=bb_info.get("buy_box_owner", ""),
                buy_box_price=bb_info.get("buy_box_price", 0),
                our_price=price_info.get("our_price", 0),
                seller_count=bb_info.get("seller_count", 0),
                new_sellers=ns_data,
                bsr=bb_info.get("bsr", 0),
                buy_box_is_ours=bb_info.get("is_self", False),
                provenance=prov,
            ))
        return results

    async def fetch_profit(self, params: dict) -> list[ProfitData]:
        """卖家精灵不提供利润数据"""
        return []

    async def fetch_products(self, params: dict) -> list[ProductInfo]:
        """商品 → asin_detail"""
        if not self.client:
            return []
        asin_list = params.get("asin_list", [])
        results = []
        for asin in asin_list:
            start = time.time()
            resp = await self.client.call("asin_detail", {"asin": asin})
            raw = resp.get("result", resp)
            prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))
            results.append(ProductInfo(
                sku=raw.get("asin", asin),
                asin=asin,
                name=raw.get("title", ""),
                brand=raw.get("brand", ""),
                price=raw.get("price", 0),
                category=raw.get("category", ""),
                provenance=prov,
            ))
        return results

    async def fetch_competitor_profiles(self, params: dict) -> list[CompetitorProfile]:
        """竞品发现 → keyword_research + category 扫描"""
        if not self.client:
            return []
        keywords = params.get("keywords", [])
        profiles = []
        seen = set()

        for kw in keywords[:5]:  # 限制前5个关键词避免调用过多
            resp = await self.client.call("keyword_research", {"keyword": kw})
            products = resp.get("result", {}).get("products", [])[:20]
            for p in products:
                asin = p.get("asin", "")
                if asin in seen or asin in params.get("exclude_asins", []):
                    continue
                seen.add(asin)
                prov = self._make_provenance()
                profiles.append(CompetitorProfile(
                    asin=asin,
                    name=p.get("title", ""),
                    price=p.get("price", 0),
                    bsr=p.get("bsr", 0),
                    reviews=p.get("reviews", 0),
                    rating=p.get("rating", 0),
                    discovery_path="keyword",
                    discovery_keyword=kw,
                    first_seen=datetime.now().isoformat(),
                    last_updated=datetime.now().isoformat(),
                    provenance=prov,
                ))
        return profiles
