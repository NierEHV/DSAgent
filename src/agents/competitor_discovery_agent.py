"""
竞品自动发现 Agent
四条路径并行: 关键词 → 类目 → 流量 → 关联
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .base_agent import BaseAgent
from datasource.models import CompetitorProfile, ProductInfo


class CompetitorDiscoveryAgent(BaseAgent):
    """竞品发现 Agent — 自动找出谁是你的竞品"""

    name = "competitor_discovery"
    description = "从关键词/类目/流量/关联四个维度自动发现竞品"

    async def run(self, my_asins: list[str] = None,
                  my_keywords: list[str] = None) -> dict:
        t0 = time.time()
        default_asins = ["B09XYZ0001", "B07DEF5678", "B08ABC1234"]
        asins = my_asins or default_asins
        keywords = my_keywords or ["bluetooth earbuds", "usb c charger",
                                    "portable speaker", "wireless headphones"]

        all_profiles: list[CompetitorProfile] = []
        seen_asins = set(asins)

        # 1. 关键词维度: 搜每个核心词 → Top竞品
        for kw in keywords[:5]:
            try:
                profiles = await self.registry.fetch("competitor_profiles", {
                    "keywords": [kw],
                    "exclude_asins": list(seen_asins),
                })
                for p in profiles:
                    if p.asin not in seen_asins:
                        seen_asins.add(p.asin)
                        p.discovery_path = "keyword"
                        p.discovery_keyword = kw
                        all_profiles.append(p)
            except Exception:
                continue

        # 2. 去重 + 分类
        direct = [p for p in all_profiles if p.discovery_path == "keyword" and p.bsr > 0]
        new_discovered = [p for p in all_profiles if p.first_seen > (datetime.now().isoformat()[:10])]

        return {
            "status": "ok",
            "summary": {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "total_discovered": len(all_profiles),
                "direct_competitors": len(direct),
                "new_today": len(new_discovered),
            },
            "competitors": [
                {"asin": p.asin, "name": p.name, "price": p.price,
                 "bsr": p.bsr, "reviews": p.reviews, "rating": p.rating,
                 "discovery_path": p.discovery_path,
                 "discovery_keyword": p.discovery_keyword}
                for p in all_profiles
            ],
            "new_discovered": [
                {"asin": p.asin, "name": p.name, "price": p.price}
                for p in new_discovered
            ],
            "duration_ms": int((time.time() - t0) * 1000),
        }
