"""
广告 API MCP Server — Mock 实现
封装广告活动管理、数据报表、关键词分析等工具

API 端点:
  GET  /health           — 健康检查
  GET  /tools             — 列出可用工具
  POST /call/{tool_name}  — 调用工具
"""

from __future__ import annotations

import time
from datetime import datetime
from fastapi import FastAPI, HTTPException

from .mock_data import (
    AD_CAMPAIGNS, AD_PERFORMANCE_TODAY, AD_PERFORMANCE_14D_AVG,
    TODAY, YESTERDAY,
)

app = FastAPI(title="广告 API MCP Server", version="1.0.0")

TOOLS = {
    "get_ad_campaigns": {
        "name": "get_ad_campaigns",
        "description": "获取广告活动列表，支持按类型/状态筛选",
        "parameters": {"type": "Optional[SP|SB|SD]", "status": "Optional[str]", "asin": "Optional[str]"},
        "risk_level": "READ_ONLY",
    },
    "get_ad_report": {
        "name": "get_ad_report",
        "description": "获取广告数据报表（展示/点击/花费/销售额/ACOS/ROAS）",
        "parameters": {"start_date": "str", "end_date": "str", "campaign_id": "Optional[str]", "type": "Optional[SP|SB|SD]"},
        "risk_level": "READ_ONLY",
    },
    "get_keyword_performance": {
        "name": "get_keyword_performance",
        "description": "获取关键词维度的广告表现数据",
        "parameters": {"campaign_id": "Optional[str]", "asin": "Optional[str]", "limit": "int = 50"},
        "risk_level": "READ_ONLY",
    },
    "get_ad_performance_today": {
        "name": "get_ad_performance_today",
        "description": "获取今日广告表现数据（对比14天均值）",
        "parameters": {},
        "risk_level": "READ_ONLY",
    },
    "get_budget_status": {
        "name": "get_budget_status",
        "description": "获取广告预算使用状态，检测预算提前耗尽风险",
        "parameters": {},
        "risk_level": "READ_ONLY",
    },
}

@app.get("/health")
async def health():
    return {
        "service": "ad-api",
        "status": "connected",
        "mode": "mock",
        "tool_count": len(TOOLS),
    }


@app.get("/tools")
async def list_tools():
    return {"service": "ad-api", "tools": list(TOOLS.values())}


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
        "get_ad_campaigns": _get_ad_campaigns,
        "get_ad_report": _get_ad_report,
        "get_keyword_performance": _get_keyword_performance,
        "get_ad_performance_today": _get_ad_performance_today,
        "get_budget_status": _get_budget_status,
    }
    handler = dispatch_map.get(tool_name)
    if handler:
        return await handler(**params)
    return {"error": "未实现的工具"}


async def _get_ad_campaigns(type: str = None, status: str = None, asin: str = None, **kwargs):
    result = AD_CAMPAIGNS
    if type:
        result = [c for c in result if c["type"] == type]
    if status:
        result = [c for c in result if c["status"] == status]
    if asin:
        result = [c for c in result if c["asin_target"] == asin]
    return {"campaigns": result, "count": len(result)}


async def _get_ad_report(start_date: str = None, end_date: str = None, campaign_id: str = None, type: str = None, **kwargs):
    result = AD_PERFORMANCE_TODAY
    if campaign_id:
        result = [p for p in result if p["campaign_id"] == campaign_id]

    # 合并14天均值
    for perf in result:
        avg = next((a for a in AD_PERFORMANCE_14D_AVG if a["campaign_id"] == perf["campaign_id"]), {})
        perf["avg_acos_14d"] = avg.get("avg_acos", 0)
        perf["avg_cpc_14d"] = avg.get("avg_cpc", 0)
        perf["avg_roas_14d"] = avg.get("avg_roas", 0)
        perf["acos_change_pct"] = round((perf["acos"] - avg.get("avg_acos", perf["acos"])) / avg.get("avg_acos", 1) * 100, 1)

    summary = {
        "total_impressions": sum(p["impressions"] for p in result),
        "total_clicks": sum(p["clicks"] for p in result),
        "total_spend": round(sum(p["spend"] for p in result), 2),
        "total_sales": round(sum(p["sales"] for p in result), 2),
        "overall_acos": round(sum(p["spend"] for p in result) / sum(p["sales"] for p in result) * 100, 2) if sum(p["sales"] for p in result) > 0 else 0,
        "total_orders": sum(p["orders"] for p in result),
    }

    return {"performance": result, "summary": summary, "count": len(result)}


