"""
WebSocket 消息处理器 — 处理 GUI 发来的命令并推送状态更新
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket

from backend.core.agent import Agent

# 消息类型 (type field)
MSG_RUN_FLOW = "run_flow"
MSG_STOP_FLOW = "stop_flow"
MSG_AGENT_STATUS = "agent_status"
MSG_AGENT_MESSAGE = "agent_message"
MSG_FLOW_COMPLETE = "flow_complete"
MSG_FLOW_ERROR = "flow_error"
MSG_LIST_SKILLS = "list_skills"
MSG_UPDATE_CONFIG = "update_config"
# 技能管理
MSG_SKILL_LIST_USER = "skill_list_user"
MSG_SKILL_GET_CODE = "skill_get_code"
MSG_SKILL_SAVE_CODE = "skill_save_code"
MSG_SKILL_CREATE = "skill_create"
MSG_SKILL_DELETE = "skill_delete"
MSG_SKILL_RELOAD = "skill_reload"


class WebSocketHandler:
    """管理 WebSocket 连接和消息路由"""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()
        self._agent: Agent | None = None

    def set_agent(self, agent: Agent) -> None:
        """挂载 Agent 实例"""
        self._agent = agent

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active_connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active_connections.discard(ws)

    async def handle_message(self, ws: WebSocket, raw: str) -> None:
        """路由收到的 WS 消息"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self._send(ws, {"type": "error", "payload": {"message": "无效的 JSON"}})
            return

        msg_type = data.get("type", "")
        payload = data.get("payload", {})

        if msg_type == MSG_LIST_SKILLS:
            await self._handle_list_skills(ws)

        elif msg_type == MSG_RUN_FLOW:
            await self._handle_run_flow(ws, payload)

        elif msg_type == MSG_UPDATE_CONFIG:
            await self._handle_update_config(ws, payload)

        # 技能管理
        elif msg_type == MSG_SKILL_LIST_USER:
            await self._handle_skill_list_user(ws)
        elif msg_type == MSG_SKILL_GET_CODE:
            await self._handle_skill_get_code(ws, payload)
        elif msg_type == MSG_SKILL_SAVE_CODE:
            await self._handle_skill_save_code(ws, payload)
        elif msg_type == MSG_SKILL_CREATE:
            await self._handle_skill_create(ws, payload)
        elif msg_type == MSG_SKILL_DELETE:
            await self._handle_skill_delete(ws, payload)
        elif msg_type == MSG_SKILL_RELOAD:
            await self._handle_skill_reload(ws, payload)

        else:
            await self._send(ws, {
                "type": "error",
                "payload": {"message": f"未知消息类型: {msg_type}"},
            })

    # ---- 消息处理 ----

    async def _handle_list_skills(self, ws: WebSocket) -> None:
        """返回技能列表"""
        if not self._agent:
            await self._send(ws, {"type": "error", "payload": {"message": "Agent 未初始化"}})
            return
        skills = self._agent.registry.list_skills()
        await self._send(ws, {"type": MSG_LIST_SKILLS, "payload": {"skills": skills}})

    async def _handle_run_flow(self, ws: WebSocket, payload: dict) -> None:
        """运行 Agent 任务"""
        if not self._agent:
            await self._send(ws, {"type": "error", "payload": {"message": "Agent 未初始化"}})
            return

        task = payload.get("task", "")

        # 发送状态更新
        await self.broadcast({
            "type": MSG_AGENT_STATUS,
            "payload": {"agent_id": self._agent.config.agent_id, "status": "running"},
        })

        try:
            from backend.server.serializers import serialize_agent_result
            result = await self._agent.run(task)

            await self.broadcast({
                "type": MSG_FLOW_COMPLETE,
                "payload": serialize_agent_result(result),
            })
        except Exception as e:
            await self.broadcast({
                "type": MSG_FLOW_ERROR,
                "payload": {"error": str(e)},
            })

    async def _handle_update_config(self, ws: WebSocket, payload: dict) -> None:
        """更新 Agent 配置"""
        await self._send(ws, {
            "type": MSG_UPDATE_CONFIG,
            "payload": {"status": "ack", "message": "配置更新功能将在 Phase 2 实现"},
        })

    # ---- 技能管理 ----

    def _get_skill_mgr(self):
        from backend.skills.manager import SkillManager
        return SkillManager(self._agent.registry) if self._agent else None

    async def _handle_skill_list_user(self, ws: WebSocket) -> None:
        mgr = self._get_skill_mgr()
        if not mgr:
            return await self._send_error(ws, "Agent 未初始化")
        skills = mgr.list_user_skills()
        await self._send(ws, {"type": MSG_SKILL_LIST_USER, "payload": {"skills": skills}})

    async def _handle_skill_get_code(self, ws: WebSocket, payload: dict) -> None:
        mgr = self._get_skill_mgr()
        if not mgr:
            return await self._send_error(ws, "Agent 未初始化")
        name = payload.get("name", "")
        code = mgr.get_skill_code(name)
        yaml_content = mgr.get_skill_yaml(name)
        await self._send(ws, {
            "type": MSG_SKILL_GET_CODE,
            "payload": {"name": name, "code": code or "", "yaml": yaml_content or ""},
        })

    async def _handle_skill_save_code(self, ws: WebSocket, payload: dict) -> None:
        mgr = self._get_skill_mgr()
        if not mgr:
            return await self._send_error(ws, "Agent 未初始化")
        name = payload.get("name", "")
        code = payload.get("code", "")
        ok = mgr.save_skill_code(name, code)
        if ok:
            skill = mgr.reload(name)
            await self._send(ws, {
                "type": MSG_SKILL_SAVE_CODE,
                "payload": {"status": "ok", "name": name, "reloaded": skill is not None},
            })
        else:
            await self._send(ws, {
                "type": MSG_SKILL_SAVE_CODE,
                "payload": {"status": "error", "error": "保存失败"},
            })

    async def _handle_skill_create(self, ws: WebSocket, payload: dict) -> None:
        mgr = self._get_skill_mgr()
        if not mgr:
            return await self._send_error(ws, "Agent 未初始化")
        try:
            path = mgr.create(
                name=payload.get("name", ""),
                description=payload.get("description", ""),
                parameters=payload.get("parameters"),
                impl_code=payload.get("code"),
            )
            await self._send(ws, {
                "type": MSG_SKILL_CREATE,
                "payload": {"status": "ok", "path": path},
            })
        except Exception as e:
            await self._send(ws, {
                "type": MSG_SKILL_CREATE,
                "payload": {"status": "error", "error": str(e)},
            })

    async def _handle_skill_delete(self, ws: WebSocket, payload: dict) -> None:
        mgr = self._get_skill_mgr()
        if not mgr:
            return await self._send_error(ws, "Agent 未初始化")
        name = payload.get("name", "")
        ok = mgr.delete(name)
        await self._send(ws, {
            "type": MSG_SKILL_DELETE,
            "payload": {"status": "ok" if ok else "error", "name": name},
        })

    async def _handle_skill_reload(self, ws: WebSocket, payload: dict) -> None:
        mgr = self._get_skill_mgr()
        if not mgr:
            return await self._send_error(ws, "Agent 未初始化")
        count = mgr.reload_all()
        await self._send(ws, {
            "type": MSG_SKILL_RELOAD,
            "payload": {"status": "ok", "count": count},
        })

    async def _send_error(self, ws: WebSocket, message: str) -> None:
        await self._send(ws, {"type": "error", "payload": {"message": message}})

    # ---- 辅助 ----

    async def _send(self, ws: WebSocket, data: dict[str, Any]) -> None:
        """发送消息到单个连接"""
        await ws.send_json(data)

    async def broadcast(self, data: dict[str, Any]) -> None:
        """广播消息到所有连接"""
        for conn in self.active_connections:
            try:
                await conn.send_json(data)
            except Exception:
                self.disconnect(conn)
