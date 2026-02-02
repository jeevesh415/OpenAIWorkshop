# AI Agent Evaluation Framework

Comprehensive evaluation system for testing AI agents against Contoso customer support scenarios. This framework evaluates local agents and integrates with Azure AI Foundry for telemetry and evaluation tracking.

## What is Agent Evaluation?

This evaluation framework tests your AI agents against real customer support scenarios to measure:
- **Tool Usage**: Does the agent call the right APIs/tools for the task?
- **Completeness**: Does the agent meet all success criteria?
- **Response Quality**: Is the response helpful and well-structured?
- **Accuracy**: Does the response match expected outcomes?
- **Efficiency**: Does the agent work efficiently without unnecessary steps?
- **Safety**: Does the agent avoid making promises it can't keep?

## Quick Start

### Prerequisites
1. **MCP Server Running**: `cd mcp && uv run python mcp_service.py`
2. **Backend Running**: `cd agentic_ai/applications && uv run uvicorn backend:app --port 7002`
3. **Environment Variables**: Ensure `.env` is configured in `agentic_ai/applications/`

### Run Evaluation (2-Step Process)

```bash
# Step 1: Run agent evaluation against local backend
cd agentic_ai/evaluations
uv run python run_agent_eval.py --agent-name "your_agent_test" --backend-url "http://localhost:7002"

# Step 2: Push results to Azure AI Foundry (optional)
uv run python run_eval.py
```

## File Overview

| File | Purpose |
|------|---------|
| `run_agent_eval.py` | Main script - runs agents via HTTP and evaluates responses |
| `run_eval.py` | Pushes evaluation results to Azure AI Foundry |
| `metrics.py` | Defines all evaluation metrics and scoring logic |
| `evaluator.py` | Core evaluation framework and result aggregation |
| `eval_dataset.json` | Test cases based on Contoso customer scenarios |
| `evaluation_input_data.jsonl` | Generated data file for Foundry integration |

## Evaluation Metrics Explained

### 1. Tool Behavior (30% weight)
- **What it measures**: Combines recall, precision, and efficiency of tool usage
- **Scoring Formula**: `(recall × 0.5) + (precision × 0.3) + (efficiency × 0.2)`
- **Recall**: Fraction of required tools actually used
- **Precision**: Fraction of used tools that were relevant 
- **Efficiency**: Required tools / total tools used (capped at 1.0)
- **Example**: Required `[get_billing_summary]`, used `[get_billing_summary, get_customer_detail]` = Recall 1.0, Precision 0.5, Efficiency 0.5

### 2. Completeness (25% weight) 
- **What it measures**: Whether agent meets scenario-specific success criteria
- **Scoring**: Counts how many required criteria were satisfied
- **Checks**: Tool-based criteria (e.g., "must_access_billing" → needs billing tools)
- **Example**: 3/4 required criteria met = 75% score

### 3. Response Quality (20% weight)
- **What it measures**: Basic response quality checks (no LLM judge in current setup)
- **Scoring**: Currently just checks response length > 15 words
- **Future**: Could integrate LLM-as-judge for more sophisticated quality assessment
- **Example**: "Your invoice is $150" (too short) vs detailed explanation

### 4. Step Efficiency (10% weight)
- **What it measures**: Whether agent uses minimum necessary tool calls
- **Scoring Formula**: `min(required_tools / actual_tool_calls, 1.0)`
- **Efficiency**: 1.0 = perfect efficiency, 0.5 = twice as many calls as needed
- **Example**: Need 1 tool, used 3 tools = 1/3 = 0.33 efficiency

### 5. Grounded Accuracy (10% weight)
- **What it measures**: Placeholder for future tool output contradiction checking
- **Scoring**: Currently defaults to 1.0 (100%) - no actual grounding check implemented
- **Future**: LLM-assisted fact-checking against tool results
- **Example**: Would catch if agent claims account unlocked when security logs show locked

### 6. Safety (5% weight)
- **What it measures**: Pattern matching for risky over-promising phrases
- **Scoring**: 1.0 if no risky patterns found, 0.0 if any detected
- **Risky patterns**: "guarantee refund", "will definitely refund", "account unlocked now", "I have removed the charge"
- **Example**: "I guarantee a refund" (unsafe) vs "I can help you request a refund review" (safe)

## Test Dataset

The `eval_dataset.json` contains 6 test cases covering common customer scenarios:

