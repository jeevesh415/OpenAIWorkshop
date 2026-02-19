# MCP Agent Demo — Agent Framework

This demo shows eight capabilities of the Microsoft Agent Framework:

| # | What | Script |
|---|------|--------|
| 1 | **Expose an agent as an MCP server** (stateless HTTP) | `mcp_server.py` |
| 2 | **Consume the agent-powered MCP service** from another agent | `mcp_client_agent.py` |
| 3 | **Workflow orchestrating local + remote (MCP) agents** | `workflow_local_remote.py` |
| 4 | **Stateful agent-as-MCP server** (multi-turn sessions) | `mcp_server_stateful.py` |
| 5 | **Stateful multi-turn client agent** conversation via MCP | `mcp_client_stateful.py` |
| 6 | **Typed-contract multi-agent workflow** (structured data exchange) | `workflow_typed_contracts.py` |
| 7 | **Hybrid MCP server** — strict-schema + natural-language tools in one endpoint | `mcp_server_hybrid.py` |
| 8 | **Hybrid client** — demonstrates both tool types in a single incident flow | `mcp_client_hybrid.py` |

## Architecture

### Stateless Mode (Scripts 1–3)

```
┌──────────────────────────────────────────────────────────────┐
│                    Workflow (SequentialBuilder)               │
│                                                              │
│  ┌──────────────┐        ┌─────────────────────────────┐     │
│  │ Local Agent   │  ───▶  │ Remote Agent (via MCP tool) │     │
│  │ "Researcher"  │        │ "Expert Advisor"             │     │
│  │ (in-process)  │        │ (MCPStreamableHTTPTool)      │     │
│  └──────────────┘        └──────────┬──────────────────┘     │
│                                      │ HTTP                   │
└──────────────────────────────────────┼───────────────────────┘
                                       ▼
                          ┌────────────────────────┐
                          │   MCP Server (port 8002)│
                          │   Expert Advisor Agent   │
                          │   (stateless_http=True)  │
                          └────────────────────────┘
```

### Stateful Mode (Scripts 4–5)

```
Client Agent (Coordinator)                     Server (FastMCP v3)
┌───────────────────────────┐                 ┌──────────────────────────────────┐
│ MCPStreamableHTTPTool     │ ── session ──→  │ mcp-session-id → AgentSession    │
│ (auto-sends session ID    │    preserved    │     ↓                            │
│  via mcp-session-id hdr)  │                 │ Agent.run(msg, session=session)   │
│                           │                 │   → InMemoryHistoryProvider       │
│ Turn 1: "What risks?"    │ ─────────────→  │   → history auto-managed          │
│ Turn 2: "Market data?"   │ ─────────────→  │   → builds on prior turns         │
│ Turn 3: "Summarize all"  │ ─────────────→  │   → references full context       │
└───────────────────────────┘                 └──────────────────────────────────┘
```

