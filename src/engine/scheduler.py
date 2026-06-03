"""
定时调度器
按配置的 interval_minutes 定时拉数据 + 对比 + 分析
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datasource.registry import DataSourceRegistry
    from storage.snapshot_store import SnapshotStore
    from storage.raw_store import RawStore
    from storage.decision_log import DecisionLog
    from engine.diff_engine import DiffEngine
    from engine.analysis_pipeline import AnalysisPipeline
    from engine.decision_engine import DecisionEngine

logger = logging.getLogger(__name__)


class MonitorScheduler:
    """监控调度器"""

    def __init__(self, registry: "DataSourceRegistry",
                 snapshot_store: "SnapshotStore",
                 raw_store: "RawStore",
                 analysis_pipeline: "AnalysisPipeline",
                 diff_engine: "DiffEngine",
                 decision_engine: "DecisionEngine",
                 scheduler_config: dict = None):
        cfg = scheduler_config or {}
        self.registry = registry
        self.snapshot_store = snapshot_store
        self.raw_store = raw_store
        self.pipeline = analysis_pipeline
        self.diff_engine = diff_engine
        self.decision_engine = decision_engine
        self.interval_minutes = cfg.get("interval_minutes", 5)
        self.monitor_types = cfg.get("enabled_agents", ["inventory", "advertising", "competitor", "profit"])
        self.working_hours_only = cfg.get("working_hours_only", False)
        self.working_hours_start = cfg.get("working_hours_start", "09:00")
        self.working_hours_end = cfg.get("working_hours_end", "18:00")
        self._running = False
        self._task = None

    def _is_working_hours(self) -> bool:
        if not self.working_hours_only: return True
        from datetime import datetime
        now = datetime.now().strftime("%H:%M")
        return self.working_hours_start <= now <= self.working_hours_end

    async def start(self):
        """启动调度循环"""
        self._running = True
        logger.info(f"调度器启动, 间隔: {self.interval_minutes}分钟")
        while self._running:
            try:
                await self.run_all_checks()
            except Exception as e:
                logger.error(f"调度执行异常: {e}")
            await asyncio.sleep(self.interval_minutes * 60)

    async def run_all_checks(self) -> dict:
        """执行全部监控检查"""
        results = {}
        for data_type in self.monitor_types:
            try:
                result = await self.run_check(data_type)
                results[data_type] = result
            except Exception as e:
                logger.error(f"{data_type} 检查失败: {e}")
                results[data_type] = {"status": "error", "error": str(e)}
        return results

    async def run_check(self, data_type: str) -> dict:
        """执行单类型检查"""
        t0 = time.time()

        # 1. 拉取数据
        current_items = await self.registry.fetch(data_type)
        if not current_items:
            return {"status": "no_data", "data_type": data_type}

        # 2. 存原始数据 (每个 item 按来源分存)
        for item in current_items:
            prov = getattr(item, "provenance", None)
            if prov and prov.source != "mock":
                raw_data = {"data_type": data_type, "item": str(item), "snapshot_time": datetime.now().isoformat()}
                self.raw_store.save(prov.source, data_type, raw_data)

        # 3. 加载上一次快照
        prev_snapshot = self.snapshot_store.load_latest(data_type)
        prev_items = prev_snapshot.get("items", []) if prev_snapshot else []

        # 4. 保存新快照
        self.snapshot_store.save(data_type, current_items, metadata={
            "sources": list(set(
                getattr(i, "provenance", None).source
                for i in current_items
                if getattr(i, "provenance", None)
            )),
        })

        # 5. 数据对比
        curr_dicts = [_dataclass_to_dict(i) for i in current_items]
        changes = self.diff_engine.compare(data_type, prev_items, curr_dicts)

        # 6. 分析管线
        analysis = await self.pipeline.process(
            data_type=data_type,
            current_items=curr_dicts,
            previous_items=prev_items,
            changes=changes,
        )

        duration_ms = int((time.time() - t0) * 1000)
        logger.info(f"[Scheduler] {data_type}: status={analysis.status}, "
                    f"alerts={len(analysis.alerts)}, suggestions={len(analysis.suggestions)}, "
                    f"normal={analysis.normal_count}, {duration_ms}ms")

        return {
            "data_type": data_type,
            "status": analysis.status,
            "alerts": [{"id": a.item_id, "type": a.item_type, "severity": a.severity,
                        "title": a.title, "detail": a.detail,
                        "suggestion": a.suggestion, "priority": a.priority}
                       for a in analysis.alerts],
            "suggestions": [{"id": s.item_id, "type": s.item_type, "severity": "info",
                             "title": s.title, "detail": s.detail,
                             "suggestion": s.suggestion, "priority": s.priority}
                            for s in analysis.suggestions],
            "normal_count": analysis.normal_count,
            "changes_count": len(changes),
            "duration_ms": duration_ms,
        }

    def stop(self):
        self._running = False


def _dataclass_to_dict(obj) -> dict:
    """dataclass 转 dict, 处理嵌套"""
    from dataclasses import asdict, is_dataclass
    if is_dataclass(obj):
        d = asdict(obj)
        # 提取 provenance 的 source 字段到顶层方便 diff
        prov = d.pop("provenance", None)
        if prov:
            d["data_source"] = prov.get("source", "")
            d["platform"] = prov.get("platform", "")
        return d
    return dict(obj) if isinstance(obj, dict) else {}
