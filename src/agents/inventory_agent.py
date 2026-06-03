"""
库存预警 Agent v3.0
数据源 → 标准化 → 规则分析 → 变动检测 → 告警输出
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .base_agent import BaseAgent
from datasource.models import InventorySnapshot, SalesData


class InventoryAlertAgent(BaseAgent):
    """库存预警 Agent"""

    name = "inventory_alert"
    description = "FBA库存健康度检查与智能补货建议"

    async def run(self, asin_list: list[str] = None,
                  msku_list: list[str] = None) -> dict:
        t0 = time.time()

        # 1. 从数据源拉数据 (标准化后)
        inventory: list[InventorySnapshot] = await self.registry.fetch(
            "inventory", {"asin_list": asin_list, "msku_list": msku_list})
        sales: list[SalesData] = await self.registry.fetch(
            "sales", {"msku_list": msku_list})

        # 2. 合并销量数据, 计算库存天数
        sales_map = {s.sku: s for s in sales}
        for inv in inventory:
            sd = sales_map.get(inv.sku)
            if sd:
                inv.daily_sales = sd.daily_avg_7d
                if inv.daily_sales > 0:
                    inv.days_of_stock = round(inv.fba_stock / inv.daily_sales, 1)

        # 3. 转 dict 给规则引擎
        items = [self._to_dict(inv, sales_map) for inv in inventory]

        # 4. 分析管线 (规则 + LLM)
        if self.pipeline:
            analysis = await self.pipeline.process("inventory", items)
        else:
            from engine.analysis_pipeline import RuleEngine
            re = RuleEngine()
            rule_alerts, normals = re.evaluate("inventory", items)
            analysis = type('Result', (), {
                'status': 'alert' if rule_alerts else 'normal',
                'alerts': rule_alerts,
                'suggestions': [],
                'normal_count': len(normals),
            })()

        # 5. 汇总
        critical_count = sum(1 for a in analysis.alerts if a.severity == "critical")
        warning_count = sum(1 for a in analysis.alerts if a.severity == "warning")

        return {
            "status": analysis.status,
            "summary": {
                "total_skus": len(inventory),
                "healthy": analysis.normal_count,
                "critical": critical_count,
                "warning": warning_count,
                "date": datetime.now().strftime("%Y-%m-%d"),
            },
            "alerts": [
                {"msku": a.item_id, "level": a.severity, "emoji": "🔴" if a.severity == "critical" else "🟡",
                 "detail": a.detail, "suggestion": a.suggestion,
                 "fba_stock": a.source_data.get("fba_stock", ""),
                 "days_of_stock": a.source_data.get("days_of_stock", ""),
                 "asin": a.source_data.get("asin", "")}
                for a in analysis.alerts
            ],
            "suggestions": [
                {"id": s.item_id, "detail": s.detail, "suggestion": s.suggestion}
                for s in analysis.suggestions
            ],
            "details": items,
            "duration_ms": int((time.time() - t0) * 1000),
        }

    def _to_dict(self, inv: InventorySnapshot, sales_map: dict) -> dict:
        prov = inv.provenance
        return {
            "sku": inv.sku, "asin": inv.asin,
            "product_name": inv.product_name,
            "fba_stock": inv.fba_stock,
            "reserved_stock": inv.reserved_stock,
            "inbound_stock": inv.inbound_stock,
            "daily_sales": inv.daily_sales,
            "days_of_stock": inv.days_of_stock,
            "warehouse": inv.warehouse,
            "data_source": prov.source if prov else "",
            "platform": prov.platform if prov else "",
        }
