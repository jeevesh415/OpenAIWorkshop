"""
AI Agent Evaluation Framework

Evaluation toolkit for testing AI agents against business scenarios.
"""

from .evaluator import AgentEvaluationRunner, AgentTrace, TestCaseResult
from .metrics import (
    ToolBehaviorEvaluator,
    CompletenessEvaluator,
    ResponseQualityEvaluator,
    GroundedAccuracyEvaluator,
    EvaluationResult,
    MetricType
)

__all__ = [
    "AgentEvaluationRunner",
    "AgentTrace",
    "TestCaseResult",
    "ToolBehaviorEvaluator",
    "CompletenessEvaluator",
    "ResponseQualityEvaluator",
    "GroundedAccuracyEvaluator",
    "EvaluationResult",
    "MetricType"
]

__version__ = "1.0.0"
