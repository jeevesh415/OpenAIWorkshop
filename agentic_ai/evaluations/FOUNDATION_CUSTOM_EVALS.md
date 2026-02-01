# Contoso Custom Evaluations with Azure AI Foundry

This document explains how to run the Contoso **custom evaluations** against an agent and see the results in **Azure AI Foundry**, without using any key-based Azure OpenAI evaluators.

## What this evaluates

The evaluation pipeline uses your existing telecom/Contoso dataset and metrics in:

- Dataset: `eval_dataset.json`
- Metrics implementation: `metrics.py`
- Orchestrator scripts:
  - `collect_agent_runs.py`
  - `run_eval.py`

For each test case, the following custom metrics from `metrics.py` are computed:

- `tool_usage` (ToolUsageEvaluator)
  - Checks which tools the agent used vs `expected_tools` and `required_tools` from the dataset.
  - Produces:
    - `tool_usage.score` (0–1 coverage of required tools)
    - `tool_usage.passed` (1.0 if all required tools used, else 0.0)

- `completeness` (CompletenessEvaluator)
  - Checks whether scenario-specific `success_criteria` were met using:
    - Tool calls (e.g., billing, promotions, security tools).
    - Response text keywords (e.g., explaining charges, policies).
  - Produces:
    - `completeness.score` (0–1 fraction of required criteria met)
    - `completeness.passed` (1.0 if all required criteria met)

- `response_quality` (ResponseQualityEvaluator, **basic mode**)
  - Runs lightweight, rule-based checks (no judge LLM):
    - Has non-empty content
    - Sufficient length
    - Not an obvious error message
  - Produces:
    - `response_quality.score` (0–1)
    - `response_quality.passed` (1.0 if all basic checks pass)

- `accuracy` (AccuracyEvaluator, placeholder)
  - Currently a simple pass-through check (always passes if no ground truth is defined).
  - Produces:
    - `accuracy.score`
    - `accuracy.passed`

- `overall` (weighted aggregate)
  - Combines the above metrics with the same weights as the local `AgentEvaluationRunner`:
    - `tool_usage`: 0.3
    - `completeness`: 0.3
    - `response_quality_*`: 0.25
    - `accuracy`: 0.15
  - Produces:
    - `overall.score`
    - `overall.passed` (1.0 if score ≥ 0.7 and all metrics passed)

All of these are implemented in `contoso_evaluator` inside `run_eval.py` and registered as a single custom evaluator named `contoso_metrics` for Azure AI Evaluation.

## How it is wired into Foundry

The integration uses the `azure-ai-evaluation` SDK’s `evaluate(...)` function, but **only** for orchestration and logging to Foundry:

- No `AzureOpenAIModelConfiguration` or `OpenAIModelConfiguration` is created.
- No built-in AOAI/LLM judges (IntentResolution, TaskAdherence, etc.) are used.
- All scoring logic lives in `metrics.py` and `run_eval.py`.

`run_eval.py` does the following:

1. Reads `evaluation_input_data.jsonl` produced by `collect_agent_runs.py`.
2. Calls the `contoso_metrics` evaluator for each row.
3. Sends the results to your Azure AI project via `azure_ai_project`.
4. Prints a `studio_url` you can open in Azure AI Foundry to inspect the run.

## Prerequisites

Before running the evaluations:

1. Have an Azure AI project created (e.g., `proj-default`).
2. Know your Azure AI project endpoint, for example:
   - `https://<account>.services.ai.azure.com/api/projects/<project-name>`
3. Ensure your agent backend is reachable at a `/chat` HTTP endpoint.

No Azure OpenAI keys or judge models are required for these custom metrics.

## Environment variables

Two environment variables drive the evaluation pipeline:

- `BACKEND_CHAT_URL`
  - Full URL to the agent backend `/chat` endpoint.
  - Examples:
    - Local backend: `http://localhost:7000/chat`
    - Hosted Container App: `https://<your-backend-app>.azurecontainerapps.io/chat`

- `AZURE_AI_PROJECT`
  - Azure AI project endpoint used by `evaluate(...)` to log runs into Foundry.
  - Example:
    - `https://cudemov1.services.ai.azure.com/api/projects/proj-default`

Set them in PowerShell before running:

```powershell
$env:BACKEND_CHAT_URL = "http://localhost:7000/chat"           # or your hosted URL
$env:AZURE_AI_PROJECT = "https://<account>.services.ai.azure.com/api/projects/<project>"
```

