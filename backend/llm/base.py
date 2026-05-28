"""
LLM 抽象基类 — 所有模型适配器需实现 chat() 和 chat_stream() 方法
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

from backend.core.config import LLMConfig, Message, ToolCall


@dataclass
class LLMResponse:
    """LLM 调用返回"""
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    model: str = ""
    usage: dict | None = None
    finish_reason: str = "stop"


class BaseLLM(ABC):
    """LLM 适配器基类"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """非流式对话 — 返回完整响应"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMResponse]:
        """流式对话 — 逐块产出 delta"""
        ...
        yield  # pragma: no cover — 让 ABC 识别为 async generator
