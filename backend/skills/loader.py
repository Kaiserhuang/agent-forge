"""
技能动态加载器 — 从文件系统扫描并加载技能包

技能包格式:
  .skills/<skill_name>/
    ├── skill.yaml    # 元数据
    └── impl.py       # 实现代码 (BaseSkill 子类)

搜索路径（按优先级）:
  1. 项目本地: <cwd>/.skills/
  2. 用户全局: ~/.agentforge/skills/
  3. 内置:     backend/skills/builtin/  (由 registry 直接注册)
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from backend.skills.base import BaseSkill


class SkillLoadError(Exception):
    """技能加载失败"""
    pass


def discover_skill_packages(*search_paths: str | Path) -> list[dict[str, Any]]:
    """
    扫描搜索路径，返回发现的技能包信息列表

    每个技能包信息:
    {
        "name": str,
        "dir": Path,
        "yaml_path": Path,
        "impl_path": Path,
        "metadata": dict,    # skill.yaml 内容
    }
    """
    discovered: list[dict[str, Any]] = []

    for search_path in search_paths:
        base = Path(search_path)
        if not base.is_dir():
            continue

        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith(".") or entry.name.startswith("_"):
                continue

            yaml_path = entry / "skill.yaml"
            impl_path = entry / "impl.py"

            if not yaml_path.exists() or not impl_path.exists():
                continue

            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    metadata = yaml.safe_load(f)
                if not isinstance(metadata, dict):
                    raise SkillLoadError("skill.yaml 格式错误")
                if "name" not in metadata:
                    raise SkillLoadError("skill.yaml 缺少 name 字段")
            except Exception as e:
                print(f"[技能加载] 跳过 {entry.name}: {e}")
                continue

            discovered.append({
                "name": metadata["name"],
                "dir": entry,
                "yaml_path": yaml_path,
                "impl_path": impl_path,
                "metadata": metadata,
            })

    return discovered


def load_skill_package(pkg: dict[str, Any]) -> BaseSkill:
    """
    从技能包信息加载并实例化一个技能

    Args:
        pkg: discover_skill_packages() 返回的单个技能包信息

    Returns:
        BaseSkill 实例

    Raises:
        SkillLoadError: 加载失败
    """
    name = pkg["name"]
    impl_path = pkg["impl_path"]
    metadata = pkg["metadata"]

    try:
        # 动态导入 impl.py
        module_name = f"_dynamic_skill_{name}"
        spec = importlib.util.spec_from_file_location(module_name, impl_path)
        if spec is None or spec.loader is None:
            raise SkillLoadError(f"无法加载模块: {impl_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # 查找 BaseSkill 子类
        skill_class = None
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, BaseSkill) and cls is not BaseSkill:
                skill_class = cls
                break

        if skill_class is None:
            raise SkillLoadError(f"impl.py 中未找到 BaseSkill 子类")

        # 实例化
        skill_instance = skill_class()

        # 用 yaml 元数据覆盖属性（如果 yaml 中有）
        if "description" in metadata:
            skill_instance.description = metadata["description"]
        if "parameters" in metadata:
            # 如果子类没有覆盖 parameters property，用 yaml 的
            pass  # parameters 通常由子类的 @property 提供

        return skill_instance

    except SkillLoadError:
        raise
    except Exception as e:
        raise SkillLoadError(f"技能 '{name}' 加载失败: {e}") from e


def create_skill_package(
    skill_dir: str | Path,
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    impl_code: str | None = None,
) -> Path:
    """
    创建新的技能包（skill.yaml + impl.py 骨架）

    Args:
        skill_dir: 技能包存放目录（如 .skills/）
        name: 技能名
        description: 技能描述
        parameters: JSON Schema 参数描述
        impl_code: 可选的实现代码，默认生成骨架

    Returns:
        创建的技能包目录路径
    """
    base = Path(skill_dir)
    pkg_dir = base / name
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # skill.yaml
    yaml_content = {
        "name": name,
        "description": description,
        "parameters": parameters or {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "输入文本",
                },
            },
            "required": ["input"],
        },
        "run_as": "inline",
    }

    with open(pkg_dir / "skill.yaml", "w", encoding="utf-8") as f:
        yaml.dump(yaml_content, f, allow_unicode=True, sort_keys=False)

    # impl.py
    if impl_code is None:
        class_name = "".join(part.capitalize() for part in name.split("_")) + "Skill"
        impl_code = f'''"""
{name} — {description}
"""

from typing import Any
from backend.skills.base import BaseSkill
from backend.core.context import RunContext


class {class_name}(BaseSkill):
    """{description}"""

    name = "{name}"
    description = "{description}"

    @property
    def parameters(self) -> dict[str, Any]:
        return {{
            "type": "object",
            "properties": {{
                "input": {{
                    "type": "string",
                    "description": "输入文本",
                }},
            }},
            "required": ["input"],
        }}

    async def execute(self, args: dict[str, Any], ctx: RunContext) -> str:
        text = args.get("input", "")
        return f"技能「{name}」执行结果: {{text}}"
'''

    with open(pkg_dir / "impl.py", "w", encoding="utf-8") as f:
        f.write(impl_code)

    return pkg_dir
