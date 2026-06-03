"""
跟卖监控 Agent v3.0
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .base_agent import BaseAgent
from datasource.models import CompetitorSnapshot


class HijackMonitorAgent(BaseAgent):
    """跟卖监控 Agent"""

    name = "hijack_monitor"
    description = "跟卖检测 + Buy Box监控 + 价格异常预警"

    async def run(self, asin_list: list[str] = None) -> dict:
        t0 = time.time()
        default_asins = ["B09XYZ0001", "B07DEF5678", "B08ABC1234", "B05GHI9012"]
        asins = asin_list or default_asins

        # 1. 拉数据
        comps: list[CompetitorSnapshot] = await self.registry.fetch(
            "competitor", {"asin_list": asins})

        # 2. 转 dict
        items = [self._to_dict(c) for c in comps]

        # 3. 分析
        if self.pipeline:
            analysis = await self.pipeline.process("competitor", items)
        else:
            from engine.analysis_pipeline import RuleEngine
            re = RuleEngine()
            rule_alerts, normals = re.evaluate("competitor", items)
            analysis = type('Result', (), {
                'status': 'alert' if rule_alerts else 'normal',
                'alerts': rule_alerts,
                'suggestions': [],
                'normal_count': len(normals),
            })()

        buy_box_rate = round(
            sum(1 for c in comps if c.buy_box_is_ours) / len(comps) * 100, 1
        ) if comps else 0

        return {
            "status": analysis.status,
            "summary": {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "total_asins": len(comps),
                "safe": analysis.normal_count,
                "critical": sum(1 for a in analysis.alerts if a.severity == "critical"),
                "warning": sum(1 for a in analysis.alerts if a.severity == "warning"),
                "buy_box_rate": buy_box_rate,
            },
            "threats": [
                {"asin": a.item_id, "level": a.severity,
                 "detail": a.detail, "suggestion": a.suggestion}
                for a in analysis.alerts
            ],
            "suggestions": [
                {"id": s.item_id, "detail": s.detail, "suggestion": s.suggestion}
                for s in analysis.suggestions
            ],
            "asin_details": items,
            "duration_ms": int((time.time() - t0) * 1000),
        }

    def _to_dict(self, c: CompetitorSnapshot) -> dict:
        prov = c.provenance
        return {
            "asin": c.asin, "buy_box_owner": c.buy_box_owner,
            "buy_box_price": c.buy_box_price, "our_price": c.our_price,
            "seller_count": c.seller_count, "buy_box_is_ours": c.buy_box_is_ours,
            "bsr": c.bsr, "bsr_change": c.bsr_change,
            "new_sellers": c.new_sellers,
            "data_source": prov.source if prov else "",
            "platform": prov.platform if prov else "",
        }
