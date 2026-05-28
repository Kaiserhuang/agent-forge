# AgentForge 运行指南

## 环境要求

| 依赖 | 最低版本 | 用途 |
|---|---|---|
| Python | ≥ 3.10 | 后端引擎 |
| Node.js | ≥ 18 | Electron GUI |
| npm | ≥ 9 | 前端构建 |

---

## 一、安装依赖

```bash
# 1. Python 依赖
pip install -r agent-forge/requirements.txt

# 2. 可选：安装 anthropic SDK（仅当使用 Claude 时需要）
pip install anthropic

# 3. GUI 依赖
cd agent-forge/gui && npm install
```

---

## 二、配置 API Key

```bash
# 复制环境变量模板
cp agent-forge/.env.example agent-forge/.env
```

编辑 `.env`，填入你的 API Key（至少一个）：

```ini
# DeepSeek（推荐，性价比高）
DEEPSEEK_API_KEY=sk-your-deepseek-key

# OpenAI（可选）
OPENAI_API_KEY=sk-your-openai-key

# Anthropic Claude（可选）
ANTHROPIC_API_KEY=sk-ant-your-claude-key

# Ollama（本地，无需 Key）
OLLAMA_BASE_URL=http://localhost:11434/v1
```

---

## 三、启动方式

### 方式 A：Python 后端服务（推荐先启动这个）

```bash
# 启动 FastAPI 服务器（端口 8765）
python agent-forge/main.py

# 或指定端口
python agent-forge/main.py --port 8765
```

启动后访问：
- **API 文档:** http://127.0.0.1:8765/docs
- **REST API:** http://127.0.0.1:8765/
- **WebSocket:** ws://127.0.0.1:8765/ws

### 方式 B：CLI 交互模式

```bash
python agent-forge/main.py --cli
```

```
============================================================
  AgentForge v0.1.0 — CLI 交互模式
  输入你的问题，或输入 /quit 退出
============================================================
  Agent: 智能助手
  模型: deepseek-chat
  技能: web_search, file_ops, remember, recall_memory

>>> 搜索2025年AI Agent框架的最新发展
```

CLI 支持命令：
- `/quit` — 退出
- `/skills` — 查看可用技能

### 方式 C：Electron GUI 桌面应用

```bash
# 开发模式（Vite HMR 热更新）
cd agent-forge/gui && npm run dev

# 或先启动 Python 后端，再单独启动前端
python agent-forge/main.py              # 终端 1：后端
cd agent-forge/gui && npm run dev       # 终端 2：前端
```

Electron 会自动拉起 Python 后端，打开浏览器窗口访问：
- **聊天:** http://localhost:5173/#/chat
- **流程编排:** http://localhost:5173/#/flow-editor
- **Agent 管理:** http://localhost:5173/#/agents
- **技能管理:** http://localhost:5173/#/skills

### 方式 D：REST API 调用

```bash
# 对话
curl -X POST http://127.0.0.1:8765/api/run \
  -H "Content-Type: application/json" \
  -d '{"task": "搜索AI Agent最新发展"}'

# 查看技能
curl http://127.0.0.1:8765/api/skills/

# 服务状态
curl http://127.0.0.1:8765/api/status
```

---

## 四、API 参考

### REST 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | 服务状态 |
| `GET` | `/docs` | Swagger API 文档 |
| `GET` | `/api/status` | Agent 状态 |
| `GET` | `/api/skills/` | 技能列表 |
| `GET` | `/api/skills/user` | 用户自定义技能 |
| `GET` | `/api/skills/{name}/code` | 技能源码 |
| `POST` | `/api/skills/{name}/code` | 保存技能源码 |
| `POST` | `/api/skills/create` | 创建新技能 |
| `DELETE` | `/api/skills/{name}` | 删除技能 |
| `POST` | `/api/run` | 运行 Agent 任务 |
| `WS` | `/ws` | WebSocket 实时通信 |

### WebSocket 消息

**发送（客户端 → 服务端）:**

```json
{"type": "run_flow", "payload": {"task": "搜索AI发展"}}
{"type": "list_skills", "payload": {}}
{"type": "skill_create", "payload": {"name": "my_skill", "description": "..."}}
```

**接收（服务端 → 客户端）:**

```json
{"type": "agent_message", "payload": {"content": "正在搜索...", "delta": true}}
{"type": "flow_complete", "payload": {"output": "...", "total_tokens": 500}}
{"type": "flow_error", "payload": {"error": "..."}}
```

---

## 五、模型切换

修改 `backend/app.py` 中的 `create_default_agent()` 或在设置页面切换：

```python
# DeepSeek（默认）
LLMConfig(provider="deepseek", model="deepseek-chat")

# OpenAI
LLMConfig(provider="openai", model="gpt-4o")

# Claude
LLMConfig(provider="claude", model="claude-3-5-sonnet-20241022")

# Ollama 本地
LLMConfig(provider="ollama", model="llama3.2", base_url="http://localhost:11434/v1")
```

---

## 六、技能开发

### 创建自定义技能

创建 `.skills/<skill_name>/` 目录，包含两个文件：

**`.skills/my_tool/skill.yaml`:**
```yaml
name: my_tool
description: 我的自定义工具
parameters:
  type: object
  properties:
    input:
      type: string
  required: [input]
```

**`.skills/my_tool/impl.py`:**
```python
from typing import Any
from backend.skills.base import BaseSkill
from backend.core.context import RunContext

class MyToolSkill(BaseSkill):
    name = "my_tool"
    description = "我的自定义工具"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "输入"},
            },
            "required": ["input"],
        }

    async def execute(self, args: dict[str, Any], ctx: RunContext) -> str:
        return f"处理结果: {args.get('input', '')}"
```

服务启动时自动发现 `./.skills/` 和 `~/.agentforge/skills/` 下的技能包。

---

## 七、运行测试

```bash
# 全部 37 个测试
python -m pytest agent-forge/tests/ -v

# 仅编排测试
python -m pytest agent-forge/tests/test_orchestrator.py -v

# 仅记忆测试
python -m pytest agent-forge/tests/test_memory.py -v

# 仅集成测试
python -m pytest agent-forge/tests/test_integration.py -v
```

---

## 八、项目结构

```
agent-forge/
├── main.py                      # 入口（CLI / 服务器）
├── .env                         # API Key 配置
├── .skills/                     # 用户自定义技能
│   └── greeting/                
├── backend/                     # Python 后端
│   ├── core/                    # Agent 运行时 + 配置
│   ├── llm/                     # LLM 适配器（4 provider）
│   ├── skills/                  # 技能系统（内置 + 动态加载）
│   ├── orchestrator/            # 编排引擎（DAG + DSL）
│   ├── memory/                  # 混合记忆（SQLite + LanceDB）
│   └── server/                  # HTTP + WebSocket 服务
├── gui/                         # Electron 桌面应用
│   ├── electron/                # 主进程
│   └── src/                     # React 前端
│       ├── Chat/                # 聊天界面
│       ├── FlowCanvas/          # 流程编排画布
│       ├── AgentManager/        # Agent 管理
│       └── SkillManager/        # 技能编辑器
├── examples/                    # 示例
└── tests/                       # 37 个测试
```
