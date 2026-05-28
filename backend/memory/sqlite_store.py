"""
SQLite 记忆存储 — 消息历史、会话管理、键值记忆

表结构:
  - sessions:      会话
  - messages:      消息历史
  - token_usage:   Token 使用统计
  - kv_memories:   键值记忆（Agent 主动存储）
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.memory.base import BaseMemory, MemoryItem


class SQLiteStore(BaseMemory):
    """
    SQLite 持久化记忆

    用法:
        store = SQLiteStore("data/memory.db")
        await store.add_message("agent1", "user", "你好")
        history = await store.get_history("agent1")
    """

    def __init__(self, db_path: str | Path = "agentforge.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ---- 数据库初始化 ----

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id          TEXT PRIMARY KEY,
                    agent_id    TEXT NOT NULL,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id          TEXT PRIMARY KEY,
                    session_id  TEXT NOT NULL,
                    agent_id    TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    content     TEXT,
                    tool_calls  TEXT,
                    metadata    TEXT DEFAULT '{}',
                    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_messages_agent
                    ON messages(agent_id, created_at);

                CREATE TABLE IF NOT EXISTS token_usage (
                    id              TEXT PRIMARY KEY,
                    session_id      TEXT NOT NULL,
                    agent_id        TEXT NOT NULL,
                    prompt_tokens   INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens    INTEGER DEFAULT 0,
                    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS kv_memories (
                    id          TEXT PRIMARY KEY,
                    agent_id    TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    value       TEXT NOT NULL,
                    metadata    TEXT DEFAULT '{}',
                    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(agent_id, key)
                );

                CREATE INDEX IF NOT EXISTS idx_kv_agent
                    ON kv_memories(agent_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure_session(self, conn: sqlite3.Connection, agent_id: str,
                        session_id: str | None = None) -> str:
        """确保会话存在，返回 session_id"""
        if session_id:
            cur = conn.execute(
                "SELECT id FROM sessions WHERE id = ?", (session_id,)
            )
            if cur.fetchone():
                conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (self._now(), session_id),
                )
                return session_id

        sid = session_id or f"session_{uuid.uuid4().hex[:12]}"
        now = self._now()
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, agent_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (sid, agent_id, now, now),
        )
        conn.commit()
        return sid

    # ---- 接口实现 ----

    async def add_message(
        self,
        agent_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> str:
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = self._now()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        conn = self._get_conn()
        try:
            sid = self._ensure_session(conn, agent_id, session_id)
            conn.execute(
                """INSERT INTO messages (id, session_id, agent_id, role, content, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (msg_id, sid, agent_id, role, content, meta_json, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, sid),
            )
            conn.commit()
        finally:
            conn.close()

        return msg_id

    async def recall(
        self,
        query: str,
        agent_id: str | None = None,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """
        SQLite 层的 recall：简单的全文关键词匹配
        向量检索见 VectorStore
        """
        conn = self._get_conn()
        try:
            # 简单关键词匹配
            keywords = query.strip().split()[:10]
            if not keywords:
                return []

            conditions = []
            params: list[Any] = []
            for kw in keywords:
                if len(kw) < 2:
                    continue
                conditions.append("content LIKE ?")
                params.append(f"%{kw}%")

            if not conditions:
                return []

            where = " OR ".join(conditions)
            sql = f"SELECT * FROM messages WHERE {where}"
            if agent_id:
                sql += " AND agent_id = ?"
                params.append(agent_id)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(top_k * 2)  # 多取一些用于评分

            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()

        results = []
        for row in rows:
            content = row["content"] or ""
            score = self._simple_score(query, content)
            results.append(MemoryItem(
                id=row["id"],
                agent_id=row["agent_id"],
                content=content,
                role=row["role"],
                metadata=json.loads(row["metadata"] or "{}"),
                score=score,
                created_at=row["created_at"],
            ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    async def get_history(
        self,
        agent_id: str,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryItem]:
        conn = self._get_conn()
        try:
            if session_id:
                rows = conn.execute(
                    """SELECT * FROM messages
                       WHERE session_id = ?
                       ORDER BY created_at ASC LIMIT ?""",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM messages
                       WHERE agent_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (agent_id, limit),
                ).fetchall()
                rows.reverse()
        finally:
            conn.close()

        return [
            MemoryItem(
                id=row["id"],
                agent_id=row["agent_id"],
                content=row["content"] or "",
                role=row["role"],
                metadata=json.loads(row["metadata"] or "{}"),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def store_memory(
        self,
        agent_id: str,
        key: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        mid = f"kv_{uuid.uuid4().hex[:12]}"
        now = self._now()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO kv_memories
                   (id, agent_id, key, value, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (mid, agent_id, key, value, meta_json, now, now),
            )
            conn.commit()
        finally:
            conn.close()

    async def search_memories(
        self,
        agent_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM kv_memories
                   WHERE agent_id = ? AND (key LIKE ? OR value LIKE ?)
                   ORDER BY updated_at DESC LIMIT ?""",
                (agent_id, f"%{query}%", f"%{query}%", top_k),
            ).fetchall()
        finally:
            conn.close()

        return [
            MemoryItem(
                id=row["id"],
                agent_id=row["agent_id"],
                content=f"{row['key']}: {row['value']}",
                metadata=json.loads(row["metadata"] or "{}"),
                created_at=row["created_at"],
                score=1.0,
            )
            for row in rows
        ]

    # ---- 辅助 ----

    @staticmethod
    def _simple_score(query: str, content: str) -> float:
        """简单的关键词匹配得分"""
        q_words = set(query.lower().split())
        c_words = set(content.lower().split())
        if not q_words:
            return 0.0
        common = q_words & c_words
        return len(common) / len(q_words)

    # ---- 额外工具方法 ----

    def record_token_usage(
        self,
        agent_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        session_id: str | None = None,
    ) -> str:
        """记录 Token 使用（非 async，用于 Agent 同步调用）"""
        tid = f"tok_{uuid.uuid4().hex[:12]}"
        conn = self._get_conn()
        try:
            sid = session_id or self._ensure_session(conn, agent_id)
            total = prompt_tokens + completion_tokens
            conn.execute(
                """INSERT INTO token_usage
                   (id, session_id, agent_id, prompt_tokens, completion_tokens, total_tokens)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tid, sid, agent_id, prompt_tokens, completion_tokens, total),
            )
            conn.commit()
        finally:
            conn.close()
        return tid

    def get_stats(self, agent_id: str) -> dict:
        """获取 Agent 的记忆统计"""
        conn = self._get_conn()
        try:
            msg_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()["cnt"]

            tok = conn.execute(
                "SELECT SUM(prompt_tokens) as p, SUM(completion_tokens) as c, SUM(total_tokens) as t "
                "FROM token_usage WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()

            kv_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM kv_memories WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()["cnt"]
        finally:
            conn.close()

        return {
            "messages": msg_count,
            "token_usage": {
                "prompt": tok["p"] or 0,
                "completion": tok["c"] or 0,
                "total": tok["t"] or 0,
            } if tok else {},
            "kv_memories": kv_count,
        }