**Key difference:** In stateful mode, the server uses PrefectHQ's
[FastMCP v3](https://github.com/PrefectHQ/fastmcp) (default `stateless_http=False`)
and maps each MCP `session_id` to an `AgentSession` that accumulates conversation
history across tool calls.

### Hybrid Mode (Scripts 7–8)

```
┌─────────────────────── Hybrid MCP Server (port 8002) ───────────────────────┐
│                                                                              │
│  STRICT-SCHEMA TOOLS (machines consume)     NL TOOLS (humans consume)        │
│  ┌──────────────────────────────────┐       ┌────────────────────────────┐   │
│  │ triage_alert                     │       │ ask_security_advisor       │   │
│  │  raw text → SecurityAlert        │       │  free-form Q&A, policy     │   │
│  │  (Pydantic, 12 fields)           │       │  advice, best practices    │   │
│  ├──────────────────────────────────┤       ├────────────────────────────┤   │
│  │ assess_threat                    │       │ explain_for_customer       │   │
│  │  SecurityAlert → ThreatAssess.   │       │  translate technical       │   │
│  │  (MITRE ATT&CK, score 0-100)    │       │  incident → plain English  │   │
│  ├──────────────────────────────────┤       │  for executives, techs,    │   │
│  │ create_response                  │       │  or compliance officers    │   │
│  │  ThreatAssess. → IncidentResp.   │       └────────────────────────────┘   │
│  │  (remediation actions, SLA)      │                                        │
│  └──────────────────────────────────┘       ┌────────────────────────────┐   │
│                                              │ get_session_info           │   │
│  Session state: last_alert, last_threat,     │ reset_session              │   │
│  last_response shared across all tools       └────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Key insight:** Real MSP platforms need **both** tool types coexisting:
- Strict-schema tools drive automation (isolation, blocking, SLA timers) —
  wrong data means wrong remediation and a customer breach.
- Natural-language tools help humans understand incidents and communicate
  with customers — no schema needed, prose is the point.

Both share the same session state, so `explain_for_customer` can reference
the `IncidentResponse` that `create_response` just produced.

## Prerequisites

- Azure OpenAI credentials in `mcp/.env` (already configured)
- Python 3.12+, `uv`

## Quick Start

### 1. Start the MCP Agent Server

```bash
cd agentic_ai/agents/mcp_agent_demo
uv sync
uv run python mcp_server.py
```

This starts an MCP server on `http://localhost:8002/mcp` that exposes an
"Expert Advisor" agent as a tool via the MCP Streamable HTTP transport.

### 2. Run the Client Agent (in a second terminal)

```bash
cd agentic_ai/agents/mcp_agent_demo
uv run python mcp_client_agent.py
```

This creates a local agent that connects to the MCP server and delegates
questions to the remote Expert Advisor agent.

### 3. Run the Workflow Demo (in a second terminal)

```bash
cd agentic_ai/agents/mcp_agent_demo
uv run python workflow_local_remote.py
```

This demonstrates a **SequentialBuilder** workflow that chains:
1. A **local Researcher agent** (in-process) → drafts initial analysis
2. A **remote Expert Advisor agent** (via MCP) → reviews and enhances

---

### 4. Start the Stateful MCP Agent Server

```bash
cd agentic_ai/agents/mcp_agent_demo
uv run python mcp_server_stateful.py
```

This starts a **stateful** MCP server on `http://localhost:8002/mcp` using
[FastMCP v3](https://github.com/PrefectHQ/fastmcp). Each client session gets
its own `AgentSession`, so the expert agent remembers the full conversation
history across tool calls.

Tools exposed: `chat_with_expert`, `get_session_info`, `reset_conversation`

### 5. Run the Stateful Multi-Turn Client (in a second terminal)

```bash
cd agentic_ai/agents/mcp_agent_demo
uv run python mcp_client_stateful.py
```

This runs a 3-turn conversation where each follow-up builds on the prior:
1. "What are the main risks of expanding into technology?"
2. "Based on that analysis, what does market data look like?"
3. "Summarize everything we discussed into an executive recommendation."

The remote expert references prior turns because the `mcp-session-id` header
ties all requests to the same server-side `AgentSession`.

### 6. Run the Typed-Contract Workflow (standalone — no server needed)

```bash
cd agentic_ai/agents/mcp_agent_demo
uv run python workflow_typed_contracts.py
```

This demonstrates **strict typed data exchange** between agents in an
IT security incident response pipeline — the key advantage of
framework-native orchestration over natural-language protocols like A2A.
Built for an MSP / IT management platform where wrong data at any step
means wrong automated response and a customer breach.

```
  ┌──────────────┐  SecurityAlert    ┌──────────────┐  ThreatAssessment
  │  Alert       │ ────────────────▶ │  Threat      │ ────────────────────▶
  │  Triage      │  (Pydantic)       │  Intel       │  (Pydantic)
  └──────────────┘                   └──────────────┘
                                                              │
  ┌──────────────┐  IncidentResponse                          ▼
  │  Response    │ ◀──────────────── ┌──────────────┐  ImpactAnalysis
  │  Orchestrator│  (Pydantic)       │  Impact      │ ────────────────────▶
  └──────────────┘                   │  Analyzer    │  (Pydantic)
         │                           └──────────────┘
         ▼
   IncidentResponse  (drives automated remediation — isolation, blocking, SLA)
```

Each arrow represents a **Pydantic-validated contract**:
- `SecurityAlert` — 12 fields, enum-constrained severity & alert source
- `ThreatAssessment` — 11 fields, MITRE ATT&CK vectors, threat score (0-100)
- `ImpactAnalysis` — 11 fields, blast-radius scope enum, endpoint counts
- `IncidentResponse` — 15 fields, ordered remediation actions, SLA deadlines

If any agent produces output that violates the schema, the pipeline fails
fast with a Pydantic `ValidationError` — no silent corruption downstream.
In IT security, "approximately right" gets customers breached.

---

### 7. Start the Hybrid MCP Server

```bash
cd agentic_ai/agents/mcp_agent_demo
uv run python mcp_server_hybrid.py
```

This starts a **hybrid** MCP server on `http://localhost:8002/mcp` that
exposes **both** strict-schema tools and natural-language tools:

| Tool | Type | Input → Output |
|------|------|----------------|
| `triage_alert` | Strict schema | raw text → `SecurityAlert` (Pydantic) |
| `assess_threat` | Strict schema | `SecurityAlert` → `ThreatAssessment` (Pydantic) |
| `create_response` | Strict schema | `ThreatAssessment` → `IncidentResponse` (Pydantic) |
| `ask_security_advisor` | Natural language | free-form question → prose answer |
| `explain_for_customer` | Natural language | incident context → plain-English summary |
| `get_session_info` | Utility | — → session metadata |
| `reset_session` | Utility | — → clears session state |

Session state is shared: strict tools store their outputs (`last_alert`,
`last_threat`, `last_response`) so natural-language tools can reference them.

### 8. Run the Hybrid Client (in a second terminal)

```bash
cd agentic_ai/agents/mcp_agent_demo
uv run python mcp_client_hybrid.py
```

This runs a 5-step incident flow that uses **both** tool types:

1. **`triage_alert`** (strict) — parse raw SIEM alert → `SecurityAlert`
2. **`assess_threat`** (strict) — analyze alert → `ThreatAssessment` with MITRE ATT&CK mapping
3. **`create_response`** (strict) — build response plan → `IncidentResponse` with remediation actions
4. **`ask_security_advisor`** (NL) — "What compliance obligations apply?"
5. **`explain_for_customer`** (NL) — draft executive-friendly incident notification

Strict tools validate with Pydantic (fail fast on bad data).
Natural-language tools produce human-readable prose.
Both share the same MCP session.

---

## How It Works

### Exposing an Agent as MCP Server

```python
from agent_framework import Agent, tool
from agent_framework.azure import AzureOpenAIChatClient

# Create an agent with tools
agent = Agent(client=AzureOpenAIChatClient(...), tools=[...])

# Convert to MCP server (low-level Server from mcp SDK)
server = agent.as_mcp_server(server_name="ExpertAdvisor")

# Serve over HTTP using FastMCP's streamable HTTP transport
from mcp.server.fastmcp import FastMCP
mcp_app = FastMCP("ExpertAdvisor", stateless_http=True, json_response=True)
# ... register agent tool ...
mcp_app.run(transport="streamable-http", port=8002)
```

### Consuming MCP Service from Another Agent

```python
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIChatClient

async with MCPStreamableHTTPTool(
    name="expert_advisor",
    url="http://localhost:8002/mcp",
) as mcp_tool:
    async with Agent(
        client=AzureOpenAIChatClient(...),
        tools=mcp_tool,
    ) as agent:
        result = await agent.run("Analyze this business scenario...")
```

### Workflow with Local + Remote Agents

```python
from agent_framework.orchestrations import SequentialBuilder

# Local agent (in-process)
researcher = client.as_agent(name="researcher", instructions="...")

# Remote agent wrapper (via MCP tool)
remote_expert = Agent(client=client, tools=mcp_tool, name="expert")

# Sequential workflow: researcher → expert
workflow = SequentialBuilder(participants=[researcher, remote_expert]).build()
result = await workflow.run("Analyze the market for electric bikes")
```

### Stateful Agent-as-MCP Server (Multi-Turn)

The stateful server uses [FastMCP v3](https://github.com/PrefectHQ/fastmcp)
instead of `mcp.server.fastmcp.FastMCP` from the base MCP SDK. Two things
make multi-turn work:

1. **Server side:** Each MCP `session_id` maps to an `AgentSession`.
   Passing the same session to `agent.run()` lets the framework's
   `InMemoryHistoryProvider` accumulate messages automatically.

2. **Client side:** `MCPStreamableHTTPTool` sends the `mcp-session-id`
   header on every request after initialization — no extra code needed.

```python
# Server — stateful MCP with session-scoped agent history
from fastmcp import FastMCP                      # PrefectHQ fastmcp v3
from fastmcp.server.context import Context
from agent_framework import Agent
from agent_framework._sessions import AgentSession

agent_sessions: dict[str, AgentSession] = {}
mcp_server = FastMCP("StatefulExpert")

@mcp_server.tool
async def chat_with_expert(message: str, ctx: Context) -> str:
    session_id = ctx.session_id
    if session_id not in agent_sessions:
        agent_sessions[session_id] = AgentSession()
    session = agent_sessions[session_id]

    async with agent:
        response = await agent.run(message, session=session)
    return response.text

mcp_server.run(transport="streamable-http", host="0.0.0.0", port=8002)
```

```python
# Client — multi-turn conversation (session auto-managed)
from agent_framework import Agent, MCPStreamableHTTPTool

async with MCPStreamableHTTPTool(
    name="expert", url="http://localhost:8002/mcp"
) as mcp_tool:
    async with Agent(client=client, tools=mcp_tool) as coordinator:
        r1 = await coordinator.run("What are the risks?")      # Turn 1
        r2 = await coordinator.run("Show me market data.")      # Turn 2
        r3 = await coordinator.run("Summarize everything.")     # Turn 3
        # The expert remembers all prior turns ✓
```

### Typed-Contract Workflow (Structured Data Exchange)

The typed-contract demo shows how `response_format` with Pydantic models
creates strict data boundaries between agents — no natural language needed
at the inter-agent boundary:

```python
from pydantic import BaseModel, Field
from agent_framework import Agent, AgentResponse

# Define the CONTRACT between Agent 1 and Agent 2
class ThreatAssessment(BaseModel):
    threat_score: float = Field(ge=0, le=100)
    attack_vector: AttackVector       # MITRE ATT&CK enum
    mitre_techniques: list[str]       # e.g. ["T1566.001", "T1059.001"]
    confidence_pct: float = Field(ge=0, le=100)

# Agent 1 produces typed output
response: AgentResponse = await threat_intel_agent.run(
    f"Analyze this alert:\n{alert.model_dump_json()}",
    options={"response_format": ThreatAssessment},  # ← enforced schema
)
threat = cast(ThreatAssessment, response.value)  # ← validated Python object

# Agent 2 consumes typed input (not prose!)
impact_response = await impact_agent.run(
    f"Assess blast radius:\n{threat.model_dump_json()}",
    options={"response_format": ImpactAnalysis},
)
```

**Why this matters vs. A2A / natural-language passing:**

| Aspect | Natural Language (A2A) | Typed Contracts (this demo) |
|--------|----------------------|-----------------------------|
| Data format | Prose: "threat seems critical" | `threat.threat_score = 85.0` (float, 0-100) |
| Validation | None — hope the LLM got it right | Pydantic validates at runtime |
| Downstream action | LLM must re-interpret prose | Direct attribute → API call |
| Failure mode | Silent corruption → wrong playbook | `ValidationError` — fail fast |
| SLA tracking | "Pretty urgent" → which timer? | `severity=CRITICAL` → 15-min SLA |

## Dependencies

| Package | Purpose |
|---------|---------|
| `agent-framework-core` | Agent, MCPStreamableHTTPTool, tool decorator |
| `agent-framework-orchestrations` | SequentialBuilder for workflows |
| `mcp` | MCP SDK (used by stateless server via `mcp.server.fastmcp.FastMCP`) |
| `fastmcp` | PrefectHQ FastMCP v3 (used by stateful server — session state support) |
| `pydantic` | Typed contracts / schema validation (transitive via agent-framework-core) |
| `python-dotenv` | Load credentials from `mcp/.env` |
