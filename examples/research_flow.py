"""
AgentForge DSL 示例 — 调研→写作→审阅 流水线

运行方式:
    python examples/research_flow.py
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import (
    Agent, AgentConfig, LLMConfig, Flow, FlowEngine, FlowResult,
    SkillRegistry, DeepSeekAdapter,
)
from backend.skills.builtin import WebSearchSkill, FileOpsSkill


def create_agent(
    agent_id: str,
    system_prompt: str,
    skills: list[str],
    temperature: float = 0.7,
) -> Agent:
    """创建一个带 DeepSeek 和技能的 Agent"""
    registry = SkillRegistry()
    registry.register_many(WebSearchSkill(), FileOpsSkill())

    config = AgentConfig(
        agent_id=agent_id,
        name=agent_id,
        system_prompt=system_prompt,
        skills=skills,
        llm=LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
        ),
        temperature=temperature,
        verbose=True,
    )

    llm = DeepSeekAdapter(config.llm)
    return Agent(config=config, llm=llm, registry=registry)


async def main():
    # 1. 创建三个 Agent
    researcher = create_agent(
        "researcher",
        "你是一个专业的研究员，善于收集和分析信息。",
        skills=["web_search"],
        temperature=0.5,
    )

    writer = create_agent(
        "writer",
        "你是专业的技术文档写手。",
        skills=["file_ops"],
    )

    reviewer = create_agent(
        "reviewer",
        "你是严谨的审稿编辑。",
        skills=[],
        temperature=0.3,
    )

    agents = {
        "researcher": researcher,
        "writer": writer,
        "reviewer": reviewer,
    }

    # 2. 用 DSL 编排流程
    flow = (
        Flow("research_report")
        .describe("调研→写作→审阅 流水线")
        .then("research", "researcher", "请全面调研: {topic}")
        .then(
            "write_draft", "writer",
            "根据调研写报告:\n{research.output}",
        )
        .then(
            "review", "reviewer",
            "审阅报告:\n{write_draft.output}",
            use_blackboard=True,
        )
        .output("all")
        .communication("hybrid")
    )

    # 3. 执行
    engine = FlowEngine()
    print(f"▶ 启动 Flow: {flow.build().name}")
    print(f"   Agents: {list(agents.keys())}")
    print()

    result = await engine.execute(
        flow.build(),
        inputs={"topic": "2025年AI Agent框架的发展趋势"},
        agents=agents,
    )

    # 4. 输出结果
    print(f"\n{'='*60}")
    print(f"Flow 执行完成")
    print(f"  成功: {result.success}")
    print(f"  耗时: {result.elapsed_seconds:.1f}s")
    print(f"  Token: {result.total_tokens}")
    print(f"{'='*60}")

    if isinstance(result.output, dict):
        for node_id, output in result.output.get("node_outputs", {}).items():
            print(f"\n── [{node_id}] ──")
            print(output[:500] + "..." if len(output) > 500 else output)


if __name__ == "__main__":
    asyncio.run(main())
