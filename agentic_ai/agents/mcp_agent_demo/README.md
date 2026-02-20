# MCP Agent Demo — Agent Framework

This demo shows nine capabilities of the Microsoft Agent Framework:

| # | What | Script |
|---|------|--------|
| 1 | **Expose an agent as an MCP server** (stateless HTTP) | `mcp_server.py` |
| 2 | **Consume the agent-powered MCP service** from another agent | `mcp_client_agent.py` |
| 3 | **Proxy agent workflow** — local agent + remote MCP agent | `workflow_proxy_agent.py` |
| 4 | **Stateful agent-as-MCP server** (multi-turn sessions) | `mcp_server_stateful.py` |
| 5 | **Stateful multi-turn client agent** conversation via MCP | `mcp_client_stateful.py` |
| 6 | **Hybrid MCP server** — strict-schema + natural-language tools in one endpoint | `mcp_server_hybrid.py` |
| 7 | **Hybrid client** — demonstrates both tool types in a single incident flow | `mcp_client_hybrid.py` |
| 8 | **LangGraph agent as MCP server** — cross-framework interop | `mcp_server_langgraph.py` |
| 9 | **Group Chat orchestration** — local + LangGraph agent + LLM planner | `workflow_group_chat.py` |

## Architecture

### Stateless Mode (Scripts 1–3)

Scripts 1 & 2 expose / consume an agent via MCP. Script 3 adds a
SequentialBuilder workflow that chains a local agent with the remote
MCP agent via `MCPProxyAgent`.

```
SequentialBuilder Workflow
┌──────────────────┐  text output   ┌──────────────────┐  call_tool()   ┌───────────────────────┐
│  Researcher      │ ──────────────▶│  MCPProxyAgent   │ ─────────────▶│  MCP Server (8002)    │
│  (LLM agent)     │                │  (BaseAgent)     │  HTTP          │  ExpertAdvisor Agent  │
└──────────────────┘                └──────────────────┘               └───────────────────────┘
```

**Note:** `MCPProxyAgent.run()` must be a regular `def` (not `async def`) —
`SequentialBuilder` iterates with `async for`, which needs an async iterable.

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

### Hybrid Mode (Scripts 6–7)

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

### Cross-Framework Group Chat (Scripts 8–9)

Scripts 8 & 9 demonstrate **cross-framework interoperability**: a LangGraph
agent is exposed via MCP and participates in a MAF GroupChat alongside a
native MAF agent, orchestrated by an LLM-based planner.

```
GroupChatBuilder
┌───────────────────────────────────────────────────────────────────────────────┐
│                         🎯 Planner (Orchestrator)                            │
│                    LLM agent that decides who speaks next                     │
│               returns: {next_speaker, terminate, reason}                     │
└──────────────────┬──────────────────────────────┬────────────────────────────┘
                   │                              │
                   ▼                              ▼
┌──────────────────────────────┐  ┌────────────────────────────────────────────┐
│  👔 BusinessStrategist       │  │  🏗️  TechnicalArchitect (MCPProxyAgent)    │
│  Local MAF Agent             │  │  ┌──────────────────────────────────────┐  │
│  (Azure OpenAI)              │  │  │ call_tool("ask_architect", ...)      │  │
│                              │  │  │         ↓ MCP HTTP (port 8003)       │  │
│  • Business impact & ROI     │  │  │ ┌──────────────────────────────────┐ │  │
│  • Risk mitigation           │  │  │ │ LangGraph ReAct Agent           │ │  │
│  • Go-to-market strategy     │  │  │ │ • evaluate_architecture_pattern │ │  │
│  • Customer experience       │  │  │ │ • estimate_migration_effort     │ │  │
│                              │  │  │ │ • recommend_tech_stack          │ │  │
└──────────────────────────────┘  │  │ └──────────────────────────────────┘ │  │
                                  │  └──────────────────────────────────────┘  │
                                  └────────────────────────────────────────────┘
```

