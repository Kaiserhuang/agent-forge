"""
Agent 运行时 — LLM 工具调用主循环

核心流程:
  1. 构建 messages (system + task + history)
  2. 调用 LLM
  3. 若 LLM 返回 tool_calls → 执行技能 → 追加结果 → 回到 2
  4. 若 LLM 返回纯文本 → 返回最终结果
  5. 超过 max_iterations → 抛出异常
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.core.config import AgentConfig, LLMConfig, Message, ToolCall
from backend.core.context import RunContext
from backend.llm.base import BaseLLM, LLMResponse
from backend.llm.deepseek_adapter import DeepSeekAdapter
from backend.skills.base import BaseSkill
from backend.skills.registry import SkillRegistry
from backend.memory.hybrid_memory import HybridMemory


@dataclass
class StepLog:
    """Agent 运行的每一步日志"""
    iteration: int
    request_messages: list[dict] = field(default_factory=list)
    response: LLMResponse | None = None
    skill_results: list[dict] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class AgentResult:
    """Agent 运行最终结果"""
    agent_id: str
    output: str
    iterations: int = 0
    total_tokens: int = 0
    token_usage: dict | None = None
    steps: list[StepLog] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    success: bool = True
    error: str | None = None


class Agent:
    """
    Agent 运行时

    使用示例:
        agent = Agent(
            config=AgentConfig(
                agent_id="assistant",
                system_prompt="你是一个有用的助手。",
                skills=["web_search", "file_ops"],
            ),
            llm=DeepSeekAdapter(LLMConfig()),
            registry=skill_registry,
        )
        result = await agent.run("搜索 AI Agent 的最新发展")
    """

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLLM | None = None,
        registry: SkillRegistry | None = None,
        memory: HybridMemory | None = None,
    ):
        self.config = config
        self.llm = llm or DeepSeekAdapter(config.llm)

        # 技能注册中心 — 若未传入则创建空注册表
        self.registry = registry or SkillRegistry()

        # 记忆系统
        self.memory = memory

        # 从 config.skills 名称列表解析技能实例
        self._skill_instances: list[BaseSkill] = []
        for skill_name in config.skills:
            try:
                self._skill_instances.append(self.registry.get(skill_name))
            except KeyError:
                pass  # 技能不存在，跳过（运行时调用时会报错）

        # 运行时状态
        self.history: list[Message] = []
        self._current_session_id: str | None = None

    # ---- 公开接口 ----

    async def run(
        self,
        task: str,
        context: RunContext | None = None,
    ) -> AgentResult:
        """
        执行一次 Agent 任务

        Args:
            task: 用户任务描述
            context: 可选运行上下文，若不传则自动创建

        Returns:
            AgentResult 包含最终输出和运行统计
        """
        start_time = datetime.now(timezone.utc)
        ctx = context or RunContext(
            agent_id=self.config.agent_id,
            agent_name=self.config.name,
            max_iterations=self.config.max_iterations,
            verbose=self.config.verbose,
        )

        # 构建初始消息
        messages: list[Message] = []
        system_prompt = self.config.system_prompt

        # 记忆 recall：检索相关上下文注入 system prompt
        if self.memory and self.memory._auto_vectorize:
            recalled = await self.memory.recall(
                query=task,
                agent_id=self.config.agent_id,
                top_k=3,
            )
            if recalled:
                memory_context = "\n".join(
                    f"[{item.role}] {item.content[:200]}"
                    for item in recalled
                )
                system_prompt += (
                    f"\n\n**相关记忆参考:**\n{memory_context}"
                )
                if self.config.verbose:
                    print(f"[记忆] 注入 {len(recalled)} 条相关记忆")

        messages.append(Message.system(system_prompt))
        messages.append(Message.user(task))

        steps: list[StepLog] = []
        final_output = ""

        # 注入 memory 到上下文（技能可通过 ctx.get("_memory") 访问）
        ctx.set("_memory", self.memory)

        # 记录 user 消息到记忆
        if self.memory and task:
            await self.memory.add_message(
                agent_id=self.config.agent_id,
                role="user",
                content=task,
            )

        for iteration in range(1, self.config.max_iterations + 1):
            ctx.iteration = iteration

            if self.config.verbose:
                print(f"\n{'='*60}")
                print(f"[Agent:{self.config.agent_id}] 迭代 {iteration}/{self.config.max_iterations}")
                print(f"{'='*60}")

            # ---- 调用 LLM ----

            step = StepLog(iteration=iteration, timestamp=datetime.now(timezone.utc).isoformat())

            # 构建技能列表（每次重新获取，支持运行时热更新）
            active_skills = self._resolve_skills(ctx)
            tool_defs = [s.to_tool_def() for s in active_skills]

            step.request_messages = [m.model_dump(exclude_none=True) for m in messages]

            llm_response = await self.llm.chat(
                messages=messages,
                tools=tool_defs if tool_defs else None,
            )
            step.response = llm_response

            if self.config.verbose:
                if llm_response.content:
                    preview = llm_response.content[:200]
                    print(f"\n[LLM] 回复: {preview}")
                if llm_response.tool_calls:
                    for tc in llm_response.tool_calls:
                        print(f"\n[LLM] 调用工具: {tc.name}(args={json.dumps(tc.args, ensure_ascii=False)})")

            # ---- 处理 LLM 响应 ----

            # 追加 assistant 消息
            assistant_msg = Message.assistant(
                content=llm_response.content,
                tool_calls=llm_response.tool_calls,
            )
            messages.append(assistant_msg)
            self.history.append(assistant_msg)

            # 记录 assistant 消息到记忆
            if self.memory and llm_response.content:
                await self.memory.add_message(
                    agent_id=self.config.agent_id,
                    role="assistant",
                    content=llm_response.content,
                )

            # 若有工具调用 — 执行技能
            if llm_response.tool_calls:
                for tc in llm_response.tool_calls:
                    skill_result = await self._execute_tool(
                        tc, active_skills, ctx
                    )
                    step.skill_results.append({
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "result": skill_result,
                    })

                    # 追加 tool 消息
                    tool_msg = Message.tool(
                        content=skill_result,
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                    messages.append(tool_msg)
                    self.history.append(tool_msg)

                    # 记录 tool 结果到记忆
                    if self.memory:
                        await self.memory.add_message(
                            agent_id=self.config.agent_id,
                            role="tool",
                            content=skill_result[:500],
                            metadata={"skill": tc.name, "tool_call_id": tc.id},
                        )

                    if self.config.verbose:
                        print(f"\n[技能] {tc.name} 返回: {skill_result[:200]}")

                steps.append(step)
                continue  # 继续下一轮迭代

            # 无工具调用 → LLM 返回最终文本
            final_output = llm_response.content or ""
            steps.append(step)
            break

        else:
            # 循环正常结束（达到 max_iterations 未 break）
            final_output = final_output or f"已达到最大迭代次数 ({self.config.max_iterations})，任务可能未完成。"

        # ---- 统计 ----
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        total_tokens = 0
        token_usage = None
        if steps:
            last = steps[-1].response
            if last and last.usage:
                token_usage = last.usage
                total_tokens = last.usage.get("total_tokens", 0)

        # 记录到历史
        self.history.append(Message.assistant(content=final_output))

        # 记录 token 使用
        if self.memory and token_usage:
            self.memory.record_token_usage(
                agent_id=self.config.agent_id,
                prompt_tokens=token_usage.get("prompt_tokens", 0),
                completion_tokens=token_usage.get("completion_tokens", 0),
            )

        return AgentResult(
            agent_id=self.config.agent_id,
            output=final_output,
            iterations=len(steps),
            total_tokens=total_tokens,
            token_usage=token_usage,
            steps=steps,
            elapsed_seconds=elapsed,
            success=True,
        )

    # ---- 内部方法 ----

    def _resolve_skills(self, ctx: RunContext) -> list[BaseSkill]:
        """解析当前可用的技能列表"""
        skills: list[BaseSkill] = []
        for skill_name in self.config.skills:
            try:
                skills.append(self.registry.get(skill_name))
            except KeyError:
                if ctx.verbose:
                    print(f"[警告] 技能 '{skill_name}' 未注册，跳过")
        return skills

    async def _execute_tool(
        self,
        tc: ToolCall,
        skills: list[BaseSkill],
        ctx: RunContext,
    ) -> str:
        """执行单个工具调用"""
        # 查找匹配的技能
        for skill in skills:
            if skill.name == tc.name:
                try:
                    result = await skill.execute(tc.args, ctx)
                    return str(result)
                except Exception as e:
                    return f"技能 '{tc.name}' 执行错误: {e}"

        return f"错误：未找到技能 '{tc.name}'。可用技能: {[s.name for s in skills]}"
