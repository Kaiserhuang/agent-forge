"""
greeting — 问候技能
"""

from typing import Any
from backend.skills.base import BaseSkill
from backend.core.context import RunContext


class GreetingSkill(BaseSkill):
    """问候技能"""

    name = "greeting"
    description = "根据名字生成个性化问候语"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "要问候的名字",
                },
                "language": {
                    "type": "string",
                    "enum": ["zh", "en"],
                    "description": "语言",
                    "default": "zh",
                },
            },
            "required": ["name"],
        }

    async def execute(self, args: dict[str, Any], ctx: RunContext) -> str:
        name = args.get("name", "世界")
        lang = args.get("language", "zh")

        if lang == "en":
            return f"Hello, {name}! Welcome to AgentForge."
        else:
            return f"你好，{name}！欢迎使用 AgentForge。"
