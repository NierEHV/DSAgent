"""
LLM 抽象基类
所有 LLM Provider 统一接口
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMResponse:
    """LLM 响应 — 统一格式"""
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    duration_ms: int = 0
    error: Optional[str] = None


class BaseLLM(ABC):
    """LLM 抽象基类"""

    def __init__(self, config: dict):
        self.provider = config.get("provider", "unknown")
        self.model = config.get("model", "")
        self.api_key = config.get("api_key", "")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.3)

    @abstractmethod
    async def chat(self, system_prompt: str, user_message: str, **kwargs) -> LLMResponse:
        """发送对话请求"""
        ...

    @abstractmethod
    async def analyze(self, system_prompt: str, context: dict, **kwargs) -> LLMResponse:
        """发送分析请求 (结构化上下文)"""
        ...

    def _build_messages(self, system_prompt: str, user_message: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    def __repr__(self):
        return f"<LLM: {self.provider}/{self.model}>"
