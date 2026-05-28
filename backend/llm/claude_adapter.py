"""
Claude LLM 适配器 — 通过 Anthropic SDK 调用 Claude 模型

支持:
- 非流式 / 流式 chat
- 工具调用 (tool use)
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

from backend.core.config import LLMConfig, Message, ToolCall
from backend.llm.base import BaseLLM, LLMResponse


class ClaudeAdapter(BaseLLM):
    """Anthropic Claude 适配器"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        from anthropic import AsyncAnthropic

        api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")

        # Claude 的 API base_url 与 OpenAI 不同，使用 anthropic SDK 的内置地址
        self.client = AsyncAnthropic(
            api_key=api_key,
            timeout=config.timeout_sec,
        )
        self._model = config.model

    # ---- 消息转换 ----

    def _to_anthropic_messages(self, messages: list[Message]) -> tuple[str, list[dict]]:
        """将内部 Message 转为 Anthropic 格式

        返回: (system_prompt, messages_list)
        """
        system_parts = []
        api_messages: list[dict] = []

        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content or "")
                continue

            role = "assistant" if msg.role == "assistant" else "user"

            content: list[dict] = []
            if msg.content:
                content.append({"type": "text", "text": msg.content})

            # tool_use (assistant 的 function call)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.args,
                    })

            # tool_result
            if msg.role == "tool":
                content.append({
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": msg.content or "",
                })
                role = "user"  # Anthropic 要求 tool_result 用 user role

            api_messages.append({"role": role, "content": content})

        system = "\n\n".join(system_parts) if system_parts else ""
        return system, api_messages

    def _to_anthropic_tools(self, skills: list[dict] | None) -> list[dict] | None:
        """将内部技能定义转为 Anthropic tools 格式"""
        if not skills:
            return None
        return [
            {
                "name": s["name"],
                "description": s.get("description", ""),
                "input_schema": s.get("parameters", {}),
            }
            for s in skills
        ]

    def _parse_response(self, response: Any) -> LLMResponse:
        """解析 Anthropic 响应"""
        content_blocks = response.content
        text_parts = []
        tool_calls = []

        for block in content_blocks:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    args=dict(block.input) if hasattr(block, 'input') else {},
                ))

        usage_dict = None
        if hasattr(response, 'usage') and response.usage:
            usage_dict = {
                "prompt_tokens": getattr(response.usage, 'input_tokens', 0),
                "completion_tokens": getattr(response.usage, 'output_tokens', 0),
                "total_tokens": (
                    getattr(response.usage, 'input_tokens', 0) +
                    getattr(response.usage, 'output_tokens', 0)
                ),
            }

        return LLMResponse(
            content="".join(text_parts) if text_parts else None,
            tool_calls=tool_calls if tool_calls else None,
            model=response.model,
            usage=usage_dict,
        )

    # ---- 接口实现 ----

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        system, api_messages = self._to_anthropic_messages(messages)
        api_tools = self._to_anthropic_tools(tools)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if system:
            kwargs["system"] = system
        if api_tools:
            kwargs["tools"] = api_tools

        response = await self.client.messages.create(**kwargs)
        return self._parse_response(response)

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMResponse]:
        system, api_messages = self._to_anthropic_messages(messages)
        api_tools = self._to_anthropic_tools(tools)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": True,
        }
        if system:
            kwargs["system"] = system
        if api_tools:
            kwargs["tools"] = api_tools

        text_buffer = ""
        current_tool_calls: dict[str, dict] = {}

        async with self.client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        text_buffer += event.delta.text
                        yield LLMResponse(content=event.delta.text)
                    elif event.delta.type == "input_json_delta":
                        pass  # 工具参数增量，在 content_block_stop 中组装

                elif event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        cb = event.content_block
                        current_tool_calls[cb.id] = {
                            "id": cb.id,
                            "name": cb.name,
                            "args": "",
                        }

                elif event.type == "content_block_stop":
                    pass  # 块结束，数据已完整

            # 流结束后获取最终消息
            final_msg = await stream.get_final_message()
            yield self._parse_response(final_msg)