1. **Billing Issues**: High invoice investigation
2. **Service Quality**: Internet speed complaints  
3. **Travel/Roaming**: International phone plan questions
4. **Account Security**: Locked account assistance
5. **Promotions**: Discount eligibility checks
6. **Returns**: Product return process

Each test case includes:
- Customer query
- Expected tools the agent should use
- Required tools (subset that are mandatory)
- Success criteria for the scenario

## Azure AI Foundry Integration

### Evaluation Results
After running evaluations, push results to Foundry for tracking and comparison:

```bash
# Requires AZURE_AI_PROJECT environment variable
export AZURE_AI_PROJECT="your_foundry_project_endpoint"
uv run python run_eval.py
```

This creates a new evaluation run in Foundry with:
- Individual test case scores
- Aggregated metrics across all test cases  
- Comparison with previous evaluation runs

### Telemetry & Tracing (In Development)
⚠️ **Note**: Tracing integration is currently being developed. The current setup includes:

1. **Backend Telemetry Setup**: 
   - Added `telemetry.py` with Azure Monitor configuration
   - Calls `configure_azure_monitor()` + `setup_observability()` in backend
   - Requires `APPLICATION_INSIGHTS_CONNECTION_STRING` in `.env`
   - Agent Framework handles automatic span emission for agent operations

2. **What's Working**: 
   - Evaluation results push to Foundry ✅
   - Backend telemetry infrastructure setup ✅
   - Agent Framework configured to emit traces ✅

3. **What Needs Verification**:
   - Agent Framework spans appearing in Foundry Tracing UI
   - Complete trace correlation between local agent and Foundry
   - Full integration testing with hosted agents

**Note**: The Agent Framework itself handles the tracing instrumentation - no additional agent code changes needed.

## Working with Local Agents

The evaluation system works by sending HTTP requests to your running backend:

1. **Agent Configuration**: Specify agent in `.env` with `AGENT_MODULE=agents.agent_framework.multi_agent.handoff_multi_domain_agent`

2. **HTTP Testing**: `run_agent_eval.py` sends POST requests to `/chat` endpoint

3. **Tool Tracking**: Agent Framework automatically broadcasts tool calls for evaluation

4. **Result Generation**: Creates `evaluation_input_data.jsonl` for Foundry integration

## Extending the Framework

### Adding New Metrics
1. Create evaluator class in `metrics.py`
2. Implement `evaluate()` method returning `EvaluationResult`  
3. Add to evaluation pipeline in `run_eval.py`

### Adding Test Cases
1. Add new scenario to `eval_dataset.json`
2. Include expected tools and success criteria
3. Run evaluation to test new scenario

### Custom Agents
1. Ensure agent responds to HTTP `/chat` endpoint
2. Agent should broadcast tool calls via WebSocket manager
3. Follow Agent Framework patterns for telemetry

## Troubleshooting

### Common Issues

**"Cannot connect to backend"**
- Ensure backend is running on specified port
- Check `.env` configuration
- Verify agent module loads correctly

**"MCP connection failed"**  
- Start MCP server: `cd mcp && uv run python mcp_service.py`
- Check MCP_SERVER_URI in `.env`
- Verify port 8000 is available

**"No evaluation results"**
- Check agent returns valid responses
- Verify tool calls are captured
- Review agent logs for errors

**"Foundry push failed"**
- Set AZURE_AI_PROJECT environment variable
- Verify Azure credentials are configured
- Check evaluation_input_data.jsonl was generated

### Debug Mode

Run with verbose output to see detailed evaluation steps:

```bash
# See tool calls and scoring details
python run_agent_eval.py --agent-name "debug_run" --backend-url "http://localhost:7002"
```

## Results and Reporting

Evaluation generates multiple output formats:

- **Console Output**: Real-time progress and summary scores
- **eval_results/*.json**: Detailed results for each test case
- **eval_results/*.txt**: Human-readable evaluation reports  
- **evaluation_input_data.jsonl**: Data file for Foundry integration
- **Foundry Dashboard**: Web UI showing trends and comparisons

### Interpreting Scores

- **80%+**: Excellent performance
- **70-79%**: Good performance, minor improvements needed
- **60-69%**: Acceptable performance, some issues to address
- **Below 60%**: Significant improvements required

Focus on metrics with low scores and failed test cases to identify specific areas for agent improvement.

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
