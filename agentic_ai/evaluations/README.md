# AI Agent Evaluation Framework

Comprehensive evaluation framework for testing AI agents against the Contoso Communications business scenarios defined in [SCENARIO.md](../../SCENARIO.md).

## Overview

This framework provides:
- **Test Dataset**: 6 predefined test cases based on customer scenarios
- **Multiple Evaluation Metrics**: Tool usage, completeness, response quality, accuracy
- **Automated Evaluation**: Run evaluations programmatically
- **LLM-as-Judge**: Optional quality evaluation using Azure OpenAI
- **Detailed Reporting**: JSON results and human-readable reports

## Quick Start

> **📖 For detailed testing instructions, see [TESTING_GUIDE.md](TESTING_GUIDE.md)**

### 1. Test the Framework (No MCP needed)

```bash
cd agentic_ai/evaluations
python test_framework.py
```

This will:
- Validate the evaluation framework works
- Run with mock agent responses
- Generate example results

### 2. Test with Real Agents

```bash
# Terminal 1: Start MCP server
cd mcp
uv run python mcp_service.py

# Terminal 2: Run evaluation
cd agentic_ai/evaluations
python test_agents.py --mode with-mcp
```

This will:
- Load test cases from `eval_dataset.json`
- Run your actual agents
- Generate results in `eval_results/` directory

### 2. Integrate with Your Agent

```python
from evaluations.evaluator import AgentEvaluationRunner, AgentTrace

# Capture agent execution
trace = AgentTrace(
    query="I noticed my last invoice was higher than usual—can you help me?",
    response="Your agent's response here...",
    tool_calls=[
        {"name": "get_customer_detail", "args": {"customer_id": 1001}},
        {"name": "get_billing_summary", "args": {"customer_id": 1001}}
    ],
    metadata={"duration_ms": 2500}
)

# Run evaluation
runner = AgentEvaluationRunner(dataset_path="eval_dataset.json")
summary = runner.run_evaluation([trace])
print(f"Pass Rate: {summary['pass_rate']:.1%}")
```

## Test Cases

The framework includes 6 test cases based on SCENARIO.md:

| ID | Scenario | Expected Tools | Success Criteria |
|----|----------|----------------|------------------|
| `example_1_billing` | Invoice inquiry | get_customer_detail, get_billing_summary, search_knowledge_base | Must access billing & KB, explain charges |
| `example_2_service_quality` | Slow internet | get_subscription_detail, get_data_usage, search_knowledge_base | Must check subscription, provide troubleshooting |
| `example_3_international_roaming` | Travel abroad | get_subscription_detail, get_products, search_knowledge_base | Must check roaming options, explain charges |
| `example_4_account_lockout` | Locked account | get_security_logs, unlock_account, search_knowledge_base | Must check logs, offer unlock |
| `example_5_promotions` | Discount eligibility | get_customer_detail, get_eligible_promotions, search_knowledge_base | Must check promotions, explain eligibility |
| `example_6_product_return` | Return process | get_customer_orders, search_knowledge_base | Must check orders, explain return policy |

## Evaluation Metrics

### 1. Tool Usage (30% weight)
- Validates correct MCP tool calls
- Checks for required vs. optional tools
- Identifies missing or unexpected tools

**Example:**
```python
expected_tools = ["get_customer_detail", "get_billing_summary"]
actual_tools = ["get_customer_detail", "get_billing_summary", "search_knowledge_base"]
# Score: 1.0 (all required tools used)
```

### 2. Completeness (30% weight)
- Validates all success criteria are met
- Checks both tool usage and response content
- Maps criteria to specific validations

**Success Criteria Examples:**
- `must_access_billing`: Checks if billing tools were called
- `must_explain_charges`: Checks if response contains charge explanations
- `must_access_knowledge_base`: Checks if KB search was performed

### 3. Response Quality (25% weight)
- Basic checks: content length, error detection
- Optional LLM-as-judge evaluation (if Azure OpenAI client provided)
- Evaluates: relevance, accuracy, completeness, clarity, professionalism

### 4. Accuracy (15% weight)
- Validates factual correctness against ground truth
- Checks consistency with tool results
- Currently uses basic validation (extend as needed)

## File Structure

```
agentic_ai/evaluations/
├── README.md                 # This file
├── eval_dataset.json         # Test cases from SCENARIO.md
├── metrics.py                # Evaluation metric implementations
├── evaluator.py              # Main evaluation runner
├── run_eval.py              # Example usage and integration
└── eval_results/            # Generated results (gitignored)
    ├── eval_results_YYYYMMDD_HHMMSS.json
    └── eval_report_YYYYMMDD_HHMMSS.txt
```

## Usage Examples

### Basic Evaluation

```python
from evaluations.evaluator import AgentEvaluationRunner, AgentTrace

# Create traces from your agent runs
traces = [
    AgentTrace(
        query="Query from test case",
        response="Agent's response",
        tool_calls=[{"name": "tool_name", "args": {...}}],
        metadata={}
    )
]

# Run evaluation
runner = AgentEvaluationRunner()
summary = runner.run_evaluation(traces, output_dir="eval_results")
```

### With LLM-as-Judge

```python
from openai import AzureOpenAI

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

# Create runner with LLM judge
runner = AgentEvaluationRunner(
    dataset_path="eval_dataset.json",
    azure_openai_client=client
)

summary = runner.run_evaluation(traces)
```

