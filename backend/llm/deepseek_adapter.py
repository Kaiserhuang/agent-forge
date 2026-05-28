"""
DeepSeek LLM 适配器 — 通过 OpenAI 兼容协议调用 DeepSeek API

支持:
- 非流式 chat
- 流式 chat (server-sent events)
- 工具调用 (function calling)
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from backend.core.config import LLMConfig, Message, ToolCall
from backend.llm.base import BaseLLM, LLMResponse


def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """将内部 Message 转为 OpenAI API 格式"""
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
    """将内部技能定义转为 OpenAI tools 格式"""
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


def _parse_openai_response(
    choice: Any,
    usage: Any | None,
) -> LLMResponse:
    """解析 OpenAI SDK 返回的 Choice 对象"""
    msg = choice.message
    tool_calls = None
    if msg.tool_calls:
        tool_calls = []
        for tc in msg.tool_calls:
            import json
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {"raw": tc.function.arguments}
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, args=args)
            )

    usage_dict = None
    if usage:
        usage_dict = {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        }

    finish = ""
    if hasattr(choice, "finish_reason"):
        finish = choice.finish_reason or ""

    return LLMResponse(
        content=msg.content,
        tool_calls=tool_calls,
        model=getattr(msg, "model", ""),
        usage=usage_dict,
        finish_reason=finish,
    )


class DeepSeekAdapter(BaseLLM):
    """通过 OpenAI 兼容接口调用 DeepSeek"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        api_key = config.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = config.base_url or "https://api.deepseek.com/v1"

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
        return _parse_openai_response(choice, response.usage)

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
        final_usage = None

        async for chunk in stream:
            if chunk.usage:
                final_usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if delta is None:
                continue

            # 增量文本
            if delta.content:
                content_parts.append(delta.content)
                yield LLMResponse(content=delta.content)

            # 工具调用增量
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

            # 流结束 — 组装最终结果
            if chunk.choices[0].finish_reason:
                import json
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
                            ToolCall(
                                id=d["id"] or f"call_{idx}",
                                name=d["name"],
                                args=parsed_args,
                            )
                        )

                yield LLMResponse(
                    content=full_content,
                    tool_calls=tool_calls_list,
                    model=self.config.model,
                    usage=final_usage,
                    finish_reason=chunk.choices[0].finish_reason or "stop",
                )
