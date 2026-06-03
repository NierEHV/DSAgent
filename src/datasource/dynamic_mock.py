"""
动态 Mock 数据引擎
每次读取数据时注入随机波动，模拟真实数据实时变化

波动规则:
- 库存: 每次-0~3件(模拟销售)，每日首次调用重置
- 销量: 在基准值上下±15%浮动
- 广告: ACOS ±5%, 花费按时间递增
- 竞品: BSR ±200浮动, 价格±3%, 偶尔出现新卖家
- 利润: 毛利率±3%, 退款率±1%
"""

from __future__ import annotations

import copy
import hashlib
import random
import time
from datetime import datetime
from typing import Optional

from mcp.mock_data import (
    PRODUCTS, FBA_INVENTORY, SALES_DATA, INBOUND_SHIPMENTS,
    AD_CAMPAIGNS, AD_PERFORMANCE_TODAY, AD_PERFORMANCE_14D_AVG,
    PROFIT_DATA, COMPETITOR_DATA, DAILY_SUMMARY,
)


class DynamicMockEngine:
    """动态 Mock — 每次 get_xxx() 返回带波动的数据"""

    def __init__(self, seed: int = None):
        self.seed = seed or int(time.time())
        self.rng = random.Random(self.seed)
        # 记录本日累计变化
        self._day_key = datetime.now().strftime("%Y%m%d")
        self._call_counts: dict[str, int] = {}
        self._base_state: dict = {}  # 基准值快照
        self._snap_base()

    def _snap_base(self):
        """保存初始基准值"""
        self._base_state = {
            "inventory": {i["msku"]: i["available_qty"] for i in FBA_INVENTORY},
            "sales": {s["msku"]: s["daily_avg_7d"] for s in SALES_DATA},
            "acos": {p["campaign_id"]: p["acos"] for p in AD_PERFORMANCE_TODAY},
            "spend": {p["campaign_id"]: p["spend"] for p in AD_PERFORMANCE_TODAY},
            "bsr": {c["asin"]: c["bsr"] for c in COMPETITOR_DATA},
            "price": {c["asin"]: c["buy_box_price"] for c in COMPETITOR_DATA},
            "margin": {p["msku"]: p["gross_margin"] for p in PROFIT_DATA},
        }

    @property
    def _hour_factor(self) -> float:
        """按一天中的时间递增因子: 0点=0, 12点=0.5, 23点=0.95"""
        h = datetime.now().hour
        return min(h / 24, 0.95)

    @property
    def _call_noise(self) -> float:
        """每次调用产生微小的随机偏移"""
        key = self._day_key
        if key not in self._call_counts:
            self._call_counts = {key: 0}
        self._call_counts[key] = self._call_counts.get(key, 0) + 1
        n = self._call_counts[key]
        return (hash(str(n)) % 100 - 50) / 1000  # -0.05 ~ +0.05

    def _jitter(self, base: float, pct: float = 0.1) -> float:
        """基准值 ±pct% 范围内随机波动"""
        delta = base * pct * (self.rng.random() * 2 - 1)  # -pct% ~ +pct%
        return round(base + delta, 2)

    def _jitter_int(self, base: int, max_delta: int = 3) -> int:
        """整数基准值 ±max_delta"""
        delta = self.rng.randint(-max_delta, max_delta)
        return max(0, base + delta)

    # ═══════════════════════════ 公开接口 ═══════════════════════════

    def get_inventory(self) -> list[dict]:
        items = []
        for inv in FBA_INVENTORY:
            base_stock = self._base_state["inventory"].get(inv["msku"], inv["available_qty"])
            # 库存随时间递减: 每小时消耗 daily_avg/24 件 + 随机波动
            sales_speed = next((s["daily_avg_7d"] for s in SALES_DATA if s["msku"] == inv["msku"]), 1)
            hour_drain = int(sales_speed * self._hour_factor)
            # 额外随机波动: 偶尔有退货/盘点差异
            noise = self._jitter_int(0, max(3, inv["available_qty"] // 10))
            current = max(0, base_stock - hour_drain + noise)
            items.append({**inv, "available_qty": current,
                          "total_qty": current + inv.get("reserved_qty", 0),
                          "reserved_qty": self._jitter_int(inv.get("reserved_qty", 0), 2)})
        return items

    def get_sales(self) -> list[dict]:
        items = []
        for s in SALES_DATA:
            daily = self._jitter(s["daily_avg_7d"], 0.15)
            trend_chance = self.rng.random()
            trend = "up" if trend_chance > 0.7 else "down" if trend_chance < 0.3 else "stable"
            items.append({**s, "daily_avg_7d": round(daily, 1),
                          "daily_avg_30d": self._jitter(s["daily_avg_30d"], 0.1)})
        return items

    def get_advertising(self) -> list[dict]:
        items = []
        for perf in AD_PERFORMANCE_TODAY:
            base_acos = self._base_state["acos"].get(perf["campaign_id"], perf["acos"])
            base_spend = self._base_state["spend"].get(perf["campaign_id"], perf["spend"])
            # ACOS 波动 ±5 个百分点
            acos = round(base_acos + self.rng.uniform(-5, 5), 1)
            # 花费和销售额都按时间递增 + 随机波动
            spend = round(base_spend * (1 + self._hour_factor) * self.rng.uniform(0.9, 1.1), 2)
            sales = round(perf.get("sales", 0) * self.rng.uniform(0.85, 1.15), 2)
            campaign = next((c for c in AD_CAMPAIGNS if c["campaign_id"] == perf["campaign_id"]), {})
            budget = campaign.get("budget", 50)
            budget_pct = round(spend / budget * 100, 1) if budget > 0 else 0
            avg_14d = next((a["avg_acos"] for a in AD_PERFORMANCE_14D_AVG if a["campaign_id"] == perf["campaign_id"]), 0)
            anomaly = None
            if acos > avg_14d * 1.5 and acos > 30:
                anomaly = "acos_spike"
            elif budget_pct > 90:
                anomaly = "budget_exhausted"
            items.append({**perf, "acos": acos, "spend": spend, "sales": sales,
                          "budget_used_pct": budget_pct,
                          "avg_acos_14d": avg_14d,
                          "anomaly": anomaly,
                          "impressions": self._jitter_int(perf.get("impressions", 0), 200),
                          "clicks": self._jitter_int(perf.get("clicks", 0), 15)})
        return items

    def get_competitor(self) -> list[dict]:
        items = []
        for comp in COMPETITOR_DATA:
            base_bsr = self._base_state["bsr"].get(comp["asin"], comp["bsr"])
            base_price = self._base_state["price"].get(comp["asin"], comp["buy_box_price"])
            bsr_delta = self.rng.randint(-200, 200)
            new_bsr = max(1, base_bsr + bsr_delta)
            price = round(base_price * (1 + self.rng.uniform(-0.03, 0.03)), 2)
            # 10% 概率出现新卖家
            sellers = list(comp.get("sellers", []))
            if self.rng.random() < 0.1 and len(sellers) < 6:
                sellers.append({
                    "name": f"NewSeller_{self.rng.randint(100,999)}",
                    "price": round(price * self.rng.uniform(0.85, 0.95), 2),
                    "is_self": False, "rating": round(self.rng.uniform(2.0, 4.0), 1),
                    "fulfillment": random.choice(["FBA", "FBM"]),
                })
            # Buy Box 可能易主
            bb_owner = comp["buy_box_owner"]
            if self.rng.random() < 0.05:
                bb_owner = self.rng.choice([s["name"] for s in sellers if not s.get("is_self")] or [bb_owner])
            items.append({**comp, "bsr": new_bsr, "bsr_change_7d": new_bsr - base_bsr,
                          "buy_box_price": price, "buy_box_owner": bb_owner,
                          "buy_box_is_ours": bb_owner == "self", "sellers": sellers})
        return items

    def get_profit(self) -> list[dict]:
        items = []
        for p in PROFIT_DATA:
            base_margin = self._base_state["margin"].get(p["msku"], p["gross_margin"])
            margin = round(base_margin + self.rng.uniform(-3, 3), 1)
            refund = round(self._jitter(p["refund_rate"], 0.3), 1)
            ad_ratio = round(self._jitter(p["ad_ratio"], 0.2), 1)
            # 营收和利润也微调
            revenue = round(p["revenue"] * self.rng.uniform(0.9, 1.1), 2)
            profit = round(revenue * margin / 100, 2)
            items.append({**p, "gross_margin": margin, "refund_rate": refund,
                          "ad_ratio": ad_ratio, "revenue": revenue, "gross_profit": profit})
        return items

    def get_products(self) -> list[dict]:
        return [dict(p) for p in PRODUCTS]

    def get_events_since(self, minutes: int = 5) -> list[dict]:
        """生成最近 N 分钟的关键事件"""
        events = []
        now = datetime.now()
        # 库存告急事件
        if self.rng.random() < 0.3:
            low_item = self.rng.choice(FBA_INVENTORY)
            events.append({
                "time": now.strftime("%H:%M:%S"), "type": "inventory",
                "level": "warning",
                "message": f"{low_item['msku']} 库存降至 {self._jitter_int(low_item['available_qty'], 5)} 件",
            })
        # ACOS 飙升事件
        if self.rng.random() < 0.25:
            acos_item = self.rng.choice(AD_PERFORMANCE_TODAY)
            events.append({
                "time": now.strftime("%H:%M:%S"), "type": "advertising",
                "level": "warning",
                "message": f"{acos_item['campaign_id']} ACOS 升至 {round(acos_item['acos'] * self.rng.uniform(1.1, 1.5), 1)}%",
            })
        # 竞品变动事件
        if self.rng.random() < 0.2:
            comp_item = self.rng.choice(COMPETITOR_DATA)
            events.append({
                "time": now.strftime("%H:%M:%S"), "type": "competitor",
                "level": "info",
                "message": f"{comp_item['asin']} BSR 变化 {self.rng.randint(-300, 300)}",
            })
        # 跟卖事件
        if self.rng.random() < 0.15:
            comp_item = self.rng.choice(COMPETITOR_DATA)
            events.append({
                "time": now.strftime("%H:%M:%S"), "type": "competitor",
                "level": "critical",
                "message": f"发现 {comp_item['asin']} 新跟卖者，价格 ${round(comp_item['buy_box_price'] * 0.85, 2)}",
            })
        return events


# 全局单例
dynamic_mock = DynamicMockEngine()
