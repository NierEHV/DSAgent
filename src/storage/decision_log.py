"""
决策日志 — 记录所有用户决策
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DecisionRecord:
    """一条决策记录"""
    id: str
    alert_id: str = ""
    alert_type: str = ""       # inventory / advertising / profit / competitor
    severity: str = ""         # critical / warning / info
    decision: str = ""         # approved / rejected / auto_executed / pending / modified
    decided_by: str = "system"
    decided_at: str = ""
    action_taken: str = ""
    action_result: str = ""
    note: str = ""
    source_data: str = ""      # 数据源
    platform: str = ""         # amazon_us ...
    asin: str = ""
    sku: str = ""

    def __post_init__(self):
        if not self.decided_at:
            self.decided_at = datetime.now().isoformat()


class DecisionLog:
    """决策日志存储"""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self.base_dir / "decisions.jsonl"

    def record(self, decision: DecisionRecord) -> str:
        """追加一条决策"""
        d = asdict(decision)
        d["decided_at"] = datetime.now().isoformat()
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
        return decision.id

    def list_recent(self, limit: int = 50) -> list[dict]:
        """列出最近的决策"""
        if not self.filepath.exists():
            return []
        results = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return results[-limit:][::-1]  # 最新在前面

    def list_by_alert(self, alert_id: str) -> list[dict]:
        """查询某个告警的决策历史"""
        if not self.filepath.exists():
            return []
        results = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    if d.get("alert_id") == alert_id:
                        results.append(d)
                except json.JSONDecodeError:
                    continue
        return results

    def get_stats(self) -> dict:
        """决策统计"""
        recent = self.list_recent(1000)
        total = len(recent)
        approved = sum(1 for d in recent if d.get("decision") == "approved")
        rejected = sum(1 for d in recent if d.get("decision") == "rejected")
        auto = sum(1 for d in recent if d.get("decision") == "auto_executed")
        pending = total - approved - rejected - auto
        return {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "auto_executed": auto,
            "pending": pending,
        }
