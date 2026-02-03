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

## Step-by-Step Setup Guide

**Prerequisites**: You'll need an Azure AI Project (Cognitive Services resource) provisioned in Azure, plus optionally Azure OpenAI for LLM-as-judge evaluation.

Follow these steps to get the evaluation system working:

### **Step 1: Clone and Setup Repository**
```bash
# Clone the repo
git clone https://github.com/microsoft/OpenAIWorkshop.git
cd OpenAIWorkshop

# Switch to your branch with telemetry changes
git checkout heena-dev2

# Install dependencies
uv sync
```

### **Step 2: Azure Authentication Setup**
```bash
# Login to Azure
az login

# Set subscription (replace with your subscription)
az account set --subscription "your-subscription-id"

# Verify authentication
az account show
```

### **Step 3: Get Azure AI Project Details**
```bash
# Option 1: Azure CLI (if you know your resource group)
az cognitiveservices account list --resource-group "your-rg" --query "[?kind=='AIServices'].[name,properties.endpoint]" -o table

# Option 2: Azure AI Foundry Studio (Easier)
# Go to https://ai.azure.com -> Your Project -> Settings -> Project details -> Copy endpoint

# Note down the endpoint URL - you'll need this for AZURE_AI_PROJECT
```

### **Step 4: Configure Environment Variables**
Create `.env` file in `agentic_ai/applications/`:

> **🎯 Important: ALL environment variables are configured in the .env file below. No manual `$env:` or `export` commands needed!**

```bash
cd agentic_ai/applications
cat > .env << 'EOF'
# Agent Configuration
AGENT_MODULE=agents.agent_framework.multi_agent.handoff_multi_domain_agent

# Azure OpenAI Configuration (update with your values)
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# MCP Server Configuration
MCP_SERVER_URI=http://localhost:8000/mcp
DISABLE_AUTH=true

# Azure AI Foundry Project (REQUIRED for evaluation results)
# Find this at: https://ai.azure.com -> Your Project -> Settings -> Project details
# Format: https://<account>.services.ai.azure.com/api/projects/<project-name>
AZURE_AI_PROJECT=https://your-account.services.ai.azure.com/api/projects/your-project-name

# Azure Application Insights (REQUIRED for tracing)
# Find this at: Azure Portal -> Application Insights -> Your Resource -> Overview -> Connection String
APPLICATION_INSIGHTS_CONNECTION_STRING=InstrumentationKey=your-key;IngestionEndpoint=https://your-region.in.applicationinsights.azure.com/;LiveEndpoint=https://your-region.livediagnostics.monitor.azure.com/;ApplicationId=your-app-id

# Azure Content Safety (Optional - uses same endpoint as OpenAI if available)
AZURE_CONTENT_SAFETY_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_CONTENT_SAFETY_KEY=your_content_safety_key_here
EOF
```

**📝 To find your required URLs:**

> **🚨 CRITICAL: You MUST replace all placeholder values below with your actual Azure resource details!**

