"""
Ollama LLM 适配器 — 通过 OpenAI 兼容接口调用本地 Ollama 模型

Ollama 从 0.8.0 起提供 /v1/chat/completions OpenAI 兼容端点:
    https://github.com/ollama/ollama/blob/main/docs/openai.md

用法:
    1. 安装 Ollama: https://ollama.com/
    2. ollama pull llama3.2
    3. 配置 provider="ollama", model="llama3.2", base_url="http://localhost:11434/v1"
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from backend.core.config import LLMConfig, Message, ToolCall
from backend.llm.base import BaseLLM, LLMResponse


class OllamaAdapter(BaseLLM):
    """
    Ollama 本地模型适配器

    通过 OpenAI 兼容端点调用，支持大多数开源模型:
    llama3.2, qwen2.5, mistral, codellama, phi3, gemma2 等
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        # Ollama 不需要 API key
        base_url = config.base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434/v1"
        )

        self.client = AsyncOpenAI(
            api_key="ollama",  # Ollama 忽略但需要占位
            base_url=base_url,
            timeout=config.timeout_sec,
        )

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        openai_msgs = self._to_openai_msgs(messages)
        openai_tools = self._to_openai_tools(tools)

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
                tool_calls.append(ToolCall(
                    id=tc.id, name=tc.function.name, args=args
                ))

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            model=self.config.model,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMResponse]:
        openai_msgs = self._to_openai_msgs(messages)
        openai_tools = self._to_openai_tools(tools)

        stream = await self.client.chat.completions.create(
            model=self.config.model,
            messages=openai_msgs,
            tools=openai_tools,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
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
                        tool_calls_list.append(ToolCall(
                            id=d["id"] or f"call_{idx}", name=d["name"], args=parsed_args
                        ))

                yield LLMResponse(
                    content=full_content,
                    tool_calls=tool_calls_list,
                    model=self.config.model,
                    finish_reason=chunk.choices[0].finish_reason or "stop",
                )

    # ---- 消息转换 ----

    def _to_openai_msgs(self, messages: list[Message]) -> list[dict]:
        result: list[dict] = []
        for msg in messages:
            d: dict = {"role": msg.role}
            if msg.content is not None:
                d["content"] = msg.content
            if msg.tool_calls:
                d["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name, "arguments": json.dumps(tc.args)}}
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                d["tool_call_id"] = msg.tool_call_id
            if msg.name:
                d["name"] = msg.name
            result.append(d)
        return result

    def _to_openai_tools(self, skills: list[dict] | None) -> list[dict] | None:
        if not skills:
            return None
        return [
            {"type": "function", "function": {
                "name": s["name"],
                "description": s.get("description", ""),
                "parameters": s.get("parameters", {}),
            }}
            for s in skills
        ]
