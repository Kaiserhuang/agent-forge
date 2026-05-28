"""
混合记忆管理器 — 组合 SQLite + LanceDB

策略:
- 最近 N 条历史: 从 SQLite 读取（精确、有序）
- 语义检索: 从 LanceDB 向量检索（跨会话相似内容）
- 写入: 同时写入 SQLite（结构记录）和 LanceDB（向量索引）
- Token 记录: 写入 SQLite token_usage 表
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.memory.base import BaseMemory, MemoryItem
from backend.memory.embeddings import BaseEmbedding, SimpleEmbedding
from backend.memory.sqlite_store import SQLiteStore
from backend.memory.vector_store import VectorStore


class HybridMemory(BaseMemory):
    """
    混合记忆管理器

    用法:
        memory = HybridMemory("agent1", db_path="data/agentforge.db")
        await memory.add_message("agent1", "user", "你好")
        history = await memory.get_history("agent1")
        related = await memory.recall("AI 发展", agent_id="agent1")
    """

    def __init__(
        self,
        db_path: str | Path = "data/agentforge.db",
        vector_path: str | Path | None = None,
        embedding: BaseEmbedding | None = None,
        auto_vectorize: bool = True,
    ):
        """
        Args:
            db_path: SQLite 数据库路径
            vector_path: LanceDB 向量库路径（默认在 SQLite 同目录下的 vectors/）
            embedding: 嵌入函数（默认 SimpleEmbedding）
            auto_vectorize: 是否自动将消息加入向量索引
        """
        self._sqlite = SQLiteStore(db_path)

        if vector_path is None:
            p = Path(db_path)
            vector_path = p.parent / f"{p.stem}_vectors"

        self._vector = VectorStore(
            db_path=str(vector_path),
            embedding=embedding or SimpleEmbedding(dim=128),
        )
        self._auto_vectorize = auto_vectorize

    # ---- BaseMemory 接口实现 ----

    async def add_message(
        self,
        agent_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> str:
        # 1. 写入 SQLite
        msg_id = await self._sqlite.add_message(
            agent_id=agent_id,
            role=role,
            content=content,
            metadata=metadata,
            session_id=session_id,
        )

        # 2. 自动写向量索引（仅非空内容）
        if self._auto_vectorize and content and len(content) > 20:
            meta = {
                "agent_id": agent_id,
                "role": role,
                "message_id": msg_id,
                **(metadata or {}),
            }
            await self._vector.upsert(msg_id, content, meta)

        return msg_id

    async def recall(
        self,
        query: str,
        agent_id: str | None = None,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """
        语义检索相关记忆

        策略:
        1. 先用向量检索（语义相似）
        2. 再用 SQLite 关键词匹配补充
        3. 合并去重，按分数排序
        """
        seen_ids: set[str] = set()
        results: list[MemoryItem] = []

        # 向量检索
        vector_results = await self._vector.search(
            query=query, agent_id=agent_id, top_k=top_k
        )
        for item in vector_results:
            seen_ids.add(item.id)
            results.append(item)

        # SQLite 关键词补充
        sqlite_results = await self._sqlite.recall(
            query=query, agent_id=agent_id, top_k=top_k
        )
        for item in sqlite_results:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                results.append(item)

        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    async def get_history(
        self,
        agent_id: str,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryItem]:
        return await self._sqlite.get_history(
            agent_id=agent_id,
            session_id=session_id,
            limit=limit,
        )

    async def store_memory(
        self,
        agent_id: str,
        key: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        # SQLite 存储
        await self._sqlite.store_memory(agent_id, key, value, metadata)

        # 同时加入向量索引（方便语义检索）
        if value and len(value) > 10:
            meta = {
                "agent_id": agent_id,
                "memory_key": key,
                **(metadata or {}),
            }
            mem_id = f"mem_{agent_id}_{key}"
            await self._vector.upsert(mem_id, f"{key}: {value}", meta)

    async def search_memories(
        self,
        agent_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        # 从向量库检索记忆
        results = await self._vector.search(
            query=query, agent_id=agent_id, top_k=top_k
        )
        # 过滤只返回 kv_memory 类型的（metadata 含 memory_key）
        kv_results = [
            r for r in results
            if r.metadata.get("memory_key")
        ] or await self._sqlite.search_memories(agent_id, query, top_k)
        return kv_results[:top_k]

    # ---- 额外方法 ----

    def record_token_usage(
        self,
        agent_id: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """记录 Token 使用"""
        self._sqlite.record_token_usage(agent_id, prompt_tokens, completion_tokens)

    def get_stats(self, agent_id: str) -> dict:
        """获取记忆统计"""
        stats = self._sqlite.get_stats(agent_id)
        stats["vector_count"] = self._vector.count()
        return stats

    @property
    def sqlite(self) -> SQLiteStore:
        return self._sqlite

    @property
    def vector(self) -> VectorStore:
        return self._vector
