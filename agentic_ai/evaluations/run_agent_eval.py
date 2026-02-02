"""
Run evaluation on the agent configured in .env file.

This script:
1. Reads AGENT_MODULE from .env (same as backend.py does)
2. Loads that agent dynamically
3. Runs all test cases from eval_dataset.json
4. Captures traces and evaluates performance

Usage:
    cd agentic_ai/applications
    uv run python ../evaluations/run_agent_eval.py

Prerequisites:
    - MCP server must be running (cd mcp && uv run python mcp_service.py)
    - .env file must be configured in agentic_ai/applications/
"""

import os
import sys
import asyncio
import json
import warnings
import logging
from pathlib import Path
from typing import Any, Dict, List

# Suppress async generator cleanup warnings from MCP client
warnings.filterwarnings("ignore", message=".*async_generator.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*cancel scope.*")

# Add parent directory to Python path so we can import agents module
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# Debug: Print the path that was added
print(f"🔍 Added to Python path: {parent_dir}")
print(f"🔍 Agents directory exists: {(parent_dir / 'agents').exists()}")

# Note: No telemetry setup needed - using HTTP requests to backend with telemetry

# Suppress asyncio error logs about async generator cleanup
logging.getLogger('asyncio').setLevel(logging.CRITICAL)

# Add project paths
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "applications"))

# Load environment from applications/.env (or current directory .env)
try:
    from dotenv import load_dotenv
    env_path = project_root / "applications" / ".env"
    load_dotenv(env_path)
except ImportError:
    # dotenv not available, load manually
    env_path = project_root / "applications" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"')

print("=" * 80)
print("AI AGENT EVALUATION - Using Agent from .env")
print("=" * 80)

# Import evaluation framework
from evaluations import AgentEvaluationRunner, AgentTrace

# Import utilities
from applications.utils import get_state_store


class ToolCallTracker:
    """Captures tool calls emitted via the agent's WebSocket-style broadcast.

    This mirrors the lightweight tracker used in run_batch_eval.py: any
    broadcast message with type == "tool_called" is recorded so that the
    evaluator can score tool usage and completeness for Agent Framework
    agents (including the handoff multi-domain pattern).
    """

    def __init__(self) -> None:
        self.tool_calls: List[Dict[str, Any]] = []

    async def broadcast(self, session_id: str, message: dict) -> None:
        if isinstance(message, dict) and message.get("type") == "tool_called":
            tool_name = message.get("tool_name")
            if tool_name:
                # Evaluator only needs the tool name; args/results are optional
                self.tool_calls.append({"name": tool_name})


async def run_agent_on_query(agent_instance, query: str, session_id: str) -> tuple[str, List[Dict[str, Any]]]:
    """Run the agent on a single query and capture response + tool calls.

    For Agent Framework agents (single, handoff, reflection, etc.), we inject a
    ToolCallTracker via set_websocket_manager so that tool_called events emitted
    during MCP tool invocations are captured for evaluation.
    """
    captured_tools: List[Dict[str, Any]] = []

    # Inject tool-call tracker if the agent supports a WebSocket manager
    tracker: ToolCallTracker | None = None
    if hasattr(agent_instance, "set_websocket_manager"):
        tracker = ToolCallTracker()
        agent_instance.set_websocket_manager(tracker)

    try:
        # Run agent using the same methods as backend.py
        if hasattr(agent_instance, "chat_async"):
            # Agent Framework agents
            result = await agent_instance.chat_async(query)
            response_text = str(result) if result else "No response"

        elif hasattr(agent_instance, "chat_stream"):
            # Autogen streaming agents - collect full response
            response_parts = []
            async for event in agent_instance.chat_stream(query):
                if hasattr(event, 'content'):
                    response_parts.append(str(event.content))
            response_text = " ".join(response_parts) if response_parts else "No response"

        else:
            # Fallback: try calling agent directly
            result = await agent_instance(query)
            response_text = str(result) if result else "No response"

        # Prefer tools captured via tracker for Agent Framework agents
        if tracker is not None and tracker.tool_calls:
            captured_tools = tracker.tool_calls
        else:
            # Fallbacks for agents that expose tool calls directly
            if hasattr(agent_instance, 'get_tool_calls'):
                captured_tools = agent_instance.get_tool_calls()
            elif hasattr(agent_instance, '_tool_calls'):
                captured_tools = agent_instance._tool_calls  # type: ignore[attr-defined]
            elif hasattr(agent_instance, 'tool_calls'):
                captured_tools = agent_instance.tool_calls  # type: ignore[attr-defined]

    except Exception as e:
        print(f"  ⚠ Error running agent: {e}")
        response_text = f"Error: {str(e)}"
        captured_tools = []

    return response_text, captured_tools


