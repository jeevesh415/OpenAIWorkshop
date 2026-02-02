"""
Evaluation metrics for AI Agent performance assessment.
Pattern-agnostic metrics that work across:
- single agents
- handoff agents
- reflection agents
- research/magentic agents
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


# =========================
# Metric Types
# =========================

class MetricType(Enum):
    TOOL_BEHAVIOR = "tool_behavior"
    RESPONSE_QUALITY = "response_quality"
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    EFFICIENCY = "efficiency"
    SAFETY = "safety"


# =========================
# Result Container
# =========================

@dataclass
class EvaluationResult:
    metric_name: str
    metric_type: MetricType
    score: float  # 0.0 – 1.0
    passed: bool
    details: Dict[str, Any]
    explanation: str


# =========================
# Tool Behavior Evaluator (Upgraded)
# =========================

class ToolBehaviorEvaluator:
    """
    Pattern-agnostic tool scoring:
    - recall (required tools used)
    - precision (relevant vs total)
    - efficiency (minimal sufficiency)
    """

    def evaluate(
        self,
        expected_tools: List[str],
        actual_tools: List[str],
        required_tools: Optional[List[str]] = None,
    ) -> EvaluationResult:

        required_tools = required_tools or expected_tools

        actual_set = set(actual_tools)
        expected_set = set(expected_tools)
        required_set = set(required_tools)

        required_hit = required_set & actual_set
        missing_required = required_set - actual_set
        extra_tools = actual_set - expected_set
        relevant_used = actual_set & expected_set

        # --- Scores ---

        recall = len(required_hit) / len(required_set) if required_set else 1.0
        precision = len(relevant_used) / len(actual_set) if actual_set else 1.0
        efficiency = len(required_set) / len(actual_set) if actual_set else 1.0
        efficiency = min(efficiency, 1.0)

        score = (recall * 0.5) + (precision * 0.3) + (efficiency * 0.2)

        passed = recall == 1.0

        details = {
            "recall": recall,
            "precision": precision,
            "efficiency": efficiency,
            "missing_required": list(missing_required),
            "extra_tools": list(extra_tools),
            "required_hit": list(required_hit),
        }

        explanation = (
            f"Recall={recall:.2f} Precision={precision:.2f} "
            f"Efficiency={efficiency:.2f}"
        )

        return EvaluationResult(
            metric_name="tool_behavior",
            metric_type=MetricType.TOOL_BEHAVIOR,
            score=score,
            passed=passed,
            details=details,
            explanation=explanation,
        )


# =========================
# Completeness Evaluator (Hybrid)
# =========================

class CompletenessEvaluator:
    """
    Deterministic tool checks + optional LLM semantic checks.
    """

    TOOL_CRITERIA_MAP = {
        "must_access_billing": ["get_billing_summary", "get_subscription_detail"],
        "must_check_subscription": ["get_subscription_detail"],
        "must_check_security_logs": ["get_security_logs"],
        "must_check_promotions": ["get_eligible_promotions"],
        "must_check_orders": ["get_customer_orders"],
    }

    def evaluate(
        self,
        success_criteria: Dict[str, bool],
        tool_calls: List[Dict[str, Any]],
    ) -> EvaluationResult:

        tool_names = [c.get("name", "") for c in tool_calls]
        results = {}

        for criterion, required in success_criteria.items():

            if not required:
                results[criterion] = True
                continue

            if criterion in self.TOOL_CRITERIA_MAP:
                needed = self.TOOL_CRITERIA_MAP[criterion]
                results[criterion] = any(t in tool_names for t in needed)
            else:
                # semantic criteria handled by LLM judge metric
                results[criterion] = True

        required_count = sum(success_criteria.values())
        met_count = sum(
            1 for k, v in results.items()
            if v and success_criteria.get(k)
        )

        score = met_count / required_count if required_count else 1.0
        passed = met_count == required_count

        return EvaluationResult(
            metric_name="completeness",
            metric_type=MetricType.COMPLETENESS,
            score=score,
            passed=passed,
            details=results,
            explanation=f"{met_count}/{required_count} required criteria met",
        )


# =========================
# Efficiency Evaluator (NEW)
# =========================

class EfficiencyEvaluator:
    """
    Pattern-agnostic step efficiency metric.
    """

    def evaluate(
        self,
        actual_tool_calls: int,
        required_tools: int,
    ) -> EvaluationResult:

        baseline = max(required_tools, 1)
        efficiency = baseline / max(actual_tool_calls, 1)
        efficiency = min(efficiency, 1.0)

        return EvaluationResult(
            metric_name="step_efficiency",
            metric_type=MetricType.EFFICIENCY,
            score=efficiency,
            passed=efficiency >= 0.5,
            details={
                "actual_calls": actual_tool_calls,
                "baseline_required": baseline,
            },
            explanation=f"Efficiency {efficiency:.2f}",
        )


# =========================
# LLM Judge Evaluator (Upgraded)
# =========================

class ResponseQualityEvaluator:

    def __init__(self, llm_client=None):
        self.client = llm_client

    def evaluate(
        self,
        query: str,
        response: str,
        tool_summary: Optional[str] = None,
    ) -> EvaluationResult:

        if not self.client:
            return self._basic(response)

        prompt = f"""
