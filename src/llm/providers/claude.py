"""
Claude LLM Provider
使用 Anthropic SDK
"""

from __future__ import annotations

import time
from typing import Optional

from ..base import BaseLLM, LLMResponse


class ClaudeLLM(BaseLLM):
    """Anthropic Claude Provider"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.provider = "claude"
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def chat(self, system_prompt: str, user_message: str, **kwargs) -> LLMResponse:
        start = time.time()
        try:
            client = self._get_client()
            max_tok = kwargs.get("max_tokens", self.max_tokens)
            response = client.messages.create(
                model=kwargs.get("model", self.model),
                max_tokens=max_tok,
                temperature=kwargs.get("temperature", self.temperature),
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                provider="claude",
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                provider="claude",
                duration_ms=int((time.time() - start) * 1000),
                error=str(e),
            )

    async def analyze(self, system_prompt: str, context: dict, **kwargs) -> LLMResponse:
        import json
        user_message = json.dumps(context, ensure_ascii=False, indent=2, default=str)
        return await self.chat(system_prompt, user_message, **kwargs)
