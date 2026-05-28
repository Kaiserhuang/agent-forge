"""
WebSearch 技能 — 通过 DuckDuckGo 搜索互联网

无需 API Key，开箱即用。
"""

from __future__ import annotations

from typing import Any

from duckduckgo_search import DDGS

from backend.core.context import RunContext
from backend.skills.base import BaseSkill


class WebSearchSkill(BaseSkill):
    """互联网搜索技能"""

    name = "web_search"
    description = "搜索互联网并返回相关结果。当你需要回答关于最新信息、实时事件或非确定性知识的问题时使用。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词（自然语言）",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量，默认 5",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, args: dict[str, Any], ctx: RunContext) -> str:
        query = args.get("query", "")
        top_k = min(int(args.get("top_k", 5)), 20)

        if not query.strip():
            return "错误：搜索关键词不能为空。"

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=top_k))
        except Exception as e:
            return f"搜索失败: {e}"

        if not results:
            return f"未找到关于「{query}」的搜索结果。"

        lines = [f"## 「{query}」的搜索结果\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            href = r.get("href", "")
            body = r.get("body", "")
            lines.append(f"### {i}. {title}")
            lines.append(f"   链接: {href}")
            lines.append(f"   摘要: {body}\n")

        return "\n".join(lines)
