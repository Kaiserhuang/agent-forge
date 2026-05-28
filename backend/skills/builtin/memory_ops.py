"""
MemoryOps 技能 — Agent 主动读写记忆

包含:
- remember: 存储一条键值记忆（"记住用户的喜好"）
- recall: 搜索已存储的记忆（"我上次的调研结果是什么"）
"""

from __future__ import annotations

from typing import Any

from backend.core.context import RunContext
from backend.skills.base import BaseSkill


class RememberSkill(BaseSkill):
    """记忆存储技能 — Agent 主动记住信息"""

    name = "remember"
    description = "记住一条信息。当用户告诉你他们的偏好、重要事实、或需要长期保留的信息时使用。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "记忆的键名，如 'user_preference', 'research_topic', 'important_fact'",
                },
                "value": {
                    "type": "string",
                    "description": "要记住的内容",
                },
            },
            "required": ["key", "value"],
        }

    async def execute(self, args: dict[str, Any], ctx: RunContext) -> str:
        key = args.get("key", "")
        value = args.get("value", "")

        if not key or not value:
            return "错误：key 和 value 不能为空"

        memory = ctx.get("_memory")
        if memory is None:
            return "错误：记忆系统未启用"

        await memory.store_memory(
            agent_id=ctx.agent_id,
            key=key,
            value=value,
        )
        return f"✓ 已记住「{key}」: {value[:100]}{'...' if len(value) > 100 else ''}"


class RecallMemorySkill(BaseSkill):
    """记忆检索技能 — 搜索已存储的记忆"""

    name = "recall_memory"
    description = "搜索已记住的信息。当你需要回想之前存储的信息（如用户偏好、调研结果）时使用。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，描述你想回忆什么",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量，默认 3",
                    "default": 3,
                },
            },
            "required": ["query"],
        }

    async def execute(self, args: dict[str, Any], ctx: RunContext) -> str:
        query = args.get("query", "")
        top_k = min(int(args.get("top_k", 3)), 20)

        if not query.strip():
            return "错误：搜索关键词不能为空"

        memory = ctx.get("_memory")
        if memory is None:
            return "错误：记忆系统未启用"

        results = await memory.search_memories(
            agent_id=ctx.agent_id,
            query=query,
            top_k=top_k,
        )

        if not results:
            return f"未找到与「{query}」相关的记忆。"

        lines = [f"## 记忆搜索结果: 「{query}」\n"]
        for i, item in enumerate(results, 1):
            lines.append(f"{i}. {item.content}")
            if item.score:
                lines.append(f"   相关度: {item.score:.2f}")
        lines.append("")

        return "\n".join(lines)
