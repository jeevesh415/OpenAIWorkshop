"""
Batch Evaluation Runner for Contoso Customer Support Agent

Usage:
    python run_batch_eval.py                          # Run all scenarios
    python run_batch_eval.py --scenario scenario_3    # Run single scenario
    python run_batch_eval.py --agent single           # Specify agent type
    python run_batch_eval.py --output results.json    # Save results to file
    python run_batch_eval.py --verbose                # Show full responses
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directories to path for imports
AGENTIC_AI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(AGENTIC_AI_ROOT / "applications"))
sys.path.insert(0, str(AGENTIC_AI_ROOT / "agents"))
sys.path.insert(0, str(AGENTIC_AI_ROOT))

from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment
load_dotenv(Path(__file__).parent.parent / "applications" / ".env")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Tool Call Tracker - Captures tools used during agent execution
# ─────────────────────────────────────────────────────────────────────────────
class ToolCallTracker:
    """Captures tool calls made by the agent during execution."""
    
    def __init__(self):
        self.tool_calls: List[Dict[str, Any]] = []
    
    async def broadcast(self, session_id: str, message: dict) -> None:
        """Intercept broadcast messages to capture tool calls."""
        if isinstance(message, dict) and message.get("type") == "tool_called":
            tool_name = message.get("tool_name")
            if tool_name:
                self.tool_calls.append({"name": tool_name})
    
    def get_tool_names(self) -> List[str]:
        """Return list of tool names called."""
        return [tc["name"] for tc in self.tool_calls]
    
    def reset(self):
        """Clear tracked tool calls."""
        self.tool_calls = []


# ─────────────────────────────────────────────────────────────────────────────
# LLM-as-Judge Evaluator
# ─────────────────────────────────────────────────────────────────────────────
class LLMJudge:
    """Uses Azure OpenAI to score agent responses against ground truth."""
    
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )
        self.model = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
    
    def evaluate(
        self,
        scenario: Dict[str, Any],
        agent_response: str,
        tools_used: List[str],
        rubric: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate agent response against ground truth using LLM-as-judge.
        
        Returns scores for each metric (1-5 scale).
        """
        ground_truth = scenario["ground_truth"]
        
        # Build evaluation prompt
        eval_prompt = f"""You are an expert evaluator for a customer support AI agent.

## Customer Query
{scenario["input"]}

## Agent Response
{agent_response}

## Expected Behavior (Ground Truth)
- **Expected Tools**: {', '.join(ground_truth.get('expected_tools', []))}
- **Expected Actions**: {chr(10).join('- ' + a for a in ground_truth.get('expected_actions', []))}
- **Solution Criteria**: {ground_truth.get('solution_criteria', 'N/A')}
- **Required KB Articles**: {', '.join(ground_truth.get('required_kb_articles', []))}

## Tools Actually Used by Agent
{', '.join(tools_used) if tools_used else 'None'}

## Scoring Rubric
For each metric, score 1-5 based on the criteria:

1. **Solution Score** (Did the agent solve the customer's problem?)
   - 5: Fully solved with correct information and actionable next steps
   - 4: Mostly solved with minor gaps
   - 3: Partially solved, missing key elements
   - 2: Attempted but incorrect or incomplete
   - 1: Failed to address the problem

2. **Intent Score** (Did the agent understand the customer's intent?)
   - 5: Perfect understanding of intent and context
   - 4: Good understanding with minor misinterpretation
   - 3: Understood main intent but missed nuances
   - 2: Misunderstood significant aspects
   - 1: Completely misunderstood intent

3. **Tool Usage Score** (Did the agent use the right tools?)
   - 5: Used all expected tools appropriately
   - 4: Used most expected tools correctly
   - 3: Used some expected tools, missed others
   - 2: Used wrong tools or missed critical ones
   - 1: Failed to use necessary tools

4. **Coherence Score** (Is the response logically structured?)
   - 5: Clear, logical, well-organized response
   - 4: Mostly clear with minor organization issues
   - 3: Somewhat clear but disorganized
   - 2: Confusing structure
   - 1: Incoherent or contradictory

5. **Relevance Score** (Did the agent stay on topic?)
   - 5: Completely relevant, no off-topic content
   - 4: Mostly relevant with minor tangents
   - 3: Relevant but includes unnecessary information
   - 2: Significant off-topic content
   - 1: Mostly irrelevant

6. **Fluency Score** (Is the response grammatically correct and readable?)
   - 5: Perfect grammar and natural flow
   - 4: Minor grammatical issues
   - 3: Some grammatical errors but readable
   - 2: Frequent errors affecting readability
   - 1: Poor grammar making comprehension difficult

## Instructions
Evaluate the agent's response and provide scores. Return ONLY a JSON object with this exact structure:
{{
    "solution_score": <1-5>,
    "intent_score": <1-5>,
    "tool_usage_score": <1-5>,
    "coherence_score": <1-5>,
    "relevance_score": <1-5>,
    "fluency_score": <1-5>,
    "reasoning": "<brief explanation of scores>"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert AI evaluator. Return only valid JSON."},
                    {"role": "user", "content": eval_prompt},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON from response (handle markdown code blocks)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            scores = json.loads(result_text)
            return scores
            
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            # Return default scores on failure
            return {
                "solution_score": 1,
                "intent_score": 1,
                "tool_usage_score": 1,
                "coherence_score": 1,
                "relevance_score": 1,
                "fluency_score": 1,
                "reasoning": f"Evaluation failed: {str(e)}",
            }


# ─────────────────────────────────────────────────────────────────────────────
# Batch Evaluator
# ─────────────────────────────────────────────────────────────────────────────
class BatchEvaluator:
    """Runs batch evaluation against the agent."""
    
    def __init__(self, agent_type: str = "single"):
        self.agent_type = agent_type
        self.judge = LLMJudge()
        self.dataset_path = Path(__file__).parent / "eval_dataset.json"
        self.dataset = self._load_dataset()
    
    def _load_dataset(self) -> Dict[str, Any]:
        """Load evaluation dataset from JSON file."""
        with open(self.dataset_path, "r") as f:
            return json.load(f)
    
    def _create_agent(self, session_id: str):
        """Create agent instance based on type using direct file import."""
        state_store = {}
        
        # Ensure agents directory is in path for base_agent import
        agents_dir = AGENTIC_AI_ROOT / "agents"
        if str(agents_dir) not in sys.path:
            sys.path.insert(0, str(agents_dir))
        
        # Use importlib to load agent module directly by file path
        # This avoids conflict with the external 'agent_framework' pip package
        if self.agent_type == "single":
            agent_path = AGENTIC_AI_ROOT / "agents" / "agent_framework" / "single_agent.py"
            logger.info(f"    → Using SINGLE agent")
        elif self.agent_type == "reflection":
            agent_path = AGENTIC_AI_ROOT / "agents" / "agent_framework" / "multi_agent" / "reflection_agent.py"
            logger.info(f"    → Using REFLECTION agent")
        else:
            logger.warning(f"Unknown agent type '{self.agent_type}', defaulting to single")
            agent_path = AGENTIC_AI_ROOT / "agents" / "agent_framework" / "single_agent.py"
        
        # First load base_agent module to make it available
        base_agent_path = AGENTIC_AI_ROOT / "agents" / "base_agent.py"
        base_spec = importlib.util.spec_from_file_location("agents.base_agent", base_agent_path)
        base_module = importlib.util.module_from_spec(base_spec)
        sys.modules["agents.base_agent"] = base_module
        base_spec.loader.exec_module(base_module)
        
        # Load the agent module dynamically
        spec = importlib.util.spec_from_file_location("agent_module", agent_path)
        agent_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent_module)
        Agent = agent_module.Agent
        
        return Agent(state_store, session_id)
    
    async def run_scenario(
        self,
        scenario: Dict[str, Any],
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Run a single scenario and return results."""
        scenario_id = scenario["id"]
        scenario_name = scenario["name"]
        
        logger.info(f"  Running: {scenario_name}...")
        
        # Create fresh agent and tool tracker for this scenario
        session_id = f"eval_{scenario_id}_{int(time.time())}"
        agent = self._create_agent(session_id)
        tool_tracker = ToolCallTracker()
        
        # Inject tool tracker to capture tool calls
        if hasattr(agent, "set_websocket_manager"):
            agent.set_websocket_manager(tool_tracker)
        
        # Run agent
        start_time = time.time()
        try:
            response = await agent.chat_async(scenario["input"])
            elapsed = time.time() - start_time
            error = None
        except Exception as e:
            response = f"ERROR: {str(e)}"
            elapsed = time.time() - start_time
            error = str(e)
        
        # Get tools used
        tools_used = tool_tracker.get_tool_names()
        
        # Evaluate with LLM-as-judge
        scores = self.judge.evaluate(
            scenario=scenario,
            agent_response=response,
            tools_used=tools_used,
            rubric=self.dataset.get("scoring_rubric", {}),
        )
        
        # Calculate weighted overall score
        rubric = self.dataset.get("scoring_rubric", {})
        overall_score = 0
        for metric, weight_info in rubric.items():
            score_key = metric  # e.g., "solution_score"
            weight = weight_info.get("weight", 0)
            score = scores.get(score_key, 3)
            overall_score += score * weight
        
        # Determine pass/fail
        pass_criteria = self.dataset.get("pass_criteria", {})
        solution_min = pass_criteria.get("solution_score_minimum", 3)
        overall_min = pass_criteria.get("overall_weighted_minimum", 3.5)
        
        passed = (
            scores.get("solution_score", 0) >= solution_min
            and overall_score >= overall_min
        )
        
        result = {
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "input": scenario["input"],
            "response": response,
            "tools_used": tools_used,
            "expected_tools": scenario["ground_truth"].get("expected_tools", []),
            "scores": scores,
            "overall_score": round(overall_score, 2),
            "passed": passed,
            "elapsed_seconds": round(elapsed, 2),
            "error": error,
        }
        
        if verbose:
            logger.info(f"    Response: {response[:200]}...")
            logger.info(f"    Tools: {tools_used}")
            logger.info(f"    Scores: {scores}")
        
        return result
    
    async def run_all(
        self,
        scenario_filter: Optional[str] = None,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Run all scenarios (or filtered subset) and return aggregated results."""
        scenarios = self.dataset["scenarios"]
        
        # Filter if specified
        if scenario_filter:
            scenarios = [s for s in scenarios if s["id"] == scenario_filter]
            if not scenarios:
                logger.error(f"Scenario '{scenario_filter}' not found!")
                return {"error": f"Scenario '{scenario_filter}' not found"}
        
        logger.info(f"\n{'═' * 70}")
        logger.info(f"  BATCH EVAL - {self.agent_type.upper()} AGENT - {len(scenarios)} scenarios")
        logger.info(f"{'═' * 70}\n")
        
        results = []
        for scenario in scenarios:
            result = await self.run_scenario(scenario, verbose)
            results.append(result)
        
        # Aggregate results
        passed_count = sum(1 for r in results if r["passed"])
        total_count = len(results)
        
        avg_scores = {}
        score_keys = ["solution_score", "intent_score", "tool_usage_score", 
                      "coherence_score", "relevance_score", "fluency_score"]
        for key in score_keys:
            scores = [r["scores"].get(key, 0) for r in results]
            avg_scores[key] = round(sum(scores) / len(scores), 2) if scores else 0
        
        avg_overall = sum(r["overall_score"] for r in results) / len(results) if results else 0
        total_time = sum(r["elapsed_seconds"] for r in results)
        total_tools = sum(len(r["tools_used"]) for r in results)
        
        summary = {
            "agent_type": self.agent_type,
            "timestamp": datetime.now().isoformat(),
            "scenarios_passed": passed_count,
            "scenarios_total": total_count,
            "pass_rate": f"{(passed_count/total_count)*100:.1f}%" if total_count else "0%",
            "avg_scores": avg_scores,
            "avg_overall_score": round(avg_overall, 2),
            "total_time_seconds": round(total_time, 2),
            "total_tools_called": total_tools,
        }
        
        return {
            "summary": summary,
            "results": results,
        }
    
    def print_results(self, eval_results: Dict[str, Any]) -> None:
        """Print results in a nice table format."""
        summary = eval_results["summary"]
        results = eval_results["results"]
        
        # Header
        print(f"\n{'═' * 100}")
        print(f"  RESULTS: {summary['agent_type'].upper()} AGENT")
        print(f"{'═' * 100}")
        
        # Column headers
        print(f"\n{'Scenario':<35} {'Solution':>8} {'Intent':>8} {'Tools':>8} {'Cohere':>8} {'Relev':>8} {'Time':>8} {'Pass':>6}")
        print(f"{'─' * 100}")
        
        # Rows
        for r in results:
            name = r["scenario_name"][:33]
            s = r["scores"]
            passed = "✓" if r["passed"] else "✗"
            print(
                f"{name:<35} "
                f"{s.get('solution_score', 0):>6}/5 "
                f"{s.get('intent_score', 0):>6}/5 "
                f"{s.get('tool_usage_score', 0):>6}/5 "
                f"{s.get('coherence_score', 0):>6}/5 "
                f"{s.get('relevance_score', 0):>6}/5 "
                f"{r['elapsed_seconds']:>6.1f}s "
                f"{passed:>6}"
            )
        
        # Summary
        print(f"{'─' * 100}")
        avg = summary["avg_scores"]
        print(
            f"{'AVERAGE':<35} "
            f"{avg.get('solution_score', 0):>6}/5 "
            f"{avg.get('intent_score', 0):>6}/5 "
            f"{avg.get('tool_usage_score', 0):>6}/5 "
            f"{avg.get('coherence_score', 0):>6}/5 "
            f"{avg.get('relevance_score', 0):>6}/5 "
            f"{summary['total_time_seconds']:>6.1f}s "
            f""
        )
        print(f"{'═' * 100}")
        print(f"\n  SUMMARY: {summary['scenarios_passed']}/{summary['scenarios_total']} passed ({summary['pass_rate']})")
        print(f"  Avg Overall Score: {summary['avg_overall_score']}/5")
        print(f"  Total Tools Called: {summary['total_tools_called']}")
        print(f"  Total Time: {summary['total_time_seconds']}s")
        print(f"{'═' * 100}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Run batch evaluation on agent")
    parser.add_argument(
        "--agent",
        type=str,
        default="single",
        choices=["single", "reflection"],
        help="Agent type to evaluate (default: single)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Run specific scenario by ID (e.g., scenario_3)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output results to JSON file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output including full responses",
    )
    
    args = parser.parse_args()
    
    # Run evaluation
    evaluator = BatchEvaluator(agent_type=args.agent)
    results = asyncio.run(evaluator.run_all(
        scenario_filter=args.scenario,
        verbose=args.verbose,
    ))
    
    # Print results table
    evaluator.print_results(results)
    
    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to: {output_path}")
    
    # Exit with error code if pass rate is below threshold
    pass_rate = results["summary"]["scenarios_passed"] / results["summary"]["scenarios_total"]
    if pass_rate < 0.7:
        logger.warning(f"⚠️  Pass rate ({pass_rate*100:.0f}%) below 70% threshold")
        sys.exit(1)


if __name__ == "__main__":
    main()
