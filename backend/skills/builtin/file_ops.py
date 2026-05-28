"""
FileOps 技能 — 文件读写操作

包含: read_file, write_file, list_directory
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from backend.core.context import RunContext
from backend.skills.base import BaseSkill


class FileOpsSkill(BaseSkill):
    """文件操作技能 — 读取、写入、列出目录"""

    name = "file_ops"
    description = "文件系统操作：读取文件内容、写入文件、列出目录。工作区在项目根目录下。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "list"],
                    "description": "操作类型: read=读取, write=写入, list=列出目录",
                },
                "file_path": {
                    "type": "string",
                    "description": "文件路径（相对工作区根目录）",
                },
                "content": {
                    "type": "string",
                    "description": "写入内容（仅在 write 操作时使用）",
                },
                "directory": {
                    "type": "string",
                    "description": "要列出的目录路径（仅在 list 操作时使用，默认 .）",
                },
            },
            "required": ["operation"],
        }

    async def execute(self, args: dict[str, Any], ctx: RunContext) -> str:
        op: str = args.get("operation", "")

        if op == "read":
            return self._read_file(args)
        elif op == "write":
            return self._write_file(args)
        elif op == "list":
            return self._list_directory(args)
        else:
            return f"错误：不支持的操作 '{op}'，可选: read, write, list"

    # ---- 内部实现 ----

    def _resolve_path(self, user_path: str) -> Path:
        """将用户提供的路径解析为工作区内的绝对路径"""
        # 以项目根目录为基准
        root = Path.cwd().resolve()
        # 防止路径穿越
        target = (root / user_path).resolve()
        if not str(target).startswith(str(root)):
            raise PermissionError(f"路径 '{user_path}' 超出工作区范围")
        return target

    def _read_file(self, args: dict[str, Any]) -> str:
        path_str = args.get("file_path", "")
        if not path_str:
            return "错误：请提供 file_path"

        try:
            target = self._resolve_path(path_str)
        except PermissionError as e:
            return f"错误: {e}"

        if not target.exists():
            return f"错误：文件不存在: {path_str}"
        if not target.is_file():
            return f"错误：路径不是文件: {path_str}"

        try:
            content = target.read_text(encoding="utf-8")
            size = len(content)
            return f"文件: {path_str} ({size} 字符)\n\n```\n{content}\n```"
        except Exception as e:
            return f"读取文件失败: {e}"

    def _write_file(self, args: dict[str, Any]) -> str:
        path_str = args.get("file_path", "")
        content = args.get("content", "")

        if not path_str:
            return "错误：请提供 file_path"

        try:
            target = self._resolve_path(path_str)
        except PermissionError as e:
            return f"错误: {e}"

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"文件已写入: {path_str} ({len(content)} 字符)"
        except Exception as e:
            return f"写入文件失败: {e}"

    def _list_directory(self, args: dict[str, Any]) -> str:
        dir_str = args.get("directory", ".")
        try:
            target = self._resolve_path(dir_str)
        except PermissionError as e:
            return f"错误: {e}"

        if not target.exists():
            return f"错误：目录不存在: {dir_str}"
        if not target.is_dir():
            return f"错误：路径不是目录: {dir_str}"

        try:
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            lines = [f"目录: {dir_str}\n"]
            for entry in entries:
                suffix = "/" if entry.is_dir() else ""
                size = entry.stat().st_size if entry.is_file() else 0
                lines.append(f"  {entry.name}{suffix}  ({size} B)" if size else f"  {entry.name}{suffix}")
            return "\n".join(lines)
        except Exception as e:
            return f"列出目录失败: {e}"
