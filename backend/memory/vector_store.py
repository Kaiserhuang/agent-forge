"""
向量记忆存储 — 基于 LanceDB

用于语义相似度检索，存储对话嵌入。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lancedb

from backend.memory.base import MemoryItem
from backend.memory.embeddings import BaseEmbedding, SimpleEmbedding


class VectorStore:
    """
    LanceDB 向量存储

    用法:
        store = VectorStore("data/vectors", embedding=SimpleEmbedding())
        await store.upsert("msg1", "你好", {"agent_id": "a1"})
        results = await store.search("你好吗", top_k=5)
    """

    def __init__(
        self,
        db_path: str | Path = "data/vectors",
        embedding: BaseEmbedding | None = None,
        table_name: str = "agent_memories",
    ):
        self._db_path = str(db_path)
        self._embedding = embedding or SimpleEmbedding(dim=128)
        self._table_name = table_name

        # 连接 LanceDB
        self._db = lancedb.connect(self._db_path)
        self._ensure_table()

    def _ensure_table(self) -> None:
        """确保表存在"""
        try:
            self._table = self._db.open_table(self._table_name)
        except Exception:
            import pyarrow as pa
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self._embedding.dim)),
                pa.field("text", pa.string()),
                pa.field("agent_id", pa.string()),
                pa.field("role", pa.string()),
                pa.field("metadata", pa.string()),
                pa.field("timestamp", pa.string()),
            ])
            self._table = self._db.create_table(self._table_name, schema=schema)

    # ---- 写入 ----

    async def upsert(
        self,
        id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """插入或更新一条向量记忆"""
        if not text.strip():
            return

        embedding = await self._embedding.embed(text)
        meta = metadata or {}
        now = datetime.now(timezone.utc).isoformat()

        import pyarrow as pa
        vector_array = pa.FixedSizeListArray.from_arrays(
            pa.array(embedding, type=pa.float32()),
            list_size=self._embedding.dim,
        )
        data = pa.table({
            "id": pa.array([id]),
            "vector": vector_array,
            "text": pa.array([text]),
            "agent_id": pa.array([meta.get("agent_id", "")]),
            "role": pa.array([meta.get("role", "")]),
            "metadata": pa.array([str(meta)]),
            "timestamp": pa.array([now]),
        })

        # 使用 add + merge_insert（先删后加，模拟 upsert）
        try:
            self._table.delete(f"id = '{id}'")
        except Exception:
            pass  # 表空时 delete 可能失败
        self._table.add(data)

    async def upsert_many(
        self,
        items: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        """批量插入"""
        if not items:
            return

        texts = [item[1] for item in items]
        embeddings = await self._embedding.embed_many(texts)
        now = datetime.now(timezone.utc).isoformat()

        import pyarrow as pa
        ids = [item[0] for item in items]
        texts_list = [item[1] for item in items]
        metas = [item[2] for item in items]

        # 构建 FixedSizeListArray 作为 vector 列
        flat_vectors = []
        for vec in embeddings:
            flat_vectors.extend(vec)
        vector_array = pa.FixedSizeListArray.from_arrays(
            pa.array(flat_vectors, type=pa.float32()),
            list_size=self._embedding.dim,
        )

        data = pa.table({
            "id": pa.array(ids),
            "vector": vector_array,
            "text": pa.array(texts_list),
            "agent_id": pa.array([m.get("agent_id", "") for m in metas]),
            "role": pa.array([m.get("role", "") for m in metas]),
            "metadata": pa.array([str(m) for m in metas]),
            "timestamp": pa.array([now] * len(items)),
        })

        # 先删除已存在的 id，再批量添加
        for item_id in ids:
            try:
                self._table.delete(f"id = '{item_id}'")
            except Exception:
                pass
        self._table.add(data)

    # ---- 检索 ----

    async def search(
        self,
        query: str,
        agent_id: str | None = None,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """语义检索相似记忆"""
        if not query.strip():
            return []

        query_vec = await self._embedding.embed(query)

        # LanceDB 向量搜索
        search_query = self._table.search(query_vec).limit(top_k * 2)

        if agent_id:
            search_query = search_query.where(f"agent_id = '{agent_id}'")

        try:
            results = search_query.to_list()
        except Exception as e:
            # 空表或搜索错误
            return []

        items = []
        for r in results:
            import json
            meta = {}
            try:
                meta = json.loads(r.get("metadata", "{}"))
            except (json.JSONDecodeError, TypeError):
                pass

            items.append(MemoryItem(
                id=r.get("id", ""),
                agent_id=r.get("agent_id", ""),
                content=r.get("text", ""),
                role=r.get("role", ""),
                metadata=meta,
                score=float(r.get("_distance", 0)),
                created_at=r.get("timestamp", ""),
            ))

        # 按距离排序（LanceDB 默认按距离升序，越小越相似）
        items.sort(key=lambda x: x.score)
        return items[:top_k]

    # ---- 统计 ----

    def count(self) -> int:
        """向量库中的记录数"""
        try:
            return self._table.count_rows()
        except Exception:
            return 0
