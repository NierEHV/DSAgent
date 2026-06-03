"""
数据源注册中心 + 路由器
管理多个数据源, 按路由规则决定每个 Agent 从哪取数据
"""

from __future__ import annotations

import logging
from typing import Optional

from .base import BaseAdapter
from .models import (
    InventorySnapshot, SalesData, AdMetrics, CompetitorSnapshot,
    ProfitData, ProductInfo, CompetitorProfile,
)
from mcp.mock_data import (
    PRODUCTS as MOCK_PRODUCTS,
    FBA_INVENTORY as MOCK_INVENTORY,
    SALES_DATA as MOCK_SALES,
    AD_CAMPAIGNS as MOCK_CAMPAIGNS,
    AD_PERFORMANCE_TODAY as MOCK_AD_PERF,
    PROFIT_DATA as MOCK_PROFIT,
    COMPETITOR_DATA as MOCK_COMPETITOR,
)

logger = logging.getLogger(__name__)


# 数据获取方法名 → 适配器方法
FETCH_METHODS = {
    "inventory": "fetch_inventory",
    "sales": "fetch_sales",
    "advertising": "fetch_advertising",
    "competitor": "fetch_competitor",
    "profit": "fetch_profit",
    "product": "fetch_products",
    "competitor_profiles": "fetch_competitor_profiles",
}

# 默认路由 (可被 YAML config 覆盖)
DEFAULT_ROUTING = {
    "inventory": ["lingxing", "sellersprite"],
    "sales": ["lingxing", "sellersprite", "sorftime"],
    "advertising": ["lingxing", "sellersprite"],
    "competitor": ["sellersprite", "sorftime"],
    "keyword": ["sellersprite", "sorftime"],
    "market": ["sellersprite", "sorftime"],
    "review": ["sellersprite", "sorftime"],
    "profit": ["lingxing"],
    "product": ["sellersprite", "sorftime", "lingxing"],
}


