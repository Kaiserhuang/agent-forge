"""
技能管理 REST API 路由
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/skills", tags=["skills"])

# 由 app.py 注入
ws_handler: Any = None


def init_skill_routes(handler: Any) -> None:
    global ws_handler
    ws_handler = handler


@router.get("/")
async def list_skills() -> dict:
    """列出所有技能"""
    if ws_handler is None or ws_handler._agent is None:
        return {"skills": []}
    skills = ws_handler._agent.registry.list_skills()
    return {"skills": skills}


@router.get("/user")
async def list_user_skills() -> dict:
    """列出用户自定义技能"""
    if ws_handler is None or ws_handler._agent is None:
        return {"skills": []}
    from backend.skills.manager import SkillManager
    mgr = SkillManager(ws_handler._agent.registry)
    user_skills = mgr.list_user_skills()
    return {"skills": user_skills}


@router.get("/{name}/code")
async def get_skill_code(name: str) -> dict:
    """获取技能源码"""
    if ws_handler is None or ws_handler._agent is None:
        return {"error": "Agent 未初始化"}
    from backend.skills.manager import SkillManager
    mgr = SkillManager(ws_handler._agent.registry)
    code = mgr.get_skill_code(name)
    yaml_content = mgr.get_skill_yaml(name)
    return {"name": name, "code": code or "", "yaml": yaml_content or ""}


@router.post("/{name}/code")
async def save_skill_code(name: str, data: dict) -> dict:
    """保存技能源码并重载"""
    if ws_handler is None or ws_handler._agent is None:
        return {"error": "Agent 未初始化"}
    from backend.skills.manager import SkillManager
    mgr = SkillManager(ws_handler._agent.registry)
    code = data.get("code", "")
    ok = mgr.save_skill_code(name, code)
    if ok:
        skill = mgr.reload(name)
        return {"status": "ok", "reloaded": skill is not None}
    return {"status": "error", "error": "保存失败"}


@router.post("/create")
async def create_skill(data: dict) -> dict:
    """创建新技能"""
    if ws_handler is None or ws_handler._agent is None:
        return {"error": "Agent 未初始化"}
    from backend.skills.manager import SkillManager
    mgr = SkillManager(ws_handler._agent.registry)
    try:
        path = mgr.create(
            name=data.get("name", ""),
            description=data.get("description", ""),
            parameters=data.get("parameters"),
            impl_code=data.get("code"),
        )
        return {"status": "ok", "path": path}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.delete("/{name}")
async def delete_skill(name: str) -> dict:
    """删除用户技能"""
    if ws_handler is None or ws_handler._agent is None:
        return {"error": "Agent 未初始化"}
    from backend.skills.manager import SkillManager
    mgr = SkillManager(ws_handler._agent.registry)
    ok = mgr.delete(name)
    return {"status": "ok" if ok else "error"}
