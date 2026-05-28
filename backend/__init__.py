"""
AgentForge — 通用 LLM Agent 框架

提供 Agent 运行时、技能系统、LLM 适配、编排引擎。
"""

from backend.core.agent import Agent, AgentResult
from backend.core.config import AgentConfig, LLMConfig, Message, ToolCall
from backend.llm.base import BaseLLM
from backend.llm.deepseek_adapter import DeepSeekAdapter
from backend.skills.base import BaseSkill
from backend.skills.registry import SkillRegistry
from backend.orchestrator import (
    FlowDefinition, FlowNode, FlowEdge, NodeType, Condition,
    OutputMode, CommunicationMode,
    Blackboard,
    FlowEngine, FlowResult,
    Flow,
    FlowParser,
)

__all__ = [
    "Agent", "AgentResult",
    "AgentConfig", "LLMConfig", "Message", "ToolCall",
    "BaseLLM", "DeepSeekAdapter",
    "BaseSkill", "SkillRegistry",
    "FlowDefinition", "FlowNode", "FlowEdge", "NodeType", "Condition",
    "OutputMode", "CommunicationMode",
    "Blackboard",
    "FlowEngine", "FlowResult",
    "Flow",
    "FlowParser",
]
