"""
决策引擎 — 风险分级 + 自动执行 + 人工审批
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from storage.decision_log import DecisionLog, DecisionRecord

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK = "LOW_RISK"
    ANALYSIS = "ANALYSIS"
    HIGH_RISK = "HIGH_RISK"


class ApprovalStatus(str, Enum):
    PENDING = "pending"       # 待运营初审
    REVIEWED = "reviewed"     # 运营已审,待主管终审
    APPROVED = "approved"     # 批准
    REJECTED = "rejected"     # 驳回


class DecisionEngine:
    """决策引擎 — 支持多级审批"""

    def __init__(self, decision_log: "DecisionLog", auto_approve_low_risk: bool = True):
        self.log = decision_log
        self.auto_approve_low_risk = auto_approve_low_risk
        self._approvals: dict[str, dict] = {}  # decision_id → approval state

    def assess_risk(self, severity: str, action_type: str = "") -> RiskLevel:
        if action_type in ("补货", "调价", "投诉", "test_buy"):
            return RiskLevel.HIGH_RISK
        if action_type in ("降出价", "追加预算", "降价促销"):
            return RiskLevel.ANALYSIS
        if severity == "critical":
            return RiskLevel.HIGH_RISK
        if severity == "warning":
            return RiskLevel.ANALYSIS
        return RiskLevel.LOW_RISK

    def should_auto_approve(self, risk_level: RiskLevel) -> bool:
        if risk_level in (RiskLevel.READ_ONLY, RiskLevel.LOW_RISK) and self.auto_approve_low_risk:
            return True
        return False

    def needs_workflow(self, risk_level: RiskLevel) -> bool:
        """是否需要多级审批"""
        return risk_level == RiskLevel.HIGH_RISK

    async def submit(self, alert: dict, user: str = "system", note: str = "") -> "DecisionRecord":
        """提交审批 → PENDING"""
        from storage.decision_log import DecisionRecord
        risk = self.assess_risk(alert.get("severity", "warning"), alert.get("action_type", ""))

        if self.should_auto_approve(risk):
            return await self._record(alert, "auto_executed", user, note)

        if not self.needs_workflow(risk):
            return await self._record(alert, "pending", user, note)

        # HIGH_RISK: 走多级审批
        record = await self._record(alert, "pending", user, note)
        self._approvals[record.id] = {
            "status": ApprovalStatus.PENDING,
            "reviewer": None, "review_note": "",
            "approver": None, "approve_note": "",
        }
        return record

    async def review(self, decision_id: str, reviewer: str, decision: str, note: str = "") -> dict:
        """运营初审 → REVIEWED or REJECTED"""
        state = self._approvals.get(decision_id, {})
        if state.get("status") != ApprovalStatus.PENDING:
            return {"status": "error", "message": "当前状态不允许初审"}

        if decision == "rejected":
            state["status"] = ApprovalStatus.REJECTED
            state["reviewer"] = reviewer; state["review_note"] = note
            self._update_record(decision_id, "rejected", reviewer, note)
            return {"status": "rejected", "decision_id": decision_id}

        state["status"] = ApprovalStatus.REVIEWED
        state["reviewer"] = reviewer; state["review_note"] = note
        self._update_record(decision_id, "reviewed", reviewer, note)
        return {"status": "reviewed", "decision_id": decision_id}

    async def approve_final(self, decision_id: str, approver: str, decision: str, note: str = "") -> dict:
        """主管终审 → APPROVED or REJECTED"""
        state = self._approvals.get(decision_id, {})
        if state.get("status") != ApprovalStatus.REVIEWED:
            return {"status": "error", "message": "当前状态不允许终审"}

        if decision == "rejected":
            state["status"] = ApprovalStatus.REJECTED
            state["approver"] = approver; state["approve_note"] = note
            self._update_record(decision_id, "rejected", approver, note)
            return {"status": "rejected", "decision_id": decision_id}

        state["status"] = ApprovalStatus.APPROVED
        state["approver"] = approver; state["approve_note"] = note
        self._update_record(decision_id, "approved", approver, note)
        return {"status": "approved", "decision_id": decision_id}

    def get_approval_status(self, decision_id: str) -> dict:
        return self._approvals.get(decision_id, {"status": "unknown"})

    async def decide(self, alert: dict, decision: str,
                     user: str = "system", note: str = "") -> "DecisionRecord":
        return await self.submit(alert, user, note)

    async def _record(self, alert: dict, decision: str, user: str, note: str) -> "DecisionRecord":
        from storage.decision_log import DecisionRecord
        record = DecisionRecord(
            id=f"dec_{uuid.uuid4().hex[:12]}",
            alert_id=alert.get("id", ""),
            alert_type=alert.get("type", ""),
            severity=alert.get("severity", ""),
            decision=decision,
            decided_by=user,
            action_taken=alert.get("suggestion", ""),
            note=note,
            source_data=alert.get("data_source", ""),
            platform=alert.get("platform", ""),
            asin=alert.get("asin", ""),
            sku=alert.get("sku", ""),
        )
        self.log.record(record)
        return record

    def _update_record(self, decision_id: str, decision: str, user: str, note: str):
        """更新已有决策记录的状态"""
        record = self.log.list_recent(100)
        # 追加一条新的决策记录 (JSONL 不可原地更新)
        from storage.decision_log import DecisionRecord
        import uuid as _uuid
        new_record = DecisionRecord(
            id=decision_id,
            decision=decision,
            decided_by=user,
            note=note,
        )
        self.log.record(new_record)
