"""
Sorftime MCP 适配器
34+ 工具, 覆盖 Amazon/Walmart/Shopee/TikTok/1688
MCP HTTP 协议
"""

from __future__ import annotations

import time
from datetime import datetime

from .base import BaseAdapter
from .models import (
    InventorySnapshot, SalesData, AdMetrics, CompetitorSnapshot,
    ProfitData, ProductInfo, CompetitorProfile,
)


class SorftimeAdapter(BaseAdapter):
    """Sorftime 适配器"""

    source_name = "sorftime"

    def _source_type(self) -> str:
        return "mcp_http"

    async def fetch_inventory(self, params: dict) -> list[InventorySnapshot]:
        if not self.client:
            return []
        asin_list = params.get("asin_list", [])
        results = []
        for asin in asin_list:
            start = time.time()
            resp = await self.client.call("product_detail", {"asin": asin})
            raw = resp.get("result", resp)
            prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))
            results.append(InventorySnapshot(
                sku=raw.get("asinCode", asin),
                asin=asin,
                product_name=raw.get("title", ""),
                fba_stock=raw.get("fbaStock", 0),
                daily_sales=round(raw.get("sales30d", 0) / 30, 1),
                provenance=prov,
            ))
        return results

    async def fetch_sales(self, params: dict) -> list[SalesData]:
        if not self.client:
            return []
        asin_list = params.get("asin_list", [])
        results = []
        for asin in asin_list:
            start = time.time()
            resp = await self.client.call("product_trend", {"asin": asin})
            raw = resp.get("result", resp)
            prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))
            results.append(SalesData(
                sku=raw.get("asinCode", asin),
                asin=asin,
                daily_avg_7d=round(raw.get("sales7d", 0) / 7, 1),
                daily_avg_30d=round(raw.get("sales30d", 0) / 30, 1),
                trend=raw.get("trend", "stable"),
                provenance=prov,
            ))
        return results

    async def fetch_advertising(self, params: dict) -> list[AdMetrics]:
        return []

    async def fetch_competitor(self, params: dict) -> list[CompetitorSnapshot]:
        if not self.client:
            return []
        asin_list = params.get("asin_list", [])
        results = []
        for asin in asin_list:
            start = time.time()
            # Sorftime: 产品详情含卖家信息
            resp = await self.client.call("product_detail", {"asin": asin})
            raw = resp.get("result", resp)
            prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))
            results.append(CompetitorSnapshot(
                asin=asin,
                buy_box_owner=raw.get("buyBoxOwner", ""),
                buy_box_price=raw.get("buyBoxPrice", 0),
                our_price=raw.get("ourPrice", 0),
                seller_count=raw.get("sellerCount", 0),
                buy_box_is_ours=raw.get("buyBoxIsOurs", False),
                bsr=raw.get("bSRRank", 0),
                provenance=prov,
            ))
        return results

    async def fetch_profit(self, params: dict) -> list[ProfitData]:
        return []

    async def fetch_products(self, params: dict) -> list[ProductInfo]:
        if not self.client:
            return []
        asin_list = params.get("asin_list", [])
        results = []
        for asin in asin_list:
            start = time.time()
            resp = await self.client.call("product_detail", {"asin": asin})
            raw = resp.get("result", resp)
            prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))
            results.append(ProductInfo(
                sku=raw.get("asinCode", asin),
                asin=asin,
                name=raw.get("title", ""),
                brand=raw.get("brand", ""),
                price=raw.get("currentPrice", 0),
                category=raw.get("category", ""),
                provenance=prov,
            ))
        return results

    async def fetch_competitor_profiles(self, params: dict) -> list[CompetitorProfile]:
        if not self.client:
            return []
        keywords = params.get("keywords", [])
        profiles = []
        seen = set()
        for kw in keywords[:5]:
            resp = await self.client.call("hot_keywords", {"keyword": kw})
            products = resp.get("result", {}).get("products", [])[:20]
            for p in products:
                asin = p.get("asinCode", "")
                if asin in seen or asin in params.get("exclude_asins", []):
                    continue
                seen.add(asin)
                prov = self._make_provenance()
                profiles.append(CompetitorProfile(
                    asin=asin,
                    name=p.get("title", ""),
                    price=p.get("currentPrice", 0),
                    bsr=p.get("bSRRank", 0),
                    reviews=p.get("reviewCount", 0),
                    rating=p.get("rating", 0),
                    discovery_path="keyword",
                    discovery_keyword=kw,
                    first_seen=datetime.now().isoformat(),
                    last_updated=datetime.now().isoformat(),
                    provenance=prov,
                ))
        return profiles
