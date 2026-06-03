"""
MCP 工具层 — 积木式外部服务集成
- base_server: MCP 基类
- client: MCP 客户端 (调用 MCP Server)
- lingxing_server: 领星 ERP MCP Server
- amazon_sp_server: 亚马逊 SP-API MCP Server
- ad_api_server: 广告 API MCP Server
- mock_data: 共享模拟数据层
"""

from .base_server import BaseMCPServer, ToolDefinition, DatabaseMCPServer, NotifyMCPServer
from .client import MCPHub, MCPClient, mcp_hub
