"""
数据源适配器基类
定义适配器接口 + 标准化转换方法
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .models import (
    DataProvenance, ProductInfo, InventorySnapshot, SalesData,
    AdMetrics, CompetitorSnapshot, ProfitData, CompetitorProfile,
)


class BaseAdapter(ABC):
    """数据源适配器基类"""

    source_name: str = "unknown"

    def __init__(self, client=None):
        self.client = client
        self._last_error: Optional[str] = None
        self._is_online: bool = True

    @property
    def is_online(self) -> bool:
        return self._is_online

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    async def health_check(self) -> dict:
        """健康检查"""
        try:
            if self.client:
                result = await self.client.health()
                self._is_online = result.get("status") == "connected"
                return {"source": self.source_name, "status": "connected" if self._is_online else "error"}
            return {"source": self.source_name, "status": "no_client"}
        except Exception as e:
            self._is_online = False
            self._last_error = str(e)
            return {"source": self.source_name, "status": "error", "error": str(e)}

    def _make_provenance(self, platform: str = "amazon_us",
                         marketplace: str = "ATVPDKIKX0DER",
                         duration_ms: int = 0) -> DataProvenance:
        """创建溯源标记"""
        from datetime import datetime
        return DataProvenance(
            source=self.source_name,
            source_type=self._source_type(),
            platform=platform,
            marketplace=marketplace,
            fetched_at=datetime.now().isoformat(),
            query_duration_ms=duration_ms,
            is_fresh=True,
        )

    @abstractmethod
    def _source_type(self) -> str:
        """返回源类型: mcp_sse / mcp_http / rest_api"""
        ...

    # ──── 标准化转换 (子类实现) ────

    @abstractmethod
    async def fetch_inventory(self, params: dict) -> list[InventorySnapshot]:
        ...

    @abstractmethod
    async def fetch_sales(self, params: dict) -> list[SalesData]:
        ...

    @abstractmethod
    async def fetch_advertising(self, params: dict) -> list[AdMetrics]:
        ...

    @abstractmethod
    async def fetch_competitor(self, params: dict) -> list[CompetitorSnapshot]:
        ...

    @abstractmethod
    async def fetch_profit(self, params: dict) -> list[ProfitData]:
        ...

    @abstractmethod
    async def fetch_products(self, params: dict) -> list[ProductInfo]:
        ...

    async def fetch_competitor_profiles(self, params: dict) -> list[CompetitorProfile]:
        """竞品发现 — 可选实现"""
        return []

    def __repr__(self):
        status = "online" if self._is_online else "offline"
        return f"<{self.source_name} [{status}]>"
