"""
全量 AI 分析管线
三道工序: 规则引擎 → LLM 深度分析 → 分类输出
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llm.base import BaseLLM

logger = logging.getLogger(__name__)


@dataclass
class AnalysisItem:
    """单条分析结果"""
    item_id: str = ""
    item_type: str = ""           # inventory / advertising / competitor / profit
    severity: str = "normal"      # normal / warning / critical
    title: str = ""
    detail: str = ""
    suggestion: str = ""
    suggestion_reason: str = ""
    has_optimization: bool = False
    priority: int = 0             # 0-10, 0=无需关注
    source_data: dict = field(default_factory=dict)
    change: Optional[Any] = None  # DataChange


@dataclass
class AnalysisResult:
    """分析管线输出"""
    data_type: str = ""
    status: str = "normal"        # normal / suggestion / alert
    alerts: list[AnalysisItem] = field(default_factory=list)       # 🔴 需要决策
    suggestions: list[AnalysisItem] = field(default_factory=list)   # 🟡 可选优化
    normal_count: int = 0         # 🟢 已记录的正常项
    analyzed_at: str = ""

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now().isoformat()


# ═══════════════════════════ 规则引擎 ═══════════════════════════

class RuleEngine:
    """硬规则筛子 — 阈值从配置读取, 可前端实时修改"""

    RULES_TEMPLATE = {
        "inventory": [
            {"name": "inventory_critical_low", "severity": "critical",
             "title": "库存严重不足", "template": "{sku} 仅剩 {fba_stock}件, 可售 {days_of_stock}天",
             "suggestion": "建议立即补货 {suggested_qty} 件", "priority": 10},
            {"name": "inventory_low_warning", "severity": "warning",
             "title": "库存偏低", "template": "{sku} 剩余 {fba_stock}件, 可售 {days_of_stock}天",
             "suggestion": "建议本周内补货", "priority": 7},
            {"name": "inventory_excess", "severity": "warning",
             "title": "库存冗余", "template": "{sku} 可售 {days_of_stock}天, 存在长期仓储费风险",
             "suggestion": "建议降价促销或移除库存", "priority": 4},
        ],
        "advertising": [
            {"name": "acos_spike", "severity": "warning",
             "title": "ACOS 异常飙升", "template": "{campaign_name}: ACOS {acos}% (14天均值 {avg_acos_14d}%)",
             "suggestion": "检查搜索词报告, 暂停高花费低转化关键词, 降低出价10-15%", "priority": 7},
            {"name": "budget_exhausted", "severity": "warning",
             "title": "广告预算即将耗尽", "template": "{campaign_name}: 已花费 ${spend}/{budget} ({budget_used_pct}%)",
             "suggestion": "追加预算或调整出价策略", "priority": 6},
            {"name": "high_performer", "severity": "normal",
             "title": "表现优异", "template": "{campaign_name}: ACOS {acos}% ROAS {roas}x",
             "suggestion": "可适当增加预算, 扩展关键词", "priority": 3, "has_optimization": True},
        ],
        "competitor": [
            {"name": "buy_box_lost", "severity": "critical",
             "title": "Buy Box 丢失", "template": "{asin} Buy Box 被 {buy_box_owner} 抢占, 价格 ${buy_box_price}",
             "suggestion": "检查价格竞争力, 必要时调价", "priority": 10},
            {"name": "new_hijacker", "severity": "critical",
             "title": "发现新卖家", "template": "{asin} 发现 {count} 个新卖家",
             "suggestion": "检查卖家资质, 考虑投诉或 Test Buy", "priority": 9},
        ],
        "profit": [
            {"name": "profit_margin_collapse", "severity": "critical",
             "title": "利润率严重偏低", "template": "{sku}: 毛利率 {gross_margin}%",
             "suggestion": "检查退款率、广告占比、FBA费率变化", "priority": 10},
            {"name": "profit_margin_low", "severity": "warning",
             "title": "利润率偏低", "template": "{sku}: 毛利率 {gross_margin}%",
             "suggestion": "关注广告效率和退款率", "priority": 6},
            {"name": "refund_rate_high", "severity": "critical",
             "title": "退款率异常高", "template": "{sku}: 退款率 {refund_rate}%",
             "suggestion": "检查产品描述是否准确, 分析退款原因", "priority": 9},
        ],
    }

    def __init__(self, alert_config: dict = None):
        self._built_rules: dict = {}
        self.build(alert_config or {})

    def build(self, alert_config: dict):
        """根据配置重建规则 (阈值动态注入)"""
        inv = alert_config.get("inventory", {})
        ad = alert_config.get("advertising", {})
        prof = alert_config.get("profit", {})
        comp = alert_config.get("competitor", {})

        crit_days = inv.get("critical_days", 7)
        warn_days = inv.get("warning_days", 14)
        excess_days = inv.get("excess_days", 90)

        acos_thresh = ad.get("acos_spike_threshold", 30)
        acos_ratio = ad.get("acos_spike_ratio", 1.5)
        budget_pct = ad.get("budget_exhausted_pct", 90)
        hp_acos = ad.get("high_performer_acos", 15)
        hp_roas = ad.get("high_performer_roas", 5.0)

        p_crit = prof.get("critical_margin", 10)
        p_warn = prof.get("warning_margin", 15)
        ref_crit = prof.get("refund_rate_critical", 10)

        bb_enabled = comp.get("buy_box_lost_enabled", True)
        ns_enabled = comp.get("new_seller_enabled", True)

        self._built_rules = {
            "inventory": [
                {**self.RULES_TEMPLATE["inventory"][0],
                 "condition": self._mkcond(lambda i, c=crit_days: i.get("days_of_stock", 999) < c)},
                {**self.RULES_TEMPLATE["inventory"][1],
                 "condition": self._mkcond(lambda i, cw=crit_days, w=warn_days: cw <= i.get("days_of_stock", 0) < w)},
                {**self.RULES_TEMPLATE["inventory"][2],
                 "condition": self._mkcond(lambda i, e=excess_days: i.get("days_of_stock", 0) > e)},
            ],
            "advertising": [
                {**self.RULES_TEMPLATE["advertising"][0],
                 "condition": self._mkcond(lambda i, at=acos_thresh, ar=acos_ratio:
                     i.get("acos",0) > i.get("avg_acos_14d",100) * ar and i.get("acos",0) > at)},
                {**self.RULES_TEMPLATE["advertising"][1],
                 "condition": self._mkcond(lambda i, bp=budget_pct: i.get("budget_used_pct", 0) > bp)},
                {**self.RULES_TEMPLATE["advertising"][2],
                 "condition": self._mkcond(lambda i, ha=hp_acos, hr=hp_roas: i.get("acos",100) < ha and i.get("roas",0) > hr),
                 "has_optimization": True},
            ],
            "competitor": [
                {**self.RULES_TEMPLATE["competitor"][0],
                 "condition": self._mkcond(lambda i: bb_enabled and not i.get("buy_box_is_ours", True))},
                {**self.RULES_TEMPLATE["competitor"][1],
                 "condition": self._mkcond(lambda i: ns_enabled and len(i.get("new_sellers", [])) > 0)},
            ],
            "profit": [
                {**self.RULES_TEMPLATE["profit"][0],
                 "condition": self._mkcond(lambda i, pc=p_crit: i.get("gross_margin", 100) < pc)},
                {**self.RULES_TEMPLATE["profit"][1],
                 "condition": self._mkcond(lambda i, pc=p_crit, pw=p_warn: pc <= i.get("gross_margin", 0) < pw)},
                {**self.RULES_TEMPLATE["profit"][2],
                 "condition": self._mkcond(lambda i, rc=ref_crit: i.get("refund_rate", 0) > rc)},
            ],
        }

    @staticmethod
    def _mkcond(fn):
        """包装 condition lambda, 异常时返回 False"""
        def _wrapped(item):
            try: return fn(item)
            except Exception: return False
        return _wrapped

    @staticmethod
    def _safe_format(template: str, item: dict) -> str:
        """安全模板替换, 缺失的 key 保留原样不报错"""
        import re
        def _repl(m):
            key = m.group(1)
            val = item.get(key)
            if val is not None:
                return str(val)
            return m.group(0)  # 保留原占位符
        return re.sub(r'\{(\w+)\}', _repl, template)

    def evaluate(self, data_type: str, items: list[dict]) -> tuple[list[AnalysisItem], list[str]]:
        """
        评估所有规则
        返回: (命中的分析项, 正常项的ID列表)
        """
        rules = self._built_rules.get(data_type, [])
        alerts = []
        normal_ids = []

        for item in items:
            item_id = item.get("sku") or item.get("asin") or item.get("campaign_id") or str(hash(str(item)))
            triggered = False

            for rule in rules:
                try:
                    if rule["condition"](item):
                        detail = self._safe_format(rule["template"], item)
                        suggestion = self._safe_format(rule.get("suggestion", ""), item)

                        analysis_item = AnalysisItem(
                            item_id=str(item_id),
                            item_type=data_type,
                            severity=rule["severity"],
                            title=rule["title"],
                            detail=detail,
                            suggestion=suggestion,
                            has_optimization=rule.get("has_optimization", rule["severity"] != "normal"),
                            priority=rule.get("priority", 5),
                            source_data=item,
                        )

                        if rule["severity"] in ("critical", "warning"):
                            alerts.append(analysis_item)
                        elif rule.get("has_optimization"):
                            analysis_item.severity = "info"
                            alerts.append(analysis_item)

                        triggered = True
                        break  # 一个 item 只匹配第一条规则
                except Exception:
                    continue

            if not triggered:
                normal_ids.append(str(item_id))

        return alerts, normal_ids

    def identify_normal(self, data_type: str, items: list[dict]) -> list[str]:
        """快速识别明显正常的项"""
        rules = self._built_rules.get(data_type, [])
        normal_ids = []
        for item in items:
            item_id = item.get("sku") or item.get("asin") or item.get("campaign_id") or str(hash(str(item)))
            if not any(r["condition"](item) for r in rules):
                normal_ids.append(str(item_id))
        return normal_ids


# ═══════════════════════════ 分析管线 ═══════════════════════════

ANALYSIS_PROMPT = """你是一个专业的亚马逊运营分析专家。请对以下数据进行逐项深度分析。