class DataSourceRegistry:
    """数据源注册中心"""

    def __init__(self):
        self._adapters: dict[str, BaseAdapter] = {}
        self._routing: dict[str, list[str]] = dict(DEFAULT_ROUTING)
        self.mock_mode: bool = False
        self.log = logger

    def register(self, name: str, adapter: BaseAdapter):
        self._adapters[name] = adapter
        self.log.info(f"数据源已注册: {name}")

    def get(self, name: str) -> Optional[BaseAdapter]:
        return self._adapters.get(name)

    def set_routing(self, routing: dict[str, list[str]]):
        self._routing.update(routing)

    @property
    def adapters(self) -> dict[str, BaseAdapter]:
        return dict(self._adapters)

    @property
    def all_online(self) -> bool:
        return all(a.is_online for a in self._adapters.values()) if self._adapters else False

    async def health_check_all(self) -> dict:
        results = {}
        for name, adapter in self._adapters.items():
            results[name] = await adapter.health_check()
        return results

    # ──── 核心路由获取 ────

    async def fetch(self, data_type: str, params: dict = None) -> list:
        """
        根据路由规则拉取标准化数据

        data_type: inventory / sales / advertising / competitor / profit / product
        params: 查询参数 (asin_list, msku_list, days 等)
        """
        params = params or {}
        sources = self._routing.get(data_type, [])

        last_error = None
        for source_name in sources:
            adapter = self._adapters.get(source_name)
            if not adapter:
                continue

            method_name = FETCH_METHODS.get(data_type)
            if not method_name:
                continue

            try:
                method = getattr(adapter, method_name)
                result = await method(params)
                if result:
                    return result
                # 返回空列表可能是数据源不支持此类型, 继续尝试下一个
                self.log.info(f"{source_name}.{method_name} 返回空, 尝试下一个")
            except Exception as e:
                last_error = str(e)
                self.log.warning(f"{source_name} 查询 {data_type} 失败: {e}")
                continue

        # 所有数据源都失败 → Mock 降级 (仅开发模式)
        if self.mock_mode:
            self.log.warning(f"所有数据源不可用, 降级到 Mock: {data_type}")
            return self._mock_fallback(data_type, params)

        # 生产环境: 返回空, 不降级
        self.log.error(f"所有数据源不可用: {data_type}. 最后错误: {last_error}")
        return []

    def _mock_fallback(self, data_type: str, params: dict) -> list:
        """Mock 数据降级 (仅开发模式) — 使用动态 Mock 引擎"""
        from .models import DataProvenance
        from .dynamic_mock import dynamic_mock
        from datetime import datetime
        prov = DataProvenance(
            source="mock", source_type="mock", platform="amazon_us",
            marketplace="ATVPDKIKX0DER", fetched_at=datetime.now().isoformat(),
            query_duration_ms=0, is_fresh=True,
        )

        if data_type == "inventory":
            return [InventorySnapshot(
                sku=i["msku"], asin=i["asin"],
                fba_stock=i.get("available_qty", 0),
                reserved_stock=i.get("reserved_qty", 0),
                inbound_stock=i.get("inbound_qty", 0),
                warehouse=i.get("warehouse", ""),
                provenance=prov,
            ) for i in dynamic_mock.get_inventory()]

        if data_type == "sales":
            return [SalesData(
                sku=s["msku"], asin=s["asin"],
                daily_avg_7d=s.get("daily_avg_7d", 0),
                daily_avg_30d=s.get("daily_avg_30d", 0),
                trend=s.get("trend", "stable"),
                change_pct=s.get("change_pct", 0),
                provenance=prov,
            ) for s in dynamic_mock.get_sales()]

        if data_type == "advertising":
            return [AdMetrics(
                campaign_id=p["campaign_id"],
                campaign_name=next((c["campaign_name"] for c in MOCK_CAMPAIGNS if c["campaign_id"] == p["campaign_id"]), ""),
                ad_type=next((c["type"] for c in MOCK_CAMPAIGNS if c["campaign_id"] == p["campaign_id"]), "SP"),
                spend=p.get("spend", 0), sales=p.get("sales", 0),
                impressions=p.get("impressions", 0), clicks=p.get("clicks", 0),
                acos=p.get("acos", 0), roas=p.get("roas", 0),
                cpc=p.get("cpc", 0), ctr=p.get("ctr", 0),
                budget=next((c["budget"] for c in MOCK_CAMPAIGNS if c["campaign_id"] == p["campaign_id"]), 0),
                orders=p.get("orders", 0),
                avg_acos_14d=p.get("avg_acos_14d", 0),
                anomaly_type=p.get("anomaly"),
                budget_used_pct=p.get("budget_used_pct", 0),
                provenance=prov,
            ) for p in dynamic_mock.get_advertising()]

        if data_type == "competitor":
            return [CompetitorSnapshot(
                asin=c["asin"],
                buy_box_owner=c.get("buy_box_owner", ""),
                buy_box_price=c.get("buy_box_price", 0),
                seller_count=c.get("seller_count", 0),
                sellers=c.get("sellers", []),
                buy_box_is_ours=c.get("buy_box_is_ours", False),
                bsr=c.get("bsr", 0),
                bsr_change=c.get("bsr_change_7d", 0),
                provenance=prov,
            ) for c in dynamic_mock.get_competitor()]

        if data_type == "profit":
            return [ProfitData(
                sku=p["msku"], asin=p["asin"],
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
            ) for p in dynamic_mock.get_profit()]

        if data_type == "product":
            return [ProductInfo(
                sku=p["msku"], asin=p["asin"],
                name=p.get("name", ""), brand=p.get("brand", ""),
                price=p.get("price", 0), cost=p.get("cost", 0),
                category=p.get("category", ""), status=p.get("status", "active"),
                provenance=prov,
            ) for p in dynamic_mock.get_products()]

        return []
