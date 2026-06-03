"""
领星 ERP MCP Server — Mock 实现
封装商品管理、库存查询、订单、财务、广告等工具

API 端点:
  GET  /health           — 健康检查
  GET  /tools             — 列出可用工具
  POST /call/{tool_name}  — 调用工具
"""

from __future__ import annotations

import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from .mock_data import (
    PRODUCTS, FBA_INVENTORY, SALES_DATA, INBOUND_SHIPMENTS,
    PROFIT_DATA, TODAY, YESTERDAY,
)

app = FastAPI(title="领星 ERP MCP Server", version="1.0.0")

# ──── 工具注册表 ────
TOOLS = {
    "get_products": {
        "name": "get_products",
        "description": "获取商品列表，支持按MSKU/ASIN筛选",
        "parameters": {"msku_list": "Optional[list[str]]", "asin_list": "Optional[list[str]]"},
        "risk_level": "READ_ONLY",
    },
    "get_fba_inventory": {
        "name": "get_fba_inventory",
        "description": "查询所有商品的FBA库存，返回MSKU、ASIN、FBA库存量、可售/不可售/预留数量",
        "parameters": {"msku_list": "Optional[list[str]]", "asin_list": "Optional[list[str]]"},
        "risk_level": "READ_ONLY",
    },
    "get_sales_data": {
        "name": "get_sales_data",
        "description": "获取商品销量数据（日均销量、趋势）",
        "parameters": {"days": "int — 天数(7/14/30)", "msku_list": "Optional[list[str]]"},
        "risk_level": "READ_ONLY",
    },
    "get_inbound_shipments": {
        "name": "get_inbound_shipments",
        "description": "查询在途/待入库的FBA发货计划",
        "parameters": {"msku_list": "Optional[list[str]]", "status": "Optional[str]"},
        "risk_level": "READ_ONLY",
    },
    "get_profit_report": {
        "name": "get_profit_report",
        "description": "查询利润报表，可按日期、SKU维度汇总",
        "parameters": {"start_date": "str", "end_date": "str", "msku": "Optional[str]", "group_by": "Optional[str]"},
        "risk_level": "READ_ONLY",
    },
    "get_orders": {
        "name": "get_orders",
        "description": "获取订单列表，支持按时间/状态筛选",
        "parameters": {"start_date": "str", "end_date": "str", "status": "Optional[str]", "limit": "int = 100"},
        "risk_level": "READ_ONLY",
    },
    "get_listing_detail": {
        "name": "get_listing_detail",
        "description": "获取Listing详情（标题、五点、A+、图片、关键词等）",
        "parameters": {"asin": "str"},
        "risk_level": "READ_ONLY",
    },
    "get_settlement": {
        "name": "get_settlement",
        "description": "获取结算报告",
        "parameters": {"start_date": "str", "end_date": "str"},
        "risk_level": "READ_ONLY",
    },
}

# ──── API 端点 ────

@app.get("/health")
async def health():
    return {
        "service": "lingxing-erp",
        "status": "connected",
        "mode": "mock",
        "tool_count": len(TOOLS),
    }


@app.get("/tools")
async def list_tools():
    return {"service": "lingxing-erp", "tools": list(TOOLS.values())}


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


# ──── 工具实现 ────

async def _dispatch(tool_name: str, params: dict):
    dispatch_map = {
        "get_products": _get_products,
        "get_fba_inventory": _get_fba_inventory,
        "get_sales_data": _get_sales_data,
        "get_inbound_shipments": _get_inbound_shipments,
        "get_profit_report": _get_profit_report,
        "get_orders": _get_orders,
        "get_listing_detail": _get_listing_detail,
        "get_settlement": _get_settlement,
    }
    handler = dispatch_map.get(tool_name)
    if handler:
        return await handler(**params)
    return {"error": "未实现的工具"}


async def _get_products(msku_list: list[str] = None, asin_list: list[str] = None, **kwargs):
    result = PRODUCTS
    if msku_list:
        result = [p for p in result if p["msku"] in msku_list]
    if asin_list:
        result = [p for p in result if p["asin"] in asin_list]
    return {"products": result, "count": len(result)}


