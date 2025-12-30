# Testing Agents with Evaluations - Step by Step Guide

## Overview

There are **two ways** to test your agents with the evaluation framework:

### Option 1: Mock Mode (Quickest)
- No servers needed
- Good for testing the framework itself
- Use pre-defined responses

### Option 2: Integration Mode (Real Testing)
- Run with actual MCP server
- Real agent execution
- True end-to-end testing

---

## Option 1: Quick Test (Framework Validation Only)

> ⚠️ **Note:** This does NOT test real agents - only validates the evaluation framework itself.

### Step 1: Test the Framework
```bash
cd agentic_ai/evaluations
python test_framework.py
```

**What it does:**
- Validates evaluation metrics work correctly
- Uses completely **mocked data** (not real agent responses)
- Generates sample reports
- **Does NOT test your agents**

**Expected output:**
```
Testing Tool Usage Evaluator
Score: 1.00
Passed: True

EVALUATION SUMMARY
Pass Rate: 50.0%
Average Score: 0.72
```

**Use this when:** You want to verify the evaluation framework code itself works.

### Step 2: Test with Mock Agents (Still No Real Agents)
```bash
python test_agents.py --mode mock
```

**What it does:**
- Simulates agent patterns with fake responses
- No MCP server needed
- Fast iteration
- **Still NOT testing real agents**

**Use this when:** Testing framework changes without waiting for MCP.

---

## Option 2: Real Agent Testing (Recommended)

> ✅ **This is the proper way to evaluate your agents with real MCP tools and data.**

### Why You Need MCP Running

Your agents **require MCP** to function because:
- MCP provides all the tools (`get_customer_detail`, `get_billing_summary`, etc.)
- MCP has the Contoso customer data
- Without MCP, agents cannot make tool calls
- **You cannot test real agent behavior without MCP**

The evaluation framework doesn't replace MCP - it captures what your agent does **while using MCP**.

### Complete Setup

#### Terminal 1: Start MCP Server (**REQUIRED**)
```bash
cd mcp
uv run python mcp_service.py
```

**Wait for:** `MCP server running on http://localhost:8000`

> ⚠️ **Do not skip this step** - agents won't work without MCP running!

#### Terminal 2: Run Evaluation Tests
```bash
cd agentic_ai/evaluations
python test_agents.py --mode with-mcp
```

**What happens:**
1. Test script loads queries from `eval_dataset.json`
2. Sends query to your agent (same as frontend would)
3. Agent calls MCP tools to get data
4. MCP returns real customer data
5. Agent generates response
6. Evaluation framework captures everything
7. Scores are calculated and saved

### Architecture During Evaluation

```
Test Script → Agent → MCP Server → Contoso Data
     ↓         ↓         ↓
  Query    Tool Calls  Results
     ↓         ↓         ↓
Evaluator ← Response ← Agent
     ↓
  Scores
```

This is identical to normal operation, except:
- Test script replaces frontend
- Evaluator captures and scores the interaction
- No human reviewing responses

---

## Testing Different Agent Patterns

### Test Single Agent

**1. Modify your single agent to capture traces:**

Edit `agentic_ai/agents/agent_framework/single_agent.py` (or create a wrapper):

```python
# At the top
from evaluations import AgentTrace

# Global list to capture traces during testing
_eval_traces = []

def run_with_eval_capture(query: str, customer_id: int):
    """Wrapper that captures traces for evaluation."""
    
    # Run your normal agent
    response = run_your_agent(query, customer_id)
    
    # Capture tool calls (you need to track these in your agent)
    tool_calls = get_tool_calls_from_agent()  # Your tracking logic
    
    # Create trace
    trace = AgentTrace(
        query=query,
        response=response,
        tool_calls=tool_calls,
        metadata={"agent": "single_agent"}
    )
    
    _eval_traces.append(trace)
    return response

# After running all test queries
def save_and_evaluate():
    from evaluations import AgentEvaluationRunner
    
    runner = AgentEvaluationRunner()
    summary = runner.run_evaluation(_eval_traces)
    print(f"Pass Rate: {summary['pass_rate']:.1%}")
```

**2. Run test:**
```python
# Load test queries from eval_dataset.json
import json
with open('evaluations/eval_dataset.json') as f:
    test_cases = json.load(f)['test_cases']

# Run each test
for test in test_cases:
    run_with_eval_capture(test['customer_query'], test['customer_id'])

# Evaluate
save_and_evaluate()
```

### Test Handoff Multi-Domain Agent

Same approach but for handoff agent:

