"""
领星 ERP 适配器
REST API 协议, 覆盖商品/库存/订单/财务/广告
"""

from __future__ import annotations

import time
from datetime import datetime

from .base import BaseAdapter
from .models import (
    InventorySnapshot, SalesData, AdMetrics, CompetitorSnapshot,
    ProfitData, ProductInfo, CompetitorProfile,
)


class LingxingAdapter(BaseAdapter):
    """领星 ERP 适配器"""

    source_name = "lingxing"

    def _source_type(self) -> str:
        return "rest_api"

    async def fetch_inventory(self, params: dict) -> list[InventorySnapshot]:
        if not self.client:
            return []
        msku_list = params.get("msku_list")
        start = time.time()
        resp = await self.client.call("get_fba_inventory",
            {"msku_list": msku_list} if msku_list else {})
        raw = resp.get("result", {})
        inventory_list = raw.get("inventory", [])
        prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))

        results = []
        for inv in inventory_list:
            results.append(InventorySnapshot(
                sku=inv.get("msku", ""),
                asin=inv.get("asin", ""),
                fba_stock=inv.get("available_qty", 0),
                reserved_stock=inv.get("reserved_qty", 0),
                inbound_stock=inv.get("inbound_qty", 0),
                warehouse=inv.get("warehouse", ""),
                provenance=prov,
            ))
        return results

    async def fetch_sales(self, params: dict) -> list[SalesData]:
        if not self.client:
            return []
        start = time.time()
        resp = await self.client.call("get_sales_data", {"days": params.get("days", 7)})
        raw = resp.get("result", {})
        sales_list = raw.get("sales_data", [])
        prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))

        results = []
        for s in sales_list:
            results.append(SalesData(
                sku=s.get("msku", ""),
                asin=s.get("asin", ""),
                daily_avg_7d=s.get("daily_avg_7d", 0),
                daily_avg_30d=s.get("daily_avg_30d", 0),
                trend=s.get("trend", "stable"),
                change_pct=s.get("change_pct", 0),
                provenance=prov,
            ))
        return results

    async def fetch_advertising(self, params: dict) -> list[AdMetrics]:
        if not self.client:
            return []
        start = time.time()
        campaigns_resp = await self.client.call("get_ad_campaigns", {})
        perf_resp = await self.client.call("get_ad_report", {})

        campaigns = campaigns_resp.get("result", {}).get("campaigns", [])
        performance = perf_resp.get("result", {}).get("performance", [])
        prov = self._make_provenance(duration_ms=perf_resp.get("duration_ms", 0))

        results = []
        for perf in performance:
            campaign = next((c for c in campaigns if c.get("campaign_id") == perf.get("campaign_id")), {})
            results.append(AdMetrics(
                campaign_id=perf.get("campaign_id", ""),
                campaign_name=campaign.get("campaign_name", perf.get("campaign_id", "")),
                ad_type=campaign.get("type", "SP"),
                spend=perf.get("spend", 0),
                sales=perf.get("sales", 0),
                impressions=perf.get("impressions", 0),
                clicks=perf.get("clicks", 0),
                acos=perf.get("acos", 0),
                roas=perf.get("roas", 0),
                cpc=perf.get("cpc", 0),
                ctr=perf.get("ctr", 0),
                budget=campaign.get("budget", 0),
                budget_used_pct=round(perf.get("spend", 0) / campaign.get("budget", 1) * 100, 1),
                orders=perf.get("orders", 0),
                avg_acos_14d=perf.get("avg_acos_14d", 0),
                anomaly_type=perf.get("anomaly"),
                provenance=prov,
            ))
        return results

    async def fetch_competitor(self, params: dict) -> list[CompetitorSnapshot]:
        """领星 ERP 不直接提供竞品数据, 返回空"""
        return []

    async def fetch_profit(self, params: dict) -> list[ProfitData]:
        if not self.client:
            return []
        start = time.time()
        resp = await self.client.call("get_profit_report", {})
        raw = resp.get("result", {})
        profit_list = raw.get("profit_data", [])
        prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))

        results = []
        for p in profit_list:
            results.append(ProfitData(
                sku=p.get("msku", ""),
                asin=p.get("asin", ""),
                date=p.get("date", ""),
                revenue=p.get("revenue", 0),
                sales_qty=p.get("sales_qty", 0),
                gross_profit=p.get("gross_profit", 0),
                gross_margin=p.get("gross_margin", 0),
                refund_rate=p.get("refund_rate", 0),
                refund_amount=p.get("refund_amount", 0),
                ad_spend=p.get("ad_spend", 0),
                ad_ratio=p.get("ad_ratio", 0),
                fba_fees=p.get("fba_fees", 0),
                cogs=p.get("cogs", 0),
                provenance=prov,
            ))
        return results

    async def fetch_products(self, params: dict) -> list[ProductInfo]:
        if not self.client:
            return []
        start = time.time()
        resp = await self.client.call("get_products", {})
        raw = resp.get("result", {})
        product_list = raw.get("products", [])
        prov = self._make_provenance(duration_ms=resp.get("duration_ms", 0))

        results = []
        for p in product_list:
            results.append(ProductInfo(
                sku=p.get("msku", ""),
                asin=p.get("asin", ""),
                name=p.get("name", ""),
                brand=p.get("brand", ""),
                price=p.get("price", 0),
                cost=p.get("cost", 0),
                category=p.get("category", ""),
                status=p.get("status", "active"),
                provenance=prov,
            ))
        return results

    async def fetch_competitor_profiles(self, params: dict) -> list[CompetitorProfile]:
        """领星不提供竞品发现"""
        return []
