"""
SkillManager — 技能管理器

功能:
1. 扫描文件系统发现技能包
2. 动态加载/卸载/重载技能
3. 文件变更监控（热重载，Phase 5 基础版手动重载）
4. 技能 CRUD（创建/编辑/删除）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.skills.base import BaseSkill
from backend.skills.builtin import (
    FileOpsSkill, WebSearchSkill,
    RememberSkill, RecallMemorySkill,
)
from backend.skills.loader import (
    create_skill_package,
    discover_skill_packages,
    load_skill_package,
)
from backend.skills.registry import SkillRegistry


class SkillManager:
    """
    技能管理器

    用法:
        mgr = SkillManager(registry)
        mgr.discover()
        mgr.reload("web_search")
        mgr.create("my_skill", "描述", ...)
    """

    def __init__(self, registry: SkillRegistry):
        self._registry = registry
        self._loaded_packages: dict[str, dict[str, Any]] = {}
        self._search_paths: list[Path] = []

    def add_search_path(self, path: str | Path) -> None:
        """添加技能扫描路径"""
        p = Path(path)
        if p.exists() and p.is_dir() and p not in self._search_paths:
            self._search_paths.append(p)

    def discover(self) -> int:
        """
        扫描所有搜索路径，加载新发现的技能

        Returns:
            新加载的技能数量
        """
        # 按优先级反向（高优先级 later，覆盖前面的同名技能）
        search_dirs = list(self._search_paths)

        # 默认搜索路径
        cwd_skills = Path.cwd() / ".skills"
        if cwd_skills.exists():
            search_dirs.insert(0, cwd_skills)

        home_skills = Path.home() / ".agentforge" / "skills"
        if home_skills.exists():
            search_dirs.insert(0, home_skills)

        # 发现
        all_packages = []
        for search_dir in search_dirs:
            packages = discover_skill_packages(search_dir)
            all_packages.extend(packages)

        # 加载
        count = 0
        for pkg in all_packages:
            try:
                skill = load_skill_package(pkg)
                self._registry.register(skill)
                self._loaded_packages[skill.name] = pkg
                count += 1
            except Exception as e:
                print(f"[SkillManager] 加载 '{pkg['name']}' 失败: {e}")

        return count

    def reload(self, skill_name: str) -> BaseSkill | None:
        """
        重新加载单个技能

        1. 从 registry 中移除旧实例
        2. 重新扫描加载
        3. 注册新实例
        """
        # 先移除
        self._registry._skills.pop(skill_name, None)

        # 查找包信息
        pkg = self._loaded_packages.get(skill_name)
        if not pkg:
            # 重新发现
            self.discover()
            try:
                return self._registry.get(skill_name)
            except KeyError:
                return None

        # 重新加载
        try:
            skill = load_skill_package(pkg)
            self._registry.register(skill)
            return skill
        except Exception as e:
            print(f"[SkillManager] 重载 '{skill_name}' 失败: {e}")
            return None

    def reload_all(self) -> int:
        """重新加载所有文件系统技能"""
        self._loaded_packages.clear()
        return self.discover()

    def create(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        impl_code: str | None = None,
        target_dir: str | Path | None = None,
    ) -> str:
        """
        创建新技能

        Args:
            name: 技能名（也是目录名）
            description: 描述
            parameters: JSON Schema
            impl_code: Python 实现代码
            target_dir: 存放目录，默认 ~/.agentforge/skills/

        Returns:
            技能包目录路径
        """
        if target_dir is None:
            target_dir = Path.home() / ".agentforge" / "skills"
            target_dir.mkdir(parents=True, exist_ok=True)

        path = create_skill_package(
            skill_dir=target_dir,
            name=name,
            description=description,
            parameters=parameters,
            impl_code=impl_code,
        )

        # 自动加载
        self.add_search_path(target_dir)
        self.discover()

        return str(path)

    def delete(self, skill_name: str) -> bool:
        """删除一个用户自定义技能（从文件和 registry）"""
        # 从 registry 移除
        self._registry._skills.pop(skill_name, None)

        # 从加载列表移除
        pkg = self._loaded_packages.pop(skill_name, None)
        if pkg and pkg["dir"].exists():
            import shutil
            shutil.rmtree(pkg["dir"])
            return True

        # 尝试从搜索路径删除
        for search_path in self._search_paths:
            target = search_path / skill_name
            if target.exists():
                import shutil
                shutil.rmtree(target)
                return True

        return False

    def get_package_info(self, skill_name: str) -> dict[str, Any] | None:
        """获取技能包信息"""
        return self._loaded_packages.get(skill_name)

    def get_skill_code(self, skill_name: str) -> str | None:
        """获取技能源码"""
        pkg = self._loaded_packages.get(skill_name)
        if pkg:
            try:
                return pkg["impl_path"].read_text(encoding="utf-8")
            except Exception:
                pass
        return None

    def get_skill_yaml(self, skill_name: str) -> str | None:
        """获取技能 YAML 元数据"""
        pkg = self._loaded_packages.get(skill_name)
        if pkg:
            try:
                return pkg["yaml_path"].read_text(encoding="utf-8")
            except Exception:
                pass
        return None

    def save_skill_code(self, skill_name: str, code: str) -> bool:
        """保存技能源码"""
        pkg = self._loaded_packages.get(skill_name)
        if pkg:
            try:
                pkg["impl_path"].write_text(code, encoding="utf-8")
                return True
            except Exception:
                pass
        return False

    def list_user_skills(self) -> list[dict[str, Any]]:
        """列出用户自定义技能"""
        return [
            {
                "name": name,
                "description": self._registry.get(name).description,
                "type": "user",
            }
            for name in self._loaded_packages
            if name in self._registry
        ]
