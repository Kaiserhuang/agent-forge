"""
消息序列化 — 内部模型 ↔ WebSocket/API JSON
"""

from __future__ import annotations

from typing import Any

from backend.core.agent import AgentResult, StepLog
from backend.skills.registry import SkillRegistry


def serialize_agent_result(result: AgentResult) -> dict[str, Any]:
    """AgentResult → WS 消息 payload"""
    return {
        "agent_id": result.agent_id,
        "output": result.output,
        "iterations": result.iterations,
        "total_tokens": result.total_tokens,
        "token_usage": result.token_usage,
        "steps": [serialize_step(s) for s in result.steps],
        "elapsed_seconds": round(result.elapsed_seconds, 2),
        "success": result.success,
        "error": result.error,
    }


def serialize_step(step: StepLog) -> dict[str, Any]:
    """StepLog → dict"""
    return {
        "iteration": step.iteration,
        "response": {
            "content": step.response.content if step.response else None,
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "args": tc.args}
                for tc in (step.response.tool_calls or [])
            ] if step.response else None,
        } if step.response else None,
        "skill_results": step.skill_results,
        "timestamp": step.timestamp,
    }


def serialize_skill_list(registry: SkillRegistry) -> list[dict[str, str]]:
    return registry.list_skills()
