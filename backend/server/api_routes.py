"""
REST API 路由 — 提供 Agent 运行的 HTTP 接口
Phase 1 提供基本的运行和状态查询接口
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["api"])

# 全局 WS handler 引用，由 app.py 注入
ws_handler: Any = None


def init_routes(handler: Any) -> None:
    """注入 WS handler 引用"""
    global ws_handler
    ws_handler = handler


@router.post("/run")
async def api_run_agent(payload: dict[str, Any]) -> dict[str, Any]:
    """通过 REST API 运行 Agent"""
    if ws_handler is None or ws_handler._agent is None:
        return {"error": "Agent 未初始化"}

    task = payload.get("task", "")
    if not task:
        return {"error": "task 字段不能为空"}

    from backend.server.serializers import serialize_agent_result
    try:
        result = await ws_handler._agent.run(task)
        return {"status": "ok", "result": serialize_agent_result(result)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/skills")
async def api_list_skills() -> dict[str, Any]:
    """列出注册的技能"""
    if ws_handler is None or ws_handler._agent is None:
        return {"skills": []}
    return {"skills": ws_handler._agent.registry.list_skills()}


@router.get("/status")
async def api_status() -> dict[str, str]:
    """服务状态"""
    return {
        "status": "running",
        "agent": ws_handler._agent.config.agent_id if ws_handler and ws_handler._agent else "未初始化",
    }


@router.post("/update-key")
async def api_update_key(payload: dict[str, Any]) -> dict[str, str]:
    """更新 LLM API Key（运行时热更新）"""
    if ws_handler is None or ws_handler._agent is None:
        return {"status": "error", "message": "Agent 未初始化"}

    api_key = payload.get("api_key", "")
    model = payload.get("model", "")

    if api_key:
        import os
        os.environ["DEEPSEEK_API_KEY"] = api_key
        # 更新 Agent 的 LLM 配置
        ws_handler._agent.config.llm.api_key = api_key
        # 重建 LLM 适配器
        from backend.llm.deepseek_adapter import DeepSeekAdapter
        ws_handler._agent.llm = DeepSeekAdapter(ws_handler._agent.config.llm)
        # 也更新记忆中的配置
        if ws_handler._agent.memory:
            await ws_handler._agent.memory.store_memory(
                "_system", "llm_api_key", "configured"
            )

    if model:
        ws_handler._agent.config.llm.model = model

    return {"status": "ok", "message": f"API Key 已更新, model={model or 'unchanged'}"}
