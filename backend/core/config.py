"""
核心配置数据模型 — AgentConfig, LLMConfig, Message, ToolCall
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """LLM 返回的工具调用指令"""
    id: str
    name: str
    args: dict[str, Any]


class Message(BaseModel):
    """对话消息"""
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str | None = None,
                  tool_calls: list[ToolCall] | None = None) -> "Message":
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, content: str, tool_call_id: str, name: str | None = None) -> "Message":
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)


class LLMConfig(BaseModel):
    """LLM 连接配置"""
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str | None = None
    base_url: str | None = "https://api.deepseek.com/v1"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_sec: int = 120


class AgentConfig(BaseModel):
    """Agent 定义"""
    agent_id: str = "default"
    name: str = "Default Agent"
    system_prompt: str = "你是一个有用的 AI 助手。"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    skills: list[str] = Field(default_factory=list)
    memory_enabled: bool = False
    max_iterations: int = 15
    verbose: bool = True