### Capturing Traces During Agent Execution

```python
from evaluations.run_eval import AgentTraceCollector

collector = AgentTraceCollector()

# In your agent loop
for query in test_queries:
    response, tools = run_your_agent(query)
    
    collector.capture_trace(
        query=query,
        response=response,
        tool_calls=tools,
        metadata={"agent_type": "handoff_multi_domain"}
    )

# Save for later evaluation
collector.save_traces("my_agent_traces.json")

# Or evaluate immediately
runner = AgentEvaluationRunner()
summary = runner.run_evaluation(collector.get_traces())
```

## Evaluation Results

### JSON Output (`eval_results_YYYYMMDD_HHMMSS.json`)

```json
{
  "results": [
    {
      "test_case_id": "example_1_billing",
      "query": "Customer query...",
      "agent_response": "Agent response...",
      "overall_score": 0.85,
      "passed": true,
      "metrics": [
        {
          "name": "tool_usage",
          "score": 1.0,
          "passed": true,
          "explanation": "✓ Correctly used: get_customer_detail, get_billing_summary"
        }
      ]
    }
  ],
  "summary": {
    "total_tests": 6,
    "passed": 5,
    "failed": 1,
    "pass_rate": 0.833,
    "average_score": 0.82
  }
}
```

### Text Report (`eval_report_YYYYMMDD_HHMMSS.txt`)

```
================================================================================
AI AGENT EVALUATION REPORT
================================================================================

Timestamp: 2024-12-10T14:30:00
Total Tests: 6
Passed: 5
Failed: 1
Pass Rate: 83.3%
Average Score: 0.82

================================================================================
METRIC AVERAGES
================================================================================
tool_usage                    : 0.92
completeness                  : 0.78
response_quality_basic        : 0.85
accuracy                      : 1.00

================================================================================
DETAILED RESULTS
================================================================================

✓ PASS example_1_billing (Score: 0.88)
Query: I noticed my last invoice was higher than usual...
Metrics:
  - tool_usage: 1.00 - ✓ Correctly used: get_customer_detail, get_billing_summary
  - completeness: 0.80 - ✓ Met: must_access_billing, must_access_knowledge_base
```

## Customization

### Adding New Test Cases

Edit `eval_dataset.json`:

```json
{
  "test_cases": [
    {
      "id": "custom_test_1",
      "customer_query": "Your custom query",
      "customer_id": 1007,
      "expected_tools": ["tool1", "tool2"],
      "success_criteria": {
        "must_check_something": true
      }
    }
  ]
}
```

### Custom Metrics

Extend metrics in `metrics.py`:

```python
class CustomEvaluator:
    def evaluate(self, ...):
        # Your custom logic
        return EvaluationResult(...)
```

### Custom Weights

Modify weights in `evaluator.py`:

```python
weights = {
    "tool_usage": 0.4,        # Increase tool usage importance
    "completeness": 0.3,
    "response_quality": 0.2,
    "accuracy": 0.1
}
```

## Integration with Different Agent Patterns

### Single Agent

```python
# After running single agent
trace = AgentTrace(
    query=user_query,
    response=agent_response,
    tool_calls=agent.get_tool_calls(),  # Your agent's tool tracking
    metadata={"pattern": "single_agent"}
)
```

### Multi-Domain Agent

```python
# Track which specialist handled the request
trace = AgentTrace(
    query=user_query,
    response=specialist_response,
    tool_calls=all_tool_calls,
    metadata={
        "pattern": "multi_domain",
        "specialist": "billing_agent"
    }
)
```

### Collaborative Multi-Agent

```python
# Track coordination
trace = AgentTrace(
    query=user_query,
    response=final_response,
    tool_calls=aggregated_tool_calls,
    metadata={
        "pattern": "collaborative",
        "agents_involved": ["planner", "billing", "kb_search"]
    }
)
```

## Best Practices

1. **Capture Real Agent Runs**: Use actual agent executions, not mocked data
2. **Test All Patterns**: Evaluate single, multi-domain, and collaborative agents
3. **Iterate on Failures**: Analyze failed tests to improve agents
4. **Track Over Time**: Save results with timestamps to track improvements
5. **Use LLM-as-Judge**: Enable for better response quality assessment
6. **Add Custom Tests**: Create domain-specific test cases for your use case

## Troubleshooting

### "No trace found for test case"
- Ensure your agent query exactly matches the `customer_query` in test case
- Or modify the matching logic in `evaluator.py`

### Low tool usage scores
- Check that you're capturing all tool calls correctly
- Verify tool names match MCP tool definitions

### Low completeness scores
- Review success criteria mappings in `metrics.py`
- Ensure agent responses contain expected keywords

### LLM judge errors
- Verify Azure OpenAI credentials in `.env`
- Check model deployment name matches configuration
- Falls back to basic quality check on error

## Contributing

To extend this framework:

1. Add test cases to `eval_dataset.json`
2. Create custom evaluators in `metrics.py`
3. Update weights/logic in `evaluator.py`
4. Document changes in this README

## Related Documentation

- [SCENARIO.md](../../SCENARIO.md) - Business scenarios and test case source
- [Agent Framework README](../agents/agent_framework/README.md) - Agent implementation
- [MCP README](../../mcp/README.md) - MCP tool definitions

---

**Questions?** Check the example in `run_eval.py` or review the inline documentation in each module.
