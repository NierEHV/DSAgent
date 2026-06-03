"""
MCP 客户端 — 通过 HTTP 调用 MCP Server 的工具
积木式集成：只需配置 URL，自动发现和调用工具

Mock 模式：当 MCP Server 不可用时，自动降级使用本地 mock_data
"""

from __future__ import annotations

import os
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

MOCK_MODE = os.environ.get("MOCK_MODE", "true").lower() in ("true", "1", "yes")


class MCPClient:
    """MCP 工具调用客户端 — 通过 HTTP 与 MCP Server 通信"""

    def __init__(self, name: str, base_url: str, timeout: int = 10):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._tools_cache: Optional[list[dict]] = None
        self._offline = MOCK_MODE  # Mock 模式默认离线

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
                resp = await client.get(f"{self.base_url}/health")
                self._offline = False
                return resp.json()
        except Exception as e:
            self._offline = True
            return {"service": self.name, "status": "offline", "mode": "mock_fallback", "error": str(e)[:100]}

    async def list_tools(self) -> list[dict]:
        if self._tools_cache:
            return self._tools_cache
        if self._offline:
            return self._get_mock_tools()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
                resp = await client.get(f"{self.base_url}/tools")
                data = resp.json()
                self._tools_cache = data.get("tools", [])
                return self._tools_cache
        except Exception:
            self._offline = True
            return self._get_mock_tools()

    async def call(self, tool_name: str, params: dict = None) -> dict:
        """调用工具 — 自动降级到 mock 数据"""
        params = params or {}

        if self._offline:
            return self._mock_call(tool_name, params)

        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
                resp = await client.post(
                    f"{self.base_url}/call/{tool_name}",
                    json=params,
                )
                data = resp.json()
                if not data.get("success"):
                    logger.warning(f"[{self.name}] {tool_name}: {data.get('error')}")
                return data
        except Exception as e:
            logger.info(f"[{self.name}] {tool_name} — MCP 不可用，使用 mock 数据")
            self._offline = True
            return self._mock_call(tool_name, params)

    def _mock_call(self, tool_name: str, params: dict) -> dict:
        """本地 Mock 数据调用"""
        from .mock_data import (
            PRODUCTS, FBA_INVENTORY, SALES_DATA, INBOUND_SHIPMENTS,
            PROFIT_DATA, AD_CAMPAIGNS, AD_PERFORMANCE_TODAY, AD_PERFORMANCE_14D_AVG,
            COMPETITOR_DATA, DAILY_SUMMARY,
        )
        from datetime import datetime

        mock_handlers = {
            # 领星 ERP
            "get_products": lambda **kw: {"result": {"products": PRODUCTS, "count": len(PRODUCTS)}},
            "get_fba_inventory": lambda **kw: {"result": {"inventory": FBA_INVENTORY, "count": len(FBA_INVENTORY), "snapshot_time": datetime.now().isoformat()}},
            "get_sales_data": lambda **kw: {"result": {"sales_data": SALES_DATA, "days": kw.get("days", 7), "count": len(SALES_DATA)}},
            "get_inbound_shipments": lambda **kw: {"result": {"shipments": INBOUND_SHIPMENTS, "count": len(INBOUND_SHIPMENTS)}},
            "get_profit_report": lambda **kw: {"result": {
                "profit_data": PROFIT_DATA,
                "summary": {
                    "total_revenue": sum(p["revenue"] for p in PROFIT_DATA),
                    "total_gross_profit": sum(p["gross_profit"] for p in PROFIT_DATA),
                    "avg_gross_margin": round(sum(p["gross_margin"] for p in PROFIT_DATA) / len(PROFIT_DATA), 1),
                },
                "count": len(PROFIT_DATA),
            }},
            # 广告 API
            "get_ad_campaigns": lambda **kw: {"result": {"campaigns": AD_CAMPAIGNS, "count": len(AD_CAMPAIGNS)}},
            "get_ad_performance_today": lambda **kw: {"result": {
                "performance": [
                    {**p, "avg_acos_14d": next((a["avg_acos"] for a in AD_PERFORMANCE_14D_AVG if a["campaign_id"] == p["campaign_id"]), 0),
                     "campaign_name": next((c["campaign_name"] for c in AD_CAMPAIGNS if c["campaign_id"] == p["campaign_id"]), ""),
                     "acos_change_vs_14d": round(p["acos"] - next((a["avg_acos"] for a in AD_PERFORMANCE_14D_AVG if a["campaign_id"] == p["campaign_id"]), p["acos"]), 1),
                     "budget_utilization": round(p["spend"] / next((c["budget"] for c in AD_CAMPAIGNS if c["campaign_id"] == p["campaign_id"]), 1) * 100, 1),
                     "anomaly": None}
                    for p in AD_PERFORMANCE_TODAY
                ],
                "snapshot_time": datetime.now().isoformat(),
            }},
            "get_budget_status": lambda **kw: {"result": {
                "budgets": [
                    {**c, "spend": next((p["spend"] for p in AD_PERFORMANCE_TODAY if p["campaign_id"] == c["campaign_id"]), 0),
                     "remaining": round(c["budget"] - next((p["spend"] for p in AD_PERFORMANCE_TODAY if p["campaign_id"] == c["campaign_id"]), 0), 2),
                     "utilization": round(next((p["spend"] for p in AD_PERFORMANCE_TODAY if p["campaign_id"] == c["campaign_id"]), 0) / c["budget"] * 100, 1),
                     "status": "normal"}
                    for c in AD_CAMPAIGNS
                ],
                "total_spend": round(sum(p["spend"] for p in AD_PERFORMANCE_TODAY), 2),
                "total_budget": sum(c["budget"] for c in AD_CAMPAIGNS),
            }},
            # 亚马逊 SP-API
            "get_buy_box": lambda **kw: {"result": {
                "buy_boxes": [
                    {"asin": c["asin"], "buy_box_owner": c["buy_box_owner"], "buy_box_price": c["buy_box_price"],
                     "is_self": c["buy_box_owner"] == "self", "seller_count": c["seller_count"], "sellers": c["sellers"]}
                    for c in COMPETITOR_DATA
                ],
                "our_buy_box_rate": sum(1 for c in COMPETITOR_DATA if c["buy_box_owner"] == "self") / len(COMPETITOR_DATA),
            }},
            "get_new_sellers": lambda **kw: {"result": {
                "new_sellers": [
                    {"asin": c["asin"], "seller_name": s["name"], "seller_price": s["price"],
                     "seller_rating": s["rating"], "our_price": c["buy_box_price"],
                     "detected_at": datetime.now().isoformat(), "risk": "HIGH" if s["rating"] < 3.0 else "MEDIUM"}
                    for c in COMPETITOR_DATA for s in c["sellers"]
                    if not s["is_self"] and (s["rating"] < 3.0 or s["price"] < c["buy_box_price"] * 0.8)
                ],
                "total_found": sum(1 for c in COMPETITOR_DATA for s in c["sellers"] if not s["is_self"] and (s["rating"] < 3.0 or s["price"] < c["buy_box_price"] * 0.8)),
            }},
            "get_price_comparison": lambda **kw: {"result": {
                "price_comparisons": [
                    {"asin": c["asin"], "our_price": next((s["price"] for s in c["sellers"] if s["is_self"]), c["buy_box_price"]),
                     "min_competitor_price": min((s["price"] for s in c["sellers"] if not s["is_self"]), default=c["buy_box_price"]),
                     "price_diff_pct": round((next((s["price"] for s in c["sellers"] if s["is_self"]), c["buy_box_price"]) - min((s["price"] for s in c["sellers"] if not s["is_self"]), default=c["buy_box_price"])) / next((s["price"] for s in c["sellers"] if s["is_self"]), 1) * 100, 1)}
                    for c in COMPETITOR_DATA
                ],
            }},
        }

        handler = mock_handlers.get(tool_name)
        if handler:
            result = handler(**params)
            result["success"] = True
            result["tool"] = tool_name
            result["duration_ms"] = 1
            result["mock"] = True
            return result
        return {"success": False, "error": f"Mock 工具未实现: {tool_name}", "mock": True}

    def _get_mock_tools(self) -> list[dict]:
        """返回 mock 工具列表"""
        mock_tools = {
            "lingxing": [
                {"name": "get_fba_inventory", "description": "查询FBA库存"},
                {"name": "get_sales_data", "description": "查询销量数据"},
                {"name": "get_inbound_shipments", "description": "查询在途库存"},
                {"name": "get_profit_report", "description": "查询利润报表"},
                {"name": "get_products", "description": "查询商品列表"},
                {"name": "get_orders", "description": "查询订单"},
            ],
            "amazon_sp": [
                {"name": "get_buy_box", "description": "查询Buy Box"},
                {"name": "get_new_sellers", "description": "检测新卖家"},
                {"name": "get_price_comparison", "description": "价格对比"},
                {"name": "get_bsr", "description": "查询BSR排名"},
            ],
            "ad_api": [
                {"name": "get_ad_campaigns", "description": "查询广告活动"},
                {"name": "get_ad_performance_today", "description": "查询今日广告表现"},
                {"name": "get_budget_status", "description": "查询预算状态"},
                {"name": "get_keyword_performance", "description": "查询关键词表现"},
            ],
        }
        return mock_tools.get(self.name, [])

    def __repr__(self):
        mode = "offline(mock)" if self._offline else "online"
        return f"<MCPClient: {self.name} ({self.base_url}) [{mode}]>"


