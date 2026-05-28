"""
运行上下文 — 在 Agent 和 Skill 执行间传递状态
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunContext:
    """
    Agent 运行上下文

    每个 Agent.run() 调用创建一个上下文实例，传递给每个执行的技能。
    包含:
    - 会话级变量 (variables)
    - 共享黑板数据 (blackboard, 多 Agent 编排时使用)
    - Agent 自身引用
    """

    agent_id: str = ""
    agent_name: str = ""

    # 会话变量 — 技能可读写
    variables: dict[str, Any] = field(default_factory=dict)

    # 多 Agent 共享黑板 (Phase 2+ 使用)
    blackboard: dict[str, Any] = field(default_factory=dict)

    # 元数据
    iteration: int = 0
    max_iterations: int = 15
    verbose: bool = True

    def get(self, key: str, default: Any = None) -> Any:
        """获取会话变量"""
        return self.variables.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置会话变量"""
        self.variables[key] = value
