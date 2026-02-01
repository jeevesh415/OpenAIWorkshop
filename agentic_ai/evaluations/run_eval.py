import os
from pathlib import Path
from typing import Dict, Any

from azure.ai.evaluation import evaluate

from metrics import (
    ToolUsageEvaluator,
    CompletenessEvaluator,
    ResponseQualityEvaluator,
    AccuracyEvaluator,
    EvaluationResult,
)


def main() -> None:
    root = Path(__file__).resolve().parent
    data_path = root / "evaluation_input_data.jsonl"

    if not data_path.exists():
        raise FileNotFoundError(
            f"{data_path} not found. Run collect_agent_runs.py first to generate it."
        )

    # Instantiate our custom, non-LLM metrics to mirror the local
    # AgentEvaluationRunner behavior.
    tool_eval = ToolUsageEvaluator()
    completeness_eval = CompletenessEvaluator()
    quality_eval = ResponseQualityEvaluator(azure_openai_client=None)
    accuracy_eval = AccuracyEvaluator()

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

        # 1. Tool usage
        tool_result = tool_eval.evaluate(
            expected_tools=expected_tools_list,
            actual_tools=actual_tools,
            required_tools=required_tools_list,
        )

        # 2. Completeness (criteria + tools)
        completeness_result = completeness_eval.evaluate(
            success_criteria=success_criteria or {},
            agent_response=response,
            tool_calls=tool_calls_list,
        )

        # 3. Response quality (basic checks only; no judge LLM)
        quality_result = quality_eval.evaluate(
            query=query,
            response=response,
            context={"tool_calls": actual_tools},
        )

        # 4. Accuracy (placeholder, as in local runner)
        accuracy_result = accuracy_eval.evaluate(
            response=response,
            ground_truth=None,
            tool_results=None,
        )

        metrics: list[EvaluationResult] = [
            tool_result,
            completeness_result,
            quality_result,
            accuracy_result,
        ]

        # Weighted overall score, matching AgentEvaluationRunner.
        weights = {
            "tool_usage": 0.3,
            "completeness": 0.3,
            "response_quality_llm": 0.25,
            "response_quality_basic": 0.25,
            "accuracy": 0.15,
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
            "tool_usage.score": tool_result.score,
            "tool_usage.passed": 1.0 if tool_result.passed else 0.0,
            "completeness.score": completeness_result.score,
            "completeness.passed": 1.0 if completeness_result.passed else 0.0,
            "response_quality.score": quality_result.score,
            "response_quality.passed": 1.0 if quality_result.passed else 0.0,
            "accuracy.score": accuracy_result.score,
            "accuracy.passed": 1.0 if accuracy_result.passed else 0.0,
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
