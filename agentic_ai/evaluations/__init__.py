"""
AI Agent Evaluation Framework

Evaluation toolkit for testing AI agents against business scenarios.
"""

from .evaluator import AgentEvaluationRunner, AgentTrace, TestCaseResult
from .metrics import (
    ToolUsageEvaluator,
    CompletenessEvaluator,
    ResponseQualityEvaluator,
    AccuracyEvaluator,
    EvaluationResult,
    MetricType
)

__all__ = [
    "AgentEvaluationRunner",
    "AgentTrace",
    "TestCaseResult",
    "ToolUsageEvaluator",
    "CompletenessEvaluator",
    "ResponseQualityEvaluator",
    "AccuracyEvaluator",
    "EvaluationResult",
    "MetricType"
]

__version__ = "1.0.0"
