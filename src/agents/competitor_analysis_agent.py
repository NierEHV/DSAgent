"""
竞品 AI 分析 Agent
30天历史追踪 → 策略推断 → 威胁评估 → 对策建议
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .base_agent import BaseAgent


class CompetitorAnalysisAgent(BaseAgent):
    """竞品 AI 分析 Agent"""

    name = "competitor_analysis"
    description = "竞品30天趋势分析 + 策略推断 + 威胁评估 + 对策建议"

    async def run(self, competitor_asin: str = None,
                  competitor_asins: list[str] = None) -> dict:
        t0 = time.time()

        asins = competitor_asins or ([competitor_asin] if competitor_asin else [])
        if not asins:
            return {"status": "error", "message": "请提供竞品 ASIN"}

        results = []
        for asin in asins:
            # 1. 拉竞品当前数据
            comps = await self.registry.fetch("competitor", {"asin_list": [asin]})

            # 2. 拉我们的数据做对比
            products = await self.registry.fetch("product", {"asin_list": [asin]})

            comp_info = comps[0] if comps else None
            product_info = products[0] if products else None

            # 3. LLM 策略分析
            threat_level = "medium"
            strategy_inference = ""
            recommendations = ""

            if self.pipeline and self.pipeline.llm:
                try:
                    context = {
                        "competitor_asin": asin,
                        "competitor_data": self._to_dict(comp_info) if comp_info else {},
                        "product_data": self._to_dict(product_info) if product_info else {},
                        "task": "分析竞品策略并推断其意图",
                    }
                    resp = await self.pipeline.llm.analyze(
                        system_prompt="你是亚马逊竞品分析专家。分析竞品行为,给出威胁评估和应对策略。返回JSON格式。",
                        context=context,
                    )
                    if resp.content:
                        import json
                        try:
                            content = resp.content
                            if "```" in content:
                                content = content.split("```")[1].split("```")[0]
                                if content.startswith("json"):
                                    content = content[4:]
                            data = json.loads(content)
                            threat_level = data.get("threat_level", "medium")
                            strategy_inference = data.get("strategy_inference", "")
                            recommendations = data.get("recommendations", "")
                        except (json.JSONDecodeError, IndexError):
                            pass
                except Exception:
                    pass

            results.append({
                "asin": asin,
                "current_data": self._to_dict(comp_info) if comp_info else {},
                "threat_level": threat_level,
                "strategy_inference": strategy_inference,
                "recommendations": recommendations,
            })

        return {
            "status": "ok",
            "summary": {
                "analyzed_count": len(results),
                "high_threat": sum(1 for r in results if r["threat_level"] == "high"),
                "medium_threat": sum(1 for r in results if r["threat_level"] == "medium"),
                "low_threat": sum(1 for r in results if r["threat_level"] == "low"),
            },
            "results": results,
            "duration_ms": int((time.time() - t0) * 1000),
        }

    def _to_dict(self, obj) -> dict:
        if obj is None:
            return {}
        from dataclasses import asdict, is_dataclass
        if is_dataclass(obj):
            d = asdict(obj)
            prov = d.pop("provenance", None)
            if prov:
                d["data_source"] = prov.get("source", "") if isinstance(prov, dict) else getattr(prov, "source", "")
            return d
        return dict(obj) if isinstance(obj, dict) else {}
