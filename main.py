#!/usr/bin/env python3
"""
AgentForge v0.1.0 — 快速入口

用法:
    python main.py              # 启动服务器 (http://localhost:8765)
    python main.py --cli        # 启动 CLI 交互模式
    python main.py --help       # 查看帮助
"""

from backend.app import main

if __name__ == "__main__":
    main()
