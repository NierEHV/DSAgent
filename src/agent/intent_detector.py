"""
意图识别器 — 自然语言 → 结构化意图 → 工作流匹配
参考 n8n-workflows-main: src/ai_assistant.py
  - extract_keywords()
  - detect_intent()
  - search_workflows_intelligent()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Intent:
    intent: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    entities: dict = field(default_factory=dict)


class IntentDetector:
    """
    意图识别器
    将运营人员的自然语言请求转换为结构化的业务意图
    """

    # 电商关键词库（参考 ai_assistant.py automation_terms）
    ECOM_KEYWORDS = {
        "inventory": {
            "keywords": ["库存", "FBA", "断货", "补货", "仓储", "冗余", "周转", "可售",
                        "预留", "入库", "出库", "移仓", "库存量", "在途", "安全库存", "IPI",
                        "inventory", "stock", "FBA", "out of stock"],
            "trigger_words": ["快没了", "卖完了", "要补", "不够卖了", "太多了"],
        },
        "advertising": {
            "keywords": ["广告", "ACOS", "SP", "SB", "SD", "投放", "出价", "预算", "CTR",
                        "CPC", "曝光", "点击", "转化", "ROAS", "TACOS", "竞价", "关键词",
                        "campaign", "ad group", "targeting"],
            "trigger_words": ["太高了", "飙升", "花不出去", "没曝光", "没点击", "要调"],
        },
        "profit": {
            "keywords": ["利润", "毛利", "净利", "亏损", "退款", "费用", "成本", "FBA费",
                        "佣金", "仓储费", "头程", "采购价", "毛利率", "净利率", "盈利",
                        "margin", "profit", "P&L", "ROI"],
            "trigger_words": ["赔钱", "亏了", "不赚钱", "利润低", "费用高"],
        },
        "listing": {
            "keywords": ["Listing", "标题", "五点", "A+", "描述", "主图", "变体",
                        "详情页", "搜索词", "关键词", "类目", "节点",
                        "bullet points", "description", "images", "variation"],
            "trigger_words": ["优化", "改一下", "更新", "上传", "修改"],
        },
        "competitor": {
            "keywords": ["竞品", "跟卖", "价格战", "BSR", "排名", "对手", "同行",
                        "Best Seller", "buy box", "购物车", "价格变动",
                        "competitor", "hijacker", "ranking", "price war"],
            "trigger_words": ["被跟卖了", "降价了", "排名掉了", "抢购物车"],
        },
        "order": {
            "keywords": ["订单", "销量", "转化率", "Buy Box", "购物车", "出单",
                        "pending", "canceled", "退货", "refund",
                        "order", "conversion", "session", "page view"],
            "trigger_words": ["今天卖了多少", "订单量", "转化怎么样"],
        },
        "report": {
            "keywords": ["日报", "周报", "月报", "报表", "导出", "汇总", "数据",
                        "dashboard", "report", "summary", "KPI"],
            "trigger_words": ["给我看看", "汇总一下", "统计", "整理"],
        },
    }

    # 意图 → 工作流映射（参考 ai_assistant.py search_workflows_intelligent）
    WORKFLOW_MAPPING = {
        "inventory": "inventory_alert_workflow",
        "advertising": "ad_analysis_workflow",
        "profit": "profit_analysis_workflow",
        "listing": "listing_query_workflow",
        "competitor": "competitor_monitor_workflow",
        "order": "order_query_workflow",
        "report": "report_generation_workflow",
    }

    def __init__(self):
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    def detect_intent(self, query: str) -> dict:
        """
        意图检测 — 核心方法
        参考 ai_assistant.py detect_intent() 的 keyword + intent 双层匹配

        返回: {"intent": "inventory", "confidence": 0.83, "matched_keywords": [...], "entities": {...}}
        """
        query_lower = query.lower()
        scores = {}
        matched_keywords = {}

        for intent, config in self.ECOM_KEYWORDS.items():
            # 关键词匹配计分
            keyword_hits = [kw for kw in config["keywords"] if kw.lower() in query_lower]
            # 触发词匹配加权
            trigger_hits = [tw for tw in config["trigger_words"] if tw in query_lower]

            score = len(keyword_hits) + len(trigger_hits) * 2  # 触发词权重翻倍
            if score > 0:
                scores[intent] = score
                matched_keywords[intent] = keyword_hits + trigger_hits

        if not scores:
            return {
                "intent": "general_chat",
                "confidence": 0.0,
                "matched_keywords": [],
                "entities": self._extract_entities(query),
            }

        # 最佳匹配意图
        best_intent = max(scores, key=scores.get)
        max_possible = len(self.ECOM_KEYWORDS[best_intent]["keywords"]) + \
                       len(self.ECOM_KEYWORDS[best_intent]["trigger_words"]) * 2

        return {
            "intent": best_intent,
            "confidence": min(scores[best_intent] / max(max_possible, 1), 1.0),
            "matched_keywords": matched_keywords.get(best_intent, []),
            "entities": self._extract_entities(query),
        }

    def match_workflow(self, intent: str, query: str = "") -> str:
        """
        意图 → 工作流匹配
        参考 ai_assistant.py search_workflows_intelligent() 的 intent-based filtering
        """
        return self.WORKFLOW_MAPPING.get(intent, "general_chat_workflow")

    def _extract_entities(self, query: str) -> dict:
        """
        实体提取 — 从用户查询中提取结构化信息
        例如：ASIN、SKU、日期范围、百分比、金额等
        """
        import re
        entities = {}

        # ASIN 提取 (B0 + 8位字母数字)
        asin_pattern = r'B[A-Z0-9]{9}'
        asins = re.findall(asin_pattern, query, re.IGNORECASE)
        if asins:
            entities["asins"] = [a.upper() for a in asins]

        # 百分比提取
        pct_pattern = r'(\d+(?:\.\d+)?)\s*%'
        percentages = re.findall(pct_pattern, query)
        if percentages:
            entities["percentages"] = [float(p) for p in percentages]

        # 金额提取 ($/¥ 后跟数字)
        money_pattern = r'[$¥]\s*(\d+(?:,\d{3})*(?:\.\d+)?)'
        amounts = re.findall(money_pattern, query)
        if amounts:
            entities["amounts"] = [float(a.replace(",", "")) for a in amounts]

        # 日期提取 (自然语言 → 日期范围)
        if "昨天" in query:
            entities["date_range"] = "yesterday"
        elif "今天" in query:
            entities["date_range"] = "today"
        elif "本周" in query:
            entities["date_range"] = "this_week"
        elif "上周" in query:
            entities["date_range"] = "last_week"
        elif "本月" in query:
            entities["date_range"] = "this_month"
        elif "上月" in query:
            entities["date_range"] = "last_month"
        elif "近7天" in query or "最近一周" in query or "这周" in query:
            entities["date_range"] = "7d"
        elif "近30天" in query or "最近一个月" in query:
            entities["date_range"] = "30d"

        return entities
