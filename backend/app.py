"""
AgentForge 服务器入口

提供:
1. FastAPI + WebSocket 服务（为 Electron GUI 准备）
2. 命令行交互模式 (python -m backend.app --cli)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.core.agent import Agent
from backend.core.config import AgentConfig, LLMConfig
from backend.llm.deepseek_adapter import DeepSeekAdapter
from backend.server.api_routes import router as api_router, init_routes
from backend.server.ws_handler import WebSocketHandler
from backend.server.skill_routes import router as skill_router, init_skill_routes
from backend.memory.hybrid_memory import HybridMemory
from backend.skills.builtin import FileOpsSkill, WebSearchSkill, RememberSkill, RecallMemorySkill
from backend.skills.registry import SkillRegistry
from backend.skills.manager import SkillManager

# 加载 .env 文件（DEEPSEEK_API_KEY）
load_dotenv()

# ---- FastAPI 应用 ----

app = FastAPI(title="AgentForge", version="0.1.0")

# CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ws_handler = WebSocketHandler()

# 注册路由
app.include_router(api_router)
app.include_router(skill_router)


def create_default_agent() -> Agent:
    """创建默认 Agent（含内置技能）"""
    config = AgentConfig(
        agent_id="assistant",
        name="智能助手",
        system_prompt=(
            "你是一个功能强大的 AI 助手。你可以使用以下工具来帮助用户：\n"
            "1. web_search — 搜索互联网获取实时信息\n"
            "2. file_ops — 读写文件、列出目录\n\n"
            "当用户的问题需要实时或最新信息时，请使用 web_search 工具搜索。\n"
            "如果需要操作文件，请使用 file_ops 工具。\n"
            "在给出最终答案时，请引用你使用的信息来源。"
        ),
        llm=LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        ),
        skills=["web_search", "file_ops"],
        verbose=True,
    )

    # 注册技能（含记忆技能）
    registry = SkillRegistry()
    registry.register_many(
        WebSearchSkill(), FileOpsSkill(),
        RememberSkill(), RecallMemorySkill(),
    )

    # 创建记忆系统
    memory = HybridMemory(db_path="data/agentforge.db")

    # 创建 LLM 适配器
    llm_adapter = DeepSeekAdapter(config.llm)

    agent = Agent(
        config=config,
        llm=llm_adapter,
        registry=registry,
        memory=memory,
    )
    return agent


@app.on_event("startup")
async def startup() -> None:
    """应用启动时初始化 Agent"""
    agent = create_default_agent()
    ws_handler.set_agent(agent)
    init_routes(ws_handler)
    init_skill_routes(ws_handler)

    # 动态加载用户技能
    mgr = SkillManager(agent.registry)
    count = mgr.discover()
    if count > 0:
        print(f"   ⚡ 动态加载 {count} 个用户技能")

    print(f"[OK] AgentForge 服务已启动")
    print(f"   模型: {agent.config.llm.model}")
    skills_list = [s['name'] for s in agent.registry.list_skills()]
    print(f"   技能: {skills_list}")


@app.get("/")
async def root() -> dict:
    return {
        "name": "AgentForge",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws_handler.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            await ws_handler.handle_message(ws, raw)
    except WebSocketDisconnect:
        ws_handler.disconnect(ws)


# ---- CLI 交互模式 ----

async def cli_mode() -> None:
    """命令行交互模式"""
    print("=" * 60)
    print("  AgentForge v0.1.0 — CLI 交互模式")
    print("  输入你的问题，或输入 /quit 退出")
    print("=" * 60)

    agent = create_default_agent()

    print(f"  Agent: {agent.config.name}")
    print(f"  模型: {agent.config.llm.model}")
    skills = agent.registry.list_skills()
    print(f"  技能: {', '.join(s['name'] for s in skills)}")
    print()

    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            print("再见！")
            break
        if user_input == "/skills":
            for s in skills:
                print(f"  - {s['name']}: {s['description']}")
            continue

        print(f"\n[运行中...] (需要 DEEPSEEK_API_KEY)")
        result = await agent.run(user_input)

        print(f"\n{'='*60}")
        print(f"最终输出:")
        print(f"{result.output}")
        print(f"{'='*60}")
        print(f"迭代: {result.iterations} | Token: {result.total_tokens} | 耗时: {result.elapsed_seconds:.1f}s")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentForge 服务")
    parser.add_argument("--cli", action="store_true", help="启动 CLI 交互模式")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8765, help="监听端口")
    args = parser.parse_args()

    if args.cli:
        asyncio.run(cli_mode())
    else:
        print(f"启动服务器: http://{args.host}:{args.port}")
        print(f"WebSocket:   ws://{args.host}:{args.port}/ws")
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
