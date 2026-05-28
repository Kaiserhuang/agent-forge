"""
OpenAI LLM 适配器 — 通过 OpenAI SDK 调用 GPT-4o / GPT-4 / GPT-3.5 等
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from backend.core.config import LLMConfig, Message, ToolCall
from backend.llm.base import BaseLLM, LLMResponse


def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for msg in messages:
        d: dict[str, Any] = {"role": msg.role}
        if msg.content is not None:
            d["content"] = msg.content
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": str(tc.args)},
                }
                for tc in msg.tool_calls
            ]
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        if msg.name:
            d["name"] = msg.name
        result.append(d)
    return result


def _to_openai_tools(skills: list[dict] | None) -> list[dict[str, Any]] | None:
    if not skills:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s.get("description", ""),
                "parameters": s.get("parameters", {}),
            },
        }
        for s in skills
    ]


class OpenAIAdapter(BaseLLM):
    """OpenAI 模型适配器"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        api_key = config.api_key or os.environ.get("OPENAI_API_KEY", "")
        base_url = config.base_url or "https://api.openai.com/v1"

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=config.timeout_sec,
        )

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        openai_msgs = _to_openai_messages(messages)
        openai_tools = _to_openai_tools(tools)

        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=openai_msgs,
            tools=openai_tools,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        choice = response.choices[0]
        msg = choice.message

        tool_calls = None
        if msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {"raw": tc.function.arguments}
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, args=args)
                )

        usage_dict = None
        if response.usage:
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            model=response.model,
            usage=usage_dict,
            finish_reason=choice.finish_reason or "",
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMResponse]:
        openai_msgs = _to_openai_messages(messages)
        openai_tools = _to_openai_tools(tools)

        stream = await self.client.chat.completions.create(
            model=self.config.model,
            messages=openai_msgs,
            tools=openai_tools,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )

        content_parts: list[str] = []
        tool_call_deltas: dict[int, dict] = {}

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if delta is None:
                continue

            if delta.content:
                content_parts.append(delta.content)
                yield LLMResponse(content=delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_call_deltas:
                        tool_call_deltas[idx] = {
                            "id": tc_delta.id or "",
                            "name": tc_delta.function.name or "",
                            "args": tc_delta.function.arguments or "",
                        }
                    else:
                        if tc_delta.id:
                            tool_call_deltas[idx]["id"] = tc_delta.id
                        if tc_delta.function and tc_delta.function.name:
                            tool_call_deltas[idx]["name"] = tc_delta.function.name
                        if tc_delta.function and tc_delta.function.arguments:
                            tool_call_deltas[idx]["args"] += tc_delta.function.arguments

            if chunk.choices[0].finish_reason:
                full_content = "".join(content_parts) or None
                tool_calls_list = None
                if tool_call_deltas:
                    tool_calls_list = []
                    for idx in sorted(tool_call_deltas.keys()):
                        d = tool_call_deltas[idx]
                        try:
                            parsed_args = json.loads(d["args"])
                        except json.JSONDecodeError:
                            parsed_args = {"raw": d["args"]}
                        tool_calls_list.append(
                            ToolCall(id=d["id"] or f"call_{idx}", name=d["name"], args=parsed_args)
                        )

                yield LLMResponse(
                    content=full_content,
                    tool_calls=tool_calls_list,
                    model=self.config.model,
                    finish_reason=chunk.choices[0].finish_reason or "stop",
                )
