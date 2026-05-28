"""
技能抽象基类

每个 Skill 是一个可被 LLM 调用的工具，遵循统一接口:
- name / description / parameters 用于 LLM function calling schema
- execute() 为具体实现
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.core.context import RunContext


class BaseSkill(ABC):
    """技能基类"""

    name: str = ""
    description: str = ""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema 格式的参数描述，用于 LLM function calling"""
        ...

    def to_tool_def(self) -> dict[str, Any]:
        """转为 LLM tool definition 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    @abstractmethod
    async def execute(self, args: dict[str, Any], ctx: RunContext) -> str:
        """执行技能，返回文本结果"""
        ...
