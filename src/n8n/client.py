"""
n8n 工作流客户端 — DSAgent ↔ n8n 双向通信

n8n REST API 文档: https://docs.n8n.io/api/

调用链:
  Agent → n8n_client.trigger_workflow() → n8n 执行工作流 → 回调 DSAgent Webhook
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class N8NClient:
    """n8n 工作流引擎客户端"""

    def __init__(self, base_url: str = None, api_key: str = None, timeout: int = 30):
        self.base_url = (base_url or os.environ.get("N8N_URL", "http://localhost:5678")).rstrip("/")
        self.api_key = api_key or os.environ.get("N8N_API_KEY", "")
        self.timeout = timeout
        self._connected = False

    @property
    def headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-N8N-API-KEY"] = self.api_key
        return h

    # ═══════════════════════════ 健康 & 发现 ═══════════════════════════

    async def health(self) -> dict:
        """检查 n8n 是否可用"""
        try:
            async with httpx.AsyncClient(timeout=5, proxy=None) as client:
                resp = await client.get(f"{self.base_url}/healthz", headers=self.headers)
                self._connected = resp.status_code == 200
                return {
                    "status": "connected" if self._connected else "error",
                    "url": self.base_url,
                    "code": resp.status_code,
                }
        except Exception as e:
            self._connected = False
            return {"status": "offline", "error": str(e)[:100]}

    async def list_workflows(self) -> list[dict]:
        """列出所有工作流 — GET /rest/workflows"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
                resp = await client.get(
                    f"{self.base_url}/rest/workflows",
                    headers=self.headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    workflows = data.get("data", data) if isinstance(data, dict) else data
                    return [
                        {
                            "id": w.get("id"),
                            "name": w.get("name"),
                            "active": w.get("active", False),
                            "created_at": w.get("createdAt"),
                            "updated_at": w.get("updatedAt"),
                            "tags": [t.get("name") for t in w.get("tags", [])],
                        }
                        for w in (workflows if isinstance(workflows, list) else [])
                    ]
                return []
        except Exception as e:
            logger.warning(f"n8n list workflows 失败: {e}")
            return []

    async def list_active_workflows(self) -> list[dict]:
        """列出已激活的工作流"""
        workflows = await self.list_workflows()
        return [w for w in workflows if w.get("active")]

    # ═══════════════════════════ 触发执行 ═══════════════════════════

    async def trigger_webhook(self, webhook_path: str, data: dict) -> dict:
        """
        触发 n8n Webhook 工作流
        POST http://n8n:5678/webhook/{path}

        webhook_path: 工作流的 Webhook 路径 (如 "restock_alert" 或 "shopify/order-new")
        data: 传给工作流的 JSON 数据
        """
        start = time.time()
        # n8n webhook URL 默认在 /webhook/{path}
        url = f"{self.base_url}/webhook/{webhook_path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
                resp = await client.post(url, json=data, headers=self.headers)
                duration_ms = int((time.time() - start) * 1000)
                result = {
                    "success": resp.status_code in (200, 201, 202),
                    "status_code": resp.status_code,
                    "webhook_path": webhook_path,
                    "duration_ms": duration_ms,
                }
                if resp.status_code == 404:
                    result["error"] = f"Webhook 路径不存在: {webhook_path}"
                elif resp.status_code >= 400:
                    result["error"] = resp.text[:200]
                return result
        except Exception as e:
            return {
                "success": False,
                "webhook_path": webhook_path,
                "error": str(e)[:200],
                "duration_ms": int((time.time() - start) * 1000),
            }

    async def trigger_workflow_by_id(self, workflow_id: str, data: dict) -> dict:
        """
        通过工作流 ID 触发执行 (使用 n8n REST API)
        POST /rest/workflows/{id}/activate 或直接用 execution API
        """
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
                # 方案: 找到工作流的 webhook 节点, 构造 webhook URL
                # 更简单的方案: 用 n8n execution API
                resp = await client.post(
                    f"{self.base_url}/rest/workflows/{workflow_id}/execute",
                    json={"data": data},
                    headers=self.headers,
                )
                return {
                    "success": resp.status_code in (200, 201),
                    "workflow_id": workflow_id,
                    "duration_ms": int((time.time() - start) * 1000),
                    "response": resp.json() if resp.status_code < 400 else resp.text[:200],
                }
        except Exception as e:
            return {"success": False, "workflow_id": workflow_id, "error": str(e)[:200]}

    # ═══════════════════════════ 导入工作流 ═══════════════════════════

    async def import_workflow(self, json_path: str) -> dict:
        """
        导入工作流 JSON 文件到 n8n
        POST /rest/workflows
        """
        path = Path(json_path)
        if not path.exists():
            return {"success": False, "error": f"文件不存在: {json_path}"}

        with open(path, "r", encoding="utf-8") as f:
            workflow_data = json.load(f)

        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
                resp = await client.post(
                    f"{self.base_url}/rest/workflows",
                    json={"name": workflow_data.get("name", path.stem),
                          "nodes": workflow_data.get("nodes", []),
                          "connections": workflow_data.get("connections", {}),
                          "settings": workflow_data.get("settings", {}),
                          "active": False},
                    headers=self.headers,
                )
                if resp.status_code in (200, 201):
                    result = resp.json()
                    return {"success": True, "workflow_id": result.get("id"),
                            "name": result.get("name")}
                return {"success": False, "error": resp.text[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    async def batch_import(self, directory: str, pattern: str = "*.json") -> dict:
        """批量导入目录下的工作流 JSON"""
        dir_path = Path(directory)
        if not dir_path.exists():
            return {"success": False, "error": f"目录不存在: {directory}"}

        files = list(dir_path.glob(pattern))
        imported = 0
        failed = 0
        skipped = 0

        for fp in files:
            # 检查是否已存在同名工作流
            existing = await self.list_workflows()
            if any(w.get("name") == fp.stem for w in existing):
                skipped += 1
                continue

            result = await self.import_workflow(str(fp))
            if result.get("success"):
                imported += 1
            else:
                failed += 1

        return {"imported": imported, "skipped": skipped, "failed": failed, "total": len(files)}

    # ═══════════════════════════ 执行历史 ═══════════════════════════

    async def get_executions(self, limit: int = 20) -> list[dict]:
        """获取最近的执行记录"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
                resp = await client.get(
                    f"{self.base_url}/rest/executions",
                    params={"limit": limit},
                    headers=self.headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    executions = data.get("data", data) if isinstance(data, dict) else data
                    return [
                        {
                            "id": e.get("id"),
                            "workflow_name": e.get("workflowName", ""),
                            "status": e.get("status"),
                            "started_at": e.get("startedAt"),
                            "stopped_at": e.get("stoppedAt"),
                        }
                        for e in (executions if isinstance(executions, list) else [])
                    ]
                return []
        except Exception:
            return []

    # ═══════════════════════════ 高级: 触发电商工作流 ═══════════════════════════

    async def notify_slack(self, message: str, channel: str = None) -> dict:
        """触发 Slack 通知工作流"""
        return await self.trigger_webhook("slack-notify", {
            "message": message,
            "channel": channel or "#ops-alerts",
            "timestamp": datetime.now().isoformat(),
        })

    async def send_dingtalk(self, title: str, content: str, at_users: list = None) -> dict:
        """触发钉钉通知工作流"""
        return await self.trigger_webhook("dingtalk-notify", {
            "title": title,
            "content": content,
            "at_users": at_users or [],
        })

    async def create_fulfillment_order(self, sku: str, qty: int, warehouse: str = "FBA") -> dict:
        """触发补货工单工作流"""
        return await self.trigger_webhook("create-fulfillment", {
            "sku": sku,
            "quantity": qty,
            "warehouse": warehouse,
            "priority": "high" if qty > 100 else "normal",
        })

    async def trigger_alert(self, alert_type: str, data: dict) -> dict:
        """通用的告警工作流触发

        alert_type: inventory_low / acos_spike / buy_box_lost / new_hijacker / profit_drop
        """
        webhook_map = {
            "inventory_low": "restock-alert",
            "acos_spike": "ad-alert",
            "buy_box_lost": "competitor-alert",
            "new_hijacker": "competitor-alert",
            "profit_drop": "profit-alert",
        }
        path = webhook_map.get(alert_type, f"alert-{alert_type}")
        return await self.trigger_webhook(path, {**data, "alert_type": alert_type})

    def __repr__(self):
        status = "connected" if self._connected else "offline"
        return f"<N8NClient: {self.base_url} [{status}]>"


# 全局单例 (延迟初始化)
n8n_client: Optional[N8NClient] = None


def get_n8n_client() -> N8NClient:
    global n8n_client
    if n8n_client is None:
        n8n_client = N8NClient()
    return n8n_client
