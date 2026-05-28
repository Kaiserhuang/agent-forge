"""
LLM 模型工厂 — 根据 provider 名称创建对应的适配器实例

支持:
- deepseek → DeepSeekAdapter
- openai   → OpenAIAdapter
- claude   → ClaudeAdapter
- ollama   → OllamaAdapter
"""

from __future__ import annotations

import os

from backend.core.config import LLMConfig
from backend.llm.base import BaseLLM


def create_llm(config: LLMConfig) -> BaseLLM:
    """
    根据 LLMConfig.provider 创建对应的适配器

    Args:
        config: LLM 配置

    Returns:
        BaseLLM 适配器实例

    Raises:
        ValueError: 不支持的 provider
    """
    provider = config.provider.lower()

    if provider == "deepseek":
        from backend.llm.deepseek_adapter import DeepSeekAdapter
        return DeepSeekAdapter(config)

    elif provider == "openai":
        from backend.llm.openai_adapter import OpenAIAdapter
        return OpenAIAdapter(config)

    elif provider == "claude":
        from backend.llm.claude_adapter import ClaudeAdapter
        return ClaudeAdapter(config)

    elif provider == "ollama":
        from backend.llm.ollama_adapter import OllamaAdapter
        return OllamaAdapter(config)

    else:
        raise ValueError(
            f"不支持的 provider: '{provider}'。"
            f"可选: deepseek, openai, claude, ollama"
        )


SUPPORTED_PROVIDERS = {
    "deepseek": {
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "env_key": "DEEPSEEK_API_KEY",
        "default_base_url": "https://api.deepseek.com/v1",
    },
    "openai": {
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "env_key": "OPENAI_API_KEY",
        "default_base_url": "https://api.openai.com/v1",
    },
    "claude": {
        "models": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
        "env_key": "ANTHROPIC_API_KEY",
        "default_base_url": "https://api.anthropic.com",
    },
    "ollama": {
        "models": ["llama3.2", "llama3.1", "qwen2.5", "mistral", "codellama"],
        "env_key": "",
        "default_base_url": "http://localhost:11434/v1",
    },
}


def get_supported_models(provider: str | None = None) -> dict:
    """返回支持的模型列表"""
    if provider:
        info = SUPPORTED_PROVIDERS.get(provider.lower())
        if info:
            return {provider.lower(): info}
        return {}
    return SUPPORTED_PROVIDERS