当前数据:
{current_data}

历史对比 (变动部分):
{changes}

请逐项分析，对每一项给出 JSON 输出：
{{
  "items": [
    {{
      "item_id": "...",
      "status": "normal | warning | critical",
      "assessment": "简短判断 (1-2句)",
      "cause_analysis": "变动原因分析",
      "suggestion": "具体可执行的建议 (如果确实需要优化则填写，否则留空)",
      "has_optimization": true/false,
      "priority": 0-10
    }}
  ]
}}

注意：
- 确实没问题的项，status 给 normal, suggestion 留空, has_optimization=false
- 不要为了刷存在感而硬给建议
- 考虑和竞品动态、市场趋势的关联
- 优先考虑对我们利润和运营安全的实际影响"""


class AnalysisPipeline:
    """全量分析管线"""

    def __init__(self, llm: "BaseLLM" = None, alert_config: dict = None):
        self.rule_engine = RuleEngine(alert_config)
        self.llm = llm

    def update_thresholds(self, alert_config: dict):
        """前端改了阈值 → 重建规则"""
        self.rule_engine.build(alert_config)

    async def process(self, data_type: str, current_items: list[dict],
                      previous_items: list[dict] = None,
                      changes: list = None) -> AnalysisResult:
        """
        分析管线入口
        1. 规则引擎预筛
        2. LLM 深度分析 (对不明显的数据)
        3. 分类输出
        """
        # Step 1: 规则引擎
        rule_alerts, rule_normal_ids = self.rule_engine.evaluate(data_type, current_items)

        # Step 2: 找出需要 AI 分析的 (不明显的)
        needs_ai = []
        for item in current_items:
            item_id = str(item.get("sku") or item.get("asin") or item.get("campaign_id") or "")
            if item_id not in rule_normal_ids:
                # 规则已经标记为异常或优化建议
                pass
            else:
                # 规则判断正常, 但有变动 → 需要 AI 再看一遍
                has_changes = any(
                    c.sku == item_id or c.asin == item_id or c.campaign_id == item_id
                    for c in (changes or [])
                )
                if has_changes and self.llm:
                    needs_ai.append(item)

        # Step 3: LLM 分析
        llm_items = []
        if needs_ai and self.llm:
            try:
                llm_items = await self._llm_analyze(data_type, needs_ai, changes or [])
            except Exception as e:
                logger.warning(f"LLM 分析失败: {e}")

        # Step 4: 合并结果
        all_alerts = list(rule_alerts) + [
            item for item in llm_items
            if item.severity in ("critical", "warning")
        ]
        all_suggestions = [
            item for item in llm_items
            if item.has_optimization and item.severity not in ("critical", "warning")
        ]
        # 也把规则的优化建议加进去
        for ra in rule_alerts:
            if ra.severity not in ("critical", "warning") and ra.has_optimization:
                all_suggestions.append(ra)

        normal_count = len(current_items) - len(all_alerts)

        status = "alert" if all_alerts else "suggestion" if all_suggestions else "normal"

        return AnalysisResult(
            data_type=data_type,
            status=status,
            alerts=all_alerts,
            suggestions=all_suggestions,
            normal_count=max(0, normal_count),
        )

    async def _llm_analyze(self, data_type: str,
                           items: list[dict],
                           changes: list) -> list[AnalysisItem]:
        """调用 LLM 进行分析"""
        prompt = ANALYSIS_PROMPT.format(
            current_data=json.dumps(items, ensure_ascii=False, indent=2, default=str),
            changes=json.dumps(
                [{"field": c.field, "prev": c.previous_value, "curr": c.current_value,
                  "change_pct": c.change_pct} for c in changes],
                ensure_ascii=False, indent=2, default=str,
            ),
        )

        response = await self.llm.analyze(
            system_prompt="你是亚马逊运营分析专家。只返回 JSON, 不返回其他内容。",
            context={"prompt": prompt},
        )

        # 解析 LLM 返回的 JSON
        try:
            content = response.content
            # 去掉可能的 markdown 代码块标记
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            data = json.loads(content)
            llm_items = data.get("items", [])
        except (json.JSONDecodeError, IndexError):
            logger.warning("LLM 返回格式无法解析, 使用原始内容")
            return []

        results = []
        for li in llm_items:
            results.append(AnalysisItem(
                item_id=li.get("item_id", ""),
                item_type=data_type,
                severity=li.get("status", "normal"),
                title=li.get("assessment", ""),
                detail=li.get("cause_analysis", ""),
                suggestion=li.get("suggestion", ""),
                has_optimization=li.get("has_optimization", False),
                priority=li.get("priority", 0),
                source_data={},
            ))
        return results
