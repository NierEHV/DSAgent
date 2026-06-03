"""
Agent 工作流执行引擎
参考 n8n-workflows-main 的 workflow JSON 格式 + 执行模式

n8n workflow JSON 结构：
{
  "nodes": [...],       # 节点列表 (trigger, action, condition, etc.)
  "connections": {...},  # 节点连接关系
  "settings": {...},     # 执行设置 (timeout, retry, etc.)
  "meta": {...}          # 元数据
}
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


class NodeType(str, Enum):
    """节点类型 — 对应 n8n 的 node types"""
    TRIGGER = "trigger"           # 触发器（Cron / Webhook / Manual）
    TOOL_CALL = "tool_call"       # MCP 工具调用
    LLM_CALL = "llm_call"         # LLM 推理
    CONDITION = "condition"       # 条件分支
    HUMAN_REVIEW = "human_review" # 人工审批节点
    NOTIFY = "notify"             # 通知发送
    OUTPUT = "output"             # 结果输出


class RiskLevel(int, Enum):
    """操作风险等级"""
    READ_ONLY = 0     # 只读查询 — 无需审批
    ANALYSIS = 1      # 分析建议 — 仅生成报告
    LOW_RISK = 2      # 低风险操作 — 通知 + 日志
    HIGH_RISK = 3     # 高风险操作 — 必须人审


@dataclass
class WorkflowNode:
    """
    工作流节点
    参考 n8n workflow JSON 中的 nodes[] 元素
    """
    id: str
    name: str
    type: NodeType
    config: dict = field(default_factory=dict)      # 节点配置
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    retry_count: int = 3
    timeout_ms: int = 30000
    position: tuple[int, int] = (0, 0)              # 可视化位置 (x, y)


@dataclass
class WorkflowDefinition:
    """
    工作流定义
    参考 n8n workflow JSON 文件的完整结构
    """
    name: str
    description: str
    nodes: list[WorkflowNode]
    connections: dict[str, list[str]]                 # node_id → [next_node_ids]
    trigger_type: str = "manual"                      # scheduled / webhook / manual
    trigger_config: dict = field(default_factory=dict)
    settings: dict = field(default_factory=lambda: {
        "executionTimeout": 3600,
        "retryOnFail": True,
        "retryCount": 3,
        "maxExecutions": 100,
    })
    tags: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=lambda: {
        "version": "1.0.0",
        "category": "automation",
        "status": "active",
    })

    @classmethod
    def from_json(cls, filepath: str) -> "WorkflowDefinition":
        """从 JSON 文件加载工作流定义"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = []
        for node_data in data.get("nodes", []):
            nodes.append(WorkflowNode(
                id=node_data["id"],
                name=node_data["name"],
                type=NodeType(node_data.get("type", "tool_call")),
                config=node_data.get("config", {}),
                risk_level=RiskLevel(node_data.get("risk_level", 0)),
                retry_count=node_data.get("retry_count", 3),
                timeout_ms=node_data.get("timeout_ms", 30000),
                position=tuple(node_data.get("position", (0, 0))),
            ))

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            nodes=nodes,
            connections=data.get("connections", {}),
            trigger_type=data.get("trigger_type", "manual"),
            trigger_config=data.get("trigger_config", {}),
            settings=data.get("settings", {}),
            tags=data.get("tags", []),
            meta=data.get("meta", {}),
        )

    def to_json(self, filepath: str):
        """保存工作流定义为 JSON 文件"""
        data = {
            "name": self.name,
            "description": self.description,
            "trigger_type": self.trigger_type,
            "trigger_config": self.trigger_config,
            "nodes": [
                {
                    "id": n.id,
                    "name": n.name,
                    "type": n.type.value,
                    "config": n.config,
                    "risk_level": n.risk_level.value,
                    "retry_count": n.retry_count,
                    "timeout_ms": n.timeout_ms,
                    "position": list(n.position),
                }
                for n in self.nodes
            ],
            "connections": self.connections,
            "settings": self.settings,
            "tags": self.tags,
            "meta": self.meta,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class NodeExecutor:
    """
    节点执行器 — 分发到不同类型节点的执行逻辑
    参考 n8n 的 node execution 模式
    """

    def __init__(self):
        self._tool_registry: dict[str, Callable] = {}
        self._llm_client = None
        self._notify_channels: dict[str, Callable] = {}

    def register_tool(self, tool_name: str, handler: Callable):
        """注册工具处理器"""
        self._tool_registry[tool_name] = handler

    def register_notify_channel(self, channel: str, handler: Callable):
        """注册通知渠道"""
        self._notify_channels[channel] = handler

    async def execute(self, node: WorkflowNode, context: dict) -> dict:
        """
        执行单个节点
        参考 n8n 的 node execution — 按 type 分发给不同执行器
        """
        try:
            if node.type == NodeType.TOOL_CALL:
                return await self._execute_tool(node, context)
            elif node.type == NodeType.LLM_CALL:
                return await self._execute_llm(node, context)
            elif node.type == NodeType.CONDITION:
                return await self._execute_condition(node, context)
            elif node.type == NodeType.HUMAN_REVIEW:
                return await self._execute_human_review(node, context)
            elif node.type == NodeType.NOTIFY:
                return await self._execute_notify(node, context)
            elif node.type == NodeType.OUTPUT:
                return self._execute_output(node, context)
            else:
                return {"success": False, "error": f"未知节点类型: {node.type}"}
        except Exception as e:
            return {"success": False, "error": str(e), "node_id": node.id}

    async def _execute_tool(self, node: WorkflowNode, context: dict) -> dict:
        """执行 MCP 工具调用"""
        tool_name = node.config.get("tool_name")
        params = self._resolve_params(node.config.get("params", {}), context)

        if tool_name not in self._tool_registry:
            return {"success": False, "error": f"工具未注册: {tool_name}"}

        return await self._tool_registry[tool_name](**params)

    async def _execute_llm(self, node: WorkflowNode, context: dict) -> dict:
        """执行 LLM 推理"""
        prompt_template = node.config.get("prompt", "")
        # 模板变量替换 — 用 context 中的值填充 {variable}
        prompt = self._resolve_template(prompt_template, context)

        # LLM 调用
        result = await self._call_llm(prompt, node.config)
        return {"success": True, "content": result}

    async def _execute_condition(self, node: WorkflowNode, context: dict) -> dict:
        """执行条件判断"""
        condition = node.config.get("condition", "")
        # 安全的条件评估
        # TODO: 实现表达式评估器
        return {"success": True, "result": True}

    async def _execute_human_review(self, node: WorkflowNode, context: dict) -> dict:
        """执行人审节点"""
        approval_config = node.config.get("approval", {})

        # 生成审批单 → 推送到指定渠道 → 等待审批结果
        approval_request = {
            "title": approval_config.get("title", "Agent 操作审批"),
            "content": context.get("llm_suggestion", ""),
            "risk_level": node.risk_level.name,
            "channel": approval_config.get("channel", "dingtalk"),
            "timeout_minutes": approval_config.get("timeout_minutes", 30),
        }

        # 发送审批请求
        approved, comment = await self._approval_workflow(approval_request)

        return {
            "success": True,
            "approved": approved,
            "comment": comment,
        }

    async def _execute_notify(self, node: WorkflowNode, context: dict) -> dict:
        """执行通知发送"""
        channel = node.config.get("channel", "dingtalk")
        message = self._resolve_template(node.config.get("message", ""), context)

        if channel not in self._notify_channels:
            return {"success": False, "error": f"通知渠道未注册: {channel}"}

        await self._notify_channels[channel](message)
        return {"success": True, "channel": channel}

    def _execute_output(self, node: WorkflowNode, context: dict) -> dict:
        """组装输出"""
        return {"success": True, "result": context.get("results", {})}

    def _resolve_params(self, params: dict, context: dict) -> dict:
        """解析参数 — 替换 {variable} 引用"""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_template(value, context)
            else:
                resolved[key] = value
        return resolved

    def _resolve_template(self, template: str, context: dict) -> str:
        """简单模板引擎 — 替换 {path.to.value}"""
        result = template
        for key, val in context.items():
            result = result.replace(f"{{{key}}}", str(val))
        return result

    async def _call_llm(self, prompt: str, config: dict) -> str:
        """调用 LLM"""
        # TODO: 实际接入 Claude/OpenAI API
        return f"[LLM Response for: {prompt[:100]}...]"

    async def _approval_workflow(self, request: dict) -> tuple[bool, str]:
        """审批工作流"""
        # TODO: 实现实际的审批机制（钉钉OA/企微审批）
        return True, "auto_approved_in_dev"


class WorkflowEngine:
    """
    工作流引擎 — 核心执行器
    参考 n8n 的 workflow execution engine
    """

    def __init__(self, workflows_dir: str = "workflows"):
        self.workflows: dict[str, WorkflowDefinition] = {}
        self.executor = NodeExecutor()
        self.workflows_dir = Path(workflows_dir)
        self.execution_history: list[dict] = []

        # 加载所有工作流定义
        self._load_all_workflows()

    def _load_all_workflows(self):
        """加载 workflows/ 目录下所有 JSON 工作流"""
        if not self.workflows_dir.exists():
            return
        for filepath in self.workflows_dir.glob("*.json"):
            try:
                workflow = WorkflowDefinition.from_json(str(filepath))
                self.workflows[workflow.name] = workflow
            except Exception as e:
                print(f"加载工作流失败 {filepath}: {e}")

    def register_workflow(self, workflow: WorkflowDefinition):
        """注册工作流"""
        self.workflows[workflow.name] = workflow

    def get_workflow(self, name: str) -> Optional[WorkflowDefinition]:
        return self.workflows.get(name)

    def list_workflows(self) -> list[dict]:
        """列出所有工作流 — 参考 enhanced_api.py 的 workflow listing"""
        return [
            {
                "name": wf.name,
                "description": wf.description,
                "trigger_type": wf.trigger_type,
                "node_count": len(wf.nodes),
                "tags": wf.tags,
                "status": wf.meta.get("status", "unknown"),
            }
            for wf in self.workflows.values()
        ]

    def get_workflow_detail(self, name: str) -> Optional[dict]:
        """获取工作流详情（含节点信息）"""
        wf = self.workflows.get(name)
        if not wf:
            return None

        return {
            "name": wf.name,
            "description": wf.description,
            "trigger_type": wf.trigger_type,
            "trigger_config": wf.trigger_config,
            "nodes": [
                {
                    "id": n.id,
                    "name": n.name,
                    "type": n.type.value,
                    "risk_level": n.risk_level.name,
                    "config_summary": list(n.config.keys()),
                }
                for n in wf.nodes
            ],
            "connections": wf.connections,
            "settings": wf.settings,
            "tags": wf.tags,
            "meta": wf.meta,
        }

    async def execute(
        self,
        workflow_name: str,
        input_data: dict,
        auto_approve: bool = False,
    ) -> dict:
        """
        执行工作流 — 核心方法

        流程：
        1. 拓扑排序所有节点
        2. 按序执行每个节点
        3. 遇到 HUMAN_REVIEW → 暂停等待审批（或 auto_approve）
        4. 记录执行历史
        """
        workflow = self.workflows.get(workflow_name)
        if not workflow:
            return {"status": "error", "message": f"工作流不存在: {workflow_name}"}

        start_time = time.time()
        context = {
            "input": input_data,
            "results": {},
            "llm_suggestion": "",
        }

        execution_id = f"{workflow_name}_{int(start_time)}"

        try:
            # 拓扑排序 → 确定执行顺序
            execution_order = self._topological_sort(workflow)

            for node in execution_order:
                node_start = time.time()

                # 执行节点（带重试 — 参考 n8n settings.retryOnFail）
                for attempt in range(node.retry_count):
                    try:
                        result = await asyncio.wait_for(
                            self.executor.execute(node, context),
                            timeout=node.timeout_ms / 1000,
                        )
                        break
                    except asyncio.TimeoutError:
                        if attempt == node.retry_count - 1:
                            raise
                        result = {"success": False, "error": "Timeout, retrying..."}
                    except Exception as e:
                        if attempt == node.retry_count - 1:
                            raise
                        result = {"success": False, "error": str(e)}

                # 人审节点处理
                if node.type == NodeType.HUMAN_REVIEW and not auto_approve:
                    if not result.get("approved"):
                        return {
                            "status": "rejected",
                            "reason": result.get("comment", "人审未通过"),
                            "rejected_at": node.name,
                            "execution_id": execution_id,
                        }

                context["results"][node.id] = {
                    "node_name": node.name,
                    "type": node.type.value,
                    "result": result,
                    "duration_ms": int((time.time() - node_start) * 1000),
                    "timestamp": time.time(),
                }

            total_duration_ms = int((time.time() - start_time) * 1000)
            self.execution_history.append({
                "execution_id": execution_id,
                "workflow": workflow_name,
                "status": "completed",
                "duration_ms": total_duration_ms,
                "timestamp": time.time(),
            })

            return {
                "status": "completed",
                "execution_id": execution_id,
                "duration_ms": total_duration_ms,
                "results": context["results"],
            }

        except Exception as e:
            return {
                "status": "error",
                "execution_id": execution_id,
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
            }

    def _topological_sort(self, workflow: WorkflowDefinition) -> list[WorkflowNode]:
        """
        拓扑排序 — 按依赖关系排列节点
        参考 n8n 的 workflow execution order
        """
        node_map = {n.id: n for n in workflow.nodes}

        # 计算入度
        in_degree = {n.id: 0 for n in workflow.nodes}
        for node_id, next_ids in workflow.connections.items():
            for next_id in next_ids:
                if next_id in in_degree:
                    in_degree[next_id] += 1

        # BFS 拓扑排序
        queue = [n.id for n in workflow.nodes if in_degree.get(n.id, 0) == 0]
        sorted_ids = []

        while queue:
            current = queue.pop(0)
            sorted_ids.append(current)
            for next_id in workflow.connections.get(current, []):
                if next_id in in_degree:
                    in_degree[next_id] -= 1
                    if in_degree[next_id] == 0:
                        queue.append(next_id)

        # 处理未排序的节点（有环）
        for node in workflow.nodes:
            if node.id not in sorted_ids:
                sorted_ids.append(node.id)

        return [node_map[nid] for nid in sorted_ids if nid in node_map]