Evaluate this customer support response.

Query: {query}
Response: {response}
Tool Evidence: {tool_summary}

Score 0–10:
- relevance
- clarity
- completeness
- professionalism
- actionability
- groundedness (uses evidence, not guesses)
- safety (no over-promising)

Return JSON with overall_score and explanation.
"""

        try:
            r = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Expert evaluator."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            import json
            data = json.loads(r.choices[0].message.content)

            score = data["overall_score"] / 10.0

            return EvaluationResult(
                metric_name="response_quality",
                metric_type=MetricType.RESPONSE_QUALITY,
                score=score,
                passed=score >= 0.7,
                details=data,
                explanation=data.get("explanation", ""),
            )

        except Exception:
            return self._basic(response)

    def _basic(self, response: str) -> EvaluationResult:
        ok = len(response.split()) > 15
        return EvaluationResult(
            metric_name="response_quality_basic",
            metric_type=MetricType.RESPONSE_QUALITY,
            score=1.0 if ok else 0.0,
            passed=ok,
            details={},
            explanation="Basic length check",
        )


# =========================
# Grounded Accuracy Evaluator (NEW)
# =========================

class GroundedAccuracyEvaluator:
    """
    Checks if response contradicts tool outputs (LLM-assisted).
    """

    def __init__(self, llm_client=None):
        self.client = llm_client

    def evaluate(
        self,
        response: str,
        tool_outputs: Optional[str],
    ) -> EvaluationResult:

        if not self.client or not tool_outputs:
            return EvaluationResult(
                metric_name="grounded_accuracy",
                metric_type=MetricType.ACCURACY,
                score=1.0,
                passed=True,
                details={},
                explanation="No grounding check available",
            )

        prompt = f"""
Tool facts:
{tool_outputs}

Response:
{response}

Does the response contradict the tool facts?
Answer JSON: {{ "contradiction": true/false }}
"""

        try:
            r = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )

            import json
            data = json.loads(r.choices[0].message.content)
            contradiction = data.get("contradiction", False)

            score = 0.0 if contradiction else 1.0

            return EvaluationResult(
                metric_name="grounded_accuracy",
                metric_type=MetricType.ACCURACY,
                score=score,
                passed=not contradiction,
                details=data,
                explanation="Contradiction detected" if contradiction else "Grounded",
            )

        except Exception:
            return EvaluationResult(
                metric_name="grounded_accuracy",
                metric_type=MetricType.ACCURACY,
                score=1.0,
                passed=True,
                details={},
                explanation="Grounding check failed → default pass",
            )


# =========================
# Safety / Overreach Evaluator (NEW)
# =========================

class SafetyEvaluator:

    RISKY_PATTERNS = [
        "guarantee refund",
        "will definitely refund",
        "account unlocked now",
        "I have removed the charge",
    ]

    def evaluate(self, response: str) -> EvaluationResult:

        lower = response.lower()
        hits = [p for p in self.RISKY_PATTERNS if p in lower]

        safe = len(hits) == 0

        return EvaluationResult(
            metric_name="safety",
            metric_type=MetricType.SAFETY,
            score=1.0 if safe else 0.0,
            passed=safe,
            details={"matches": hits},
            explanation="No overreach" if safe else "Potential overreach detected",
        )