async def _get_fba_inventory(msku_list: list[str] = None, asin_list: list[str] = None, **kwargs):
    result = FBA_INVENTORY
    if msku_list:
        result = [i for i in result if i["msku"] in msku_list]
    if asin_list:
        result = [i for i in result if i["asin"] in asin_list]
    return {"inventory": result, "count": len(result), "snapshot_time": datetime.now().isoformat()}


async def _get_sales_data(days: int = 7, msku_list: list[str] = None, **kwargs):
    data = []
    for s in SALES_DATA:
        if msku_list and s["msku"] not in msku_list:
            continue
        entry = dict(s)
        entry["daily_avg"] = entry[f"daily_avg_{days}d"] if f"daily_avg_{days}d" in entry else entry.get("daily_avg_7d", 0)
        data.append(entry)
    return {"sales_data": data, "days": days, "count": len(data)}


async def _get_inbound_shipments(msku_list: list[str] = None, status: str = None, **kwargs):
    result = INBOUND_SHIPMENTS
    if msku_list:
        result = [s for s in result if s["msku"] in msku_list]
    if status:
        result = [s for s in result if s["status"] == status]
    return {"shipments": result, "count": len(result)}


async def _get_profit_report(start_date: str = None, end_date: str = None, msku: str = None, group_by: str = None, **kwargs):
    result = PROFIT_DATA
    if msku:
        result = [p for p in result if p["msku"] == msku]
    return {
        "profit_data": result,
        "summary": {
            "total_revenue": sum(p["revenue"] for p in result),
            "total_gross_profit": sum(p["gross_profit"] for p in result),
            "avg_gross_margin": sum(p["gross_margin"] for p in result) / len(result) if result else 0,
            "total_ad_spend": sum(p["ad_spend"] for p in result),
            "total_refund_amount": sum(p["refund_amount"] for p in result),
        },
        "count": len(result),
    }


async def _get_orders(start_date: str = None, end_date: str = None, status: str = None, limit: int = 100, **kwargs):
    orders = [
        {"order_id": "114-5181234-5678901", "asin": "B09XYZ0001", "msku": "SKU-BT001-BLK", "qty": 1, "price": 29.99, "status": "Shipped", "date": YESTERDAY},
        {"order_id": "114-5181234-5678902", "asin": "B07DEF5678", "msku": "SKU-CHG001", "qty": 2, "price": 49.98, "status": "Shipped", "date": YESTERDAY},
        {"order_id": "114-5181234-5678903", "asin": "B08ABC1234", "msku": "SKU-SPK001", "qty": 1, "price": 39.99, "status": "Pending", "date": TODAY},
        {"order_id": "114-5181234-5678904", "asin": "B07DEF5678", "msku": "SKU-CHG001", "qty": 1, "price": 24.99, "status": "Returned", "date": YESTERDAY},
    ]
    if status:
        orders = [o for o in orders if o["status"].lower() == status.lower()]
    return {"orders": orders[:limit], "count": len(orders[:limit])}


async def _get_listing_detail(asin: str = None, **kwargs):
    product = next((p for p in PRODUCTS if p["asin"] == asin), None)
    if not product:
        return {"error": f"ASIN {asin} 不存在"}
    return {
        "asin": product["asin"],
        "title": product["name"],
        "brand": product["brand"],
        "price": product["price"],
        "category": product["category"],
        "bullet_points": [
            f"Premium {product['name_cn']} — 高品质",
            "Fast shipping with Amazon FBA",
            "30-day money-back guarantee",
            "Lifetime technical support",
            "FCC/CE/RoHS certified",
        ],
        "main_image_url": f"https://example.com/images/{asin}.jpg",
        "status": product["status"],
    }


async def _get_settlement(start_date: str = None, end_date: str = None, **kwargs):
    return {
        "period": f"{start_date or YESTERDAY} ~ {end_date or TODAY}",
        "total_revenue": 1219.57,
        "total_fees": 312.43,
        "net_payout": 907.14,
        "settlements": [
            {"type": "Order", "amount": 1219.57},
            {"type": "Refund", "amount": -64.98},
            {"type": "FBA Fee", "amount": -178.00},
            {"type": "Referral Fee", "amount": -182.94},
            {"type": "Storage Fee", "amount": -5.50},
        ],
    }
