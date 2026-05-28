"""
Python DSL — 用 Python 代码编排多 Agent 流程

用法:
    flow = (
        Flow("research_report")
        .describe("调研→写作→审阅")
        .agent("researcher", researcher_cfg)
        .agent("writer", writer_cfg)
        .then("research", "researcher", "调研主题: {topic}")
        .then("write", "writer", "根据调研:\n{research.output}")
        .then("review", "reviewer", "审阅:\n{write.output}", use_blackboard=True)
    )
    result = await engine.execute(flow.build(), inputs={"topic": "AI"}, agents=...)
"""

from __future__ import annotations

from typing import Any

from backend.orchestrator.models import (
    CommunicationMode,
    Condition,
    FlowDefinition,
    FlowEdge,
    FlowNode,
    GateConfig,
    LoopConfig,
    NodeType,
    OutputMode,
    RetryConfig,
    TransformConfig,
)


class Flow:
    """
    Flow 构建器 — Python DSL

    通过链式调用构建 FlowDefinition，最后调用 .build() 获取最终对象。
    """

    def __init__(self, name: str = ""):
        self._name = name
        self._description: str = ""
        self._agents: dict[str, Any] = {}
        self._nodes: list[FlowNode] = []
        self._edges: list[FlowEdge] = []
        self._blackboard_initial: dict[str, Any] = {}
        self._output_mode: OutputMode = OutputMode.LAST
        self._output_nodes: list[str] = []
        self._communication: CommunicationMode = CommunicationMode.HYBRID
        self._node_order: list[str] = []  # 按添加顺序

    def describe(self, description: str) -> "Flow":
        """设置描述"""
        self._description = description
        return self

    def agent(self, agent_id: str, config: Any) -> "Flow":
        """注册 Agent 配置"""
        self._agents[agent_id] = config
        return self

    def then(
        self,
        node_id: str,
        agent: str,
        input_template: str = "{user_input}",
        *,
        use_blackboard: bool = False,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_iterations: int | None = None,
        description: str = "",
    ) -> "Flow":
        """
        添加一个顺序节点（会自动连接上一个节点）
        """
        node = FlowNode(
            id=node_id,
            agent=agent,
            input=input_template,
            use_blackboard=use_blackboard,
            system_prompt_override=system_prompt,
            temperature=temperature,
            max_iterations=max_iterations,
            description=description,
        )
        self._nodes.append(node)

        # 自动连接上一个节点
        if self._node_order:
            self._edges.append(FlowEdge(
                source=self._node_order[-1],
                target=node_id,
            ))
        self._node_order.append(node_id)
        return self

    def fan_out(self, *nodes: tuple[str, str, str]) -> "Flow":
        """
        扇出 — 多个并行节点
        每个参数: (node_id, agent, input_template)

        用法:
            flow.fan_out(
                ("research_a", "researcher", "调研方向 A: {topic}"),
                ("research_b", "researcher", "调研方向 B: {topic}"),
            )
        """
        prev_id = self._node_order[-1] if self._node_order else None

        for node_id, agent, input_template in nodes:
            node = FlowNode(id=node_id, agent=agent, input=input_template)
            self._nodes.append(node)
            if prev_id:
                self._edges.append(FlowEdge(source=prev_id, target=node_id))
            self._node_order.append(node_id)

        return self

    def gather(
        self,
        node_id: str,
        agent: str,
        input_template: str,
        *,
        use_blackboard: bool = False,
    ) -> "Flow":
        """
        汇聚 — 收集前面所有扇出节点的输出

        在 input_template 中用 {prev_1.output}, {prev_2.output} 引用各个扇出结果
        或用 {blackboard.agent.*.output} 从黑板读取
        """
        # 自动汇聚前面所有节点
        prev_nodes = [nid for nid in self._node_order if nid != node_id]

        node = FlowNode(
            id=node_id,
            agent=agent,
            input=input_template,
            use_blackboard=use_blackboard,
        )
        self._nodes.append(node)

        # 连接所有前驱节点
        for prev in prev_nodes:
            # 避免重复边
            if not any(e.source == prev and e.target == node_id for e in self._edges):
                self._edges.append(FlowEdge(source=prev, target=node_id))

        self._node_order.append(node_id)
        return self

    def gate(
        self,
        node_id: str,
        agent: str,
        input_template: str,
        *,
        condition_type: str = "always",
        condition_value: str = "",
        condition_target: str = "",
    ) -> "Flow":
        """
        条件门节点 — 根据条件决定是否执行

        condition_type: contains | not_contains | equals | length_gt | always
        """
        node = FlowNode(
            id=node_id,
            agent=agent,
            input=input_template,
            conditions=[
                Condition(
                    type=condition_type,
                    value=condition_value,
                    target=condition_target,
                )
            ],
        )
        self._nodes.append(node)

        if self._node_order:
            self._edges.append(FlowEdge(
                source=self._node_order[-1],
                target=node_id,
            ))
        self._node_order.append(node_id)
        return self

    def loop(
        self,
        node_id: str,
        agent: str,
        input_template: str = "{user_input}",
        *,
        max_iterations: int = 5,
        stop_condition: str = "",
        use_blackboard: bool = False,
    ) -> "Flow":
        """
        循环节点 — 重复执行直到满足停止条件
        """
        node = FlowNode(
            id=node_id,
            agent=agent,
            input=input_template,
            use_blackboard=use_blackboard,
            loop=LoopConfig(
                max_iterations=max_iterations,
                stop_condition=stop_condition,
            ),
        )
        self._add_node(node)
        return self

    def retry(
        self,
        node_id: str,
        agent: str,
        input_template: str = "{user_input}",
        *,
        max_retries: int = 3,
        delay_sec: float = 1.0,
        use_blackboard: bool = False,
    ) -> "Flow":
        """
        带重试的节点 — 失败后自动重试
        """
        node = FlowNode(
            id=node_id,
            agent=agent,
            input=input_template,
            use_blackboard=use_blackboard,
            retry=RetryConfig(max_retries=max_retries, delay_sec=delay_sec),
        )
        self._add_node(node)
        return self

    def transform(
        self,
        node_id: str,
        template: str,
        *,
        transform_type: str = "template",
    ) -> "Flow":
        """
        变换节点 — 无 LLM 调用，仅做文本变换

        用法:
            .transform("summary", "最终结果:\n{prev.output}")
        """
        node = FlowNode(
            id=node_id,
            agent="__transform__",
            input=template,
            transform=TransformConfig(type=transform_type, template=template),
        )
        self._add_node(node)
        return self

    def gate(
        self,
        node_id: str,
        expression: str,
        *,
        true_target: str = "",
        false_target: str = "",
    ) -> "Flow":
        """
        条件门 — 根据表达式决定执行路径

        用法:
            .gate("check", "{prev.output} 包含 '成功'",
                  true_target="next_step", false_target="retry")
        """
        node = FlowNode(
            id=node_id,
            agent="__gate__",
            input="{user_input}",
            gate=GateConfig(
                expression=expression,
                true_target=true_target,
                false_target=false_target,
            ),
        )
        self._add_node(node)
        return self

    def _add_node(self, node: FlowNode) -> None:
        """内部：添加节点并自动连线"""
        self._nodes.append(node)
        if self._node_order:
            self._edges.append(FlowEdge(
                source=self._node_order[-1],
                target=node.id,
            ))
        self._node_order.append(node.id)

    def output(self, mode: str = "last", *node_ids: str) -> "Flow":
        """设置输出模式"""
        if mode == "all":
            self._output_mode = OutputMode.ALL
        elif mode == "named" and node_ids:
            self._output_mode = OutputMode.NAMED
            self._output_nodes = list(node_ids)
        else:
            self._output_mode = OutputMode.LAST
        return self

    def communication(self, mode: str) -> "Flow":
        """设置通信模式: pipeline | blackboard | hybrid"""
        self._communication = CommunicationMode(mode)
        return self

    def blackboard(self, **kwargs: Any) -> "Flow":
        """设置黑板初始值"""
        self._blackboard_initial.update(kwargs)
        return self

    def build(self) -> FlowDefinition:
        """构建最终的 FlowDefinition"""
        return FlowDefinition(
            name=self._name,
            description=self._description,
            agents=self._agents,
            nodes=self._nodes,
            edges=self._edges,
            blackboard_initial=self._blackboard_initial,
            output_mode=self._output_mode,
            output_nodes=self._output_nodes,
            communication=self._communication,
        )
