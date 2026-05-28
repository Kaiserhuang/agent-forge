"""
技能注册中心 — 管理所有可用技能的注册、查找、动态加载
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any

from backend.skills.base import BaseSkill


class SkillRegistry:
    """技能注册中心"""

    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}

    # ---- 注册 ----

    def register(self, skill: BaseSkill) -> None:
        """注册单个技能实例"""
        if not skill.name:
            raise ValueError(f"Skill must have a name: {type(skill).__name__}")
        self._skills[skill.name] = skill

    def register_many(self, *skills: BaseSkill) -> None:
        """批量注册"""
        for skill in skills:
            self.register(skill)

    # ---- 查找 ----

    def get(self, name: str) -> BaseSkill:
        """按名称获取技能"""
        if name not in self._skills:
            raise KeyError(f"技能 '{name}' 未注册。可用技能: {list(self._skills.keys())}")
        return self._skills[name]

    def get_tool_defs(self, skill_names: list[str]) -> list[dict[str, Any]]:
        """批量获取 tool definitions"""
        return [self.get(name).to_tool_def() for name in skill_names]

    def list_skills(self) -> list[dict[str, str]]:
        """列出所有注册的技能"""
        return [
            {"name": s.name, "description": s.description}
            for s in self._skills.values()
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)

    # ---- 自动发现（委托给 SkillManager） ----

    def discover(self, *paths: str | Path) -> int:
        """委托给 SkillManager 发现技能（兼容旧接口）"""
        from backend.skills.manager import SkillManager
        mgr = SkillManager(self)
        for p in paths:
            mgr.add_search_path(p)
        return mgr.discover()
