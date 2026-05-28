"""
AgentForge 一键启动

自动安装依赖、构建前端、启动后端 + 前端服务器。
双击运行或: python run.py
"""

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND_PORT = 8765
FRONTEND_PORT = 5183


def check_env() -> bool:
    """检查 .env 文件"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        example = ROOT / ".env.example"
        if example.exists():
            env_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            print("[!] .env 已从模板创建，请编辑填入 API Key 后重新运行")
            os.startfile(str(env_file))
            return False
    return True


def run_command(cmd: list[str], cwd: str | Path = ROOT, timeout: int = 300) -> bool:
    """运行命令并输出结果"""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            if err:
                print(f"  [WARN] {err[:200]}")
            return False
        return True
    except FileNotFoundError:
        return False
    except subprocess.TimeoutExpired:
        print(f"  [WARN] 命令超时")
        return False


def wait_for_server(url: str, max_retries: int = 15, interval: float = 2) -> bool:
    """等待服务器就绪"""
    import urllib.request
    for i in range(max_retries):
        try:
            r = urllib.request.urlopen(url, timeout=2)
            if r.status == 200:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def main():
    print("=" * 50)
    print("  AgentForge - One-Click Start")
    print("=" * 50)
    print()

    # 1. 检查 .env
    if not check_env():
        input("\n按回车退出...")
        return

    # 2. 检查 Python
    print("[..] 检查运行环境...")
    if sys.version_info < (3, 10):
        print("[ERROR] Python 3.10+  required")
        input("\n按回车退出...")
        return
    print("[OK] Python", sys.version_info.major, sys.version_info.minor)

    # 3. 安装依赖
    print("\n[..] 安装 Python 依赖...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt"), "-q"],
        capture_output=True,
    )
    print("[OK] Python 依赖就绪")

    # 4. 构建前端
    dist_dir = ROOT / "gui" / "dist-web"
    if not (dist_dir / "index.html").exists():
        # 检查 Node.js
        node_ok = run_command(["node", "--version"])
        if node_ok:
            print("[..] 构建前端...")
            run_command(["npm", "install"], cwd=ROOT / "gui")
            run_command(
                ["npx", "vite", "build", "--config", "vite.web.config.ts"],
                cwd=ROOT / "gui",
                timeout=120,
            )
            if (dist_dir / "index.html").exists():
                print("[OK] 前端构建完成")
            else:
                print("[WARN] 前端构建失败，仅启动后端")
                dist_dir = None
        else:
            print("[WARN] Node.js 未安装，仅启动后端")
            dist_dir = None
    else:
        print("[OK] 前端已构建")

    # 5. 启动后端
    print("\n[..] 启动后端服务...")
    backend_log = open(ROOT / "backend.log", "w", encoding="utf-8")
    backend_proc = subprocess.Popen(
        [sys.executable, "-X", "utf8", str(ROOT / "main.py")],
        cwd=ROOT,
        stdout=backend_log,
        stderr=subprocess.STDOUT,
    )

    print("[..] 等待后端就绪...")
    if wait_for_server(f"http://127.0.0.1:{BACKEND_PORT}/"):
        print(f"[OK] 后端运行中: http://127.0.0.1:{BACKEND_PORT}")
    else:
        print("[ERROR] 后端启动失败，查看 backend.log")
        backend_proc.terminate()
        input("\n按回车退出...")
        return

    # 6. 启动前端
    frontend_proc = None
    if dist_dir:
        print("[..] 启动前端界面...")

        # 启动前端服务器
        frontend_proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", str(ROOT / "serve_frontend.py")],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        time.sleep(2)
        if wait_for_server(f"http://127.0.0.1:{FRONTEND_PORT}/", max_retries=8, interval=2):
            print(f"[OK] 前端就绪: http://127.0.0.1:{FRONTEND_PORT}")
        else:
            print(f"[WARN] 前端启动稍慢，试试手动打开 http://127.0.0.1:{FRONTEND_PORT}")

    # 7. 显示信息并打开浏览器
    print()
    print("=" * 50)
    print("  AgentForge is running!")
    print()
    print("  BACKEND")
    print(f"    API:        http://127.0.0.1:{BACKEND_PORT}")
    print(f"    API docs:   http://127.0.0.1:{BACKEND_PORT}/docs")
    if frontend_proc:
        print()
        print("  FRONTEND")
        print(f"    Dashboard:  http://127.0.0.1:{FRONTEND_PORT}")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    print()

    # 打开浏览器
    if frontend_proc:
        webbrowser.open(f"http://127.0.0.1:{FRONTEND_PORT}")

    # 保持运行
    try:
        while True:
            time.sleep(1)
            # 检查进程是否还活着
            rc = backend_proc.poll()
            if rc is not None:
                print(f"\n[ERROR] 后端异常退出 (exit code={rc})，查看 backend.log")
                break
            if frontend_proc and frontend_proc.poll() is not None:
                print("\n[WARN] 前端已退出，后端仍在运行")
                frontend_proc = None
    except KeyboardInterrupt:
        print("\n[..] 正在停止服务...")
    finally:
        backend_proc.terminate()
        if frontend_proc:
            frontend_proc.terminate()
        try:
            backend_log.close()
        except Exception:
            pass
        print("[OK] 服务已停止")


if __name__ == "__main__":
    main()
