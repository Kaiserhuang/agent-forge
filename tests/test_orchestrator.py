"""
编排引擎集成测试 — 验证 DAG 执行、模板插值、YAML/DSL 双模式
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import tempfile
from pathlib import Path

import pytest

from backend.core.agent import Agent, AgentConfig
from backend.core.config import LLMConfig
from backend.llm.base import BaseLLM, LLMResponse
from backend.orchestrator.engine import FlowEngine, FlowResult
from backend.orchestrator.dsl import Flow
from backend.orchestrator.parser import FlowParser
from backend.orchestrator.models import (
    CommunicationMode, FlowDefinition, FlowNode, FlowEdge, OutputMode,
)
from backend.skills.base import BaseSkill
from backend.skills.registry import SkillRegistry


# ============================================================
# Mock LLM — 不调用真实 API
# ============================================================

class MockLLM(BaseLLM):
    """模拟 LLM，返回预设的 tool_call 或文本"""

    def __init__(self, responses: list[LLMResponse] | None = None):
        super().__init__(LLMConfig(api_key="mock"))
        self.responses = responses or []
        self.call_count = 0

    async def chat(self, messages, tools=None):
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return LLMResponse(content="模拟最终回复")

    async def chat_stream(self, messages, tools=None):
        yield LLMResponse(content="模拟流式回复")


class EchoSkill(BaseSkill):
    """测试用技能 — 返回参数原文"""
    name = "echo"
    description = "回显输入"
    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要回显的文本"},
            },
            "required": ["text"],
        }
    async def execute(self, args, ctx):
        return f"ECHO: {args.get('text', '')}"


def make_agent(agent_id: str, skill_names: list[str] | None = None) -> Agent:
    """创建带 mock LLM 的 Agent"""
    from backend.llm.base import LLMResponse, ToolCall

    # 注册技能
    registry = SkillRegistry()
    registry.register(EchoSkill())

    agent = Agent(
        config=AgentConfig(
            agent_id=agent_id,
            name=f"Agent-{agent_id}",
            system_prompt="你是一个测试助手。",
            skills=skill_names or [],
            llm=LLMConfig(api_key="mock"),
            verbose=False,
        ),
        llm=MockLLM(),
        registry=registry,
    )
    return agent


# ============================================================
# 测试用例
# ============================================================

class TestFlowEngine:
    """DAG 执行引擎测试"""

    @pytest.mark.asyncio
    async def test_simple_chain(self):
        """链式执行: A → B"""
        agents = {
            "a": make_agent("a"),
            "b": make_agent("b"),
        }

        flow = FlowDefinition(
            name="test_chain",
            nodes=[
                FlowNode(id="node_a", agent="a", input="任务A: {topic}"),
                FlowNode(id="node_b", agent="b", input="任务B: {node_a.output}"),
            ],
            edges=[
                FlowEdge(source="node_a", target="node_b"),
            ],
        )

        engine = FlowEngine()
        result = await engine.execute(flow, inputs={"topic": "测试"}, agents=agents)

        assert result.success, f"执行失败: {result.error}"
        assert "node_a" in result.node_results
        assert "node_b" in result.node_results
        assert result.output

    @pytest.mark.asyncio
    async def test_template_resolution(self):
        """模板插值: {topic} → inputs, {node_a.output} → 上游输出"""
        agents = {"a": make_agent("a")}

        flow = FlowDefinition(
            name="test_template",
            nodes=[
                FlowNode(id="node_a", agent="a", input="用户说: {topic}，风格: {input.style}"),
            ],
        )

        engine = FlowEngine()
        result = await engine.execute(
            flow,
            inputs={"topic": "AI发展", "style": "专业"},
            agents=agents,
        )

        assert result.success

    @pytest.mark.asyncio
    async def test_parallel_fan_out(self):
        """扇出执行: A → B, C 并行"""
        agents = {
            "a": make_agent("a"),
            "b": make_agent("b"),
            "c": make_agent("c"),
        }

        flow = FlowDefinition(
            name="test_fanout",
            nodes=[
                FlowNode(id="node_a", agent="a", input="前置任务"),
                FlowNode(id="node_b", agent="b", input="并行B"),
                FlowNode(id="node_c", agent="c", input="并行C"),
            ],
            edges=[
                FlowEdge(source="node_a", target="node_b"),
                FlowEdge(source="node_a", target="node_c"),
            ],
        )

        engine = FlowEngine()
        result = await engine.execute(flow, inputs={}, agents=agents)

        assert result.success
        assert "node_b" in result.node_results
        assert "node_c" in result.node_results

    @pytest.mark.asyncio
    async def test_blackboard_hybrid(self):
        """黑板模式: 共享上下文"""
        agents = {"a": make_agent("a"), "b": make_agent("b")}

        flow = FlowDefinition(
            name="test_blackboard",
            communication=CommunicationMode.HYBRID,
            blackboard_initial={"project": "测试项目"},
            nodes=[
                FlowNode(id="node_a", agent="a", input="任务A", use_blackboard=True),
                FlowNode(id="node_b", agent="b", input="任务B: {blackboard.project}"),
            ],
            edges=[FlowEdge(source="node_a", target="node_b")],
        )

        engine = FlowEngine()
        result = await engine.execute(flow, inputs={}, agents=agents)
        assert result.success
        assert result.blackboard is not None

    @pytest.mark.asyncio
    async def test_output_modes(self):
        """输出模式: last / all / named"""
        agents = {"a": make_agent("a"), "b": make_agent("b")}

        base_nodes = [
            FlowNode(id="n1", agent="a", input="第一"),
            FlowNode(id="n2", agent="b", input="第二"),
        ]
        base_edges = [FlowEdge(source="n1", target="n2")]

        # last mode
        flow_last = FlowDefinition(
            name="test_last", nodes=base_nodes, edges=base_edges,
            output_mode=OutputMode.LAST,
        )
        r1 = await FlowEngine().execute(flow_last, inputs={}, agents=agents)
        assert isinstance(r1.output, str), "LAST 模式应返回字符串"

        # all mode
        flow_all = FlowDefinition(
            name="test_all", nodes=base_nodes, edges=base_edges,
            output_mode=OutputMode.ALL,
        )
        r2 = await FlowEngine().execute(flow_all, inputs={}, agents=agents)
        assert isinstance(r2.output, dict), "ALL 模式应返回 dict"

    @pytest.mark.asyncio
    async def test_cyclic_dag_detection(self):
        """环检测: 应拒绝有环图"""
        agents = {"a": make_agent("a")}

        flow = FlowDefinition(
            name="test_cycle",
            nodes=[
                FlowNode(id="a", agent="a", input="A"),
                FlowNode(id="b", agent="a", input="B"),
            ],
            edges=[
                FlowEdge(source="a", target="b"),
                FlowEdge(source="b", target="a"),  # 环
            ],
        )

        result = await FlowEngine().execute(flow, inputs={}, agents=agents)
        assert not result.success, "环应被检测到"


class TestFlowDSL:
    """Python DSL 测试"""

    @pytest.mark.asyncio
    async def test_dsl_build(self):
        """DSL 构建 FlowDefinition"""
        flow = (
            Flow("test")
            .describe("描述")
            .then("step1", "agent_a", "输入: {topic}")
            .then("step2", "agent_b", "加工: {step1.output}")
            .output("last")
        )

        fd = flow.build()
        assert fd.name == "test"
        assert fd.description == "描述"
        assert len(fd.nodes) == 2
        assert len(fd.edges) == 1
        assert fd.edges[0].source == "step1"
        assert fd.edges[0].target == "step2"

    @pytest.mark.asyncio
    async def test_dsl_fan_out_gather(self):
        """DSL 扇出 + 汇聚"""
        flow = (
            Flow("parallel")
            .then("plan", "planner", "规划: {topic}")
            .fan_out(
                ("research_a", "researcher", "调研A"),
                ("research_b", "researcher", "调研B"),
            )
            .gather("summary", "writer", "综合:\n{research_a.output}\n{research_b.output}")
            .output("all")
        )

        fd = flow.build()
        assert len(fd.nodes) == 4
        # plan → research_a, plan → research_b, research_a → summary, research_b → summary
        assert len(fd.edges) >= 3

    @pytest.mark.asyncio
    async def test_dsl_blackboard(self):
        """DSL 黑板配置"""
        flow = (
            Flow("bb_test")
            .blackboard(project="测试", version="1.0")
            .communication("hybrid")
            .then("step1", "a", "任务", use_blackboard=True)
            .output("last")
        )

        fd = flow.build()
        assert fd.communication == CommunicationMode.HYBRID
        assert fd.blackboard_initial["project"] == "测试"
        assert fd.nodes[0].use_blackboard is True

    @pytest.mark.asyncio
    async def test_dsl_execution(self):
        """DSL 完整执行"""
        agents = {"a": make_agent("a"), "b": make_agent("b")}

        flow = (
            Flow("dsl_exec")
            .then("first", "a", "第一轮: {topic}")
            .then("second", "b", "第二轮: {first.output}")
            .output("last")
        )

        engine = FlowEngine()
        result = await engine.execute(
            flow.build(), inputs={"topic": "DSL测试"}, agents=agents
        )

        assert result.success
        assert result.output


class TestFlowParser:
    """YAML 解析器测试"""

    def test_parse_simple_yaml(self):
        """解析基本 YAML"""
        yaml_content = """
