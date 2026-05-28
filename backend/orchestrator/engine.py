"""
DAG 执行引擎 — Flow 的核心调度器

职责:
1. 根据 FlowDefinition 构建 DAG (有向无环图)
2. 拓扑排序，就绪节点并行执行 (asyncio.gather)
3. 模板插值：{node_id.output} / {blackboard.key} / {user_input}
4. 支持管道/黑板混合通信模式
5. 条件门分支
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from backend.core.agent import Agent, AgentResult
from backend.core.context import RunContext
from backend.orchestrator.blackboard import Blackboard
from backend.orchestrator.models import (
    CommunicationMode,
    FlowDefinition,
    FlowEdge,
    FlowNode,
    NodeType,
    OutputMode,
)


@dataclass
class FlowResult:
    """Flow 执行结果"""
    flow_name: str
    node_results: dict[str, Any] = field(default_factory=dict)  # node_id → AgentResult
    blackboard: Blackboard | None = None
    output: Any = None
    total_tokens: int = 0
    elapsed_seconds: float = 0.0
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 WS 推送）"""
        return {
            "flow_name": self.flow_name,
            "node_results": {
                nid: {
                    "agent_id": r.agent_id if isinstance(r, AgentResult) else r.get("agent_id", ""),
                    "output": r.output if isinstance(r, AgentResult) else r.get("output", ""),
                    "iterations": r.iterations if isinstance(r, AgentResult) else r.get("iterations", 0),
                    "total_tokens": r.total_tokens if isinstance(r, AgentResult) else r.get("total_tokens", 0),
                    "elapsed_seconds": getattr(r, "elapsed_seconds", 0),
                }
                for nid, r in self.node_results.items()
            },
            "blackboard": self.blackboard.snapshot() if self.blackboard else {},
            "output": self.output,
            "total_tokens": self.total_tokens,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "success": self.success,
            "error": self.error,
        }


