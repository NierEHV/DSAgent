"""
MCP Server 基类 — 标准化 Agent 工具接口
参考 n8n-workflows-main: src/integration_hub.py 的 IntegrationHub 设计模式

每个外部服务（领星 ERP、亚马逊 SP-API、广告 API 等）封装为一个 MCP Server，
统一提供：
- list_tools()    → 发现可用工具
- call_tool()     → 执行工具调用
- get_resources() → 获取资源（可选）
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """工具定义 — MCP 标准格式"""
    name: str
    description: str
    parameters: dict = field(default_factory=dict)  # JSON Schema
    risk_level: str = "READ_ONLY"  # READ_ONLY / LOW_RISK / HIGH_RISK
    timeout_ms: int = 30000
    retry_count: int = 3
    cache_ttl_seconds: int = 0  # 0 = 不缓存


class BaseMCPServer(ABC):
    """
    MCP Server 基类
    参考 integration_hub.py IntegrationHub 的：
    - register_integration() → 服务注册
    - sync_with_*() → 标准化调用接口
    """

    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url
        self._tools: dict[str, tuple[ToolDefinition, Callable]] = {}
        self._is_connected = False
        self._setup_tools()

    @abstractmethod
    def _setup_tools(self):
        """子类实现：注册所有工具"""
        pass

    def register_tool(self, definition: ToolDefinition, handler: Callable):
        """注册一个工具 — 参考 integration_hub.py register_integration()"""
        self._tools[definition.name] = (definition, handler)
        logger.info(f"[{self.name}] 注册工具: {definition.name}")

    def list_tools(self) -> list[dict]:
        """列出所有可用工具 — MCP list_tools 标准接口"""
        return [
            {
                "name": td.name,
                "description": td.description,
                "parameters": td.parameters,
                "risk_level": td.risk_level,
            }
            for td, _ in self._tools.values()
        ]

    async def call_tool(self, tool_name: str, params: dict) -> dict:
        """
        调用工具 — MCP call_tool 标准接口
        参考 integration_hub.py 的 sync_with_*() 方法模式
        """
        if tool_name not in self._tools:
            return {"success": False, "error": f"工具不存在: {tool_name}"}

        tool_def, handler = self._tools[tool_name]
        start_time = time.time()

        try:
            result = await handler(**params)
            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "tool": tool_name,
                "result": result,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            logger.error(f"[{self.name}] 工具调用失败: {tool_name} → {e}")
            return {
                "success": False,
                "tool": tool_name,
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
            }

    async def health_check(self) -> dict:
        """健康检查 — 参考 integration_hub.py get_integration_status()"""
        try:
            self._is_connected = await self._ping()
            return {
                "service": self.name,
                "status": "connected" if self._is_connected else "disconnected",
                "tool_count": len(self._tools),
            }
        except Exception as e:
            return {
                "service": self.name,
                "status": "error",
                "error": str(e),
            }

    @abstractmethod
    async def _ping(self) -> bool:
        """检查服务连通性"""
        pass

    def __repr__(self):
        return f"<MCPServer: {self.name} ({len(self._tools)} tools)>"


# ──── 内置通用 MCP Server ────

class DatabaseMCPServer(BaseMCPServer):
    """数据库 MCP Server — 提供 SQL 查询能力"""

    def __init__(self, connection_string: str):
        super().__init__("database", base_url="")
        self.connection_string = connection_string

    def _setup_tools(self):
        self.register_tool(
            ToolDefinition(
                name="sql_query",
                description="执行 SQL 查询（只读）",
                parameters={
                    "query": "string — SQL SELECT 查询语句",
                    "params": "Optional[dict] — 查询参数",
                    "limit": "Optional[int] — 返回行数限制，默认100",
                },
                risk_level="READ_ONLY",
            ),
            self._sql_query,
        )

    async def _sql_query(self, query: str, params: dict = None, limit: int = 100) -> dict:
        """执行 SQL 查询"""
        # 安全检查：只允许 SELECT
        if not query.strip().upper().startswith("SELECT"):
            return {"success": False, "error": "仅允许 SELECT 查询"}

        # TODO: 实际数据库查询
        return {"rows": [], "count": 0, "query": query}

    async def _ping(self) -> bool:
        return True


class NotifyMCPServer(BaseMCPServer):
    """通知 MCP Server — 参考 integration_hub.py sync_with_slack/discord"""

    def __init__(self):
        super().__init__("notify", base_url="")
        self._channels: dict[str, Callable] = {}

    def _setup_tools(self):
        self.register_tool(
            ToolDefinition(
                name="send_notification",
                description="发送通知到指定渠道（钉钉/企微/邮件）",
                parameters={
                    "channel": "dingtalk|wecom|email — 通知渠道",
                    "title": "string — 标题",
                    "content": "string — 内容（支持 Markdown）",
                    "level": "Optional[INFO|WARNING|CRITICAL] — 级别",
                    "at_users": "Optional[list[str]] — @指定用户",
                },
                risk_level="LOW_RISK",
            ),
            self._send_notification,
        )

    async def _send_notification(
        self,
        channel: str,
        title: str,
        content: str,
        level: str = "INFO",
        at_users: list[str] = None,
    ) -> dict:
        """发送通知"""
        level_emoji = {"INFO": "ℹ️", "WARNING": "🟡", "CRITICAL": "🔴"}
        emoji = level_emoji.get(level, "ℹ️")

        message = f"{emoji} **{title}**\n{content}"

        if channel == "dingtalk":
            if at_users:
                message += "\n" + " ".join(f"@{u}" for u in at_users)
            # TODO: 调用钉钉 Webhook
        elif channel == "wecom":
            # TODO: 调用企微 Webhook
            pass
        elif channel == "email":
            # TODO: 调用邮件服务
            pass

        return {"success": True, "channel": channel, "message": message}

    async def _ping(self) -> bool:
        return True
