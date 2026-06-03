"""
配置系统 — 统一入口
"""

from __future__ import annotations

from .settings import settings
from .llm_config import create_llm
from .datasource_config import build_registry