class FlowEngine:
    """
    DAG 执行引擎

    用法:
        engine = FlowEngine()
        result = await engine.execute(flow_def, inputs={"topic": "AI Agents"}, agents={...})
    """

    def __init__(self):
        self._template_pattern = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")

    async def execute(
        self,
        flow: FlowDefinition,
        inputs: dict[str, Any],
        agents: dict[str, Agent],
    ) -> FlowResult:
        """
        执行一个 Flow

        Args:
            flow: Flow 定义
            inputs: 用户输入，如 {"topic": "AI Agent"}
            agents: Agent 实例字典，key=agent_id
        """
        start_time = time.time()

        # 构建 DAG
        graph = self._build_graph(flow)
        if graph.get("error"):
            return FlowResult(
                flow_name=flow.name, success=False,
                error=graph["error"],
                elapsed_seconds=time.time() - start_time,
            )

        adjacency = graph["adjacency"]   # node_id → [child_id]
        in_degree = graph["in_degree"]   # node_id → int
        all_nodes = graph["all_nodes"]

        # 节点查找表
        flow_node_map = {n.id: n for n in flow.nodes}

        # 初始化黑板
        blackboard = Blackboard(flow.blackboard_initial)
        for k, v in inputs.items():
            blackboard.set(f"input.{k}", v)

        # 节点结果缓存
        node_results: dict[str, Any] = {}
        node_outputs: dict[str, str] = {}

        # 拓扑排序执行
        ready = deque([nid for nid in all_nodes if in_degree[nid] == 0])
        running: dict[str, Any] = {}

        while ready or running:
            # 启动所有就绪节点
            batch = list(ready)
            ready.clear()

            async def run_node(node_id: str) -> tuple[str, Any, str]:
                node = flow_node_map[node_id]
                return await self._execute_node(
                    node, flow, inputs, node_outputs, blackboard, agents
                )

            # 并行执行就绪节点
            if batch:
                tasks = [run_node(nid) for nid in batch]
                results = await asyncio_gather_safe(tasks)

                for nid, (result_or_error, ok) in zip(batch, results):
                    if not ok:
                        return FlowResult(
                            flow_name=flow.name, success=False,
                            error=f"节点 '{nid}' 执行失败: {result_or_error}",
                            blackboard=blackboard,
                            elapsed_seconds=time.time() - start_time,
                        )

                    # result_or_error is (node_id, agent_result, output_text)
                    _, agent_result, output_text = result_or_error

                    node_results[nid] = agent_result
                    node_outputs[nid] = output_text

                    # 记录到黑板
                    if isinstance(agent_result, AgentResult):
                        blackboard.record_agent_output(
                            agent_result.agent_id, nid, output_text
                        )

                    # 更新下游 in_degree
                    for child_id in adjacency.get(nid, []):
                        in_degree[child_id] -= 1
                        if in_degree[child_id] == 0:
                            ready.append(child_id)

        # 解析输出
        output = self._resolve_output(flow, node_outputs, blackboard)

        total_tokens = sum(
            r.total_tokens for r in node_results.values()
            if isinstance(r, AgentResult)
        )

        return FlowResult(
            flow_name=flow.name,
            node_results=node_results,
            blackboard=blackboard,
            output=output,
            total_tokens=total_tokens,
            elapsed_seconds=time.time() - start_time,
            success=True,
        )

    # ---- 内部方法 ----

    def _build_graph(self, flow: FlowDefinition) -> dict:
        """构建 DAG 邻接表"""
        nodes_by_id = {n.id: n for n in flow.nodes}

        if not flow.nodes:
            return {"error": "Flow 没有节点"}

        # 自动生成边（如果用户没提供 edges，按 nodes 顺序串连）
        edges = list(flow.edges)
        if not edges and len(flow.nodes) > 1:
            for i in range(len(flow.nodes) - 1):
                edges.append(FlowEdge(
                    source=flow.nodes[i].id,
                    target=flow.nodes[i + 1].id,
                ))

        adjacency: dict[str, list[str]] = {n.id: [] for n in flow.nodes}
        in_degree: dict[str, int] = {n.id: 0 for n in flow.nodes}

        for edge in edges:
            if edge.source in adjacency and edge.target in adjacency:
                adjacency[edge.source].append(edge.target)
                in_degree[edge.target] += 1

        # 检查环
        if self._has_cycle(adjacency, list(nodes_by_id.keys())):
            return {"error": "Flow 中存在循环依赖"}

        return {
            "adjacency": adjacency,
            "in_degree": in_degree,
            "all_nodes": list(nodes_by_id.keys()),
        }

    def _has_cycle(self, adjacency: dict[str, list[str]], nodes: list[str]) -> bool:
        """DFS 检测是否有环"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in nodes}

        def dfs(nid: str) -> bool:
            color[nid] = GRAY
            for child in adjacency.get(nid, []):
                if color.get(child) == GRAY:
                    return True
                if color.get(child) == WHITE and dfs(child):
                    return True
            color[nid] = BLACK
            return False

        for n in nodes:
            if color[n] == WHITE and dfs(n):
                return True
        return False

    async def _execute_node(
        self,
        node: FlowNode,
        flow: FlowDefinition,
        inputs: dict[str, Any],
        node_outputs: dict[str, str],
        blackboard: Blackboard,
        agents: dict[str, Agent],
    ) -> tuple[str, Any, str]:
        """执行单个节点"""
        agent = agents.get(node.agent)
        if not agent:
            raise ValueError(f"Agent '{node.agent}' 未找到")

        # 解析输入模板
        resolved_input = self._resolve_template(
            node.input, inputs, node_outputs, blackboard
        )

        # 构建上下文（黑板模式 vs 管道模式）
        if node.use_blackboard or flow.communication in (
            CommunicationMode.BLACKBOARD, CommunicationMode.HYBRID
        ):
            ctx = RunContext(
                agent_id=agent.config.agent_id,
                agent_name=agent.config.name,
                blackboard=blackboard.snapshot(),
                max_iterations=node.max_iterations or agent.config.max_iterations,
                verbose=agent.config.verbose,
            )
        else:
            ctx = RunContext(
                agent_id=agent.config.agent_id,
                agent_name=agent.config.name,
                max_iterations=node.max_iterations or agent.config.max_iterations,
                verbose=agent.config.verbose,
            )

        # 覆盖 system prompt / temperature
        if node.system_prompt_override:
            original_prompt = agent.config.system_prompt
            agent.config.system_prompt = node.system_prompt_override
        original_temp = agent.config.llm.temperature
        if node.temperature is not None:
            agent.config.llm.temperature = node.temperature

        # 重试逻辑
        max_retries = (node.retry.max_retries if node.retry else 0) + 1
        last_error: str | None = None

        for attempt in range(max_retries):
            try:
                result = await agent.run(task=resolved_input, context=ctx)
                output_text = result.output
                last_error = None
                break
            except Exception as e:
                last_error = str(e)
                if node.retry and node.retry.retry_on_error and attempt < max_retries - 1:
                    import asyncio
                    delay = node.retry.delay_sec if node.retry else 1.0
                    if ctx.verbose:
                        print(f"[重试] 节点 '{node.id}' 第 {attempt+1} 次失败: {e}，{delay}s 后重试")
                    await asyncio.sleep(delay)
                else:
                    raise

        if last_error:
            raise RuntimeError(f"节点 '{node.id}' 重试 {max_retries-1} 次后仍失败: {last_error}")

        # 恢复被覆盖的配置
        if node.system_prompt_override:
            agent.config.system_prompt = original_prompt
        if node.temperature is not None:
            agent.config.llm.temperature = original_temp

        return node.id, result, output_text

    _TEMPLATE_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")

    def _resolve_template(
        self,
        template: str,
        inputs: dict[str, Any],
        node_outputs: dict[str, str],
        blackboard: Blackboard,
    ) -> str:
        """解析模板中的 {变量} 引用"""

        def replacer(m: re.Match) -> str:
            key = m.group(1)

            # {user_input}
            if key == "user_input":
                return inputs.get("task", inputs.get("topic", ""))

            # {input.*}
            if key.startswith("input."):
                field = key.split(".", 1)[1]
                return str(inputs.get(field, m.group(0)))

            # {blackboard.*}
            if key.startswith("blackboard."):
                field = key.split(".", 1)[1]
                val = blackboard.get(field)
                return str(val) if val is not None else m.group(0)

            # {node_id.output}
            if key.endswith(".output"):
                node_id = key.rsplit(".", 1)[0]
                return node_outputs.get(node_id, m.group(0))

            # {prev.output} — 指向上一个节点
            if key == "prev.output" and node_outputs:
                last_key = list(node_outputs.keys())[-1]
                return node_outputs[last_key]

            return m.group(0)

        return self._TEMPLATE_RE.sub(replacer, template)

    def _resolve_output(
        self,
        flow: FlowDefinition,
        node_outputs: dict[str, str],
        blackboard: Blackboard,
    ) -> Any:
        """根据 output_mode 解析最终输出"""
        if flow.output_mode == OutputMode.LAST:
            if not node_outputs:
                return ""
            last_id = list(node_outputs.keys())[-1]
            return node_outputs[last_id]

        elif flow.output_mode == OutputMode.ALL:
            return {
                "node_outputs": node_outputs,
                "blackboard": blackboard.snapshot(),
            }

        elif flow.output_mode == OutputMode.NAMED:
            selected = {}
            for nid in flow.output_nodes:
                if nid in node_outputs:
                    selected[nid] = node_outputs[nid]
            return selected

        return node_outputs


async def asyncio_gather_safe(tasks: list) -> list[tuple[Any, bool]]:
    """安全的 gather：捕获异常不抛"""
    import asyncio
    results = []
    for coro in tasks:
        try:
            res = await coro
            results.append((res, True))
        except Exception as e:
            results.append((str(e), False))
    return results
