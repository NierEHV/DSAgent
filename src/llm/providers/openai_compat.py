"""
OpenAI 兼容 LLM Provider
支持: OpenAI / DeepSeek / Qwen / GLM / 自定义
所有遵循 OpenAI API 格式的 Provider 统一走此通道
"""

from __future__ import annotations

import json
import time
from typing import Optional

from ..base import BaseLLM, LLMResponse


class OpenAICompatLLM(BaseLLM):
    """OpenAI 兼容协议 Provider"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    async def chat(self, system_prompt: str, user_message: str, **kwargs) -> LLMResponse:
        start = time.time()
        try:
            client = self._get_client()
            max_tok = kwargs.get("max_tokens", self.max_tokens)
            response = await client.chat.completions.create(
                model=kwargs.get("model", self.model),
                max_tokens=max_tok,
                temperature=kwargs.get("temperature", self.temperature),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                provider=self.provider,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                provider=self.provider,
                duration_ms=int((time.time() - start) * 1000),
                error=str(e),
            )

    async def analyze(self, system_prompt: str, context: dict, **kwargs) -> LLMResponse:
        user_message = json.dumps(context, ensure_ascii=False, indent=2, default=str)
        return await self.chat(system_prompt, user_message, **kwargs)
