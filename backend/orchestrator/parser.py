"""
YAML 解析器 — 将 YAML 格式的 Flow 定义解析为 FlowDefinition 对象

YAML 格式:

```yaml
version: "1.0"
name: research_report
description: 调研→写作→审阅

agents:
  researcher:
    llm:
      provider: deepseek
      model: deepseek-chat
    system_prompt: "你是研究员"
    skills: [web_search]

flows:
  - name: "main"
    nodes:
      - id: research
        agent: researcher
        input: "调研: {topic}"
      - id: write
        agent: writer
        input: "写作: {research.output}"
    output_mode: last
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.orchestrator.models import (
    CommunicationMode,
    Condition,
    FlowDefinition,
    FlowEdge,
    FlowNode,
    NodeType,
    OutputMode,
)


class FlowParser:
    """YAML → FlowDefinition 解析器"""

    @staticmethod
    def parse_file(path: str | Path) -> list[FlowDefinition]:
        """
        从 YAML 文件解析，返回 FlowDefinition 列表

        一个文件可包含多个 flow（在 flows 数组下）
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Flow 文件不存在: {path}")

        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError("YAML 根节点必须是对象")

        return FlowParser.parse_multi(data)

    @staticmethod
    def parse_string(yaml_content: str) -> list[FlowDefinition]:
        """从 YAML 字符串解析"""
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            raise ValueError("YAML 根节点必须是对象")
        return FlowParser.parse_multi(data)

    @staticmethod
    def parse_multi(data: dict[str, Any]) -> list[FlowDefinition]:
        """从解析后的 dict 解析为多个 FlowDefinition"""
        version = data.get("version", "1.0")
        global_agents = data.get("agents", {})

        flows_data = data.get("flows", [data])  # 兼容单 flow 和最外层
        if not isinstance(flows_data, list):
            flows_data = [flows_data]

        results: list[FlowDefinition] = []
        for flow_data in flows_data:
            if not isinstance(flow_data, dict):
                continue
            results.append(FlowParser._parse_one(
                flow_data, global_agents, version
            ))
        return results

    @classmethod
    def _parse_one(
        cls,
        data: dict[str, Any],
        global_agents: dict[str, Any],
        version: str,
    ) -> FlowDefinition:
        """解析单个 Flow"""
        # 节点
        nodes: list[FlowNode] = []
        for nd in data.get("nodes", []):
            node = FlowNode(
                id=nd["id"],
                agent=nd.get("agent", ""),
                input=nd.get("input", "{user_input}"),
                use_blackboard=nd.get("use_blackboard", False),
                system_prompt_override=nd.get("system_prompt"),
                temperature=nd.get("temperature"),
                max_iterations=nd.get("max_iterations"),
                description=nd.get("description", ""),
                conditions=[
                    Condition(**c) for c in nd.get("conditions", [])
                ],
            )
            nodes.append(node)

        # 边
        edges: list[FlowEdge] = []
        for ed in data.get("edges", []):
            edge = FlowEdge(
                source=ed["source"],
                target=ed["target"],
                condition=ed.get("condition"),
            )
            edges.append(edge)

        # 输出模式
        output_mode_str = data.get("output_mode", "last")
        output_mode_map = {
            "last": OutputMode.LAST,
            "all": OutputMode.ALL,
            "named": OutputMode.NAMED,
        }
        output_mode = output_mode_map.get(output_mode_str, OutputMode.LAST)

        # 通信模式
        comm_str = data.get("communication", "hybrid")
        comm_map = {
            "pipeline": CommunicationMode.PIPELINE,
            "blackboard": CommunicationMode.BLACKBOARD,
            "hybrid": CommunicationMode.HYBRID,
        }
        communication = comm_map.get(comm_str, CommunicationMode.HYBRID)

        # 合并 Agent 配置（flow-level 覆盖 global）
        flow_agents = {**global_agents, **(data.get("agents", {}))}

        return FlowDefinition(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=version,
            agents=flow_agents,
            nodes=nodes,
            edges=edges,
            blackboard_initial=data.get("blackboard_initial", {}),
            output_mode=output_mode,
            output_nodes=data.get("output_nodes", []),
            communication=communication,
        )