name: research_flow
description: 调研流程

agents:
  researcher:
    llm:
      provider: deepseek
      model: deepseek-chat

nodes:
  - id: research
    agent: researcher
    input: "调研: {topic}"
    use_blackboard: true

  - id: write
    agent: researcher
    input: "写作: {research.output}"

edges:
  - source: research
    target: write

output_mode: last
"""
        flows = FlowParser.parse_string(yaml_content)
        assert len(flows) == 1
        flow = flows[0]
        assert flow.name == "research_flow"
        assert len(flow.nodes) == 2
        assert flow.nodes[0].id == "research"
        assert flow.nodes[0].use_blackboard is True
        assert flow.nodes[1].input == "写作: {research.output}"

    def test_parse_multi_flow(self):
        """解析多 Flow YAML"""
        yaml_content = """
version: "1.0"

agents:
  researcher:
    system_prompt: "你是一个研究员"

flows:
  - name: flow1
    nodes:
      - id: step1
        agent: researcher
        input: "任务1"

  - name: flow2
    nodes:
      - id: step1
        agent: researcher
        input: "任务2"
"""
        flows = FlowParser.parse_string(yaml_content)
        assert len(flows) == 2
        assert flows[0].name == "flow1"
        assert flows[1].name == "flow2"

    def test_parse_from_file(self):
        """从文件解析"""
        yaml_content = """
name: file_test
nodes:
  - id: a
    agent: test
    input: hello
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            flows = FlowParser.parse_file(tmp_path)
            assert len(flows) == 1
            assert flows[0].name == "file_test"
        finally:
            os.unlink(tmp_path)

    def test_parse_auto_edge(self):
        """无 edges 时 parser 不生成边（引擎的 _build_graph 会按顺序生成）"""
        yaml_content = """
name: auto_edge
nodes:
  - id: a
    agent: x
    input: "A"
  - id: b
    agent: x
    input: "B"
  - id: c
    agent: x
    input: "C"
"""
        flows = FlowParser.parse_string(yaml_content)
        flow = flows[0]
        # parser 保持原样，引擎执行时自动补边
        assert len(flow.edges) == 0
        assert len(flow.nodes) == 3


if __name__ == "__main__":
    import asyncio
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
