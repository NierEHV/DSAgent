"""
告警引擎 — 多维度监控 + 规则评估 + 告警分发
参考 n8n-workflows-main: src/analytics_engine.py + src/performance_monitor.py

设计思路：
- analytics_engine.py → 数据分析 + 趋势检测 + 推荐生成
- performance_monitor.py → 告警规则 + 分发 + 解决跟踪
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional


class AlertLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass
class AlertRule:
    """告警规则定义 — 参考 analytics_engine.py 的趋势/模式分析"""
    name: str
    description: str
    condition: str                    # 条件表达式
    level: AlertLevel
    message_template: str             # 告警消息模板
    category: str                     # inventory/advertising/profit/listing/competitor
    channels: list[str] = field(default_factory=lambda: ["dingtalk"])
    cooldown_minutes: int = 60        # 冷却时间（避免频繁告警）
    enabled: bool = True
    auto_resolve_condition: Optional[str] = None  # 自动解除条件


@dataclass
class Alert:
    """告警实例"""
    id: str
    rule_name: str
    level: AlertLevel
    message: str
    category: str
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolve_note: Optional[str] = None


class AlertEngine:
    """
    告警引擎 — 参考 analytics_engine.py + performance_monitor.py

    核心流程：
    1. 拉取最新数据快照
    2. 逐条评估告警规则
    3. 去重 + 冷却检查
    4. 生成告警 → 分发到渠道
    5. 跟踪解决状态
    """

    def __init__(self, db_path: str = "data/alerts.db"):
        self.rules: dict[str, AlertRule] = {}
        self.active_alerts: dict[str, Alert] = {}
        self.alert_history: list[Alert] = []
        self._dispatcher: Optional[Callable] = None
        self._last_fired: dict[str, float] = {}  # rule_name → last_fired_timestamp

        self._register_default_rules()

    def _register_default_rules(self):
        """
        注册默认告警规则
        参考 analytics_engine.py analyze_workflow_patterns() — 从数据中发现模式
        """

        # ──── 库存告警 ────
        self.register_rule(AlertRule(
            name="inventory_critical_low",
            description="FBA库存低于安全线（< 7天销量）",
            condition="days_of_stock < 7 AND fba_stock > 0",
            level=AlertLevel.CRITICAL,
            message_template=(
                "🔴 **库存严重不足**\n"
                "SKU: {sku} | ASIN: {asin}\n"
                "FBA库存: {fba_stock} 件\n"
                "日均销量（7天）: {daily_sales} 件/天\n"
                "可售天数: {days_of_stock} 天\n"
                "建议: 立即补货，预计断货时间: {out_of_stock_date}"
            ),
            category="inventory",
            channels=["dingtalk", "wecom"],
        ))

        self.register_rule(AlertRule(
            name="inventory_excess",
            description="库存冗余（> 90天销量）",
            condition="days_of_stock > 90 AND fba_stock > 0",
            level=AlertLevel.WARNING,
            message_template=(
                "🟡 **库存冗余提醒**\n"
                "SKU: {sku} | ASIN: {asin}\n"
                "FBA库存: {fba_stock} 件\n"
                "可售天数: {days_of_stock} 天\n"
                "建议: 考虑清货/降价/移除，避免长期仓储费"
            ),
            category="inventory",
            cooldown_minutes=360,  # 6小时冷却
        ))

        # ──── 广告告警 ────
        self.register_rule(AlertRule(
            name="ad_acos_spike",
            description="ACOS 异常飙升（超过均值150%）",
            condition="current_acos > avg_acos_14d * 1.5 AND current_acos > 30",
            level=AlertLevel.WARNING,
            message_template=(
                "🟡 **ACOS 异常飙升**\n"
                "Campaign: {campaign_name}\n"
                "当前 ACOS: {current_acos}%\n"
                "14天均值: {avg_acos_14d}%\n"
                "广告花费: ${spend} | 销售额: ${sales}\n"
                "建议: 检查搜索词报告，暂停高花费低转化关键词"
            ),
            category="advertising",
            cooldown_minutes=120,
        ))

        self.register_rule(AlertRule(
            name="ad_budget_premature_exhaustion",
            description="广告预算可能提前耗尽",
            condition="budget_utilization > 0.95 AND current_hour < 18",
            level=AlertLevel.WARNING,
            message_template=(
                "🟡 **广告预算即将耗尽**\n"
                "Campaign: {campaign_name}\n"
                "已花费: ${spend} / 预算: ${budget}\n"
                "使用率: {utilization}%\n"
                "预计耗尽时间: {exhausted_time}\n"
                "建议: 追加预算或调整出价策略"
            ),
            category="advertising",
            cooldown_minutes=30,
        ))

        # ──── 利润告警 ────
        self.register_rule(AlertRule(
            name="profit_margin_collapse",
            description="利润大幅下降",
            condition="current_margin < avg_margin_30d * 0.8 AND current_margin < 10",
            level=AlertLevel.CRITICAL,
            message_template=(
                "🔴 **利润率大幅下降**\n"
                "SKU: {sku}\n"
                "当前毛利率: {current_margin}%\n"
                "30天均值: {avg_margin_30d}%\n"
                "退款率: {refund_rate}%\n"
                "广告费占比: {ad_ratio}%\n"
                "可能原因: {likely_cause}\n"
                "建议: 检查退款原因 + 广告效率 + FBA费率变化"
            ),
            category="profit",
            channels=["dingtalk", "wecom"],
        ))

        # ──── 竞品告警 ────
        self.register_rule(AlertRule(
            name="hijacker_detected",
            description="发现新跟卖者",
            condition="new_seller_count > 0",
            level=AlertLevel.CRITICAL,
            message_template=(
                "🔴 **发现新跟卖者**\n"
                "ASIN: {asin}\n"
                "新卖家: {seller_name}\n"
                "跟卖价格: ${seller_price}\n"
                "我方价格: ${our_price}\n"
                "卖家评级: {seller_rating}\n"
                "建议: 检查是否恶意跟卖，考虑投诉/Test Buy"
            ),
            category="competitor",
            channels=["dingtalk"],
            cooldown_minutes=10,
        ))

        self.register_rule(AlertRule(
            name="buy_box_lost",
            description="Buy Box 丢失",
            condition="buy_box_owner != 'self'",
            level=AlertLevel.CRITICAL,
            message_template=(
                "🔴 **Buy Box 丢失**\n"
                "ASIN: {asin}\n"
                "当前 Buy Box 卖家: {buy_box_owner}\n"
                "价格差: {price_diff}%\n"
                "失去时长: {lost_duration}\n"
                "建议: 检查价格竞争力，必要时调价"
            ),
            category="competitor",
            channels=["dingtalk", "wecom"],
            cooldown_minutes=30,
        ))

    def register_rule(self, rule: AlertRule):
        """注册告警规则"""
        self.rules[rule.name] = rule

    def evaluate(self, data_snapshot: dict) -> list[Alert]:
        """
        评估所有告警规则
        参考 analytics_engine.py get_workflow_analytics() 的多维度扫描
        """
        triggered_alerts = []

        for rule_name, rule in self.rules.items():
            if not rule.enabled:
                continue

            # 冷却检查
            last_fired = self._last_fired.get(rule_name, 0)
            if time.time() - last_fired < rule.cooldown_minutes * 60:
                continue

            # 规则评估
            if self._evaluate_condition(rule.condition, data_snapshot):
                # 生成告警消息
                message = rule.message_template
                for key, value in data_snapshot.items():
                    message = message.replace(f"{{{key}}}", str(value))

                alert = Alert(
                    id=f"{rule_name}_{int(time.time())}",
                    rule_name=rule_name,
                    level=rule.level,
                    message=message,
                    category=rule.category,
                )

                triggered_alerts.append(alert)
                self._last_fired[rule_name] = time.time()

                # 追踪告警
                self.active_alerts[alert.id] = alert

        return triggered_alerts

    async def evaluate_and_dispatch(
        self,
        data_snapshot: dict,
        dispatcher: Optional[Callable] = None,
    ) -> list[Alert]:
        """评估 + 分发"""
        alerts = self.evaluate(data_snapshot)

        dispatch_fn = dispatcher or self._dispatcher
        if dispatch_fn:
            for alert in alerts:
                rule = self.rules[alert.rule_name]
                for channel in rule.channels:
                    await dispatch_fn(channel, alert)

        return alerts

    def acknowledge(self, alert_id: str, user: str) -> bool:
        """确认告警"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now().isoformat()
            alert.acknowledged_by = user
            return True
        return False

    def resolve(self, alert_id: str, note: str = "", user: str = "system") -> bool:
        """
        解决告警 — 参考 performance_monitor.py resolve_alert()
        """
        if alert_id in self.active_alerts:
            alert = self.active_alerts.pop(alert_id)
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now().isoformat()
            alert.resolved_by = user
            alert.resolve_note = note
            self.alert_history.append(alert)
            return True
        return False

    def get_alerts(
        self,
        status: Optional[str] = None,
        level: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[dict]:
        """查询告警列表 — 参考 performance_monitor.py get_alerts()"""
        all_alerts = list(self.active_alerts.values()) + self.alert_history[-100:]

        results = []
        for alert in all_alerts:
            if status and alert.status.value != status:
                continue
            if level and alert.level.value != level:
                continue
            if category and alert.category != category:
                continue
            results.append({
                "id": alert.id,
                "rule_name": alert.rule_name,
                "level": alert.level.value,
                "message": alert.message,
                "category": alert.category,
                "status": alert.status.value,
                "created_at": alert.created_at,
                "resolved_at": alert.resolved_at,
            })

        return results

    def get_summary(self) -> dict:
        """告警摘要"""
        active = list(self.active_alerts.values())
        return {
            "total_active": len(active),
            "critical": sum(1 for a in active if a.level == AlertLevel.CRITICAL),
            "warning": sum(1 for a in active if a.level == AlertLevel.WARNING),
            "info": sum(1 for a in active if a.level == AlertLevel.INFO),
            "by_category": {
                cat: sum(1 for a in active if a.category == cat)
                for cat in set(a.category for a in active)
            },
        }

    def _evaluate_condition(self, condition: str, data: dict) -> bool:
        """
        安全的条件评估
        参考 analytics_engine.py 中的条件分析逻辑
        """
        try:
            # 安全的表达式评估（仅允许有限的运算符）
            safe_vars = {k: v for k, v in data.items() if isinstance(v, (int, float, bool, str))}
            return bool(eval(condition, {"__builtins__": {}}, safe_vars))
        except Exception:
            return False


# 全局单例
alert_engine = AlertEngine()