1. **AZURE_AI_PROJECT**: Go to [Azure AI Foundry Studio](https://ai.azure.com) → Your Project → **Settings** → **Project details** → Copy endpoint
2. **APPLICATION_INSIGHTS_CONNECTION_STRING**: Go to [Azure Portal](https://portal.azure.com) → Application Insights → Your Resource → **Overview** → Copy Connection String
3. **AZURE_OPENAI_**: Your existing Azure OpenAI resource credentials

> **❌ Common Error: Leaving placeholder values like `your-account.services.ai.azure.com` will cause DNS resolution failures!**

> **✅ Once the .env file is configured, all scripts automatically load these variables. No terminal commands needed!**

## 📋 **Prerequisites Summary (Complete This Order):**

### **Must Complete BEFORE Starting Services:**
1. ✅ Azure CLI authenticated (`az login`)
2. ✅ Azure AI Developer role assigned 
3. ✅ **`.env` file created with YOUR ACTUAL resource URLs** (not placeholders)
4. ✅ Python environment ready (`uv` installed)

### **Service Startup Order (Do This Every Time):**
1. 🟢 **First**: Start MCP server on port 8000
2. 🟡 **Second**: Start backend on port 7000 (with telemetry auto-enabled)
3. 🔵 **Third**: Run evaluations (they connect to backend)

### **Step 5: Assign Azure Roles**

You can assign roles in two ways:

**Option 1: Azure Portal (Recommended)**
1. Go to your Azure AI Project resource in Azure Portal
2. Navigate to **Access Control (IAM)**
3. Click **Add role assignment**
4. Assign these roles to your user account:
   - **Azure AI Developer** (required for evaluation runs)
   - **Cognitive Services User** (required if using Azure OpenAI)

**Option 2: Command Line**
```bash
# Get your user principal ID
USER_ID=$(az ad signed-in-user show --query id -o tsv)

# Get the AI project resource ID
AI_PROJECT_ID=$(az cognitiveservices account show --name "your-ai-project-name" --resource-group "your-rg" --query id -o tsv)

# Assign Azure AI Developer role
az role assignment create \
  --assignee $USER_ID \
  --role "Azure AI Developer" \
  --scope $AI_PROJECT_ID

# Assign Cognitive Services User role (if using Azure OpenAI)
az role assignment create \
  --assignee $USER_ID \
  --role "Cognitive Services User" \
  --scope $AI_PROJECT_ID
```

### **Step 6: Start Required Services**

> **⚠️ Important: Start services in this exact order!**

```bash
# Terminal 1: Start MCP server
cd mcp
uv run python mcp_service.py
# Wait for: "MCP server running on http://localhost:8000"

# Terminal 2: Start backend (AFTER MCP server is running)
cd agentic_ai/applications
uv run python -m uvicorn backend:app --port 7000 --reload
# Wait for: "🎉 DEBUG: Telemetry setup complete!" and "Application startup complete"
```

**✅ Verify both services are running:**
```bash
# Test MCP server
curl http://localhost:8000/health

# Test backend
curl http://localhost:7000/chat
```

### **Step 7: Run Evaluation Pipeline**

> **🔧 No environment variable setup needed! All values loaded automatically from .env file.**

```bash
# Run evaluation against local backend
cd agentic_ai/evaluations
uv run python run_agent_eval.py --agent-name "teammate_test" --backend-url "http://localhost:7000"

# Should see output like:
# "Processing test case: example_1_billing"
# "Overall Score: 0.XX, Passed: True/False"
# "Generated evaluation_input_data.jsonl"
```

### **Step 11: Push Results to Foundry**

> **🔧 AZURE_AI_PROJECT and all credentials loaded automatically from .env file.**

```bash
# Push evaluation results to Foundry
uv run python run_eval.py

# Should see output like:
# "Created evaluation run: [run-id]"
# "Results pushed to Foundry successfully"
```

### **Step 12: Verify Complete Integration**
1. **Evaluation Results**: Check that `evaluation_input_data.jsonl` was generated
2. **Foundry Evaluation**: Go to [https://ai.azure.com](https://ai.azure.com) → **Evaluation** section → Look for your run
3. **Foundry Tracing**: Navigate to **Tracing** section → Verify agent traces appear  
4. **Metrics Dashboard**: Check evaluation metrics (Tool Behavior, Completeness, etc.)

## 📋 **Verification Checklist**

### **Core Evaluation (Required):**
- [ ] Azure CLI authenticated
- [ ] Azure AI Developer role assigned
- [ ] `.env` file configured with AZURE_AI_PROJECT
- [ ] MCP server running on port 8000
- [ ] Backend running on port 7000
- [ ] Evaluation runs successfully (80%+ score expected)
- [ ] `evaluation_input_data.jsonl` generated
- [ ] Results appear in Foundry evaluation portal

### **Optional Tracing (If Enabled):**
- [ ] Application Insights resource created
- [ ] `APPLICATION_INSIGHTS_CONNECTION_STRING` in `.env` 
- [ ] Backend shows "Telemetry setup complete!" message
- [ ] Tracing data visible in Foundry tracing portal

## File Overview

| File | Purpose |
|------|---------|
| `run_agent_eval.py` | Main script - runs agents via HTTP and evaluates responses |
| `run_eval.py` | Pushes evaluation results to Azure AI Foundry |
| `metrics.py` | Defines all evaluation metrics and scoring logic |
| `evaluator.py` | Core evaluation framework and result aggregation |
| `eval_dataset.json` | Test cases based on Contoso customer scenarios |
| `evaluation_input_data.jsonl` | Generated data file for Foundry integration |
| `telemetry.py` | **Optional**: Azure Monitor configuration for tracing |

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

The evaluation system automatically integrates with Azure AI Foundry when properly configured (see Step-by-Step Setup Guide above). This provides:

- **Evaluation Tracking**: All evaluation runs are stored and compared over time
- **Real-time Tracing**: Agent operations and tool calls are captured automatically 
- **Performance Monitoring**: Token usage, duration, and error tracking
- **Collaborative Review**: Team can access results via Foundry portal

## What Changes Were Made for Integration

### Backend Changes:
1. **Created `telemetry.py`** - Azure Monitor + Agent Framework observability setup (located in `agentic_ai/evaluations/`)
2. **Modified `backend.py`** - Added `from evaluations.telemetry import setup_telemetry` and setup call
3. **Updated `pyproject.toml`** - Added telemetry dependencies

### Evaluation System Changes:
4. **Modified `run_agent_eval.py`** - HTTP-based evaluation approach with correct port 7000
5. **Enhanced `metrics.py`** - Production-ready evaluation metrics
6. **Updated `run_eval.py`** - Foundry integration for result submission

### Agent Changes:
- **No agent code changes required** - Agent Framework handles tracing automatically

### What Gets Traced Automatically:
- **Agent Operations**: Single agent, multi-domain, collaborative patterns
- **Tool Calls**: MCP tool invocations and responses  
- **Request/Response**: HTTP requests and agent responses
- **Performance**: Duration, token usage, error rates
- **Handoffs**: Multi-agent coordination and specialist routing
- **Errors & Exceptions**: Failed requests and debugging information

All tracing happens at the infrastructure level - existing agent implementations get comprehensive observability without any code modifications!

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

### **"Failed to resolve hostname" / DNS Error**
```bash
# Error: getaddrinfo failed for 'your-account.services.ai.azure.com'
# Solution: Update .env file with actual Azure AI project endpoint
cd agentic_ai/applications
grep "AZURE_AI_PROJECT" .env
# Should show your real endpoint, not placeholder values
```

### **Backend Won't Start**
```bash
# Use correct uvicorn command:
cd agentic_ai/applications
uv run python -m uvicorn backend:app --port 7000 --reload

# Look for these success messages:
# ✅ "🎉 DEBUG: Telemetry setup complete!"
# ✅ "INFO: Application startup complete"
```

### **"Authentication failed"**
```bash
# Verify Azure login
az account show

# Check role assignments
az role assignment list --assignee $(az ad signed-in-user show --query id -o tsv)
```

### **"Cannot connect to backend"**
```bash
# Check if backend is running
curl http://localhost:7000/health

# Check MCP server
curl http://localhost:8000/health
```

### **"Foundry evaluation push failed"**
```bash
# Verify AZURE_AI_PROJECT is set correctly
echo $AZURE_AI_PROJECT

# Check if evaluation_input_data.jsonl was generated
ls -la evaluation_input_data.jsonl
```

### **"No evaluation results"**
```bash
# Check agent returns valid responses
curl -X POST http://localhost:7000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test query"}'
```

### **Tracing Issues (If Enabled):**

### **"Telemetry setup failed"**
```bash
# All values loaded from .env file automatically - no manual setting needed
# To verify your .env file has the connection string:
cd agentic_ai/applications
grep "APPLICATION_INSIGHTS_CONNECTION_STRING" .env

# Test telemetry directly
cd ../evaluations
python -c "from telemetry import setup_telemetry; setup_telemetry()"
```

### **"No traces in Foundry"**
- Wait 1-2 minutes for ingestion delay
- Verify backend shows "Telemetry setup complete!" message
- Check that agent interactions are happening via backend

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