```bash
# Set the agent module in .env
AGENT_MODULE="agents.agent_framework.multi_agent.handoff_multi_domain_agent"

# Run backend with eval capture
cd agentic_ai/applications
python test_agent_with_eval.py  # Your custom test script
```

### Test Magentic Collaborative Agent

```bash
AGENT_MODULE="agents.agent_framework.multi_agent.magentic_group"
python test_agent_with_eval.py
```

---

## Practical Integration Example

Here's how to create a test script for your actual agent:

**Create `agentic_ai/applications/test_with_eval.py`:**

```python
"""
Test your agent with evaluation framework.
Run this instead of frontend.py when you want to evaluate.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluations import AgentEvaluationRunner, AgentTrace

# Import your actual backend/agent code
from backend import create_agent, process_message  # Your imports

load_dotenv()

async def run_evaluation_tests():
    """Run evaluation on your actual agent."""
    
    # Load test cases
    with open('../evaluations/eval_dataset.json') as f:
        test_cases = json.load(f)['test_cases']
    
    # Initialize your agent (like backend does)
    agent = create_agent()
    
    traces = []
    
    print("Running agent on test cases...")
    for test_case in test_cases:
        print(f"\nTest: {test_case['id']}")
        
        # Run your agent
        response = await process_message(
            agent=agent,
            message=test_case['customer_query'],
            thread_id=f"eval_{test_case['id']}"
        )
        
        # Capture trace
        trace = AgentTrace(
            query=test_case['customer_query'],
            response=response,
            tool_calls=agent.get_tool_calls(),  # Your tool tracking
            metadata={"test_id": test_case['id']}
        )
        traces.append(trace)
    
    # Run evaluation
    runner = AgentEvaluationRunner()
    summary = runner.run_evaluation(traces, output_dir='../evaluations/eval_results')
    
    print("\n" + "=" * 80)
    print(f"✓ Evaluation Complete!")
    print(f"Pass Rate: {summary['pass_rate']:.1%}")
    print(f"Average Score: {summary['average_score']:.2f}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_evaluation_tests())
```

**Run it:**
```bash
# Terminal 1: Start MCP
cd mcp
uv run python mcp_service.py

# Terminal 2: Run evaluation
cd agentic_ai/applications
uv run python test_with_eval.py
```

---

## Compare Different Agents

To compare all agent patterns:

```bash
cd agentic_ai/evaluations
python test_agents.py --mode compare
```

This will:
1. Test single agent
2. Test handoff multi-domain
3. Test Magentic collaborative
4. Generate comparison report

**Output:**
```
COMPARISON RESULTS
single_agent                  : 0.82
handoff_multi_domain_agent   : 0.88
magentic_group               : 0.91
```

---

## Without Backend/Frontend

The evaluation framework **doesn't need backend or frontend**, but it **DOES need MCP**.

```
Normal Flow:
Frontend → Backend → Agent → MCP → Results → Frontend
   ↑                              ↓
  User                        Real Data

Evaluation Flow:
Test Script → Agent → MCP → Results → Evaluator → Report
    ↑                   ↓                           ↓
Test Cases          Real Data                    Scores
```

**What's removed:** Frontend, Backend (HTTP server layer)
**What's kept:** Agent logic, MCP server, real tool calls, real data

The evaluator directly invokes your agent code (like backend does), but programmatically instead of via HTTP requests.

---

## Quick Reference

| What to Test | Command | Prerequisites |
|-------------|---------|---------------|
| Framework only | `python test_framework.py` | None |
| Mock agents | `python test_agents.py --mode mock` | None |
| Real agents | `python test_agents.py --mode with-mcp` | MCP server running |
| All patterns | `python test_agents.py --mode compare` | MCP server running |
| Your agent | `python test_with_eval.py` | MCP + your custom script |

---

## Troubleshooting

**"No MCP server available"**
- Start MCP server first: `cd mcp && uv run python mcp_service.py`

**"No traces found for test case"**
- Check query matching in evaluator.py
- Ensure query strings match exactly

**"Agent module not found"**
- Check Python path setup
- Verify agent import statements

**"Low scores"**
- Review detailed report in `eval_results/`
- Check which metrics are failing
- Adjust agent logic or test expectations

---

## Next Steps

1. **Start simple**: Run `test_framework.py` to verify setup
2. **Add tool tracking**: Modify your agent to capture tool calls
3. **Create test script**: Based on `test_with_eval.py` example
4. **Iterate**: Use evaluation results to improve agents
5. **Compare patterns**: Test different agent architectures

The key is **separating evaluation from your normal dev workflow** - treat it as automated testing!
