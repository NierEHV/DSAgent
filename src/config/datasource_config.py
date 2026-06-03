"""
数据源配置 & 注册中心
加载 YAML 中的数据源列表, 创建对应的适配器实例
"""

from __future__ import annotations

from typing import Optional

from datasource.registry import DataSourceRegistry
from datasource.adapter_sellersprite import SellerSpriteAdapter
from datasource.adapter_sorftime import SorftimeAdapter
from datasource.adapter_lingxing import LingxingAdapter
from datasource.mcp_client import MCPClient


ADAPTER_MAP = {
    "sellersprite": SellerSpriteAdapter,
    "sorftime": SorftimeAdapter,
    "lingxing": LingxingAdapter,
}


def build_registry(datasources: list[dict], mock_mode: bool = False) -> DataSourceRegistry:
    """
    从配置列表构建数据源注册中心

    每个 datasource 配置格式:
      {
        "name": "sellersprite",
        "type": "mcp_sse",
        "url": "https://mcp.sellersprite.com/sse",
        "secret_key": "xxx",
        "enabled": true,
      }
    """
    registry = DataSourceRegistry()
    registry.mock_mode = mock_mode

    for ds_config in datasources:
        name = ds_config.get("name", "")
        if not name or not ds_config.get("enabled", True):
            continue

        adapter_class = ADAPTER_MAP.get(name)
        if not adapter_class:
            registry.log.warning(f"未知数据源类型: {name}, 跳过")
            continue

        # 创建 MCP/API 客户端
        client = _create_client(ds_config)

        # 创建适配器
        adapter = adapter_class(client=client)

        # 注册
        registry.register(name, adapter)

    return registry


def _create_client(config: dict) -> Optional[MCPClient]:
    """根据配置创建对应的客户端"""
    ds_type = config.get("type", "mcp_http")
    url = config.get("url", "")
    if not url:
        return None

    auth_headers = {}
    if config.get("secret_key"):
        auth_headers["secret-key"] = config["secret_key"]
    if config.get("auth_key"):
        auth_headers["Authorization"] = f"Bearer {config['auth_key']}"
    if config.get("api_key"):
        auth_headers["X-API-Key"] = config["api_key"]

    return MCPClient(
        name=config["name"],
        base_url=url,
        transport_type=ds_type,
        auth_headers=auth_headers,
    )
