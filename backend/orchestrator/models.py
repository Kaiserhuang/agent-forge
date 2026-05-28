"""
编排数据模型 — Flow 定义、节点、边、条件
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Flow 节点类型"""
    TASK = "task"           # 执行 Agent 任务
    GATE = "gate"           # 条件分支门
    LOOP = "loop"           # 循环
    TRANSFORM = "transform" # 文本变换（无 LLM 调用）


class OutputMode(str, Enum):
    """Flow 输出模式"""
    LAST = "last"               # 只返回最后一个节点的输出
    ALL = "all"                 # 返回所有节点输出
    NAMED = "named"             # 返回指定节点的输出


class CommunicationMode(str, Enum):
    """节点间通信模式"""
    PIPELINE = "pipeline"       # 管道：上游输出 → 下游输入
    BLACKBOARD = "blackboard"   # 黑板：所有节点共享上下文
    HYBRID = "hybrid"           # 混合：默认 pipeline，可单独指定


class Condition(BaseModel):
    """条件分支定义"""
    type: Literal["contains", "not_contains", "equals", "length_gt", "always"] = "always"
    value: str = ""
    target: str = ""   # 满足条件时跳转到的节点 id


class FlowNode(BaseModel):
    """Flow 中的一个节点"""
    id: str
    agent: str                                        # 对应的 Agent id
    input: str = "{user_input}"                       # 输入模板
    use_blackboard: bool = False                      # 是否使用黑板模式
    system_prompt_override: str | None = None         # 覆盖 Agent 的 system prompt
    temperature: float | None = None                  # 覆盖温度
    max_iterations: int | None = None                 # 覆盖最大迭代
    conditions: list[Condition] = Field(default_factory=list)  # 条件（gate 节点用）
    description: str = ""                             # 节点描述（用于 GUI 显示）
    # 高级编排特性
    retry: RetryConfig | None = None                  # 重试配置
    loop: LoopConfig | None = None                    # 循环配置
    gate: GateConfig | None = None                    # 条件门配置
    transform: TransformConfig | None = None          # 变换节点配置
    timeout_sec: float | None = None                  # 节点级超时


class FlowEdge(BaseModel):
    """Flow 中的连接边"""
    source: str   # 源节点 id
    target: str   # 目标节点 id
    condition: str | None = None  # 可选条件标签


class RetryConfig(BaseModel):
    """节点重试配置"""
    max_retries: int = 0
    delay_sec: float = 1.0
    retry_on_error: bool = True


class LoopConfig(BaseModel):
    """循环节点配置"""
    max_iterations: int = 5
    stop_condition: str = ""            # 停止条件模板
    continue_condition: str = ""        # 继续条件模板


class GateConfig(BaseModel):
    """条件门节点配置"""
    expression: str = ""                # 条件表达式
    true_target: str = ""               # 条件真时跳转
    false_target: str = ""              # 条件假时跳转


class TransformConfig(BaseModel):
    """变换节点配置 — 无 LLM 调用"""
    type: Literal["template", "join", "python"] = "template"
    template: str = "{input}"
    separator: str = "\n"
    code: str = ""


class FlowDefinition(BaseModel):
    """完整的 Flow 定义"""
    name: str = ""
    description: str = ""
    agents: dict[str, Any] = Field(default_factory=dict)   # Agent 配置（内联或引用）
    nodes: list[FlowNode] = Field(default_factory=list)
    edges: list[FlowEdge] = Field(default_factory=list)
    blackboard_initial: dict[str, Any] = Field(default_factory=dict)
    output_mode: OutputMode = OutputMode.LAST
    output_nodes: list[str] = Field(default_factory=list)
    communication: CommunicationMode = CommunicationMode.HYBRID
    version: str = "1.0"
    max_concurrency: int = 10           # 最大并行节点数
    timeout_sec: float = 600.0          # Flow 级超时（10分钟）
    retry_on_failure: bool = False      # 全局重试