**Key insight:** MCP is the universal connector. MAF's GroupChatBuilder
doesn't know (or care) that one participant is LangGraph behind the scenes.
This pattern works with any framework that can expose tools via MCP.

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

### 3. Run the Proxy Agent Workflow (in a second terminal)

```bash
cd agentic_ai/agents/mcp_agent_demo
uv run python workflow_proxy_agent.py
```

This runs a **SequentialBuilder** workflow that chains a local Researcher
agent with the remote Expert Advisor via `MCPProxyAgent`:
1. **Researcher** → drafts initial analysis
2. **MCPProxyAgent** → forwards output to `ask_expert` via `call_tool()`

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

---

### 6. Start the Hybrid MCP Server

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

### 7. Run the Hybrid Client (in a second terminal)

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

### 8. Start the LangGraph MCP Server

```bash
cd agentic_ai/agents/mcp_agent_demo
uv run python mcp_server_langgraph.py
```

This starts a **LangGraph-based** Technical Architect agent as an MCP server
on `http://localhost:8003/mcp`. The agent uses a ReAct loop with
architecture-related tools:

| Tool | Purpose |
|------|---------|
| `evaluate_architecture_pattern` | Evaluate microservices, monolith, serverless, event-driven patterns |
| `estimate_migration_effort` | Estimate timeline, cost, and team size for a migration |
| `recommend_tech_stack` | Recommend technologies for a given domain and scale |

**Cross-framework interop:** The agent is built entirely with LangGraph
but served via MCP — any MCP client can consume it regardless of framework.

### 9. Run the Group Chat Orchestration (in a second terminal)

```bash
cd agentic_ai/agents/mcp_agent_demo
uv run python workflow_group_chat.py
```

This runs a multi-agent **GroupChat** discussion using MAF's
`GroupChatBuilder` with an LLM-based planner. Three roles participate:

1. **🎯 Planner** (orchestrator) — decides who speaks next
2. **👔 BusinessStrategist** (local MAF agent) — business impact, ROI, risk
3. **🏗️ TechnicalArchitect** (LangGraph via MCP) — architecture, tech stack

Each turn shows which agent was selected and their response. The planner
alternates between participants to build a comprehensive strategy.

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

### Integrating a Remote MCP Agent into a Workflow

```python
from agent_framework import BaseAgent, MCPStreamableHTTPTool, Message
from agent_framework.orchestrations import SequentialBuilder

class MCPProxyAgent(BaseAgent):
    """Forwards messages to a remote MCP tool via call_tool()."""
    def __init__(self, *, mcp_tool, tool_name, param_name="question", **kw):
        super().__init__(**kw)
        self._mcp_tool, self._tool_name, self._param_name = mcp_tool, tool_name, param_name

    def run(self, messages=None, *, stream=False, **kw):  # must be regular def
        return self._stream(messages) if stream else self._impl(messages)

    async def _impl(self, messages):
        result = await self._mcp_tool.call_tool(self._tool_name, **{self._param_name: text})
        ...

researcher = client.as_agent(name="researcher", instructions="...")
proxy = MCPProxyAgent(mcp_tool=mcp_tool, tool_name="ask_expert", name="proxy")

workflow = SequentialBuilder(participants=[researcher, proxy]).build()
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

## Dependencies

| Package | Purpose |
|---------|---------|
| `agent-framework-core` | Agent, MCPStreamableHTTPTool, tool decorator |
| `agent-framework-orchestrations` | SequentialBuilder, GroupChatBuilder for workflows |
| `mcp` | MCP SDK (used by stateless server via `mcp.server.fastmcp.FastMCP`) |
| `fastmcp` | PrefectHQ FastMCP v3 (used by stateful server — session state support) |
| `langgraph` | LangGraph — stateful agent graphs (used by Script 8) |
| `langchain-openai` | Azure OpenAI integration for LangGraph agents |
| `langchain-core` | LangChain core abstractions (messages, tools) |
| `python-dotenv` | Load credentials from `mcp/.env` |