async def main():
    """Main evaluation entry point."""
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Run agent evaluations")
    parser.add_argument("--agent-name", default="agent_eval", help="Name for telemetry tracking")
    parser.add_argument("--backend-url", default="http://localhost:7002", help="Backend URL to send requests to")
    args = parser.parse_args()
    
    agent_name = args.agent_name
    backend_url = args.backend_url
    
    print(f"Using backend: {backend_url}")
    print(f"Agent name: {agent_name}")
    
    # 1. No need to load agent module - we're sending HTTP requests
    print(f"\n🌐 Using HTTP requests to backend instead of direct agent creation")
    
    # 2. Test backend connection
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            health_response = await client.get(f"{backend_url}/health", timeout=5.0)
            print(f"✓ Backend is responding")
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print(f"   Make sure backend is running on {backend_url}")
        return
    
    # 3. Check MCP server
    mcp_uri = os.getenv("MCP_SERVER_URI", "http://localhost:8000/mcp")
    print(f"\n🔌 MCP Server: {mcp_uri}")
    
    try:
        import requests
        health_check = requests.get(mcp_uri.replace("/mcp", "/health"), timeout=2)
        print(f"✓ MCP server is responding")
    except:
        print(f"⚠ WARNING: Could not connect to MCP server")
        print(f"   Make sure it's running: cd mcp && uv run python mcp_service.py")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # 4. Load test cases
    dataset_path = Path(__file__).parent / "eval_dataset.json"
    with open(dataset_path) as f:
        data = json.load(f)
    test_cases = data["test_cases"]
    
    print(f"\n📋 Loaded {len(test_cases)} test cases from eval_dataset.json")
    
    # 5. Run each test case
    traces = []
    
    print(f"\n{'=' * 80}")
    print(f"RUNNING AGENT ON TEST CASES")
    print(f"{'=' * 80}\n")
    
    for i, test_case in enumerate(test_cases, 1):
        test_id = test_case["id"]
        query = test_case["customer_query"]
        customer_id = test_case.get("customer_id")
        
        # Augment query with customer ID if available
        if customer_id and f"customer {customer_id}" not in query.lower():
            query = f"I'm customer {customer_id}. {query}"
        
        print(f"[{i}/{len(test_cases)}] {test_id}")
        print(f"Query: {query[:80]}...")
        
        # Send HTTP request to backend instead of creating agent directly
        session_id = f"{agent_name}_eval_{test_id}"
        
        try:
            import httpx
            
            # Send request to local backend
            request_data = {
                "prompt": query,
                "session_id": session_id
            }
            
            async with httpx.AsyncClient() as client:
                response_obj = await client.post(
                    f"{backend_url}/chat",
                    json=request_data,
                    timeout=60.0
                )
                response_obj.raise_for_status()
                
                result = response_obj.json()
                response = result.get("response", "")
                tools_used = result.get("tools_used", [])
                
                # Convert tools_used (List[str]) to tool_calls format expected by evaluator
                tool_calls = [
                    {"name": tool_name, "args": {}}
                    for tool_name in (tools_used or [])
                ]
            
            print(f"  ✓ Response: {response[:100]}...")
            print(f"  ✓ Tools called: {len(tool_calls)}")
            
            # Create trace
            trace = AgentTrace(
                query=test_case["customer_query"],  # Use original query for matching
                response=response,
                tool_calls=tool_calls,  # THIS is what evaluator.py uses!
                metadata={
                    "test_id": test_id,
                    "agent_backend": backend_url,
                    "session_id": session_id,
                    "augmented_query": query  # Store augmented query in metadata
                }
            )
            traces.append(trace)
            
            # No cleanup needed for HTTP requests
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            # Create a failed trace
            trace = AgentTrace(
                query=query,
                response=f"Error: {str(e)}",
                tool_calls=[],
                metadata={
                    "test_id": test_id,
                    "agent_backend": backend_url,
                    "error": str(e)
                }
            )
            traces.append(trace)
        
        print()
    
    # 6. Generate evaluation_input_data.jsonl for Foundry integration
    print(f"{'=' * 80}")
    print(f"GENERATING FOUNDRY DATA FILE")
    print(f"{'=' * 80}\n")
    
    foundry_data_file = Path(__file__).parent / "evaluation_input_data.jsonl"
    with open(foundry_data_file, 'w') as f:
        for trace in traces:
            # Extract test case data from metadata
            test_id = trace.metadata.get("test_id", "unknown")
            
            # Find matching test case from original dataset
            matching_test = None
            for test_case in test_cases:
                if test_case.get("id") == test_id:
                    matching_test = test_case
                    break
            
            # Prepare data in format expected by run_eval.py
            foundry_row = {
                "query": trace.query,
                "response": trace.response,
                "expected_tools": matching_test.get("expected_tools", []) if matching_test else [],
                "required_tools": matching_test.get("required_tools", []) if matching_test else [],
                "success_criteria": matching_test.get("success_criteria", {}) if matching_test else {},
                "tool_calls": [{"name": tc["name"], "args": tc.get("args", {})} for tc in trace.tool_calls]
            }
            
            f.write(json.dumps(foundry_row) + '\n')
    
    print(f"✓ Generated {foundry_data_file} with {len(traces)} evaluation rows")
    
    # 7. Run evaluation
    print(f"{'=' * 80}")
    print(f"EVALUATING RESULTS")
    print(f"{'=' * 80}\n")
    
    runner = AgentEvaluationRunner(dataset_path=str(dataset_path))
    summary = runner.run_evaluation(
        traces,
        output_dir=str(Path(__file__).parent / "eval_results")
    )
    
    # 7. Display summary
    print(f"\n{'=' * 80}")
    print(f"EVALUATION SUMMARY - {backend_url}")
    print(f"{'=' * 80}")
    print(f"Total Tests:    {summary['total_tests']}")
    print(f"Passed:         {summary['passed']} ✓")
    print(f"Failed:         {summary['failed']} ✗")
    print(f"Pass Rate:      {summary['pass_rate']:.1%}")
    print(f"Average Score:  {summary['average_score']:.2f}")
    
    print(f"\nMetric Breakdown:")
    for metric, score in summary['metric_averages'].items():
        bar = "█" * int(score * 20)
        print(f"  {metric:30s}: {score:4.2f} {bar}")
    
    print(f"\n{'=' * 80}")
    print(f"✓ Evaluation complete! Check eval_results/ for detailed reports.")
    print(f"{'=' * 80}\n")
    
    # Give async tasks time to cleanup
    await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nEvaluation cancelled by user.")
    finally:
        # Ensure all async resources are cleaned up
        pass
