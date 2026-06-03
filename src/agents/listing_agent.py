"""
Listing 查询 + 优化 Agent
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .base_agent import BaseAgent


class ListingAgent(BaseAgent):
    """Listing 数据查询 + AI 优化 Agent"""

    name = "listing"
    description = "Listing 数据查询 + AI 优化建议 + 竞品对比"

    async def run(self, asin: str = None, asin_list: list[str] = None,
                  action: str = "query") -> dict:
        t0 = time.time()
        asins = asin_list or ([asin] if asin else [])
        if not asins:
            return {"status": "error", "message": "请提供至少一个 ASIN"}

        # 1. 拉 Listing 数据
        products = await self.registry.fetch("product", {"asin_list": asins})

        # 2. 额外数据: 关键词 + 流量词
        keyword_data = []
        competitor_data = [] if action != "compare" else await self.registry.fetch(
            "competitor", {"asin_list": asins})

        # 3. 按 action 处理
        if action == "optimize":
            llm_analysis = await self._optimize(products, keyword_data)
        elif action == "compare":
            llm_analysis = await self._compare(products, competitor_data)
        else:
            llm_analysis = {"action": "query", "message": "Listing 数据查询完成"}

        return {
            "status": "ok",
            "action": action,
            "products": [self._to_dict(p) for p in products],
            "keywords": keyword_data,
            "competitors": [self._to_dict(c) for c in competitor_data] if action == "compare" else [],
            "optimization": llm_analysis,
            "duration_ms": int((time.time() - t0) * 1000),
        }

    async def _optimize(self, products, keywords) -> dict:
        """AI 优化分析"""
        if self.pipeline and self.pipeline.llm:
            try:
                prompt = self._get_prompt("listing_optimization")
                context = {
                    "products": [self._to_dict(p) for p in products],
                    "keywords": keywords,
                    "task": "分析Listing并给出具体优化方案",
                }
                resp = await self.pipeline.llm.analyze(
                    system_prompt=prompt or "你是亚马逊Listing优化专家",
                    context=context,
                )
                if resp and resp.content:
                    return {"analysis": resp.content, "source": "ai"}
            except Exception:
                pass
        return {"analysis": "LLM 不可用, 请配置 LLM 后重试"}

    async def _compare(self, products, competitors) -> dict:
        if self.pipeline and self.pipeline.llm:
            prompt = self._get_prompt("listing_optimization")
            context = {
                "our_products": [self._to_dict(p) for p in products],
                "competitors": [self._to_dict(c) for c in competitors],
                "task": "对比我方和竞品Listing,找出差距和优化空间",
            }
            try:
                resp = await self.pipeline.llm.analyze(
                    system_prompt=prompt or "你是亚马逊Listing对比分析专家",
                    context=context,
                )
                if resp and resp.content:
                    return {"analysis": resp.content, "source": "ai"}
            except Exception:
                pass
        return {"analysis": "LLM 不可用"}

    def _get_prompt(self, name: str) -> str:
        try:
            from prompts.manager import prompt_manager
            return prompt_manager.get("analysis", name)
        except Exception:
            return ""

    def _to_dict(self, obj) -> dict:
        if obj is None:
            return {}
        from dataclasses import asdict, is_dataclass
        if is_dataclass(obj):
            d = asdict(obj)
            d.pop("provenance", None)
            return d
        return dict(obj) if isinstance(obj, dict) else {}
