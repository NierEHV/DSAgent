"""
Agent 基类 — 统一接口
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from datasource.registry import DataSourceRegistry
    from engine.analysis_pipeline import AnalysisPipeline, AnalysisResult
    from engine.decision_engine import DecisionEngine


class BaseAgent(ABC):
    """Agent 基类"""

    name: str = "base"
    description: str = ""

    def __init__(self, registry: "DataSourceRegistry" = None,
                 pipeline: "AnalysisPipeline" = None,
                 decision_engine: "DecisionEngine" = None):
        self.registry = registry
        self.pipeline = pipeline
        self.decision_engine = decision_engine

    @abstractmethod
    async def run(self, **params) -> dict:
        """执行 Agent 核心逻辑"""
        ...
