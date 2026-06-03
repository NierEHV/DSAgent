"""
DS Agent v3.0 — AI 运营指挥中心
架构: 配置 → LLM → 数据源 → 存储 → 引擎 → Agent → API

启动:
  python main.py --port 8000
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Windows 编码修复
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from auth.router import router as auth_router
from auth.middleware import require_role, optional_user, get_current_user
from auth.models import Role, User
from webhooks.receiver import router as webhook_router

# ──── App ────
app = FastAPI(
    title="DS Agent v3.0 — AI 运营指挥中心",
    description="全量 AI 分析 | 多数据源 | 变动追踪 | 决策引擎",
    version="3.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Auth routes (无需认证)
app.include_router(auth_router, prefix="/auth", tags=["auth"])
# Webhook routes (无需认证 — 外部系统调用)
app.include_router(webhook_router, tags=["webhooks"])

# ──── 延迟初始化 (startup 事件中完成) ────
agent_hub: Optional["AgentHub"] = None
scheduler: Optional["MonitorScheduler"] = None


class AgentHub:
    """Agent 管理中心 — 持有所有模块引用"""
    def __init__(self):
        from config.settings import settings
        from config.datasource_config import build_registry
        from config.llm_config import create_llm

        from storage.raw_store import RawStore
        from storage.snapshot_store import SnapshotStore
        from storage.decision_log import DecisionLog

        from engine.diff_engine import DiffEngine
        from engine.analysis_pipeline import AnalysisPipeline
        from engine.decision_engine import DecisionEngine

        from agents.inventory_agent import InventoryAlertAgent
        from agents.ad_report_agent import AdReportAgent
        from agents.profit_agent import ProfitAnalysisAgent
        from agents.hijack_agent import HijackMonitorAgent
        from agents.competitor_discovery_agent import CompetitorDiscoveryAgent
        from agents.competitor_analysis_agent import CompetitorAnalysisAgent
        from agents.daily_report_agent import DailyReportAgent
        from agents.listing_agent import ListingAgent

        self.settings = settings

        # LLM
        try:
            self.llm = create_llm(settings.llm_config)
        except ValueError as e:
            print(f"[WARN] LLM 未配置: {e}")
            self.llm = None

        # 数据源
        self.registry = build_registry(settings.get_enabled_datasources(),
                                       mock_mode=settings.mock_mode)

        # 存储 (配置保留天数)
        st_cfg = settings.storage_config
        self.raw_store = RawStore("data/raw")
        self.raw_store.retention_days = st_cfg.get("raw_retention_days", 7)
        self.snapshot_store = SnapshotStore("data/snapshots")
        self.snapshot_store.retention_days = st_cfg.get("snapshot_retention_days", 90)
        self.decision_log = DecisionLog("data")

        # 引擎 (告警阈值从配置读取)
        self.diff_engine = DiffEngine()
        self.pipeline = AnalysisPipeline(llm=self.llm, alert_config=settings.alert_rules)
        self.decision_engine = DecisionEngine(
            self.decision_log,
            auto_approve_low_risk=settings.scheduler_config.get("auto_approve_low_risk", True),
        )

        # Agents
        self.agents = {
            "inventory": InventoryAlertAgent(self.registry, self.pipeline, self.decision_engine),
            "advertising": AdReportAgent(self.registry, self.pipeline, self.decision_engine),
            "profit": ProfitAnalysisAgent(self.registry, self.pipeline, self.decision_engine),
            "competitor": HijackMonitorAgent(self.registry, self.pipeline, self.decision_engine),
            "competitor_discovery": CompetitorDiscoveryAgent(self.registry, self.pipeline, self.decision_engine),
            "competitor_analysis": CompetitorAnalysisAgent(self.registry, self.pipeline, self.decision_engine),
            "report": DailyReportAgent(self.registry, self.pipeline, self.decision_engine),
            "listing": ListingAgent(self.registry, self.pipeline, self.decision_engine),
        }


# ──── 模型 ────

class AgentRunRequest(BaseModel):
    agent_name: str
    params: dict = {}


class DecisionRequest(BaseModel):
    alert_id: str
    decision: str  # approved / rejected / modified
    user: str = "admin"
    note: str = ""


# ──── 路由 ────

@app.get("/")
async def root():
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"service": "DS Agent v3.0", "status": "running", "docs": "/docs"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": datetime.now().isoformat(),
        "mock_mode": agent_hub.settings.mock_mode if agent_hub else True,
        "agents": list(agent_hub.agents.keys()) if agent_hub else [],
        "datasources": list(agent_hub.registry.adapters.keys()) if agent_hub else [],
    }


@app.get("/mcp/status")
async def mcp_status():
    if not agent_hub:
        return {"status": "not_initialized"}
    status = await agent_hub.registry.health_check_all()
    return {"status": "ok" if all(s.get("status") == "connected" for s in status.values()) else "degraded",
            "servers": status}


# ──── Agent 执行 ────

@app.post("/agents/run")
async def run_agent(request: AgentRunRequest,
                    user: User = Depends(require_role(Role.VIEWER))):
    if not agent_hub:
        raise HTTPException(500, "系统未初始化")
    agent = agent_hub.agents.get(request.agent_name)
    if not agent:
        raise HTTPException(404, f"Agent 不存在: {request.agent_name}. 可用: {list(agent_hub.agents.keys())}")
    try:
        result = await agent.run(**request.params)
        return {"status": "completed", "agent": request.agent_name, "result": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/agents")
async def list_agents():
    if not agent_hub:
        return {"agents": {}}
    return {
        "agents": {name: {"name": a.name, "description": a.description}
                    for name, a in agent_hub.agents.items()},
        "count": len(agent_hub.agents),
    }


# ──── 一键巡检 ────

@app.post("/monitor/check-all")
async def check_all(background_tasks: BackgroundTasks,
                    user: User = Depends(require_role(Role.OPERATOR))):
    if not scheduler:
        raise HTTPException(500, "调度器未启动")
    background_tasks.add_task(scheduler.run_all_checks)
    return {"status": "started", "message": "全量巡检已触发"}


@app.get("/monitor/status")
async def monitor_status():
    if not scheduler:
        return {"status": "not_running"}
    return {"status": "running", "interval_minutes": scheduler.interval_minutes,
            "monitor_types": scheduler.monitor_types}


# ──── 告警 & 决策 ────

@app.get("/alerts")
async def get_alerts(limit: int = 50):
    """获取最近的决策/告警"""
    if not agent_hub:
        return {"alerts": []}
    # 从多个快照中聚合告警
    all_alerts = []
    for data_type in ["inventory", "advertising", "competitor", "profit"]:
        snap = agent_hub.snapshot_store.load_latest(data_type)
        if snap:
            all_alerts.append({
                "data_type": data_type,
                "timestamp": snap.get("timestamp"),
                "count": snap.get("count", 0),
                "sources": snap.get("metadata", {}).get("sources", []),
            })
    return {"alerts": all_alerts, "decisions": agent_hub.decision_log.list_recent(limit)}


@app.post("/decisions/record")
async def record_decision(request: DecisionRequest,
                          user: User = Depends(require_role(Role.OPERATOR))):
    if not agent_hub:
        raise HTTPException(500, "系统未初始化")
    record = await agent_hub.decision_engine.decide(
        alert={"id": request.alert_id},
        decision=request.decision,
        user=request.user,
        note=request.note,
    )
    return {"status": "recorded", "decision_id": record.id}


@app.get("/decisions/log")
async def get_decision_log(limit: int = 50):
    if not agent_hub:
        return {"decisions": [], "stats": {}}
    return {
        "decisions": agent_hub.decision_log.list_recent(limit),
        "stats": agent_hub.decision_log.get_stats(),
    }


# ──── 数据源管理 ────

@app.get("/datasources")
async def list_datasources():
    if not agent_hub:
        return {"datasources": []}
    status = await agent_hub.registry.health_check_all()
    configs = agent_hub.settings.datasources
    result = []
    for ds in configs:
        name = ds["name"]
        result.append({
            "name": name, "type": ds.get("type"), "enabled": ds.get("enabled", True),
            "health": status.get(name, {}),
        })
    return {"datasources": result}


# ──── 全量配置管理 ────

@app.get("/config")
async def get_config():
    """查看当前完整配置"""
    if not agent_hub:
        return {"status": "not_initialized"}
    ds_status = await agent_hub.registry.health_check_all()
    return {
        "llm": {
            **agent_hub.settings.llm_config,
            "api_key_configured": bool(agent_hub.settings.llm_config.get("api_key")),
            "status": "connected" if agent_hub.llm else "not_configured",
        },
        "datasources": [
            {**ds, "health": ds_status.get(ds.get("name"), {}).get("status", "unknown")}
            for ds in agent_hub.settings.datasources
        ],
        "routing": agent_hub.settings.routing,
        "scheduler": agent_hub.settings.scheduler_config,
        "alert_rules": agent_hub.settings.alert_rules,
        "notify": agent_hub.settings.notify_config,
        "monitor": agent_hub.settings.monitor_config,
        "storage": agent_hub.settings.storage_config,
        "ui": agent_hub.settings.ui_config,
        "mock_mode": agent_hub.settings.mock_mode,
    }


class ConfigUpdateRequest(BaseModel):
    section: str  # llm / datasource / alert_rules / notify / monitor / scheduler / storage / ui / system
    data: dict = {}


@app.post("/config/update")
async def update_config(request: ConfigUpdateRequest,
                        user: User = Depends(require_role(Role.ADMIN))):
    """通用配置更新 — 任何配置节都可以通过这个接口修改"""
    if not agent_hub:
        raise HTTPException(500, "系统未初始化")

    section = request.section
    data = request.data

    if section == "llm":
        if not data.get("api_key"): data.pop("api_key", None)
        if not data.get("base_url"): data.pop("base_url", None)
        agent_hub.settings.update("llm", data)
        from config.llm_config import create_llm
        agent_hub.llm = create_llm(agent_hub.settings.llm_config)
        agent_hub.pipeline.llm = agent_hub.llm

    elif section == "datasource":
        agent_hub.settings.add_datasource(data)
        from config.datasource_config import build_registry
        agent_hub.registry = build_registry(agent_hub.settings.get_enabled_datasources(),
                                            mock_mode=agent_hub.settings.mock_mode)
        for agent in agent_hub.agents.values(): agent.registry = agent_hub.registry
        if scheduler: scheduler.registry = agent_hub.registry

    elif section == "alert_rules":
        agent_hub.settings.update("alert_rules", data)
        agent_hub.pipeline.update_thresholds(agent_hub.settings.alert_rules)

    elif section == "notify":
        agent_hub.settings.update("notify", data)

    elif section == "monitor":
        agent_hub.settings.update("monitor", data)

    elif section == "scheduler":
        agent_hub.settings.update("scheduler", data)
        if scheduler:
            scheduler.interval_minutes = data.get("interval_minutes", scheduler.interval_minutes)
            scheduler.monitor_types = data.get("enabled_agents", scheduler.monitor_types)
            scheduler.working_hours_only = data.get("working_hours_only", False)

    elif section == "storage":
        agent_hub.settings.update("storage", data)
        agent_hub.raw_store.retention_days = data.get("raw_retention_days", 7)
        agent_hub.snapshot_store.retention_days = data.get("snapshot_retention_days", 90)

    elif section == "ui":
        agent_hub.settings.update("ui", data)

    elif section == "system":
        if "mock_mode" in data:
            agent_hub.settings._config["mock_mode"] = data["mock_mode"]
            agent_hub.registry.mock_mode = data["mock_mode"]
        if "interval_minutes" in data:
            agent_hub.settings._config.setdefault("scheduler", {})["interval_minutes"] = data["interval_minutes"]
            if scheduler: scheduler.interval_minutes = data["interval_minutes"]
        if "auto_approve_low_risk" in data:
            agent_hub.settings._config.setdefault("scheduler", {})["auto_approve_low_risk"] = data["auto_approve_low_risk"]
        agent_hub.settings.save()

    else:
        raise HTTPException(400, f"未知配置节: {section}. 支持: llm, datasource, alert_rules, notify, monitor, scheduler, storage, ui, system")

    agent_hub.settings.save()
    return {"status": "updated", "section": section}


@app.post("/config/reload")
async def reload_config(user: User = Depends(require_role(Role.ADMIN))):
    if not agent_hub: raise HTTPException(500, "系统未初始化")
    agent_hub.settings.reload()
    from config.llm_config import create_llm
    try:
        agent_hub.llm = create_llm(agent_hub.settings.llm_config)
        agent_hub.pipeline.llm = agent_hub.llm
        agent_hub.pipeline.update_thresholds(agent_hub.settings.alert_rules)
    except Exception: agent_hub.llm = None
    from config.datasource_config import build_registry
    agent_hub.registry = build_registry(agent_hub.settings.get_enabled_datasources(), mock_mode=agent_hub.settings.mock_mode)
    for agent in agent_hub.agents.values(): agent.registry = agent_hub.registry
    if scheduler: scheduler.registry = agent_hub.registry
    return {"status": "reloaded"}


# ──── Prompts 管理 ────

@app.get("/prompts")
async def get_prompts():
    from prompts.manager import prompt_manager
    return {"prompts": prompt_manager.list_all()}


class PromptUpdateRequest(BaseModel):
    category: str
    name: str
    content: str = ""


@app.post("/prompts/update")
async def update_prompt(request: PromptUpdateRequest,
                        user: User = Depends(require_role(Role.OPERATOR))):
    from prompts.manager import prompt_manager
    prompt_manager.set(request.category, request.name, request.content)
    prompt_manager.save()
    return {"status": "updated", "category": request.category, "name": request.name}


# ──── RAG 知识库 ────

@app.get("/rag/documents")
async def list_rag_documents():
    from rag.knowledge_base import kb
    return {"documents": kb.list_documents()}


class RAGUploadRequest(BaseModel):
    title: str
    content: str


@app.post("/rag/upload")
async def upload_rag_document(request: RAGUploadRequest,
                              user: User = Depends(require_role(Role.OPERATOR))):
    from rag.knowledge_base import kb
    doc_id = kb.add_document(request.title, request.content)
    return {"status": "uploaded", "doc_id": doc_id}


@app.delete("/rag/documents/{doc_id}")
async def delete_rag_document(doc_id: str,
                              user: User = Depends(require_role(Role.ADMIN))):
    from rag.knowledge_base import kb
    kb.delete_document(doc_id)
    return {"status": "deleted"}


@app.get("/rag/search")
async def search_rag(query: str = Query(..., description="搜索关键词"), top_k: int = 3):
    from rag.knowledge_base import kb
    results = kb.search(query, top_k)
    return {"query": query, "results": results}


# ──── Tools / Tool Calling ────

@app.get("/tools")
async def list_tools():
    if not agent_hub:
        return {"tools": []}
    from tools.registry import ToolRegistry
    registry = ToolRegistry(agent_hub=agent_hub)
    return {"tools": [{"name": t.name, "description": t.description} for t in registry._tools.values()]}


class ToolCallRequest(BaseModel):
    query: str
    max_steps: int = 5


@app.post("/tools/call")
async def tool_calling(request: ToolCallRequest):
    if not agent_hub or not agent_hub.llm:
        raise HTTPException(400, "LLM 未配置,无法使用 Tool Calling")
    from tools.registry import ToolRegistry
    from tools.orchestrator import ToolOrchestrator
    registry = ToolRegistry(agent_hub=agent_hub)
    orchestrator = ToolOrchestrator(registry, agent_hub.llm)
    result = await orchestrator.run(request.query, request.max_steps)
    return result


# ──── 审批流 ────

@app.post("/decisions/{decision_id}/review")
async def review_decision(decision_id: str, decision: str = "approved",
                          note: str = "", user: User = Depends(require_role(Role.OPERATOR))):
    if not agent_hub:
        raise HTTPException(500, "系统未初始化")
    result = await agent_hub.decision_engine.review(
        decision_id, user.username, decision, note)
    return result


@app.post("/decisions/{decision_id}/approve")
async def approve_decision(decision_id: str, decision: str = "approved",
                           note: str = "", user: User = Depends(require_role(Role.ADMIN))):
    if not agent_hub:
        raise HTTPException(500, "系统未初始化")
    result = await agent_hub.decision_engine.approve_final(
        decision_id, user.username, decision, note)
    return result


@app.get("/decisions/{decision_id}/status")
async def get_decision_status(decision_id: str):
    if not agent_hub:
        raise HTTPException(404)
    return agent_hub.decision_engine.get_approval_status(decision_id)


# ──── 实时事件 (动态 Mock) ────

@app.get("/events/live")
async def get_live_events(minutes: int = 5):
    """获取最近 N 分钟的实时模拟事件"""
    from datasource.dynamic_mock import dynamic_mock
    events = dynamic_mock.get_events_since(minutes)
    return {"events": events, "total": len(events), "timestamp": datetime.now().isoformat()}


# ──── 日志 ────

@app.get("/logs")
async def get_logs(lines: int = 100):
    """获取最近的系统日志"""
    import subprocess
    log_entries = []

    # 调度日志
    for data_type in ["inventory", "advertising", "competitor", "profit"]:
        if agent_hub:
            snap = agent_hub.snapshot_store.load_latest(data_type)
            if snap:
                log_entries.append({
                    "time": snap.get("timestamp", ""),
                    "type": data_type,
                    "source": snap.get("metadata", {}).get("sources", []),
                    "items": snap.get("count", 0),
                })

    # 决策日志
    if agent_hub:
        decisions = agent_hub.decision_log.list_recent(20)
        for d in decisions:
            log_entries.append({
                "time": d.get("decided_at", ""),
                "type": "decision",
                "alert_id": d.get("alert_id", ""),
                "decision": d.get("decision", ""),
                "decided_by": d.get("decided_by", ""),
            })

    # 最近告警
    if agent_hub:
        recent_alerts = agent_hub.decision_log.list_recent(50)
        alert_entries = [a for a in recent_alerts if a.get("decision") == "pending"]
        for a in alert_entries[:10]:
            log_entries.append({
                "time": a.get("decided_at", ""),
                "type": "alert_pending",
                "alert_id": a.get("alert_id", ""),
                "detail": a.get("alert_type", ""),
            })

    log_entries.sort(key=lambda x: x.get("time", ""), reverse=True)
    return {"logs": log_entries[:lines], "total": len(log_entries)}


# ──── 前端 ────

@app.get("/dashboard")
async def dashboard():
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "前端文件未找到"}


# ──── 启动 ────

@app.on_event("startup")
async def startup():
    global agent_hub, scheduler

    print("🚀 DS Agent v3.0 启动中...")
    agent_hub = AgentHub()

    print(f"   LLM: {agent_hub.llm or '未配置 (Mock模式)'}")
    print(f"   数据源: {list(agent_hub.registry.adapters.keys())}")
    print(f"   Mock 模式: {agent_hub.settings.mock_mode}")
    print(f"   Agents: {list(agent_hub.agents.keys())}")

    # 数据源健康检查
    ds_health = await agent_hub.registry.health_check_all()
    for name, h in ds_health.items():
        status = h.get("status", "unknown")
        print(f"   [{name}] {status}")

    # 启动调度器
    from engine.scheduler import MonitorScheduler
    interval = agent_hub.settings.scheduler_config.get("interval_minutes", 5)
    scheduler = MonitorScheduler(
        registry=agent_hub.registry,
        snapshot_store=agent_hub.snapshot_store,
        raw_store=agent_hub.raw_store,
        analysis_pipeline=agent_hub.pipeline,
        diff_engine=agent_hub.diff_engine,
        decision_engine=agent_hub.decision_engine,
        scheduler_config=agent_hub.settings.scheduler_config,
    )

    import asyncio
    asyncio.create_task(scheduler.start())
    print(f"   ⏰ 调度器: 每 {interval} 分钟")

    # 首次巡检
    asyncio.create_task(scheduler.run_all_checks())
    print(f"   🔍 首次巡检已触发")

    print(f"   🌐 API: http://127.0.0.1:8000")
    print(f"   📊 面板: http://127.0.0.1:8000/dashboard")
    print(f"   📖 文档: http://127.0.0.1:8000/docs")
    print("=" * 55)


# ──── 入口 ────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DS Agent v3.0")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--reload", action="store_true")

    args = parser.parse_args()

    print("🚀 DS Agent v3.0 — AI 运营指挥中心")
    print(f"   http://{args.host}:{args.port}")
    print(f"   http://{args.host}:{args.port}/docs")

    uvicorn.run("main:app", host=args.host, port=args.port,
                reload=args.dev or args.reload)
