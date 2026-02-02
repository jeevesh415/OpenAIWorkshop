"""
Evaluation runner for AI Agent testing.
Tests agents against the evaluation dataset and generates reports.
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import sys

from metrics import (
    ToolBehaviorEvaluator,
    CompletenessEvaluator,
    ResponseQualityEvaluator,
    GroundedAccuracyEvaluator,
    EvaluationResult
)


@dataclass
class AgentTrace:
    """Captured trace of agent execution."""
    query: str
    response: str
    tool_calls: List[Dict[str, Any]]
    metadata: Dict[str, Any]


@dataclass
class TestCaseResult:
    """Result of evaluating a single test case."""
    test_case_id: str
    query: str
    agent_response: str
    metrics: List[EvaluationResult]
    overall_score: float
    passed: bool
    timestamp: str


class AgentEvaluationRunner:
    """Main evaluation runner for agent testing."""
    
    def __init__(
        self,
        dataset_path: str = "eval_dataset.json",
        azure_openai_client=None
    ):
        """
        Initialize evaluation runner.
        
        Args:
            dataset_path: Path to evaluation dataset JSON
            azure_openai_client: Optional Azure OpenAI client for LLM-as-judge
        """
        self.dataset_path = dataset_path
        self.test_cases = self._load_dataset()
        
        # Initialize evaluators
        self.tool_evaluator = ToolBehaviorEvaluator()
        self.completeness_evaluator = CompletenessEvaluator()
        self.quality_evaluator = ResponseQualityEvaluator(azure_openai_client)
        self.accuracy_evaluator = GroundedAccuracyEvaluator()
    
    def _load_dataset(self) -> List[Dict[str, Any]]:
        """Load evaluation dataset from JSON."""
        with open(self.dataset_path, 'r') as f:
            data = json.load(f)
        return data.get("test_cases", [])
    
    def evaluate_agent_response(
        self,
        test_case: Dict[str, Any],
        agent_trace: AgentTrace
    ) -> TestCaseResult:
        """
        Evaluate a single agent response against test case.
        
        Args:
            test_case: Test case from dataset
            agent_trace: Captured agent execution trace
            
        Returns:
            TestCaseResult with all evaluation metrics
        """
        metrics: List[EvaluationResult] = []
        
        # 1. Evaluate tool usage
        tool_names = [call.get("name", "") for call in agent_trace.tool_calls]
        
        # Use required_tools if specified, otherwise fall back to expected_tools
        required_tools = test_case.get("required_tools")
        if required_tools is None:
            required_tools = test_case.get("expected_tools", [])
        
        tool_result = self.tool_evaluator.evaluate(
            expected_tools=test_case.get("expected_tools", []),
            actual_tools=tool_names,
            required_tools=required_tools
        )
        metrics.append(tool_result)
        
        # 2. Evaluate completeness
        completeness_result = self.completeness_evaluator.evaluate(
            success_criteria=test_case.get("success_criteria", {}),
            tool_calls=agent_trace.tool_calls
        )
        metrics.append(completeness_result)
        
        # 3. Evaluate response quality  
        tool_summary = f"Tools used: {', '.join(tool_names)}" if tool_names else "No tools used"
        quality_result = self.quality_evaluator.evaluate(
            query=agent_trace.query,
            response=agent_trace.response,
            tool_summary=tool_summary
        )
        metrics.append(quality_result)
        
        # 4. Evaluate accuracy (if ground truth available)
        tool_outputs = "; ".join([str(call.get("result", "")) for call in agent_trace.tool_calls if call.get("result")])
        accuracy_result = self.accuracy_evaluator.evaluate(
            response=agent_trace.response,
            tool_outputs=tool_outputs if tool_outputs else None
        )
        metrics.append(accuracy_result)
        
        # Calculate overall score (weighted average)
        weights = {
            "tool_usage": 0.3,
            "completeness": 0.3,
            "response_quality_llm": 0.25,
            "response_quality_basic": 0.25,
            "accuracy": 0.15
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for metric in metrics:
            weight = weights.get(metric.metric_name, 0.1)
            total_score += metric.score * weight
            total_weight += weight
        
        overall_score = total_score / total_weight if total_weight > 0 else 0.0
        passed = overall_score >= 0.7 and all(m.passed for m in metrics)
        
        return TestCaseResult(
            test_case_id=test_case.get("id", "unknown"),
            query=agent_trace.query,
            agent_response=agent_trace.response,
            metrics=metrics,
            overall_score=overall_score,
            passed=passed,
            timestamp=datetime.now().isoformat()
        )
    
    def run_evaluation(
        self,
        agent_traces: List[AgentTrace],
        output_dir: str = "eval_results"
    ) -> Dict[str, Any]:
        """
        Run evaluation on all agent traces.
        
        Args:
            agent_traces: List of captured agent execution traces
            output_dir: Directory to save evaluation results
            
        Returns:
            Summary of evaluation results
        """
        os.makedirs(output_dir, exist_ok=True)
        
        results: List[TestCaseResult] = []
        
        # Match traces to test cases
        for test_case in self.test_cases:
            # Find matching trace by customer_id or query
            matching_trace = None
            for trace in agent_traces:
                if trace.query.lower().strip() == test_case["customer_query"].lower().strip():
                    matching_trace = trace
                    break
            
            if not matching_trace:
                print(f"⚠ Warning: No trace found for test case {test_case['id']}")
                continue
            
            # Evaluate
            result = self.evaluate_agent_response(test_case, matching_trace)
            results.append(result)
            
            # Print progress
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"{status} {result.test_case_id}: {result.overall_score:.2f}")
        
        # Generate summary
        summary = self._generate_summary(results)
        
        # Save results
        self._save_results(results, summary, output_dir)
        
        return summary
    
    def _generate_summary(self, results: List[TestCaseResult]) -> Dict[str, Any]:
        """Generate summary statistics."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        
        avg_score = sum(r.overall_score for r in results) / total if total > 0 else 0.0
        
        # Metric breakdowns
        metric_scores = {}
        for result in results:
            for metric in result.metrics:
                if metric.metric_name not in metric_scores:
                    metric_scores[metric.metric_name] = []
                metric_scores[metric.metric_name].append(metric.score)
        
        metric_averages = {
            name: sum(scores) / len(scores) if scores else 0.0
            for name, scores in metric_scores.items()
        }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "average_score": avg_score,
            "metric_averages": metric_averages
        }
    
    def _save_results(
        self,
        results: List[TestCaseResult],
        summary: Dict[str, Any],
        output_dir: str
    ):
        """Save evaluation results to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed results
        results_file = os.path.join(output_dir, f"eval_results_{timestamp}.json")
        with open(results_file, 'w') as f:
            json.dump({
                "results": [self._result_to_dict(r) for r in results],
                "summary": summary
            }, f, indent=2)
        
        # Save summary report
        report_file = os.path.join(output_dir, f"eval_report_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_text_report(results, summary))
        
        print(f"\n✓ Results saved to: {results_file}")
        print(f"✓ Report saved to: {report_file}")
    
    def _result_to_dict(self, result: TestCaseResult) -> Dict[str, Any]:
        """Convert TestCaseResult to dictionary."""
        return {
            "test_case_id": result.test_case_id,
            "query": result.query,
            "agent_response": result.agent_response,
            "overall_score": result.overall_score,
            "passed": result.passed,
            "timestamp": result.timestamp,
            "metrics": [
                {
                    "name": m.metric_name,
                    "type": m.metric_type.value,
                    "score": m.score,
                    "passed": m.passed,
                    "explanation": m.explanation,
                    "details": m.details
                }
                for m in result.metrics
            ]
        }
    
    def _generate_text_report(
        self,
        results: List[TestCaseResult],
        summary: Dict[str, Any]
    ) -> str:
        """Generate human-readable text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("AI AGENT EVALUATION REPORT")
        lines.append("=" * 80)
        lines.append(f"\nTimestamp: {summary['timestamp']}")
        lines.append(f"Total Tests: {summary['total_tests']}")
        lines.append(f"Passed: {summary['passed']}")
        lines.append(f"Failed: {summary['failed']}")
        lines.append(f"Pass Rate: {summary['pass_rate']:.1%}")
        lines.append(f"Average Score: {summary['average_score']:.2f}")
        
        lines.append("\n" + "=" * 80)
        lines.append("METRIC AVERAGES")
        lines.append("=" * 80)
        for metric, avg in summary['metric_averages'].items():
            lines.append(f"{metric:30s}: {avg:.2f}")
        
        lines.append("\n" + "=" * 80)
        lines.append("DETAILED RESULTS")
        lines.append("=" * 80)
        
        for result in results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            lines.append(f"\n{status} {result.test_case_id} (Score: {result.overall_score:.2f})")
            lines.append(f"Query: {result.query}")
            lines.append("\nMetrics:")
            for metric in result.metrics:
                lines.append(f"  - {metric.metric_name}: {metric.score:.2f} - {metric.explanation}")
        
        return "\n".join(lines)


def example_usage():
    """Example of how to use the evaluation runner."""
    
    # This is an example - in practice, you'd capture real agent traces
    example_traces = [
        AgentTrace(
            query="I noticed my last invoice was higher than usual—can you help me understand why and what can be done about it?",
            response="I've checked your billing history and found that your invoice increased due to a plan upgrade last month. According to our billing policy, you can request a review within 30 days.",
            tool_calls=[
                {"name": "get_customer_detail", "args": {"customer_id": 1001}, "result": {}},
                {"name": "get_billing_summary", "args": {"customer_id": 1001}, "result": {}},
                {"name": "search_knowledge_base", "args": {"query": "billing policy"}, "result": {}}
            ],
            metadata={"agent_type": "single_agent", "duration_ms": 2500}
        )
    ]
    
    # Run evaluation
    runner = AgentEvaluationRunner(dataset_path="eval_dataset.json")
    summary = runner.run_evaluation(example_traces, output_dir="eval_results")
    
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    example_usage()
