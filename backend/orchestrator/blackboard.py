"""
共享黑板 (Blackboard) — 多 Agent 间的共享上下文

支持点号路径读写: board.get("project.style") → "专业"
内部用嵌套 dict 存储。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class Blackboard:
    """
    黑板 — 多 Agent 共享上下文存储

    用法:
        board = Blackboard({"project": "AI 报告", "style": "专业"})
        board.set("author.name", "张三")
        board.get("project")       # "AI 报告"
        board.get("author.name")   # "张三"
        board.snapshot()           # 全部数据
    """

    def __init__(self, initial: dict[str, Any] | None = None):
        self._data: dict[str, Any] = deepcopy(initial) if initial else {}

    # ---- 读写 ----

    def get(self, key: str, default: Any = None) -> Any:
        """通过点号路径读取值，如 'project.style'"""
        if "." not in key:
            return self._data.get(key, default)

        parts = key.split(".")
        current = self._data
        for i, part in enumerate(parts):
            if not isinstance(current, dict):
                return default
            if part not in current:
                return default
            if i == len(parts) - 1:
                return current[part]
            current = current[part]
        return default

    def set(self, key: str, value: Any) -> None:
        """通过点号路径设置值"""
        if "." not in key:
            self._data[key] = value
            return

        parts = key.split(".")
        current = self._data
        for i, part in enumerate(parts[:-1]):
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def update(self, data: dict[str, Any]) -> None:
        """合并更新（浅合并）"""
        self._data.update(data)

    def delete(self, key: str) -> None:
        """删除一个键"""
        if "." not in key:
            self._data.pop(key, None)
            return
        parts = key.split(".")
        current = self._data
        for part in parts[:-1]:
            if not isinstance(current, dict):
                return
            current = current.get(part, {})
        if isinstance(current, dict):
            current.pop(parts[-1], None)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None and key not in self._data:
            raise KeyError(key)
        return val

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __repr__(self) -> str:
        return f"Blackboard({self._data})"

    # ---- 快照 ----

    def snapshot(self) -> dict[str, Any]:
        """返回完整数据的深拷贝"""
        return deepcopy(self._data)

    def keys(self) -> list[str]:
        """返回所有顶层键"""
        return list(self._data.keys())

    # ---- 专用于编排的方法 ----

    def record_agent_output(self, agent_id: str, node_id: str, output: str) -> None:
        """记录 Agent 的输出到黑板"""
        self.set(f"agent.{node_id}.output", output)
        self.set(f"agent.{node_id}.agent_id", agent_id)

    def get_agent_output(self, node_id: str) -> str:
        """读取某 Agent 的输出"""
        return self.get(f"agent.{node_id}.output", "")
