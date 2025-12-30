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


async def run_agent_on_query(agent_instance, query: str, session_id: str) -> tuple[str, List[Dict[str, Any]]]:
    """
    Run the agent on a single query and capture response + tool calls.
    Mimics how backend.py runs agents.
    
    Args:
        agent_instance: The instantiated agent
        query: Customer query
        session_id: Session/thread ID
        
    Returns:
        (response_text, tool_calls)
    """
    captured_tools = []
    
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
        
        # Extract tool calls from agent
        if hasattr(agent_instance, 'get_tool_calls'):
            captured_tools = agent_instance.get_tool_calls()
        elif hasattr(agent_instance, '_tool_calls'):
            captured_tools = agent_instance._tool_calls
        elif hasattr(agent_instance, 'tool_calls'):
            captured_tools = agent_instance.tool_calls
    
    except Exception as e:
        print(f"  ⚠ Error running agent: {e}")
        response_text = f"Error: {str(e)}"
        captured_tools = []
    
    return response_text, captured_tools


async def main():
    """Main evaluation entry point."""
    
    # 1. Load agent module from .env (same as backend.py)
    agent_module_path = os.getenv("AGENT_MODULE")
    if not agent_module_path:
        print("❌ ERROR: AGENT_MODULE not set in .env file")
        print(f"   Please configure in: {env_path}")
        return
    
    print(f"\n📦 Loading agent: {agent_module_path}")
    
    try:
        agent_module = __import__(agent_module_path, fromlist=["Agent"])
        Agent = getattr(agent_module, "Agent")
        print(f"✓ Agent class loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load agent: {e}")
        return
    
    # 2. Initialize state store (same as backend)
    state_store = get_state_store()
    print(f"✓ State store initialized: {type(state_store).__name__}")
    
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
        
        # Create agent instance for this session
        session_id = f"eval_{test_id}"
        
        try:
            # Initialize agent with session_id (required by most agents)
            init_params = Agent.__init__.__code__.co_varnames
            
            if 'session_id' in init_params and 'state_store' in init_params:
                agent = Agent(state_store=state_store, session_id=session_id)
            elif 'session_id' in init_params:
                agent = Agent(session_id=session_id)
            elif 'state_store' in init_params:
                agent = Agent(state_store=state_store)
            else:
                agent = Agent()
            
            # Run agent
            response, tool_calls = await run_agent_on_query(agent, query, session_id)
            
            print(f"  ✓ Response: {response[:100]}...")
            print(f"  ✓ Tools called: {len(tool_calls)}")
            
            # Create trace
            trace = AgentTrace(
                query=test_case["customer_query"],  # Use original query for matching
                response=response,
                tool_calls=tool_calls,  # THIS is what evaluator.py uses!
                metadata={
                    "test_id": test_id,
                    "agent_module": agent_module_path,
                    "session_id": session_id,
                    "augmented_query": query  # Store augmented query in metadata
                }
            )
            traces.append(trace)
            
            # Cleanup: Allow agent resources to be garbage collected
            del agent
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            # Create a failed trace
            trace = AgentTrace(
                query=query,
                response=f"Error: {str(e)}",
                tool_calls=[],
                metadata={
                    "test_id": test_id,
                    "agent_module": agent_module_path,
                    "error": str(e)
                }
            )
            traces.append(trace)
        
        print()
    
    # 6. Run evaluation
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
    print(f"EVALUATION SUMMARY - {agent_module_path}")
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
