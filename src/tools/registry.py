"""
Tool Registry — 统一工具注册, 支持 OpenAI Tool Calling
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable  # async fn


class ToolRegistry:
    """工具注册中心"""

    def __init__(self, datasource_registry=None, agent_hub=None):
        self._tools: dict[str, Tool] = {}
        self._registry = datasource_registry
        self._hub = agent_hub
        self._register_builtin()

    def _register_builtin(self):
        self.register(Tool(
            name="check_inventory",
            description="查询所有SKU的FBA库存状态,返回每个SKU的库存量、可售天数、是否需要补货",
            parameters={
                "type": "object",
                "properties": {
                    "sku_list": {"type": "array", "items": {"type": "string"}, "description": "可选,指定SKU列表"}
                },
                "required": []
            },
            handler=self._run_inventory_check,
        ))
        self.register(Tool(
            name="analyze_advertising",
            description="分析广告数据,返回ACOS、ROAS、预算使用率,检测异常",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._run_ad_analysis,
        ))
        self.register(Tool(
            name="scan_competitors",
            description="扫描竞品/跟卖状态,返回Buy Box持有情况和新卖家检测",
            parameters={
                "type": "object",
                "properties": {
                    "asin_list": {"type": "array", "items": {"type": "string"}, "description": "ASIN列表"}
                },
                "required": []
            },
            handler=self._run_competitor_scan,
        ))
        self.register(Tool(
            name="check_profit",
            description="查询利润数据,返回毛利率、退款率、广告占比",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._run_profit_check,
        ))
        self.register(Tool(
            name="generate_report",
            description="生成运营日报,汇总全店核心指标",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._run_report,
        ))

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools.get(name)

    def get_openai_schema(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            }
            for t in self._tools.values()
        ]

    async def execute(self, tool_name: str, args: dict) -> str:
        tool = self._tools.get(tool_name)
        if not tool:
            return json.dumps({"error": f"工具不存在: {tool_name}"}, ensure_ascii=False)
        try:
            result = await tool.handler(**args)
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False, default=str)
            return str(result)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _run_inventory_check(self, sku_list: list = None, **kw):
        if not self._hub:
            return {"error": "系统未初始化"}
        agent = self._hub.agents.get("inventory")
        if not agent:
            return {"error": "库存Agent不可用"}
        result = await agent.run()
        return {
            "status": result.get("status"),
            "summary": result.get("summary"),
            "alerts_count": len(result.get("alerts", [])),
        }

    async def _run_ad_analysis(self, **kw):
        if not self._hub:
            return {"error": "系统未初始化"}
        agent = self._hub.agents.get("advertising")
        if not agent:
            return {"error": "广告Agent不可用"}
        result = await agent.run()
        return {
            "status": result.get("status"),
            "summary": result.get("summary"),
        }

    async def _run_competitor_scan(self, asin_list: list = None, **kw):
        if not self._hub:
            return {"error": "系统未初始化"}
        agent = self._hub.agents.get("competitor")
        if not agent:
            return {"error": "竞品Agent不可用"}
        result = await agent.run(asin_list=asin_list)
        return {
            "status": result.get("status"),
            "summary": result.get("summary"),
            "threats_count": len(result.get("threats", [])),
        }

    async def _run_profit_check(self, **kw):
        if not self._hub:
            return {"error": "系统未初始化"}
        agent = self._hub.agents.get("profit")
        if not agent:
            return {"error": "利润Agent不可用"}
        result = await agent.run()
        return {
            "status": result.get("status"),
            "summary": result.get("summary"),
        }

    async def _run_report(self, **kw):
        if not self._hub:
            return {"error": "系统未初始化"}
        agent = self._hub.agents.get("report")
        if not agent:
            return {"error": "日报Agent不可用"}
        result = await agent.run()
        return {"report": result.get("markdown", "")[:2000]}
