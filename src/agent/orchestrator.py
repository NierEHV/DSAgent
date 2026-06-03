"""
Agent 编排器 v2.0 — LLM + MCP + Business Agents 积木式集成

核心流程：
  用户消息 → 意图识别 → 匹配 Agent → 执行 Agent → LLM 润色 → 返回

积木组成：
  - IntentDetector: 意图识别积木
  - WorkflowEngine: 工作流执行积木
  - MCPHub: 外部工具积木
  - LLM Client: 推理润色积木
  - Business Agents: 业务逻辑积木
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Optional

from .intent_detector import IntentDetector
from .workflow_engine import WorkflowEngine, NodeExecutor, RiskLevel

from mcp.client import mcp_hub
from agents.inventory_agent import InventoryAlertAgent
from agents.ad_report_agent import AdReportAgent
from agents.profit_agent import ProfitAnalysisAgent
from agents.hijack_agent import HijackMonitorAgent
from agents.daily_report_agent import DailyReportAgent


class LLMClient:
    """LLM 客户端 — 支持 Claude 和 OpenAI"""

    def __init__(self):
        self.provider = os.environ.get("LLM_PROVIDER", "anthropic")  # anthropic | openai

    async def chat(self, system_prompt: str, user_message: str, max_tokens: int = 2048) -> str:
        """调用 LLM 进行对话"""
        try:
            if self.provider == "anthropic":
                return await self._claude_chat(system_prompt, user_message, max_tokens)
            else:
                return await self._openai_chat(system_prompt, user_message, max_tokens)
        except Exception as e:
            # LLM 不可用时返回友好的降级响应
            return f"[LLM 暂时不可用: {e}]\n\n以下是原始数据，请人工查看。"

    async def _claude_chat(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 未设置")

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    async def _openai_chat(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        from openai import AsyncOpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 未设置")

        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content


class AgentOrchestrator:
    """
    Agent 编排器 v2.0
    积木式组装：意图识别 + LLM推理 + MCP工具 + 业务Agent
    """

    def __init__(self, workflows_dir: str = "workflows"):
        self.intent_detector = IntentDetector()
        self.workflow_engine = WorkflowEngine(workflows_dir)
        self.node_executor: NodeExecutor = self.workflow_engine.executor
        self.llm = LLMClient()
        self.conversation_history: dict[str, list[dict]] = {}

        # 注册业务 Agent
        self.business_agents = {
            "inventory": InventoryAlertAgent(),
            "advertising": AdReportAgent(),
            "profit": ProfitAnalysisAgent(),
            "competitor": HijackMonitorAgent(),
            "report": DailyReportAgent(),
        }

        # 注册 MCP 工具到执行器
        self._setup_mcp_tools()
        self._setup_notify_channels()

    def is_ready(self) -> bool:
        return True

    def _setup_mcp_tools(self):
        """将 MCP Hub 中的工具注册到工作流执行器"""

        async def call_mcp_tool(mcp_name: str, tool_name: str, **params):
            client = mcp_hub.get(mcp_name)
            if not client:
                return {"success": False, "error": f"MCP Server 未连接: {mcp_name}"}
            result = await client.call(tool_name, params)
            return result

        # 注册通用 MCP 调用工具
        self.node_executor.register_tool("mcp_call", call_mcp_tool)

        # 为每个 Agent 注册快捷工具
        async def run_inventory_agent(**params):
            agent = InventoryAlertAgent()
            return await agent.run(**params)

        async def run_ad_report_agent(**params):
            agent = AdReportAgent()
            return await agent.run(**params)

        async def run_profit_agent(**params):
            agent = ProfitAnalysisAgent()
            return await agent.run(**params)

        async def run_hijack_agent(**params):
            agent = HijackMonitorAgent()
            return await agent.run(**params)

        async def run_daily_report_agent(**params):
            agent = DailyReportAgent()
            return await agent.run(**params)

        self.node_executor.register_tool("run_inventory_alert", run_inventory_agent)
        self.node_executor.register_tool("run_ad_report", run_ad_report_agent)
        self.node_executor.register_tool("run_profit_analysis", run_profit_agent)
        self.node_executor.register_tool("run_hijack_monitor", run_hijack_agent)
        self.node_executor.register_tool("run_daily_report", run_daily_report_agent)

        # 注册 LLM 调用工具
        async def llm_reasoning(prompt: str, system_prompt: str = "你是跨境电商AI助手", **kwargs):
            result = await self.llm.chat(system_prompt, prompt)
            return {"success": True, "content": result}

        self.node_executor.register_tool("llm_reasoning", llm_reasoning)

    def _setup_notify_channels(self):
        """设置通知渠道"""

        async def dingtalk_notify(message: str, at_users: list[str] = None):
            webhook = os.environ.get("DINGTALK_WEBHOOK", "")
            if webhook:
                import httpx
                payload = {
                    "msgtype": "markdown",
                    "markdown": {"title": "DS Agent 通知", "text": message},
                }
                if at_users:
                    payload["at"] = {"atMobiles": at_users, "isAtAll": False}
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(webhook, json=payload)
            else:
                print(f"[DingTalk 模拟] {message[:200]}...")
            return {"success": True, "channel": "dingtalk"}

        async def wecom_notify(message: str):
            webhook = os.environ.get("WECOM_WEBHOOK", "")
            if webhook:
                import httpx
                payload = {"msgtype": "markdown", "markdown": {"content": message}}
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(webhook, json=payload)
            else:
                print(f"[WeCom 模拟] {message[:200]}...")
            return {"success": True, "channel": "wecom"}

        self.node_executor.register_notify_channel("dingtalk", dingtalk_notify)
        self.node_executor.register_notify_channel("wecom", wecom_notify)

    async def execute(
        self,
        workflow_name: str,
        user_query: str,
        intent: dict,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> dict:
        """
        执行 Agent 对话流程

        流程：意图 → 匹配工作流 → 执行 Agent → LLM 润色 → 返回
        """
        # 会话管理
        if session_id and session_id not in self.conversation_history:
            self.conversation_history[session_id] = []

        start_time = time.time()

        # 获取工作流
        workflow = self.workflow_engine.get_workflow(workflow_name)
        if not workflow:
            return {
                "response": f"抱歉，找不到 {workflow_name} 工作流。",
                "tool_calls": [],
                "risk_level": "READ_ONLY",
            }

        # 检查风险等级
        max_risk = max(
            (node.risk_level for node in workflow.nodes),
            default=RiskLevel.READ_ONLY,
        )

        # 执行工作流
        input_data = {
            "user_query": user_query,
            "intent": intent,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
        }

        result = await self.workflow_engine.execute(
            workflow_name=workflow_name,
            input_data=input_data,
            auto_approve=(max_risk < RiskLevel.HIGH_RISK),
        )

        # 提取工具调用
        tool_calls = self._extract_tool_calls(result)

        # 用 LLM 生成自然语言响应
        response_text = await self._build_llm_response(
            user_query=user_query,
            intent=intent,
            workflow=workflow,
            result=result,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # 记录对话
        if session_id:
            self.conversation_history[session_id].append({
                "role": "user", "content": user_query, "timestamp": datetime.now().isoformat(),
            })
            self.conversation_history[session_id].append({
                "role": "assistant", "content": response_text, "timestamp": datetime.now().isoformat(),
            })

        return {
            "response": response_text,
            "tool_calls": tool_calls,
            "risk_level": max_risk.name,
            "execution_id": result.get("execution_id"),
            "workflow": workflow_name,
            "duration_ms": duration_ms,
        }

    async def execute_agent_directly(self, agent_name: str, **params) -> dict:
        """直接执行业务 Agent（不通过工作流）"""
        agent = self.business_agents.get(agent_name)
        if not agent:
            return {"status": "error", "message": f"Agent 不存在: {agent_name}"}

        return await agent.run(**params)

    async def execute_workflow(
        self, workflow_name: str, input_data: dict, auto_approve: bool = False
    ) -> dict:
        """直接执行工作流"""
        return await self.workflow_engine.execute(
            workflow_name=workflow_name,
            input_data=input_data,
            auto_approve=auto_approve,
        )

    def list_workflows(self) -> list[dict]:
        return self.workflow_engine.list_workflows()

    def get_workflow_detail(self, workflow_name: str) -> Optional[dict]:
        return self.workflow_engine.get_workflow_detail(workflow_name)

    async def _build_llm_response(
        self, user_query: str, intent: dict, workflow, result: dict
    ) -> str:
        """用 LLM 将执行结果转换为自然语言响应"""
        if result.get("status") == "rejected":
            return f"操作被拒绝：{result.get('reason', '人审未通过')}"
        if result.get("status") == "error":
            return f"执行出错：{result.get('error', '未知错误')}"

        # 尝试用 LLM 生成友好回复
        try:
            system_prompt = """你是专业跨境电商AI助手，帮助亚马逊卖家管理业务。
