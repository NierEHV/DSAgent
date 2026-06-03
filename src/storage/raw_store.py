"""
原始数据存储 — 按数据源分库
保留原始 JSON 格式, 用于审计对账
"""

from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RawStore:
    """原始数据存储 — 按 source/data_type/timestamp.json"""

    def __init__(self, base_dir: str = "data/raw"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = 7

    def save(self, source: str, data_type: str, raw_data: dict) -> str:
        """保存原始数据"""
        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        source_dir = self.base_dir / source / data_type
        source_dir.mkdir(parents=True, exist_ok=True)
        filepath = source_dir / f"{ts}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2, default=str)
        return str(filepath)

    def load_latest(self, source: str, data_type: str) -> Optional[dict]:
        """加载最新一份原始数据"""
        source_dir = self.base_dir / source / data_type
        if not source_dir.exists():
            return None
        files = sorted(source_dir.glob("*.json"), reverse=True)
        if not files:
            return None
        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)

    def list_recent(self, source: str, data_type: str, limit: int = 10) -> list[dict]:
        """列出最近的原始数据"""
        source_dir = self.base_dir / source / data_type
        if not source_dir.exists():
            return []
        files = sorted(source_dir.glob("*.json"), reverse=True)[:limit]
        results = []
        for fp in files:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_file"] = fp.name
            results.append(data)
        return results

    def cleanup(self):
        """清理过期数据"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for source_dir in self.base_dir.iterdir():
            if not source_dir.is_dir():
                continue
            for type_dir in source_dir.iterdir():
                for filepath in type_dir.glob("*.json"):
                    mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                    if mtime < cutoff:
                        filepath.unlink()
                        logger.debug(f"清理过期原始数据: {filepath}")
