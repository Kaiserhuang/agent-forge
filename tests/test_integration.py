"""
AgentForge 端到端集成测试

验证所有模块协同工作:
1. 技能动态加载 (Loader + Manager)
2. Agent 运行时 (Agent.run)
3. 多 Agent 编排 (FlowEngine + DSL)
4. 混合记忆系统 (HybridMemory)
5. REST API 路由

不依赖真实 LLM API — 使用 MockLLM。
"""

import sys
import os
import json
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from backend.core.agent import Agent, AgentConfig, AgentResult
from backend.core.config import LLMConfig, Message
from backend.llm.base import BaseLLM, LLMResponse, ToolCall
from backend.orchestrator.engine import FlowEngine
from backend.orchestrator.dsl import Flow
from backend.orchestrator.parser import FlowParser
from backend.skills.registry import SkillRegistry
from backend.skills.manager import SkillManager
from backend.skills.base import BaseSkill
from backend.skills.builtin import WebSearchSkill, FileOpsSkill, RememberSkill
from backend.core.context import RunContext
from backend.memory.hybrid_memory import HybridMemory


# ============================================================
# Mock LLM
# ============================================================

class MockLLM(BaseLLM):
    """可控的 Mock LLM — 预设响应"""

    def __init__(self, responses: list[LLMResponse] | None = None):
        super().__init__(LLMConfig(api_key="mock"))
        self.responses = responses or []
        self.call_count = 0
        self.all_calls: list[dict] = []

    async def chat(self, messages, tools=None):
        self.all_calls.append({
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "tools": tools,
        })
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return LLMResponse(content="Mock 最终回复")

    async def chat_stream(self, messages, tools=None):
        yield LLMResponse(content="流式回复")


# ============================================================
# 测试技能
# ============================================================

class EchoSkill(BaseSkill):
    """回显技能"""
    name = "echo"
    description = "回显输入参数"

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


class CalculatorSkill(BaseSkill):
    """计算器技能"""
    name = "calculator"
    description = "执行四则运算"

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "expr": {"type": "string", "description": "数学表达式，如 1+2"},
            },
            "required": ["expr"],
        }

    async def execute(self, args, ctx):
        expr = args.get("expr", "")
        try:
            result = eval(expr, {"__builtins__": {}}, {})
            return f"{expr} = {result}"
        except Exception as e:
            return f"计算错误: {e}"


# ============================================================
# 集成测试
# ============================================================