你需要用简洁清晰的中文回复用户，适当使用emoji，数据要准确。"""

            user_prompt = f"""用户查询: {user_query}
意图: {intent.get('intent')}
置信度: {intent.get('confidence')}
执行的工作流: {workflow.name}
执行结果: {result.get('results', {})}

请用友好的语气总结执行结果。突出关键数据和发现。如果有异常，重点提醒。"""

            return await self.llm.chat(system_prompt, user_prompt)
        except Exception:
            # LLM 不可用时使用模板降级
            return self._fallback_response(result, workflow)

    def _fallback_response(self, result: dict, workflow) -> str:
        """降级响应模板"""
        templates = {
            "inventory_alert_workflow": "📦 库存分析完成。执行耗时 {}ms。",
            "ad_analysis_workflow": "📢 广告分析报告已生成。执行耗时 {}ms。",
            "profit_analysis_workflow": "💰 利润分析完成。执行耗时 {}ms。",
            "listing_query_workflow": "📋 Listing 数据查询完成。执行耗时 {}ms。",
            "competitor_monitor_workflow": "🔍 竞品扫描完成。执行耗时 {}ms。",
            "report_generation_workflow": "📊 日报已生成。执行耗时 {}ms。",
        }
        template = templates.get(workflow.name, f"✅ 工作流 {workflow.name} 执行完成。")
        return template.format(result.get("duration_ms", 0))

    def _extract_tool_calls(self, result: dict) -> list[dict]:
        """从执行结果中提取工具调用信息"""
        tool_calls = []
        for node_id, node_result in result.get("results", {}).items():
            if node_result.get("type") == "tool_call":
                tool_calls.append({
                    "node_id": node_id,
                    "node_name": node_result.get("node_name", ""),
                    "result": node_result.get("result", {}),
                    "duration_ms": node_result.get("duration_ms", 0),
                })
        return tool_calls