async def _get_keyword_performance(campaign_id: str = None, asin: str = None, limit: int = 50, **kwargs):
    keywords = [
        {"keyword": "bluetooth earbuds", "match_type": "broad", "impressions": 12400, "clicks": 380, "spend": 42.50, "sales": 299.90, "acos": 14.2, "orders": 10},
        {"keyword": "wireless earbuds bluetooth 5.3", "match_type": "phrase", "impressions": 3200, "clicks": 145, "spend": 28.30, "sales": 149.95, "acos": 18.9, "orders": 5},
        {"keyword": "bluetooth earbuds for android", "match_type": "exact", "impressions": 1800, "clicks": 72, "spend": 41.80, "sales": 119.96, "acos": 34.8, "orders": 4},  # ⚠️ ACOS高
        {"keyword": "usb c fast charger 65w", "match_type": "broad", "impressions": 8900, "clicks": 320, "spend": 35.20, "sales": 324.87, "acos": 10.8, "orders": 13},  # ✅ 表现好
        {"keyword": "gan charger type c", "match_type": "phrase", "impressions": 4500, "clicks": 168, "spend": 18.50, "sales": 174.93, "acos": 10.6, "orders": 7},
        {"keyword": "portable bluetooth speaker", "match_type": "broad", "impressions": 5600, "clicks": 89, "spend": 44.50, "sales": 79.98, "acos": 55.6, "orders": 2},  # 🔴 ACOS极高
    ]
    return {"keywords": keywords[:limit], "count": len(keywords[:limit])}


async def _get_ad_performance_today(**kwargs):
    result = []
    for perf in AD_PERFORMANCE_TODAY:
        avg = next((a for a in AD_PERFORMANCE_14D_AVG if a["campaign_id"] == perf["campaign_id"]), {})
        campaign = next((c for c in AD_CAMPAIGNS if c["campaign_id"] == perf["campaign_id"]), {})
        result.append({
            **perf,
            "campaign_name": campaign.get("campaign_name", perf["campaign_id"]),
            "avg_acos_14d": avg.get("avg_acos", 0),
            "avg_cpc_14d": avg.get("avg_cpc", 0),
            "avg_roas_14d": avg.get("avg_roas", 0),
            "acos_change_vs_14d": round(perf["acos"] - avg.get("avg_acos", perf["acos"]), 1),
            "budget_utilization": round(perf["spend"] / campaign.get("budget", 1) * 100, 1),
            "anomaly": (
                "acos_spike" if (perf["acos"] > avg.get("avg_acos", 100) * 1.5 and perf["acos"] > 30)
                else "budget_exhausted" if perf["spend"] / campaign.get("budget", 1) > 0.9
                else None
            ),
        })
    return {"performance": result, "snapshot_time": datetime.now().isoformat()}


async def _get_budget_status(**kwargs):
    budgets = []
    for campaign in AD_CAMPAIGNS:
        perf = next((p for p in AD_PERFORMANCE_TODAY if p["campaign_id"] == campaign["campaign_id"]), None)
        if not perf:
            continue
        utilization = round(perf["spend"] / campaign["budget"] * 100, 1)
        budgets.append({
            "campaign_id": campaign["campaign_id"],
            "campaign_name": campaign["campaign_name"],
            "budget": campaign["budget"],
            "spend": perf["spend"],
            "remaining": round(campaign["budget"] - perf["spend"], 2),
            "utilization": utilization,
            "status": "exhausted" if utilization >= 100 else "critical" if utilization >= 90 else "normal",
        })
    return {"budgets": budgets, "total_spend": round(sum(b["spend"] for b in budgets), 2), "total_budget": sum(b["budget"] for b in budgets)}
