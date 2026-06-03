"""
通用 MCP 协议客户端
支持 MCP SSE / MCP HTTP / REST API 三种传输方式
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP 协议客户端

    支持:
      - mcp_sse: Server-Sent Events 模式 (卖家精灵)
      - mcp_http: Streamable HTTP 模式 (Sorftime)
      - rest_api: 传统 REST API (领星)
    """

    def __init__(self, name: str, base_url: str,
                 transport_type: str = "mcp_http",
                 auth_headers: dict = None,
                 timeout: int = 30):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.transport_type = transport_type
        self.auth_headers = auth_headers or {}
        self.timeout = timeout
        self._tools_cache: Optional[list[dict]] = None
        self._offline: bool = False

    async def health(self) -> dict:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, proxy=None) as client:
                url = f"{self.base_url}/health"
                resp = await client.get(url, headers=self.auth_headers)
                if resp.status_code == 200:
                    self._offline = False
                    return {"status": "connected", "service": self.name}
                # MCP 可能没有 /health, 试试 /tools
                url2 = f"{self.base_url}/tools"
                resp2 = await client.get(url2, headers=self.auth_headers)
                if resp2.status_code == 200:
                    self._offline = False
                    return {"status": "connected", "service": self.name}
                return {"status": "error", "code": resp.status_code}
        except Exception as e:
            self._offline = True
            return {"status": "offline", "error": str(e)[:100]}

    async def list_tools(self) -> list[dict]:
        if self._tools_cache:
            return self._tools_cache
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
                if self.transport_type == "rest_api":
                    # REST API: 没有 tools 列表, 返回空
                    return []
                url = f"{self.base_url}/tools"
                resp = await client.get(url, headers=self.auth_headers)
                if resp.status_code == 200:
                    data = resp.json()
                    tools = data.get("tools", []) or data.get("functions", [])
                    self._tools_cache = tools
                    return tools
                return []
        except Exception:
            return []

    async def call(self, tool_name: str, params: dict = None) -> dict:
        """调用 MCP 工具 / REST API"""
        params = params or {}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
                if self.transport_type in ("mcp_sse", "mcp_http"):
                    return await self._call_mcp(client, tool_name, params)
                elif self.transport_type == "rest_api":
                    return await self._call_rest(client, tool_name, params)
                else:
                    return {"success": False, "error": f"未知协议: {self.transport_type}"}
        except Exception as e:
            logger.warning(f"[{self.name}] {tool_name} 调用失败: {e}")
            self._offline = True
            return {"success": False, "error": str(e), "tool": tool_name}

    async def _call_mcp(self, client, tool_name: str, params: dict) -> dict:
        """MCP 协议调用"""
        start = time.time()
        # MCP SSE 模式: POST to /call/{tool}
        url = f"{self.base_url}/call/{tool_name}"
        resp = await client.post(url, json=params, headers=self.auth_headers)
        data = resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
        data["duration_ms"] = int((time.time() - start) * 1000)
        return data

    async def _call_rest(self, client, tool_name: str, params: dict) -> dict:
        """REST API 调用 — 根据 tool_name 映射到 API 端点"""
        start = time.time()
        # REST API 端点映射
        endpoints = {
            "get_fba_inventory": ("GET", "/api/v1/inventory/fba"),
            "get_sales_data": ("GET", "/api/v1/sales/report"),
            "get_inbound_shipments": ("GET", "/api/v1/inventory/inbound"),
            "get_profit_report": ("GET", "/api/v1/finance/profit"),
            "get_products": ("GET", "/api/v1/products"),
            "get_orders": ("GET", "/api/v1/orders"),
            "get_ad_campaigns": ("GET", "/api/v1/advertising/campaigns"),
            "get_ad_report": ("GET", "/api/v1/advertising/report"),
        }
        endpoint = endpoints.get(tool_name)
        if not endpoint:
            return {"success": False, "error": f"REST 端点未配置: {tool_name}"}

        method, path = endpoint
        url = f"{self.base_url}{path}"
        headers = {**self.auth_headers}

        if method == "GET":
            resp = await client.get(url, params=params, headers=headers)
        else:
            resp = await client.post(url, json=params, headers=headers)

        data = resp.json() if resp.status_code in (200, 201) else {"success": False, "error": resp.text}
        data["duration_ms"] = int((time.time() - start) * 1000)
        return data

    def __repr__(self):
        status = "offline" if self._offline else "online"
        return f"<MCPClient: {self.name} ({self.transport_type}) [{status}]>"
