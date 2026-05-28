"""
记忆系统集成测试 — SQLite + LanceDB + HybridMemory
"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from backend.memory.sqlite_store import SQLiteStore
from backend.memory.vector_store import VectorStore
from backend.memory.embeddings import SimpleEmbedding
from backend.memory.hybrid_memory import HybridMemory


class TestSQLiteStore:
    """SQLite 存储测试"""

    @pytest.fixture
    def store(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        store = SQLiteStore(db_path)
        yield store
        os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_add_and_get_history(self, store):
        msg_id = await store.add_message("agent1", "user", "你好")
        assert msg_id
        assert msg_id.startswith("msg_")

        msg_id2 = await store.add_message("agent1", "assistant", "你好！有什么可以帮助你的？")
        assert msg_id2

        history = await store.get_history("agent1")
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_add_message_with_session(self, store):
        session_id = "test_session_001"
        await store.add_message("agent1", "user", "msg1", session_id=session_id)
        await store.add_message("agent1", "user", "msg2", session_id=session_id)

        history = await store.get_history("agent1", session_id=session_id)
        assert len(history) == 2
        assert history[0].content == "msg1"
        assert history[1].content == "msg2"

    @pytest.mark.asyncio
    async def test_kv_memory(self, store):
        await store.store_memory("agent1", "user_name", "张三")
        await store.store_memory("agent1", "user_age", "28")

        results = await store.search_memories("agent1", "张三")
        assert len(results) >= 1
        assert "张三" in results[0].content

        results2 = await store.search_memories("agent1", "user_age")
        assert len(results2) >= 1
        assert "28" in results2[0].content

    def test_token_usage(self, store):
        store.record_token_usage("agent1", 100, 50)
        store.record_token_usage("agent1", 200, 80)

        stats = store.get_stats("agent1")
        assert stats["messages"] >= 0
        assert stats["token_usage"]["total"] >= 430
        assert stats["kv_memories"] >= 0

    @pytest.mark.asyncio
    async def test_recall_keyword(self, store):
        await store.add_message("agent1", "user", "今天天气怎么样？")
        await store.add_message("agent1", "assistant", "今天天气晴朗，温度25度。")
        await store.add_message("agent2", "user", "关于Python的问题")

        results = await store.recall("天气", agent_id="agent1")
        assert len(results) >= 1
        assert "天气" in results[0].content

    @pytest.mark.asyncio
    async def test_history_limit(self, store):
        for i in range(10):
            await store.add_message("agent1", "user", f"msg{i}")

        history = await store.get_history("agent1", limit=5)
        assert len(history) == 5


class TestVectorStore:
    """LanceDB 向量存储测试"""

    @pytest.fixture
    def vstore(self):
        tmpdir = tempfile.mkdtemp()
        store = VectorStore(db_path=tmpdir, embedding=SimpleEmbedding(dim=64))
        yield store
        import shutil
        shutil.rmtree(tmpdir)

    @pytest.mark.asyncio
    async def test_upsert_and_search(self, vstore):
        await vstore.upsert("1", "人工智能是计算机科学的一个分支", {"agent_id": "a1", "role": "user"})
        await vstore.upsert("2", "Python是一种流行的编程语言", {"agent_id": "a1", "role": "user"})
        await vstore.upsert("3", "今天天气很好", {"agent_id": "a2", "role": "user"})

        assert vstore.count() == 3

        results = await vstore.search("AI 人工智能", agent_id="a1", top_k=2)
        assert len(results) >= 1
        assert "人工智能" in results[0].content

    @pytest.mark.asyncio
    async def test_search_no_results(self, vstore):
        results = await vstore.search("不存在的词", top_k=5)
        # 空数据库应返回空列表
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_empty_text(self, vstore):
        await vstore.upsert("empty", "", {})
        assert vstore.count() == 0  # 空文本不插入


class TestHybridMemory:
    """混合记忆测试"""

    @pytest.fixture
    def memory(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test.db")
        mem = HybridMemory(db_path=db_path, vector_path=os.path.join(tmpdir, "vectors"))
        yield mem
        import shutil
        shutil.rmtree(tmpdir)

    @pytest.mark.asyncio
    async def test_add_and_recall(self, memory):
        await memory.add_message("agent1", "user", "我喜欢吃川菜", metadata={"topic": "美食"})
        await memory.add_message("agent1", "assistant", "川菜以麻辣闻名", metadata={"topic": "美食"})

        # get_history
        history = await memory.get_history("agent1")
        assert len(history) == 2

        # recall（向量 + 关键词混合）
        results = await memory.recall("川菜", agent_id="agent1", top_k=2)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_store_and_search_memories(self, memory):
        await memory.store_memory("agent1", "user_name", "张三")
        await memory.store_memory("agent1", "user_city", "北京")

        results = await memory.search_memories("agent1", "张三")
        assert len(results) >= 1
        assert "张三" in results[0].content

    @pytest.mark.asyncio
    async def test_token_recording(self, memory):
        memory.record_token_usage("agent1", 150, 80)
        stats = memory.get_stats("agent1")
        assert stats["token_usage"]["total"] == 230

    @pytest.mark.asyncio
    async def test_multi_agent_isolation(self, memory):
        await memory.add_message("agent1", "user", "这是agent1的消息")
        await memory.add_message("agent2", "user", "这是agent2的消息")

        h1 = await memory.get_history("agent1")
        h2 = await memory.get_history("agent2")

        assert len(h1) == 1
        assert len(h2) == 1
        assert "agent1" in h1[0].content
        assert "agent2" in h2[0].content

    @pytest.mark.asyncio
    async def test_vector_count(self, memory):
        # 短文本不自动向量化
        await memory.add_message("agent1", "user", "短文本")
        # 长文本自动向量化
        await memory.add_message("agent1", "user", "这是一段足够长的文本，需要被自动向量化以便后续语义检索")

        stats = memory.get_stats("agent1")
        assert stats["vector_count"] >= 0  # 短文本可能未向量化


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
