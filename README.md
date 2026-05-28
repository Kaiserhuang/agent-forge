# AgentForge

<div align="center">

**通用 LLM Agent 框架 — 技能扩展 · 多 Agent 编排 · 混合记忆 · Windows GUI**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5%2B-3178C6)](https://www.typescriptlang.org/)
[![Electron](https://img.shields.io/badge/Electron-31%2B-47848F)](https://www.electronjs.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

</div>

---

## 概述

AgentForge 是一个基于通用大语言模型的 Agent 框架，提供完整的 **Agent 运行时 + 技能系统 + 多 Agent 编排 + 记忆持久化** 能力，并附带 Windows 桌面图形界面。

### 核心特性

- 🤖 **Agent 运行时** — LLM 工具调用循环，支持 DeepSeek / OpenAI / Claude / Ollama
- 🧩 **技能系统** — 内置技能 + 文件系统动态加载 + GUI 在线编辑器
- 🔀 **多 Agent 编排** — DAG 执行引擎，支持链式 / 扇出 / 汇聚 / 条件门 / 循环
- 🧠 **混合记忆** — SQLite 精确历史 + LanceDB 语义检索
- 🖥️ **Windows GUI** — Electron + React + React Flow 拖拽画布
- 🔌 **即插即用** — REST API + WebSocket 双接口

---

## 快速开始

### 环境要求

- Python ≥ 3.10
- Node.js ≥ 18

### 1. 克隆并安装

```bash
git clone https://github.com/your-username/agent-forge.git
cd agent-forge

# Python 后端
pip install -r requirements.txt

# 前端 GUI（可选）
cd gui && npm install && cd ..
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env` 填入至少一个 API Key：

```ini
DEEPSEEK_API_KEY=sk-your-key    # 推荐
# OPENAI_API_KEY=sk-your-key
# ANTHROPIC_API_KEY=sk-ant-your-key
```

### 3. 启动

**方式 A：后端服务 + 浏览器 GUI（推荐）**

```bash
# 终端 1：启动后端
python main.py

# 终端 2：构建并启动前端
cd gui
npx vite build --config vite.web.config.ts
python -m http.server 5183 -d dist-web
```

打开 http://127.0.0.1:5183

**方式 B：CLI 交互模式**

```bash
python main.py --cli
```

**方式 C：REST API**

```bash
curl -X POST http://127.0.0.1:8765/api/run \
  -H "Content-Type: application/json" \
  -d '{"task": "你好"}'
```

---

## 架构

```
┌─ Browser / Electron ──────────────────────────┐
│  React + React Flow GUI                       │
│  ┌─Chat──┐ ┌─Flow Editor──┐ ┌─Skill Editor──┐│
│  └───────┘ └──────────────┘ └───────────────┘│
└────────────────────┬──────────────────────────┘
                     │ HTTP / WebSocket
┌─ Python Backend ───▼──────────────────────────┐
│  Agent Runtime   ◄──  LLM Adapter Layer       │
│  (tool-call loop)     ├─ DeepSeek             │
│                       ├─ OpenAI               │
│  Orchestrator         ├─ Claude               │
│  (DAG Engine)         └─ Ollama               │
│                                              │
│  Skill Registry ◄──  Dynamic Loader          │
│  Hybrid Memory  ◄──  SQLite + LanceDB        │
└──────────────────────────────────────────────┘
```

### 项目结构

```
agent-forge/
├── main.py                   # 入口（CLI / 服务器）
├── .env.example              # API Key 模板
├── .skills/                  # 用户自定义技能
│   └── greeting/
├── backend/                  # Python 后端
│   ├── core/                 # Agent 运行时 + 配置
│   │   ├── agent.py          # Agent 主循环
│   │   ├── config.py         # 数据模型
│   │   └── context.py        # 运行上下文
│   ├── llm/                  # LLM 适配器
│   │   ├── deepseek_adapter.py
│   │   ├── openai_adapter.py
│   │   ├── claude_adapter.py
│   │   ├── ollama_adapter.py
│   │   └── factory.py        # 模型工厂
│   ├── skills/               # 技能系统
│   │   ├── base.py           # 技能抽象
│   │   ├── registry.py       # 注册中心
│   │   ├── loader.py         # 动态加载
│   │   ├── manager.py        # 技能管理
│   │   └── builtin/          # 内置技能
│   ├── orchestrator/         # 编排引擎
│   │   ├── models.py         # DAG 数据模型
│   │   ├── engine.py         # DAG 执行器
│   │   ├── dsl.py            # Python DSL
│   │   └── parser.py         # YAML 解析器
│   ├── memory/               # 记忆系统
│   │   ├── sqlite_store.py   # SQLite 存储
│   │   ├── vector_store.py   # LanceDB 向量库
│   │   ├── embeddings.py     # 嵌入函数
│   │   └── hybrid_memory.py  # 混合管理器
│   └── server/               # API 服务
│       ├── api_routes.py     # REST 路由
│       ├── ws_handler.py     # WebSocket 处理
│       └── skill_routes.py   # 技能管理 API
├── gui/                      # Electron + React
│   ├── electron/             # 主进程
│   └── src/                  # React 前端
│       ├── Chat/             # 对话界面
│       ├── FlowCanvas/       # 编排画布
│       ├── AgentManager/     # Agent 管理
│       └── SkillManager/     # 技能编辑器
├── tests/                    # 测试 (37 个)
└── examples/                 # 示例
```

---

## 核心功能详解

### Agent 运行时

每个 Agent 是一个独立的消息循环：

```
Agent.run(task)
  ├→ 构建 system prompt + 挂载技能工具列表
  ├→ LLM 调用 → 有 tool_call?
  │   ├→ 是 → 执行技能 → 追加结果 → 继续调用
  │   └→ 否 → 返回最终文本
  └→ 到达 max_iterations → 优雅终止
```

### 技能系统

两种技能来源：

| 来源 | 位置 | 示例 |
|---|---|---|
| **内置** | `backend/skills/builtin/` | web_search, file_ops, remember |
| **动态** | `.skills/<name>/skill.yaml + impl.py` | 用户自定义 |

技能包格式：

```yaml
# .skills/my_tool/skill.yaml
name: my_tool
description: 我的自定义工具
parameters:
  type: object
  properties:
    input:
      type: string
      description: 输入文本
  required: [input]
```

```python
# .skills/my_tool/impl.py
class MyToolSkill(BaseSkill):
    name = "my_tool"
    async def execute(self, args, ctx):
        return f"结果: {args.get('input', '')}"
```

### 多 Agent 编排

**Python DSL：**

```python
flow = (
    Flow("research")
    .then("research", "researcher", "调研: {topic}")
    .then("write", "writer", "写作: {research.output}")
    .then("review", "reviewer", "审阅: {write.output}", use_blackboard=True)
    .output("all")
)
result = await FlowEngine().execute(flow.build(), inputs={"topic": "AI"}, agents=agents)
```

**YAML 声明式：**

```yaml
nodes:
  - id: research
    agent: researcher
    input: "调研: {topic}"
  - id: write
    agent: writer
    input: "写作: {research.output}"
```

**高级编排特性：**

| DSL 方法 | 功能 |
|---|---|
| `.retry(id, agent, input, max_retries=3)` | 失败自动重试 |
| `.loop(id, agent, input, max_iterations=5)` | 循环执行 |
| `.gate(id, expression, true_target, false_target)` | 条件分支 |
| `.transform(id, template)` | 纯文本变换 |

### 混合记忆

```
Agent.run(task)
  ├→ recall(query, top_k=3)   ← LanceDB 语义检索 + SQLite 关键词补充
  │     → 注入到 system prompt
  ├→ LLM 循环 → 每条消息自动写入 SQLite + 长文本向量化
  └→ 记录 Token 用量
```

---

## API 参考

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | 服务状态 |
| `POST` | `/api/run` | 运行 Agent |
| `GET` | `/api/skills/` | 技能列表 |
| `POST` | `/api/update-key` | 更新 API Key |
| `WS` | `/ws` | WebSocket 实时通信 |

### WebSocket 消息

```json
// 发送
{"type": "run_flow", "payload": {"task": "搜索AI发展"}}

// 接收
{"type": "flow_complete", "payload": {"output": "...", "total_tokens": 500}}
{"type": "flow_error", "payload": {"error": "..."}}
```

---

## 模型支持

| Provider | 适配器 | 环境变量 | 默认模型 |
|---|---|---|---|
| DeepSeek | `DeepSeekAdapter` | `DEEPSEEK_API_KEY` | deepseek-chat |
| OpenAI | `OpenAIAdapter` | `OPENAI_API_KEY` | gpt-4o |
| Claude | `ClaudeAdapter` | `ANTHROPIC_API_KEY` | claude-3-5-sonnet |
| Ollama | `OllamaAdapter` | 无需 Key | llama3.2 |

```python
from backend.llm import create_llm

llm = create_llm(LLMConfig(provider="openai", model="gpt-4o"))
llm = create_llm(LLMConfig(provider="ollama", model="llama3.2"))
```

---

## 测试

```bash
# 全部 37 个测试
python -m pytest tests/ -v

# 单独运行
python -m pytest tests/test_orchestrator.py -v
python -m pytest tests/test_memory.py -v
python -m pytest tests/test_integration.py -v
```

---

## 开发路线

- [x] Phase 1 — Agent 运行时 + DeepSeek + 内置技能
- [x] Phase 2 — 多 Agent 编排引擎 (DAG + YAML + Python DSL)
- [x] Phase 3 — Electron + React GUI
- [x] Phase 4 — 混合记忆系统 (SQLite + LanceDB)
- [x] Phase 5 — 技能动态加载 + Skill Editor
- [x] Phase 6 — 多模型支持 + 高级编排特性

---

## 许可证

[MIT](LICENSE)
