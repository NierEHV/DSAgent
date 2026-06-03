"""
标准化数据模型
所有数据源适配后都输出这些模型, Agent 只认这些结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ═══════════════════════════ 溯源 ═══════════════════════════

@dataclass
class DataProvenance:
    """数据溯源 — 每条数据都知道自己从哪来"""
    source: str            # sellersprite / sorftime / lingxing
    source_type: str       # mcp_sse / mcp_http / rest_api
    platform: str          # amazon_us / amazon_jp / walmart
    marketplace: str       # ATVPDKIKX0DER
    fetched_at: str        # ISO8601
    query_duration_ms: int
    raw_response_id: str = ""
    is_fresh: bool = True

    def age_minutes(self) -> float:
        """数据年龄 (分钟)"""
        try:
            dt = datetime.fromisoformat(self.fetched_at.replace("Z", "+00:00"))
            return (datetime.now() - dt.replace(tzinfo=None)).total_seconds() / 60
        except Exception:
            return 999


# ═══════════════════════════ 业务模型 ═══════════════════════════

@dataclass
class ProductInfo:
    """商品信息"""
    sku: str
    asin: str
    name: str
    brand: str = ""
    price: float = 0.0
    cost: float = 0.0
    category: str = ""
    status: str = "active"
    provenance: Optional[DataProvenance] = None


@dataclass
class InventorySnapshot:
    """库存快照"""
    sku: str
    asin: str
    product_name: str = ""
    fba_stock: int = 0
    reserved_stock: int = 0
    inbound_stock: int = 0
    daily_sales: float = 0.0
    days_of_stock: float = 0.0
    warehouse: str = ""
    provenance: Optional[DataProvenance] = None

    def __post_init__(self):
        if self.daily_sales > 0 and self.days_of_stock == 0:
            self.days_of_stock = round(self.fba_stock / self.daily_sales, 1)


@dataclass
class SalesData:
    """销量数据"""
    sku: str
    asin: str
    daily_avg_7d: float = 0.0
    daily_avg_30d: float = 0.0
    trend: str = "stable"     # up / down / stable
    change_pct: float = 0.0
    provenance: Optional[DataProvenance] = None


@dataclass
class AdMetrics:
    """广告指标"""
    campaign_id: str
    campaign_name: str = ""
    ad_type: str = "SP"
    spend: float = 0.0
    sales: float = 0.0
    impressions: int = 0
    clicks: int = 0
    acos: float = 0.0
    roas: float = 0.0
    cpc: float = 0.0
    ctr: float = 0.0
    budget: float = 0.0
    budget_used_pct: float = 0.0
    orders: int = 0
    avg_acos_14d: float = 0.0
    acos_change: float = 0.0
    anomaly_type: Optional[str] = None   # acos_spike / budget_exhausted / None
    provenance: Optional[DataProvenance] = None


@dataclass
class CompetitorSnapshot:
    """竞品快照"""
    asin: str
    buy_box_owner: str = ""
    buy_box_price: float = 0.0
    our_price: float = 0.0
    seller_count: int = 0
    sellers: list = field(default_factory=list)
    new_sellers: list = field(default_factory=list)
    bsr: int = 0
    bsr_change: int = 0
    buy_box_is_ours: bool = False
    threat_level: str = "none"  # none / low / medium / high / critical
    provenance: Optional[DataProvenance] = None


@dataclass
class ProfitData:
    """利润数据"""
    sku: str
    asin: str
    date: str = ""
    revenue: float = 0.0
    sales_qty: int = 0
    gross_profit: float = 0.0
    gross_margin: float = 0.0
    refund_rate: float = 0.0
    refund_amount: float = 0.0
    ad_spend: float = 0.0
    ad_ratio: float = 0.0
    fba_fees: float = 0.0
    cogs: float = 0.0
    provenance: Optional[DataProvenance] = None


@dataclass
class CompetitorProfile:
    """竞品档案 — 竞品发现 & 追踪用"""
    asin: str
    name: str = ""
    brand: str = ""
    category: str = ""
    price: float = 0.0
    bsr: int = 0
    reviews: int = 0
    rating: float = 0.0
    discovery_path: str = ""       # keyword / category / traffic / listing
    discovery_keyword: str = ""    # 通过哪个关键词发现的
    first_seen: str = ""
    last_updated: str = ""
    threat_level: str = "none"
    provenance: Optional[DataProvenance] = None


@dataclass
class DailyReport:
    """日报"""
    date: str
    sales: dict = field(default_factory=dict)
    profit: dict = field(default_factory=dict)
    advertising: dict = field(default_factory=dict)
    inventory: dict = field(default_factory=dict)
    competitor: dict = field(default_factory=dict)
    alerts: list = field(default_factory=list)
    markdown: str = ""
