"""
LLM Provider 工厂 — 按配置创建 LLM 实例
支持: Claude / OpenAI / DeepSeek / Qwen / GLM / Custom
"""

from __future__ import annotations

from llm.base import BaseLLM
from llm.providers.claude import ClaudeLLM
from llm.providers.openai_compat import OpenAICompatLLM


# Provider 注册表
PROVIDER_MAP = {
    "claude": ClaudeLLM,
    "openai": OpenAICompatLLM,
    "deepseek": OpenAICompatLLM,
    "qwen": OpenAICompatLLM,
    "glm": OpenAICompatLLM,
    "custom": OpenAICompatLLM,
}

# provider → default base_url
DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
}


def create_llm(config: dict) -> BaseLLM:
    """
    根据配置创建 LLM 实例

    config 格式:
      {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "api_key": "sk-xxx",
        "base_url": "https://api.deepseek.com/v1",   # 可选
        "max_tokens": 4096,
        "temperature": 0.3,
      }
    """
    provider = config.get("provider", "deepseek")

    if provider not in PROVIDER_MAP:
        raise ValueError(
            f"不支持的 LLM Provider: {provider}. "
            f"支持: {list(PROVIDER_MAP.keys())}"
        )

    # 补全默认 base_url
    if not config.get("base_url") and provider in DEFAULT_BASE_URLS:
        config = {**config, "base_url": DEFAULT_BASE_URLS[provider]}

    llm_class = PROVIDER_MAP[provider]
    return llm_class(config)
