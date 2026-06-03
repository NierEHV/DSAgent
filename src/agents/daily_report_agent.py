"""
运营日报 Agent v3.0
全店指标汇总 + 告警集成
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .base_agent import BaseAgent


class DailyReportAgent(BaseAgent):
    """运营日报 Agent"""

    name = "daily_report"
    description = "全店核心指标汇总日报"

    async def run(self) -> dict:
        t0 = time.time()

        # 并行拉取所有数据
        inventory = await self.registry.fetch("inventory", {})
        advertising = await self.registry.fetch("advertising", {})
        competitor = await self.registry.fetch("competitor", {})
        profit = await self.registry.fetch("profit", {})

        # 汇总
        today = datetime.now().strftime("%Y-%m-%d")

        # 库存
        low_stock = [i for i in inventory if getattr(i, "days_of_stock", 999) < 7]
        excess_stock = [i for i in inventory if getattr(i, "days_of_stock", 0) > 90]

        # 广告
        total_ad_spend = sum(getattr(m, "spend", 0) for m in advertising)
        total_ad_sales = sum(getattr(m, "sales", 0) for m in advertising)
        overall_acos = round(total_ad_spend / total_ad_sales * 100, 2) if total_ad_sales > 0 else 0

        # 竞品
        buy_box_count = sum(1 for c in competitor if getattr(c, "buy_box_is_ours", False))
        buy_box_rate = round(buy_box_count / len(competitor) * 100, 1) if competitor else 0

        # 利润
        total_revenue = sum(getattr(p, "revenue", 0) for p in profit)
        total_profit = sum(getattr(p, "gross_profit", 0) for p in profit)
        avg_margin = round(sum(getattr(p, "gross_margin", 0) for p in profit) / len(profit), 1) if profit else 0

        # 告警汇总
        alerts = []
        if len(low_stock) > 0:
            alerts.append(f"🔴 {len(low_stock)} 个SKU库存不足")
        if len(excess_stock) > 0:
            alerts.append(f"⚠️ {len(excess_stock)} 个SKU库存冗余")
        if overall_acos > 25:
            alerts.append(f"🟡 整体ACOS {overall_acos}%，偏高")
        if buy_box_rate < 80:
            alerts.append(f"🟡 Buy Box持有率 {buy_box_rate}%")
        if avg_margin < 15:
            alerts.append(f"🟡 平均毛利率 {avg_margin}%")

        markdown = self._build_markdown(
            today, total_revenue, total_profit, avg_margin,
            total_ad_spend, total_ad_sales, overall_acos,
            len(inventory), len(low_stock), len(excess_stock),
            buy_box_rate, alerts)

        return {
            "status": "ok",
            "report": {
                "date": today,
                "sales": {"total_revenue": round(total_revenue, 2), "total_orders": 0},
                "profit": {"gross_profit": round(total_profit, 2), "gross_margin": avg_margin},
                "advertising": {"total_spend": round(total_ad_spend, 2),
                                "total_sales": round(total_ad_sales, 2),
                                "overall_acos": overall_acos},
                "inventory": {"total_skus": len(inventory),
                              "low_stock_count": len(low_stock),
                              "excess_stock_count": len(excess_stock)},
                "competitor": {"buy_box_rate": buy_box_rate},
            },
            "alerts": alerts,
            "markdown": markdown,
            "duration_ms": int((time.time() - t0) * 1000),
        }

    def _build_markdown(self, date, revenue, profit, margin,
                        ad_spend, ad_sales, acos,
                        total_sku, low, excess, bb_rate, alerts) -> str:
        md = f"""## 📊 运营日报 — {date}

━━━━━━━━━━━━━━━━━━━

### 📈 销售 & 利润
- 总营收: **${revenue:,.2f}**
- 毛利: ${profit:,.2f} | 毛利率: {margin:.1f}%

### 📢 广告
- 总花费: ${ad_spend:,.2f} | 广告销售: ${ad_sales:,.2f}
- 整体 ACOS: {acos}%

### 📦 库存
- 总SKU: {total_sku} | 低库存: {low} | 冗余: {excess}

### 🔍 竞品
- Buy Box 持有率: {bb_rate}%
"""
        if alerts:
            md += "\n### ⚠️ 今日告警\n"
            for a in alerts:
                md += f"- {a}\n"
        return md
