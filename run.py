#!/usr/bin/env python3
"""
DS Agent 一键启动脚本
用法:
  python run.py                              # 启动 API 服务
  python run.py --all                        # 启动全部服务 (API + MCP)
  python run.py --mcp-only                   # 仅启动 MCP Mock 服务
  python run.py --test                       # 运行端到端测试
"""

import os
import sys
import subprocess
import argparse
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def start_api(host="127.0.0.1", port=8000, reload=False):
    """启动 Agent API"""
    print("🚀 启动 DS Agent API...")
    os.chdir("src")
    cmd = [sys.executable, "main.py", "--host", host, "--port", str(port)]
    if reload:
        cmd.append("--reload")
    subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))


def start_mcp(server_name, port):
    """启动单个 MCP Server"""
    print(f"  🔧 启动 {server_name} MCP Server (port {port})...")
    env = os.environ.copy()
    env["MCP_SERVER"] = server_name
    env["MCP_PORT"] = str(port)

    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", f"mcp.{server_name}_server:app",
         "--host", "0.0.0.0", "--port", str(port)],
        cwd="src",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process


def start_all_mcp():
    """启动全部 MCP Mock 服务"""
    print("🔧 启动 MCP Mock 服务...")
    processes = [
        start_mcp("lingxing", 8001),
        start_mcp("amazon_sp", 8002),
        start_mcp("ad_api", 8003),
    ]
    print("✅ MCP 服务已启动:")
    print("   领星 ERP:   http://localhost:8001")
    print("   亚马逊 SP:  http://localhost:8002")
    print("   广告 API:   http://localhost:8003")
    return processes


def run_test():
    """端到端测试"""
    import asyncio
    import httpx

    async def test():
        print("🧪 DS Agent 端到端测试")
        print("=" * 50)

        async with httpx.AsyncClient(timeout=30) as client:
            # 1. Health check
            print("\n1️⃣ 健康检查...")
            resp = await client.get("http://127.0.0.1:8000/health")
            data = resp.json()
            print(f"   Status: {data['status']}")
            print(f"   Agents: {data['components']['agents_registered']}")
            print(f"   Workflows: {data['components']['workflows_loaded']}")

            # 2. MCP status
            print("\n2️⃣ MCP Server 连接...")
            try:
                resp = await client.get("http://127.0.0.1:8000/mcp/status")
                print(f"   {resp.json()}")
            except Exception:
                print("   ⚠️ MCP Server 未启动 (Mock 模式下不影响)")

            # 3. Intent detection
            print("\n3️⃣ 意图识别测试...")
            queries = [
                "BT001黑色库存还剩多少？",
                "昨天的广告ACOS怎么样？",
                "SPK001利润是不是亏了？",
                "有没有新的跟卖？",
                "帮我生成昨天的运营日报",
            ]
            for q in queries:
                resp = await client.post("http://127.0.0.1:8000/chat", json={"message": q})
                data = resp.json()
                print(f"   Q: {q}")
                print(f"   → Intent: {data['intent']} (confidence: {data['confidence']:.0%})")
                print(f"   → Workflow: {data['workflow_used']}")
                print(f"   → Duration: {data['duration_ms']}ms")

            # 4. Agent direct call
            print("\n4️⃣ Agent 直接调用...")
            resp = await client.post(
                "http://127.0.0.1:8000/agents/run",
                json={"agent_name": "inventory"},
            )
            data = resp.json()
            result = data.get("result", {})
            print(f"   库存分析: {result.get('status', 'unknown')}")
            summary = result.get("summary", {})
            print(f"   总SKU: {summary.get('total_skus', 0)}")
            print(f"   健康: {summary.get('healthy', 0)} | 预警: {summary.get('warning', 0)} | 严重: {summary.get('critical', 0)}")

            # 5. List workflows
            print("\n5️⃣ 工作流列表...")
            resp = await client.get("http://127.0.0.1:8000/workflows")
            data = resp.json()
            for wf in data.get("workflows", []):
                print(f"   📋 {wf['name']}: {wf['description']}")

        print("\n" + "=" * 50)
        print("✅ 端到端测试完成！")

    asyncio.run(test())


def main():
    parser = argparse.ArgumentParser(description="DS Agent 一键启动")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--all", action="store_true", help="启动全部服务 (API + MCP)")
    parser.add_argument("--mcp-only", action="store_true", help="仅启动 MCP 服务")
    parser.add_argument("--test", action="store_true", help="运行端到端测试")
    parser.add_argument("--dev", action="store_true", help="开发模式 (自动重载)")
    args = parser.parse_args()

    if args.test:
        run_test()
        return

    print("🚀 DS Agent — 跨境电商 AI Agent 一键启动")
    print("=" * 50)

    if args.mcp_only:
        processes = start_all_mcp()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 关闭 MCP 服务...")
            for p in processes:
                p.terminate()
        return

    if args.all:
        mcp_procs = start_all_mcp()
        time.sleep(2)  # 等待 MCP 服务就绪

    try:
        start_api(host=args.host, port=args.port, reload=args.dev)
    except KeyboardInterrupt:
        print("\n👋 DS Agent 已停止")

    if args.all:
        for p in mcp_procs:
            p.terminate()


if __name__ == "__main__":
    main()