## Running evaluations against a local backend

1. Start the local backend from `agentic_ai/applications`:

   ```powershell
   uv run python backend.py
   ```

2. In another PowerShell window, go to the evaluations folder and set env vars:

   ```powershell
   cd C:\Users\heenaugale\Openaiworkshop\OpenAIWorkshop\agentic_ai\evaluations

   $env:BACKEND_CHAT_URL = "http://localhost:7000/chat"
   $env:AZURE_AI_PROJECT = "https://<account>.services.ai.azure.com/api/projects/<project>"
   ```

3. Collect agent runs using the evaluation dataset:

   ```powershell
   python collect_agent_runs.py
   ```

   This will:
   - Read `eval_dataset.json`.
   - Call `/chat` for each test case.
   - Write `evaluation_input_data.jsonl` with `query`, `response`, and scenario metadata.

4. Run the custom Contoso evaluations and push to Foundry:

   ```powershell
   python run_eval.py
   ```

   You should see:
   - A run summary in the console.
   - Aggregated metrics for `contoso_metrics.*`.
   - A `studio_url` to open in Azure AI Foundry.

## Running evaluations against a hosted Container Apps backend

1. Identify your backend Container App name and resource group, for example:

   ```powershell
   $BACKEND_APP = "contoso-agent-backend"
   $RG = "rg-contoso-agents"
   ```

2. Retrieve its public FQDN and set `BACKEND_CHAT_URL`:

   ```powershell
   $fqdn = az containerapp show `
     -n $BACKEND_APP `
     -g $RG `
     --query "properties.configuration.ingress.fqdn" `
     -o tsv

   $env:BACKEND_CHAT_URL = "https://$fqdn/chat"
   ```

3. Verify the hosted `/chat` endpoint responds:

   ```powershell
   Invoke-WebRequest `
     -Uri $env:BACKEND_CHAT_URL `
     -Method POST `
     -ContentType "application/json" `
     -Body '{"session_id":"test-hosted","prompt":"Hello from eval pipeline"}'
   ```

   - If this returns 200 and JSON, you are ready to evaluate.
   - If it returns 500, check backend Container App logs (`az containerapp logs show`) and fix configuration first.

4. Run the same evaluation steps as for local:

   ```powershell
   cd C:\Users\heenaugale\Openaiworkshop\OpenAIWorkshop\agentic_ai\evaluations

   $env:AZURE_AI_PROJECT = "https://<account>.services.ai.azure.com/api/projects/<project>"

   python collect_agent_runs.py
   python run_eval.py
   ```

   This time, `collect_agent_runs.py` is calling the **hosted** agent, and the Foundry run reflects that behavior.

## What you should see in Foundry

After `python run_eval.py` completes, it prints a `studio_url`, for example:

- `https://ai.azure.com/resource/build/evaluation/<run-id>?wsid=...`

Open that URL to see:

- One row per test case from `eval_dataset.json`.
- Columns for each metric returned by `contoso_metrics`:
  - `contoso_metrics.tool_usage.score`, `contoso_metrics.tool_usage.passed`
  - `contoso_metrics.completeness.score`, `contoso_metrics.completeness.passed`
  - `contoso_metrics.response_quality.score`, `contoso_metrics.response_quality.passed`
  - `contoso_metrics.accuracy.score`, `contoso_metrics.accuracy.passed`
  - `contoso_metrics.overall.score`, `contoso_metrics.overall.passed`

You can drill into individual rows to compare:

- The original customer query.
- The agent response.
- The scenario metadata (expected tools, criteria).
- Pass/fail status and scores.

## Notes and limitations

- **Tool usage metrics**
  - `tool_usage.score`/`passed` depend on knowing which tools the agent actually called.
  - If the backend does not return this information (e.g., `tools_used` field), the tool usage metric will be zero or limited.

- **No AOAI keys required**
  - All metrics are computed in your own Python code.
  - The only external call is to Azure AI project for logging and visualization.

- **Extending metrics**
  - You can safely extend or refine `metrics.py` and update `contoso_evaluator` in `run_eval.py`.
  - As long as the evaluator returns a flat dict of metric names → values, they will appear in Foundry under the same `contoso_metrics.*` prefix.

This file is intended as a quick guide so anyone working in the `evaluations` folder can understand what is being evaluated, how to run it, and how it appears in Azure AI Foundry.
