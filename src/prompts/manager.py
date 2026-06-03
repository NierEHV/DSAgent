"""
Prompt Manager — YAML 存储 + 读写 API
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_PROMPTS_PATH = Path(__file__).parent / "default.yaml"


class PromptManager:
    """Prompt 模板管理器"""

    def __init__(self, store_path: str = None):
        self.store_path = Path(store_path) if store_path else Path("data/prompts.yaml")
        self._cache: dict = {}
        self._init_store()

    def _init_store(self):
        if not self.store_path.exists():
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            # 从默认模板复制
            if DEFAULT_PROMPTS_PATH.exists():
                import shutil
                shutil.copy(DEFAULT_PROMPTS_PATH, self.store_path)
        self._load()

    def _load(self):
        try:
            import yaml
            with open(self.store_path, "r", encoding="utf-8") as f:
                self._cache = yaml.safe_load(f) or {}
        except ImportError:
            self._cache = self._simple_load()

    def _simple_load(self) -> dict:
        """无 pyyaml 时的降级加载"""
        if not self.store_path.exists():
            return {}
        with open(self.store_path, "r", encoding="utf-8") as f:
            content = f.read()
        result = {}
        current_key = None
        current_value = []
        for line in content.split("\n"):
            if not line.startswith(" ") and ":" in line and not line.startswith("#"):
                if current_key and current_value:
                    result[current_key] = "\n".join(current_value).strip()
                key = line.split(":")[0].strip()
                current_key = key
                current_value = []
            elif line.startswith("  ") and current_key:
                current_value.append(line[2:])
        if current_key and current_value:
            result[current_key] = "\n".join(current_value).strip()
        return result

    def get(self, category: str, name: str) -> str:
        section = self._cache.get(category, {})
        if isinstance(section, dict):
            return section.get(name, "")
        return ""

    def set(self, category: str, name: str, content: str):
        if category not in self._cache:
            self._cache[category] = {}
        if not isinstance(self._cache[category], dict):
            self._cache[category] = {}
        self._cache[category][name] = content

    def list_all(self) -> dict:
        return dict(self._cache)

    def save(self):
        content = self._to_yaml()
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _to_yaml(self) -> str:
        lines = []
        for category, prompts in self._cache.items():
            lines.append(f"{category}:")
            if isinstance(prompts, dict):
                for name, content in prompts.items():
                    lines.append(f"  {name}: |")
                    for line in (content or "").split("\n"):
                        lines.append(f"    {line}")
                    lines.append("")
            elif isinstance(prompts, str):
                lines.append(f"  {prompts}")
        return "\n".join(lines)


# 全局单例
prompt_manager = PromptManager()