class MCPHub:
    """
    MCP 集成中心 — 管理所有 MCP Server 连接
    Mock 模式自动降级到本地数据，无需启动额外服务
    """

    def __init__(self):
        self.clients: dict[str, MCPClient] = {}
        self._init_from_env()

    def _init_from_env(self):
        servers = {
            "lingxing": os.environ.get("MCP_LINGXING_URL", "http://localhost:8001"),
            "amazon_sp": os.environ.get("MCP_AMAZON_SP_URL", "http://localhost:8002"),
            "ad_api": os.environ.get("MCP_AD_API_URL", "http://localhost:8003"),
        }
        for name, url in servers.items():
            if url:
                self.register(name, url)

    def register(self, name: str, base_url: str) -> MCPClient:
        client = MCPClient(name, base_url)
        self.clients[name] = client
        return client

    def get(self, name: str) -> Optional[MCPClient]:
        return self.clients.get(name)

    def __getattr__(self, name: str) -> MCPClient:
        if name in self.clients:
            return self.clients[name]
        raise AttributeError(f"MCP Server 未注册: {name}")

    async def check_all(self) -> dict:
        results = {}
        for name, client in self.clients.items():
            try:
                results[name] = await client.health()
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
        return results


# 全局单例
mcp_hub = MCPHub()
