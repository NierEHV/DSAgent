"""
数据对比引擎 — 快照对比 → 找变动
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DataChange:
    """一次数据变动"""
    platform: str = ""
    asin: str = ""
    sku: str = ""
    campaign_id: str = ""
    product_name: str = ""
    data_source: str = ""
    field: str = ""
    previous_value: Any = None
    current_value: Any = None
    change_pct: float = 0.0
    change_direction: str = "unchanged"   # up / down / unchanged
    previous_snapshot_at: str = ""
    detected_at: str = ""

    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now().isoformat()


class DiffEngine:
    """快照对比引擎"""

    # 需要对比的字段 (取决于数据类型)
    COMPARE_FIELDS = {
        "inventory": ["fba_stock", "daily_sales", "days_of_stock", "inbound_stock"],
        "advertising": ["spend", "sales", "acos", "roas", "impressions", "clicks", "budget_used_pct"],
        "competitor": ["buy_box_owner", "buy_box_price", "our_price", "seller_count", "bsr"],
        "profit": ["revenue", "gross_profit", "gross_margin", "refund_rate", "ad_ratio"],
    }

    # 变动阈值 (微小的变化忽略不计)
    CHANGE_THRESHOLDS = {
        "fba_stock": 0,           # 库存件数: 任何变化都记录
        "daily_sales": 0.5,       # 日均销量: >=0.5件
        "days_of_stock": 0.5,     # 可售天数: >=0.5天
        "spend": 1.0,             # 花费: >=$1
        "sales": 1.0,             # 销售: >=$1
        "acos": 2.0,              # ACOS: >=2%变化
        "roas": 0.5,              # ROAS: >=0.5变化
        "buy_box_price": 0.5,     # 价格: >=$0.5
        "seller_count": 0,        # 卖家数: 任何变化
        "bsr": 50,                # BSR: >=50名
        "gross_margin": 2.0,      # 毛利率: >=2%
        "refund_rate": 1.0,       # 退款率: >=1%
        "ad_ratio": 2.0,          # 广告占比: >=2%
    }

    def compare(self, data_type: str, previous: list[dict],
                current: list[dict]) -> list[DataChange]:
        """对比两份快照, 返回变动列表"""
        changes = []
        fields = self.COMPARE_FIELDS.get(data_type, [])

        # 构建查找索引 (优先用 sku, 其次 asin, 最后 campaign_id)
        key_field = self._key_field(data_type)
        prev_map = {self._get_key(item, key_field): item for item in previous}
        curr_map = {self._get_key(item, key_field): item for item in current}

        for key, curr_item in curr_map.items():
            prev_item = prev_map.get(key)
            if prev_item is None:
                continue  # 新增的项目, 不视为变动

            for field in fields:
                prev_val = prev_item.get(field)
                curr_val = curr_item.get(field)

                if prev_val is None or curr_val is None:
                    continue

                # 跳过微小变化
                threshold = self.CHANGE_THRESHOLDS.get(field, 0)
                if isinstance(prev_val, (int, float)) and isinstance(curr_val, (int, float)):
                    if abs(curr_val - prev_val) < threshold:
                        continue

                # 字符串字段: 值没变就跳过
                if isinstance(prev_val, str) and prev_val == curr_val:
                    continue

                # 计算变动
                change_pct = self._calc_change_pct(prev_val, curr_val)
                direction = "up" if change_pct > 0 else "down" if change_pct < 0 else "unchanged"

                # 跳过无意义的小变动
                if direction == "unchanged":
                    continue

                changes.append(DataChange(
                    platform=curr_item.get("platform", ""),
                    asin=curr_item.get("asin", ""),
                    sku=curr_item.get("sku", ""),
                    campaign_id=curr_item.get("campaign_id", ""),
                    product_name=curr_item.get("product_name", ""),
                    data_source=curr_item.get("data_source", ""),
                    field=field,
                    previous_value=prev_val,
                    current_value=curr_val,
                    change_pct=round(change_pct, 1),
                    change_direction=direction,
                    previous_snapshot_at=previous[0].get("snapshot_time", "") if previous else "",
                ))

        logger.info(f"[Diff] {data_type}: {len(current)}项, {len(changes)}个变动")
        return changes

    def _key_field(self, data_type: str) -> str:
        mapping = {
            "inventory": "sku",
            "advertising": "campaign_id",
            "competitor": "asin",
            "profit": "sku",
        }
        return mapping.get(data_type, "sku")

    def _get_key(self, item: dict, key_field: str) -> str:
        # 尝试多个可能的键名
        for k in [key_field, "msku", "sku", "asin", "campaign_id"]:
            if k in item:
                return str(item[k])
        return str(hash(json.dumps(item, default=str)))  # fallback

    def _calc_change_pct(self, prev: Any, curr: Any) -> float:
        if not isinstance(prev, (int, float)) or not isinstance(curr, (int, float)):
            return 0 if prev == curr else 100  # 字符串变化
        if prev == 0:
            return 999 if curr > 0 else -999
        return (curr - prev) / abs(prev) * 100

    def has_significant_changes(self, changes: list[DataChange],
                                severity_threshold: float = 20.0) -> bool:
        """是否有显著性变动 (>阈值%)"""
        return any(abs(c.change_pct) >= severity_threshold for c in changes if c.change_pct != 999)


import json  # noqa: E402 — needed in _get_key fallback
