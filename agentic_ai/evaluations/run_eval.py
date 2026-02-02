import os
from pathlib import Path
from typing import Dict, Any

from azure.ai.evaluation import evaluate

from metrics import (
    ToolBehaviorEvaluator,
    CompletenessEvaluator,
    EfficiencyEvaluator,
    ResponseQualityEvaluator,
    GroundedAccuracyEvaluator,
    SafetyEvaluator,
    EvaluationResult,
)


def main() -> None:
    root = Path(__file__).resolve().parent
    data_path = root / "evaluation_input_data.jsonl"

    if not data_path.exists():
        raise FileNotFoundError(
            f"{data_path} not found. Run collect_agent_runs.py first to generate it."
        )

    # Instantiate our custom, non-LLM metrics using the updated metrics.py.
    tool_eval = ToolBehaviorEvaluator()
    completeness_eval = CompletenessEvaluator()
    efficiency_eval = EfficiencyEvaluator()
    quality_eval = ResponseQualityEvaluator(llm_client=None)
    accuracy_eval = GroundedAccuracyEvaluator(llm_client=None)
    safety_eval = SafetyEvaluator()

    # Single custom evaluator that computes all Contoso metrics for a row.
    def contoso_evaluator(
        *,
        query: str,
        response: str,
        expected_tools: Any,
        required_tools: Any,
        success_criteria: Dict[str, Any],
        tool_calls: Any,
    ) -> Dict[str, Any]:
        # Normalize inputs
        expected_tools_list = expected_tools or []
        required_tools_list = required_tools or expected_tools_list
        tool_calls_list = tool_calls or []
        if not isinstance(tool_calls_list, list):
            tool_calls_list = []

        actual_tools = [call.get("name", "") for call in tool_calls_list if isinstance(call, dict)]

        # 1. Tool behavior (recall/precision/efficiency over tools)
        tool_result = tool_eval.evaluate(
            expected_tools=expected_tools_list,
            actual_tools=actual_tools,
            required_tools=required_tools_list,
        )

        # 2. Completeness (tool-based criteria only; semantic parts are handled
        # by the response-quality metric when an LLM judge is available).
        completeness_result = completeness_eval.evaluate(
            success_criteria=success_criteria or {},
            tool_calls=tool_calls_list,
        )

        # 3. Step efficiency: how many calls did we make vs how many tools were
        # required as a baseline.
        efficiency_result = efficiency_eval.evaluate(
            actual_tool_calls=len(actual_tools),
            required_tools=len(required_tools_list) if required_tools_list else 0,
        )

        # 4. Response quality (basic checks only; no judge LLM in this env).
        quality_result = quality_eval.evaluate(
            query=query,
            response=response,
            tool_summary=None,
        )

        # 5. Grounded accuracy (LLM-assisted in the future; default pass now).
        accuracy_result = accuracy_eval.evaluate(
            response=response,
            tool_outputs=None,
        )

        # 6. Safety / overreach: detect risky promises or actions.
        safety_result = safety_eval.evaluate(response=response)

        metrics: list[EvaluationResult] = [
            tool_result,
            completeness_result,
            efficiency_result,
            quality_result,
            accuracy_result,
            safety_result,
        ]

        # Weighted overall score, matching AgentEvaluationRunner.
        weights = {
            "tool_behavior": 0.3,
            "completeness": 0.25,
            "step_efficiency": 0.1,
            "response_quality_basic": 0.2,
            "response_quality": 0.2,
            "grounded_accuracy": 0.1,
            "safety": 0.05,
        }

        total_score = 0.0
        total_weight = 0.0
        for m in metrics:
            weight = weights.get(m.metric_name, 0.1)
            total_score += m.score * weight
            total_weight += weight

        overall_score = total_score / total_weight if total_weight > 0 else 0.0
        overall_passed = overall_score >= 0.7 and all(m.passed for m in metrics)

        return {
            "tool_behavior.score": tool_result.score,
            "tool_behavior.passed": 1.0 if tool_result.passed else 0.0,
            "completeness.score": completeness_result.score,
            "completeness.passed": 1.0 if completeness_result.passed else 0.0,
            "step_efficiency.score": efficiency_result.score,
            "step_efficiency.passed": 1.0 if efficiency_result.passed else 0.0,
            "response_quality.score": quality_result.score,
            "response_quality.passed": 1.0 if quality_result.passed else 0.0,
            "accuracy.score": accuracy_result.score,
            "accuracy.passed": 1.0 if accuracy_result.passed else 0.0,
            "safety.score": safety_result.score,
            "safety.passed": 1.0 if safety_result.passed else 0.0,
            "overall.score": overall_score,
            "overall.passed": 1.0 if overall_passed else 0.0,
        }

    evaluators: Dict[str, object] = {
        "contoso_metrics": contoso_evaluator,
    }

    azure_ai_project = os.environ.get("AZURE_AI_PROJECT")
    if not azure_ai_project:
        raise RuntimeError(
            "AZURE_AI_PROJECT must be set to your Foundry project endpoint to log results "
            "to the UI (for example: https://<account>.services.ai.azure.com/api/projects/<project-name>)."
        )

    print(f"Running evaluation on {data_path}...")
    response = evaluate(
        data=str(data_path),
        evaluation_name="contoso-agent-eval",
        evaluators=evaluators,
        evaluator_config={
            "contoso_metrics": {
                "column_mapping": {
                    "query": "${data.query}",
                    "response": "${data.response}",
                    "expected_tools": "${data.expected_tools}",
                    "required_tools": "${data.required_tools}",
                    "success_criteria": "${data.success_criteria}",
                    "tool_calls": "${data.tool_calls}",
                },
            },
        },
        azure_ai_project=azure_ai_project,
    )

    print("\n=== Aggregate metrics ===")
    print(response.get("metrics"))

    studio_url = response.get("studio_url")
    if studio_url:
        print("\nView detailed results in Foundry UI:")
        print(studio_url)
    else:
        print("\nNo studio_url returned; results were computed locally only.")


if __name__ == "__main__":
    main()
