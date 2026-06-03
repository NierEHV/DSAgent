"""
MCP Server 启动器
根据 MCP_SERVER 环境变量启动对应的服务

用法:
  MCP_SERVER=lingxing  python run_server.py --port 8001
  MCP_SERVER=amazon_sp python run_server.py --port 8002
  MCP_SERVER=ad_api    python run_server.py --port 8003
"""

import os
import sys
import argparse

# 确保当前目录在 Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SERVER_MAP = {
    "lingxing": "lingxing_server:app",
    "amazon_sp": "amazon_sp_server:app",
    "ad_api": "ad_api_server:app",
}


def main():
    parser = argparse.ArgumentParser(description="MCP Server Launcher")
    parser.add_argument("--port", type=int, default=8001, help="监听端口")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址")
    parser.add_argument("--server", help="MCP Server 名称 (lingxing/amazon_sp/ad_api)")
    args = parser.parse_args()

    server_name = args.server or os.environ.get("MCP_SERVER", "lingxing")

    if server_name not in SERVER_MAP:
        print(f"❌ 未知 MCP Server: {server_name}")
        print(f"   可用: {list(SERVER_MAP.keys())}")
        sys.exit(1)

    app_import = SERVER_MAP[server_name]

    print(f"🚀 启动 MCP Server: {server_name}")
    print(f"   📡 地址: http://{args.host}:{args.port}")
    print(f"   📊 健康检查: http://{args.host}:{args.port}/health")
    print(f"   🔧 工具列表: http://{args.host}:{args.port}/tools")
    print(f"   ⚡ Mock 模式: 已启用 (模拟数据)")

    import uvicorn
    uvicorn.run(app_import, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
