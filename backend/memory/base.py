"""
记忆系统抽象基类
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryItem:
    """一条记忆记录"""
    id: str
    agent_id: str
    content: str
    role: str = ""                     # user / assistant / tool / system
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0                 # 检索相似度分数
    created_at: str = ""


class BaseMemory(ABC):
    """记忆系统抽象接口"""

    @abstractmethod
    async def add_message(
        self,
        agent_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> str:
        """记录一条消息，返回消息 ID"""
        ...

    @abstractmethod
    async def recall(
        self,
        query: str,
        agent_id: str | None = None,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """语义检索相关记忆"""
        ...

    @abstractmethod
    async def get_history(
        self,
        agent_id: str,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryItem]:
        """获取最近的对话历史"""
        ...

    @abstractmethod
    async def store_memory(
        self,
        agent_id: str,
        key: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """存储一个键值记忆（Agent 可主动记忆）"""
        ...

    @abstractmethod
    async def search_memories(
        self,
        agent_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """搜索已存储的键值记忆"""
        ...
