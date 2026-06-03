"""
DS Agent 桌面应用 — pywebview 轻量版
无需 Node.js / Electron，只用 Python

启动: python desktop.py
"""

import sys
import os

if sys.platform == "win32":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass
import json
import time
import threading
import subprocess
import urllib.request

APP_URL = os.environ.get("DSAGENT_URL", "http://127.0.0.1:8000/dashboard")
APP_TITLE = "DS Agent — AI 运营指挥中心"
WIDTH, HEIGHT = 1440, 900


def check_backend(url: str, timeout: int = 30) -> bool:
    """检查后端是否就绪"""
    health_url = url.replace("/dashboard", "/health")
    for i in range(timeout):
        try:
            resp = urllib.request.urlopen(health_url, timeout=2)
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def start_docker():
    """启动 Docker 后端"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=script_dir, capture_output=True, timeout=60,
        )
    except Exception:
        try:
            subprocess.run(
                ["docker-compose", "up", "-d"],
                cwd=script_dir, capture_output=True, timeout=60,
            )
        except Exception:
            pass


def main():
    print(f"🚀 DS Agent Desktop")
    print(f"   Backend: {APP_URL}")

    # 检查后端
    if not check_backend(APP_URL, timeout=3):
        print("   Backend not running, starting Docker...")
        start_docker()
        print("   Waiting for server...")
        if not check_backend(APP_URL, timeout=30):
            print("   ⚠️  Backend did not start in time. Starting anyway...")

    print(f"   Opening desktop window...")

    try:
        import webview
        # 创建窗口
        window = webview.create_window(
            title=APP_TITLE,
            url=APP_URL,
            width=WIDTH,
            height=HEIGHT,
            min_size=(1024, 680),
            resizable=True,
            fullscreen=False,
            confirm_close=True,
        )
        webview.start(debug=False, http_server=False)
    except ImportError:
        print("   pywebview not installed. Installing...")
        env = {**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": ""}
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview"], env=env)
        import webview
        window = webview.create_window(
            title=APP_TITLE, url=APP_URL, width=WIDTH, height=HEIGHT,
            min_size=(1024, 680), resizable=True, confirm_close=True,
        )
        webview.start(debug=False, http_server=False)


if __name__ == "__main__":
    main()
