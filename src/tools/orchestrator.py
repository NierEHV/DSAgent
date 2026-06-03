"""
Tool Orchestrator — LLM 自主选择工具、执行、迭代
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


class ToolOrchestrator:
    """LLM Tool Calling 编排器"""

    def __init__(self, registry, llm):
        self.registry = registry
        self.llm = llm

    async def run(self, user_query: str, max_steps: int = 5) -> dict:
        """
        LLM 自主循环: 理解意图 → 选择工具 → 执行 → 看结果 → 决定是否继续
        """
        messages = [
            {"role": "system", "content": (
                "你是跨境电商运营AI助手。你可以调用工具来查询数据和分析问题。"
                "每次只调用一个最相关的工具。拿到结果后判断是否需要继续查询。"
                "如果不需要更多数据，直接给用户总结分析。"
                "用中文回复。"
            )},
            {"role": "user", "content": user_query},
        ]

        tools = self.registry.get_openai_schema()
        tool_calls_made = []

        for step in range(max_steps):
            try:
                response = await self.llm.chat(
                    system_prompt=messages[0]["content"],
                    user_message=self._format_messages(messages[1:]),
                    tools=tools if tools else None,
                )
            except Exception as e:
                logger.error(f"LLM调用失败 (step {step}): {e}")
                break

            content = response.content
            tool_calls = getattr(response, "tool_calls", None)

            if not tool_calls:
                # LLM 直接回复,结束
                return {
                    "response": content,
                    "tool_calls": tool_calls_made,
                    "steps": step + 1,
                }

            # 执行工具
            for tc in tool_calls:
                tool_name = tc.get("function", {}).get("name", "")
                args_str = tc.get("function", {}).get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}

                result = await self.registry.execute(tool_name, args)
                tool_calls_made.append({
                    "tool": tool_name,
                    "args": args,
                    "result": result[:500] if len(result) > 500 else result,
                })

                # 把工具结果追加到 messages
                messages.append({"role": "assistant", "content": None,
                                 "tool_calls": [tc]})
                messages.append({"role": "tool", "content": result,
                                 "tool_call_id": tc.get("id", tool_name)})

        # 最后让 LLM 总结
        try:
            final = await self.llm.chat(
                system_prompt="基于以上工具调用结果,给用户一个简洁的总结。用中文。",
                user_message=user_query + "\n\n工具调用结果:\n" + json.dumps(
                    tool_calls_made, ensure_ascii=False, default=str
                ),
            )
            return {"response": final.content, "tool_calls": tool_calls_made, "steps": max_steps}
        except Exception:
            return {"response": f"调用了 {len(tool_calls_made)} 个工具,详见上方结果",
                    "tool_calls": tool_calls_made, "steps": max_steps}

    def _format_messages(self, msgs: list[dict]) -> str:
        """简单格式化消息为 LLM 输入"""
        parts = []
        for m in msgs:
            if m.get("role") == "user":
                parts.append(f"用户: {m['content']}")
            elif m.get("role") == "tool":
                parts.append(f"工具返回: {m['content']}")
        return "\n".join(parts)
