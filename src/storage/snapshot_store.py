"""
标准化快照存储 — 所有数据源合并存储
Agent 读这里做对比, 保留 90 天
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SnapshotStore:
    """快照存储 — 按 data_type/timestamp.json, 单层合并"""

    def __init__(self, base_dir: str = "data/snapshots"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = 90

    def save(self, data_type: str, items: list, metadata: dict = None) -> str:
        """保存快照, items 为 dataclass 列表"""
        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        type_dir = self.base_dir / data_type
        type_dir.mkdir(parents=True, exist_ok=True)
        filepath = type_dir / f"{ts}.json"

        # 序列化 dataclass
        serialized = []
        for item in items:
            d = asdict(item)
            # 处理非可序列化对象
            for key, val in list(d.items()):
                if hasattr(val, '__dict__') and not isinstance(val, (str, int, float, bool, list, dict, type(None))):
                    d[key] = str(val)
            serialized.append(d)

        payload = {
            "type": data_type,
            "timestamp": ts,
            "count": len(serialized),
            "metadata": metadata or {},
            "items": serialized,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

        # 更新 latest 符号链接
        latest_link = type_dir / "latest.json"
        if latest_link.exists():
            latest_link.unlink()
        with open(latest_link, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=str)

        return str(filepath)

    def load_latest(self, data_type: str) -> Optional[dict]:
        """加载最新快照"""
        latest_link = self.base_dir / data_type / "latest.json"
        if not latest_link.exists():
            # 尝试找最近的文件
            type_dir = self.base_dir / data_type
            if not type_dir.exists():
                return None
            files = sorted(type_dir.glob("*.json"), reverse=True)
            if not files:
                return None
            latest_link = files[0]
        with open(latest_link, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_previous(self, data_type: str) -> Optional[dict]:
        """加载倒数第二份快照 (用于对比)"""
        type_dir = self.base_dir / data_type
        if not type_dir.exists():
            return None
        files = sorted(type_dir.glob("*.json"), reverse=True)
        # 过滤 latest.json
        real_files = [f for f in files if f.name != "latest.json"]
        if len(real_files) < 2:
            return None
        with open(real_files[1], "r", encoding="utf-8") as f:
            return json.load(f)

    def list_history(self, data_type: str, limit: int = 30) -> list[dict]:
        """列出历史快照"""
        type_dir = self.base_dir / data_type
        if not type_dir.exists():
            return []
        files = sorted(type_dir.glob("*.json"), reverse=True)
        real_files = [f for f in files if f.name != "latest.json"][:limit]
        results = []
        for fp in real_files:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_file"] = fp.name
            results.append(data)
        return results

    def cleanup(self):
        """清理过期快照"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for type_dir in self.base_dir.iterdir():
            if not type_dir.is_dir():
                continue
            for filepath in type_dir.glob("*.json"):
                if filepath.name == "latest.json":
                    continue
                mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                if mtime < cutoff:
                    filepath.unlink()
                    logger.debug(f"清理过期快照: {filepath}")
