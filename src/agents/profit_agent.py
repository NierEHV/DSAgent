"""
利润分析 Agent v3.0
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .base_agent import BaseAgent
from datasource.models import ProfitData


class ProfitAnalysisAgent(BaseAgent):
    """利润分析 Agent"""

    name = "profit_analysis"
    description = "利润异常检测 + 根因分析 + 退款监控"

    async def run(self) -> dict:
        t0 = time.time()

        # 1. 拉数据
        profits: list[ProfitData] = await self.registry.fetch("profit", {})

        # 2. 转 dict
        items = [self._to_dict(p) for p in profits]

        # 3. 分析
        if self.pipeline:
            analysis = await self.pipeline.process("profit", items)
        else:
            from engine.analysis_pipeline import RuleEngine
            re = RuleEngine()
            rule_alerts, normals = re.evaluate("profit", items)
            analysis = type('Result', (), {
                'status': 'alert' if rule_alerts else 'normal',
                'alerts': rule_alerts,
                'suggestions': [],
                'normal_count': len(normals),
            })()

        total_revenue = sum(p.revenue for p in profits)
        total_profit = sum(p.gross_profit for p in profits)

        return {
            "status": analysis.status,
            "summary": {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total_skus": len(profits),
                "healthy": analysis.normal_count,
                "warning": sum(1 for a in analysis.alerts if a.severity == "warning"),
                "critical": sum(1 for a in analysis.alerts if a.severity == "critical"),
                "total_revenue": round(total_revenue, 2),
                "total_profit": round(total_profit, 2),
                "avg_margin": round(sum(p.gross_margin for p in profits) / len(profits), 1) if profits else 0,
            },
            "anomalies": [
                {"sku": a.item_id, "level": a.severity,
                 "emoji": "🔴" if a.severity == "critical" else "🟡",
                 "detail": a.detail, "suggestion": a.suggestion,
                 "gross_margin": a.source_data.get("gross_margin", ""),
                 "refund_rate": a.source_data.get("refund_rate", ""),
                 "ad_ratio": a.source_data.get("ad_ratio", "")}
                for a in analysis.alerts
            ],
            "suggestions": [
                {"id": s.item_id, "detail": s.detail, "suggestion": s.suggestion}
                for s in analysis.suggestions
            ],
            "details": items,
            "duration_ms": int((time.time() - t0) * 1000),
        }

    def _to_dict(self, p: ProfitData) -> dict:
        prov = p.provenance
        return {
            "sku": p.sku, "asin": p.asin, "date": p.date,
            "revenue": p.revenue, "sales_qty": p.sales_qty,
            "gross_profit": p.gross_profit, "gross_margin": p.gross_margin,
            "refund_rate": p.refund_rate, "refund_amount": p.refund_amount,
            "ad_spend": p.ad_spend, "ad_ratio": p.ad_ratio,
            "fba_fees": p.fba_fees, "cogs": p.cogs,
            "data_source": prov.source if prov else "",
            "platform": prov.platform if prov else "",
        }
