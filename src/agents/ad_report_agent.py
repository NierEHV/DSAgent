"""
广告日报 Agent v3.0
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .base_agent import BaseAgent
from datasource.models import AdMetrics


class AdReportAgent(BaseAgent):
    """广告日报 Agent"""

    name = "ad_report"
    description = "广告表现分析 + ACOS异常检测 + 预算监控"

    async def run(self, campaign_type: str = None) -> dict:
        t0 = time.time()

        # 1. 拉数据
        metrics: list[AdMetrics] = await self.registry.fetch("advertising", {})

        # 2. 转 dict
        items = [self._to_dict(m) for m in metrics]

        # 3. 分析
        if self.pipeline:
            analysis = await self.pipeline.process("advertising", items)
        else:
            from engine.analysis_pipeline import RuleEngine
            re = RuleEngine()
            rule_alerts, normals = re.evaluate("advertising", items)
            analysis = type('Result', (), {
                'status': 'alert' if rule_alerts else 'normal',
                'alerts': rule_alerts,
                'suggestions': [],
                'normal_count': len(normals),
            })()

        total_spend = sum(m.spend for m in metrics)
        total_sales = sum(m.sales for m in metrics)
        overall_acos = round(total_spend / total_sales * 100, 2) if total_sales > 0 else 0

        return {
            "status": analysis.status,
            "summary": {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total_campaigns": len(metrics),
                "total_spend": round(total_spend, 2),
                "total_sales": round(total_sales, 2),
                "overall_acos": overall_acos,
                "overall_roas": round(total_sales / total_spend, 2) if total_spend > 0 else 0,
                "total_orders": sum(m.orders for m in metrics),
                "anomaly_count": len(analysis.alerts),
            },
            "anomalies": [
                {"campaign": a.item_id, "level": a.severity,
                 "emoji": "🔴" if a.severity == "critical" else "🟡",
                 "detail": a.detail, "suggestion": a.suggestion}
                for a in analysis.alerts
            ],
            "suggestions": [
                {"id": s.item_id, "detail": s.detail, "suggestion": s.suggestion}
                for s in analysis.suggestions
            ],
            "campaigns": items,
            "duration_ms": int((time.time() - t0) * 1000),
        }

    def _to_dict(self, m: AdMetrics) -> dict:
        prov = m.provenance
        return {
            "campaign_id": m.campaign_id, "campaign_name": m.campaign_name,
            "ad_type": m.ad_type, "spend": m.spend, "sales": m.sales,
            "impressions": m.impressions, "clicks": m.clicks,
            "acos": m.acos, "roas": m.roas, "cpc": m.cpc, "ctr": m.ctr,
            "budget": m.budget, "budget_used_pct": m.budget_used_pct,
            "orders": m.orders, "avg_acos_14d": m.avg_acos_14d,
            "data_source": prov.source if prov else "",
            "platform": prov.platform if prov else "",
        }