class TestIntegration:
    """端到端集成测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前创建临时目录"""
        self.tmpdir = tempfile.mkdtemp()
        yield
        shutil.rmtree(self.tmpdir)

    def _make_echo_agent(self, agent_id="test_agent", skills=None):
        """创建带 echo 技能的 Agent"""
        reg = SkillRegistry()
        reg.register_many(EchoSkill(), CalculatorSkill())
        agent = Agent(
            config=AgentConfig(
                agent_id=agent_id,
                system_prompt="你是一个测试助手。当被问到计算时使用 calculator 技能。",
                skills=skills or ["echo"],
                llm=LLMConfig(api_key="mock"),
                verbose=False,
            ),
            llm=MockLLM(),
            registry=reg,
        )
        return agent

    # ── 1. Agent 运行时集成 ──

    @pytest.mark.asyncio
    async def test_agent_echo_flow(self):
        """Agent 完整工具调用循环"""
        agent = self._make_echo_agent()

        # 设置 Mock 响应: 先调用工具，再返回文本
        agent.llm.responses = [
            LLMResponse(
                tool_calls=[ToolCall(id="call_1", name="echo", args={"text": "hello"})],
            ),
            LLMResponse(content="已执行回显。结果是：ECHO: hello"),
        ]

        result = await agent.run("帮我回显 hello")

        assert result.success
        assert result.iterations == 2
        assert "ECHO: hello" in result.output
        assert result.elapsed_seconds > 0

    @pytest.mark.asyncio
    async def test_agent_max_iterations(self):
        """达到 max_iterations 时优雅终止"""
        agent = self._make_echo_agent()
        agent.config.max_iterations = 3

        # 总是返回 tool_call（永不结束）
        agent.llm.responses = [
            LLMResponse(
                tool_calls=[ToolCall(id=f"call_{i}", name="echo", args={"text": "x"})],
            )
            for i in range(10)
        ]

        result = await agent.run("循环任务")
        assert result.success
        assert result.iterations <= 3

    # ── 2. 技能动态加载集成 ──

    @pytest.mark.asyncio
    async def test_dynamic_skill_loading(self):
        """从文件系统动态加载技能"""
        reg = SkillRegistry()
        reg.register_many(WebSearchSkill(), FileOpsSkill())

        mgr = SkillManager(reg)

        # 在临时目录创建技能包
        skills_dir = os.path.join(self.tmpdir, ".skills")
        path = mgr.create(
            name="greeting_demo",
            description="问候演示",
            target_dir=skills_dir,
            impl_code='''"""greeting_demo 技能"""
from typing import Any
from backend.skills.base import BaseSkill
from backend.core.context import RunContext

class GreetingDemoSkill(BaseSkill):
    name = "greeting_demo"
    description = "问候演示"
    @property
    def parameters(self):
        return {"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}
    async def execute(self, args, ctx):
        return f"你好，{args.get('name','世界')}！"
''',
        )

        assert "greeting_demo" in reg, "技能应自动注册"

        skill = reg.get("greeting_demo")
        ctx = RunContext()
        result = await skill.execute({"name": "集成测试"}, ctx)
        assert "集成测试" in result

        # 编辑后重载
        code = mgr.get_skill_code("greeting_demo")
        assert code is not None

        # 重载
        reloaded = mgr.reload("greeting_demo")
        assert reloaded is not None
        assert reloaded.name == "greeting_demo"

    # ── 3. 编排引擎集成 ──

    @pytest.mark.asyncio
    async def test_orchestration_with_agents(self):
        """多 Agent 编排完整流程"""
        agent_a = self._make_echo_agent("agent_a")
        agent_b = self._make_echo_agent("agent_b")

        agents = {"a": agent_a, "b": agent_b}

        # DSL 编排
        flow = (
            Flow("integ_test")
            .then("step1", "a", "第一步: {topic}")
            .then("step2", "b", "第二步: {step1.output}")
            .output("last")
        )

        flow_def = flow.build()
        engine = FlowEngine()
        result = await engine.execute(flow_def, inputs={"topic": "集成测试"}, agents=agents)

        assert result.success, f"编排失败: {result.error}"
        assert "step1" in result.node_results
        assert "step2" in result.node_results
        assert result.output

    @pytest.mark.asyncio
    async def test_orchestration_yaml_parse(self):
        """YAML Flow 解析 + 执行"""
        yaml_content = """
name: yaml_test
nodes:
  - id: a
    agent: agent_a
    input: "YAML输入: {topic}"
  - id: b
    agent: agent_b
    input: "处理: {a.output}"
edges:
  - source: a
    target: b
"""
        flows = FlowParser.parse_string(yaml_content)
        assert len(flows) == 1
        assert flows[0].name == "yaml_test"

        agent_a = self._make_echo_agent("agent_a")
        agent_b = self._make_echo_agent("agent_b")

        result = await FlowEngine().execute(
            flows[0],
            inputs={"topic": "YAML测试"},
            agents={"agent_a": agent_a, "agent_b": agent_b},
        )
        assert result.success

    # ── 4. 记忆系统集成 ──

    @pytest.mark.asyncio
    async def test_memory_with_agent(self):
        """Agent 集成记忆系统"""
        db_path = os.path.join(self.tmpdir, "memory.db")
        memory = HybridMemory(db_path=db_path)

        reg = SkillRegistry()
        reg.register_many(EchoSkill())

        agent = Agent(
            config=AgentConfig(
                agent_id="mem_agent",
                system_prompt="你是一个测试助手。",
                skills=["echo"],
                llm=LLMConfig(api_key="mock"),
                verbose=False,
            ),
            llm=MockLLM(responses=[LLMResponse(content="最终的回复内容")]),
            registry=reg,
            memory=memory,
        )

        result = await agent.run("测试记忆集成")

        assert result.success

        # 验证消息存入记忆
        history = await memory.get_history("mem_agent")
        assert len(history) >= 2  # user + assistant
        assert history[0].role == "user"
        assert "测试记忆集成" in history[0].content

        # 验证 Token 记录
        stats = memory.get_stats("mem_agent")
        assert stats["messages"] >= 2
        assert stats["token_usage"]["total"] >= 0

    @pytest.mark.asyncio
    async def test_memory_recall_injection(self):
        """Agent 自动 recall 注入系统提示"""
        db_path = os.path.join(self.tmpdir, "recall.db")
        memory = HybridMemory(db_path=db_path)

        # 预先存入相关记忆
        await memory.add_message("recall_agent", "assistant", "用户之前询问过 AI Agent 框架的设计")

        reg = SkillRegistry()
        reg.register_many(EchoSkill())

        # 用能记录调用的 MockLLM
        mock_llm = MockLLM(responses=[LLMResponse(content="已参考历史记忆")])

        agent = Agent(
            config=AgentConfig(
                agent_id="recall_agent",
                system_prompt="你是助手。",
                skills=["echo"],
                llm=LLMConfig(api_key="mock"),
                verbose=False,
            ),
            llm=mock_llm,
            registry=reg,
            memory=memory,
        )

        await agent.run("AI Agent 框架有什么设计模式？")

        # 验证 LLM 调用中包含了记忆注入
        assert len(mock_llm.all_calls) > 0
        system_msg = mock_llm.all_calls[0]["messages"][0]
        assert system_msg["role"] == "system"
        # 系统提示中应包含相关记忆参考
        assert "记忆参考" in system_msg["content"] or "AI Agent" in system_msg["content"]

    # ── 5. 技能热重载集成 ──

    @pytest.mark.asyncio
    async def test_skill_hot_reload(self):
        """技能热重载即时生效"""
        reg = SkillRegistry()
        reg.register_many(EchoSkill())

        mgr = SkillManager(reg)
        skills_dir = os.path.join(self.tmpdir, "hot_reload_skills")
        mgr.create(name="hot_skill", description="热重载测试", target_dir=skills_dir)

        assert "hot_skill" in reg
        skill = reg.get("hot_skill")
        ctx = RunContext()
        r1 = await skill.execute({"input": "原始"}, ctx)
        assert "原始" in r1

        # 修改源码
        code = mgr.get_skill_code("hot_skill")
        new_code = code.replace('return f"技能', 'return f"[已热更新] 技能')
        mgr.save_skill_code("hot_skill", new_code)

        # 重载
        reloaded = mgr.reload("hot_skill")
        assert reloaded is not None

        # 验证新代码生效
        r2 = await reloaded.execute({"input": "新调用"}, ctx)
        assert "已热更新" in r2
        assert "新调用" in r2

    # ── 6. Workflow 端到端 ──

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """完整流水线: 技能加载 → Agent → 编排 → 记忆"""
        db_path = os.path.join(self.tmpdir, "full.db")
        memory = HybridMemory(db_path=db_path)

        reg = SkillRegistry()
        reg.register_many(EchoSkill(), CalculatorSkill())

        # 创建带记忆的 Agent
        agent = Agent(
            config=AgentConfig(
                agent_id="main",
                system_prompt="你是一个计算助手。用 calculator 计算。",
                skills=["echo", "calculator"],
                llm=LLMConfig(api_key="mock"),
                verbose=False,
            ),
            llm=MockLLM(responses=[
                LLMResponse(tool_calls=[ToolCall(id="c1", name="calculator",
                                                  args={"expr": "1+2"})]),
                LLMResponse(content="1+2的结果是3"),
            ]),
            registry=reg,
            memory=memory,
        )

        result = await agent.run("计算 1+2")

        assert result.success
        assert "3" in result.output

        # 确认记忆写入
        history = await memory.get_history("main")
        assert len(history) >= 2
        stats = memory.get_stats("main")
        assert stats["messages"] >= 2

        # 再次询问 — 验证记忆持久化
        agent.llm.responses = [LLMResponse(content="根据之前的对话")]

        mock2 = MockLLM(responses=[LLMResponse(content="根据记忆回复")])
        agent.llm = mock2

        result2 = await agent.run("刚才的结果是什么？")

        assert result2.success

        # 验证记忆系统保留了历史（短消息可能未向量化但 SQLite 保存了）
        history2 = await memory.get_history("main")
        assert len(history2) >= 4  # 两轮对话
        # user 消息应包含两轮的内容
        user_msgs = [m.content for m in history2 if m.role == "user"]
        assert any("计算 1+2" in m for m in user_msgs)
        assert any("刚才的结果" in m for m in user_msgs)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
