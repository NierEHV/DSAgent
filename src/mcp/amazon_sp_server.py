"""
亚马逊 SP-API MCP Server — Mock 实现
封装商品详情、Buy Box、BSR、跟卖监控等工具

API 端点:
  GET  /health           — 健康检查
  GET  /tools             — 列出可用工具
  POST /call/{tool_name}  — 调用工具
"""

from __future__ import annotations

import time
from datetime import datetime
from fastapi import FastAPI, HTTPException

from .mock_data import COMPETITOR_DATA, PRODUCTS, TODAY

app = FastAPI(title="亚马逊 SP-API MCP Server", version="1.0.0")

TOOLS = {
    "get_buy_box": {
        "name": "get_buy_box",
        "description": "查询指定ASIN的Buy Box状态和卖家列表",
        "parameters": {"asin_list": "list[str] — ASIN列表"},
        "risk_level": "READ_ONLY",
    },
    "get_bsr": {
        "name": "get_bsr",
        "description": "查询BSR(Best Seller Rank)及近期变化",
        "parameters": {"asin_list": "list[str]"},
        "risk_level": "READ_ONLY",
    },
    "get_seller_list": {
        "name": "get_seller_list",
        "description": "获取ASIN下的所有第三方卖家信息",
        "parameters": {"asin": "str"},
        "risk_level": "READ_ONLY",
    },
    "get_new_sellers": {
        "name": "get_new_sellers",
        "description": "检测新出现的卖家（可能为跟卖者）",
        "parameters": {"asin_list": "list[str]", "lookback_hours": "int = 24"},
        "risk_level": "READ_ONLY",
    },
    "get_price_comparison": {
        "name": "get_price_comparison",
        "description": "我方价格 vs 竞品价格对比",
        "parameters": {"asin_list": "list[str]"},
        "risk_level": "READ_ONLY",
    },
    "get_catalog_item": {
        "name": "get_catalog_item",
        "description": "获取亚马逊目录中的商品详细信息",
        "parameters": {"asin": "str"},
        "risk_level": "READ_ONLY",
    },
}

@app.get("/health")
async def health():
    return {
        "service": "amazon-sp-api",
        "status": "connected",
        "mode": "mock",
        "tool_count": len(TOOLS),
    }


@app.get("/tools")
async def list_tools():
    return {"service": "amazon-sp-api", "tools": list(TOOLS.values())}


@app.post("/call/{tool_name}")
async def call_tool(tool_name: str, params: dict = None):
    if tool_name not in TOOLS:
        raise HTTPException(status_code=404, detail=f"工具不存在: {tool_name}")

    params = params or {}
    start = time.time()

    try:
        result = await _dispatch(tool_name, params)
        return {
            "success": True,
            "tool": tool_name,
            "result": result,
            "duration_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {
            "success": False,
            "tool": tool_name,
            "error": str(e),
            "duration_ms": int((time.time() - start) * 1000),
        }


async def _dispatch(tool_name: str, params: dict):
    dispatch_map = {
        "get_buy_box": _get_buy_box,
        "get_bsr": _get_bsr,
        "get_seller_list": _get_seller_list,
        "get_new_sellers": _get_new_sellers,
        "get_price_comparison": _get_price_comparison,
        "get_catalog_item": _get_catalog_item,
    }
    handler = dispatch_map.get(tool_name)
    if handler:
        return await handler(**params)
    return {"error": "未实现的工具"}


async def _get_buy_box(asin_list: list[str], **kwargs):
    results = []
    for asin in asin_list:
        comp = next((c for c in COMPETITOR_DATA if c["asin"] == asin), None)
        if comp:
            results.append({
                "asin": asin,
                "buy_box_owner": comp["buy_box_owner"],
                "buy_box_price": comp["buy_box_price"],
                "is_self": comp["buy_box_owner"] == "self",
                "seller_count": comp["seller_count"],
                "sellers": comp["sellers"],
            })
    return {"buy_boxes": results, "our_buy_box_rate": sum(1 for r in results if r["is_self"]) / len(results) if results else 0}


async def _get_bsr(asin_list: list[str], **kwargs):
    results = []
    for asin in asin_list:
        comp = next((c for c in COMPETITOR_DATA if c["asin"] == asin), None)
        if comp:
            results.append({
                "asin": asin,
                "current_bsr": comp["bsr"],
                "bsr_change_7d": comp["bsr_change_7d"],
                "trend": "up" if comp["bsr_change_7d"] < 0 else "down",
            })
    return {"bsr_data": results}


async def _get_seller_list(asin: str, **kwargs):
    comp = next((c for c in COMPETITOR_DATA if c["asin"] == asin), None)
    if not comp:
        return {"error": f"ASIN {asin} 无数据"}
    return {
        "asin": asin,
        "sellers": comp["sellers"],
        "seller_count": comp["seller_count"],
        "has_hijackers": any(not s["is_self"] and s["rating"] < 3.0 for s in comp["sellers"]),
    }


async def _get_new_sellers(asin_list: list[str], lookback_hours: int = 24, **kwargs):
    # Mock: 模拟发现新跟卖者
    findings = []
    for asin in asin_list:
        comp = next((c for c in COMPETITOR_DATA if c["asin"] == asin), None)
        if not comp:
            continue
        # 找出可能是新出现的卖家（评分低或价格异常）
        new_sellers = [
            s for s in comp["sellers"]
            if not s["is_self"] and (s["rating"] < 3.0 or s["price"] < comp["buy_box_price"] * 0.8)
        ]
        if new_sellers:
            for seller in new_sellers:
                findings.append({
                    "asin": asin,
                    "seller_name": seller["name"],
                    "seller_price": seller["price"],
                    "seller_rating": seller["rating"],
                    "our_price": comp["buy_box_price"] if comp["buy_box_owner"] == "self" else next(
                        (s["price"] for s in comp["sellers"] if s["is_self"]), comp["buy_box_price"]
                    ),
                    "detected_at": datetime.now().isoformat(),
                    "risk": "HIGH" if seller["rating"] < 3.0 else "MEDIUM",
                })
    return {"new_sellers": findings, "total_found": len(findings)}


async def _get_price_comparison(asin_list: list[str], **kwargs):
    results = []
    for asin in asin_list:
        comp = next((c for c in COMPETITOR_DATA if c["asin"] == asin), None)
        if not comp:
            continue
        our_seller = next((s for s in comp["sellers"] if s["is_self"]), None)
        our_price = our_seller["price"] if our_seller else comp["buy_box_price"]
        min_comp_price = min(
            (s["price"] for s in comp["sellers"] if not s["is_self"]),
            default=our_price,
        )
        results.append({
            "asin": asin,
            "our_price": our_price,
            "min_competitor_price": min_comp_price,
            "price_diff_pct": round((our_price - min_comp_price) / our_price * 100, 1),
            "competitive": our_price <= min_comp_price * 1.05,
            "avg_competitor_price": round(
                sum(s["price"] for s in comp["sellers"] if not s["is_self"]) / max(1, sum(1 for s in comp["sellers"] if not s["is_self"])), 2
            ),
        })
    return {"price_comparisons": results}


async def _get_catalog_item(asin: str, **kwargs):
    product = next((p for p in PRODUCTS if p["asin"] == asin), None)
    if not product:
        return {"error": f"ASIN {asin} 不存在"}
    return {
        "asin": product["asin"],
        "title": product["name"],
        "brand": product["brand"],
        "category": product["category"],
        "dimensions": product["dimensions"],
        "weight_lbs": product["weight_lbs"],
    }
