"""
数据源抽象层
"""

from __future__ import annotations

from .models import (
    DataProvenance, ProductInfo, InventorySnapshot, SalesData,
    AdMetrics, CompetitorSnapshot, ProfitData, CompetitorProfile, DailyReport,
)
from .base import BaseAdapter
from .mcp_client import MCPClient
from .registry import DataSourceRegistry
