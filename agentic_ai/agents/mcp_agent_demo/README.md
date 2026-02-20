# MCP as the Universal Agent Interop Layer

## The Thesis

> Every major AI framework speaks MCP today.  Instead of introducing
> another protocol for agent-to-agent communication, have teams expose
> their agentic capabilities as MCP tool servers.  Behind each tool?
> Whatever they want — multi-agent workflows, RAG pipelines, LLM
> reasoning chains, or agents built with entirely different frameworks.
> The caller doesn't know or care.

This demo series progressively proves that MCP can serve as the **universal
interop layer** between AI agents — even across frameworks, even when the
agents aren't local, even when conversations span multiple turns.

## Why MCP, Not A2A?

I keep hearing from customers: *"We need A2A for our agents to talk across
teams and frameworks."*

But do you?

The latest MCP spec now covers virtually everything A2A does:

| Capability | MCP | A2A |
|---|---|---|
| Stateful sessions | ✅ `Mcp-Session-Id` | ✅ |
| Streaming | ✅ SSE | ✅ SSE |
| Long-running tasks (polling, cancellation, TTL) | ✅ *(this was A2A's last edge, now closed)* | ✅ |
| Mid-task user input (elicitation) | ✅ | ❌ |
| OAuth 2.1 + OIDC auth | ✅ | ✅ |
| Structured input/output schemas | ✅ | ✅ |
| Ecosystem adoption | 🟢 Every major LLM platform | 🟡 Growing |

Here's the thing people miss: when an agent calls another agent via A2A,
**the LLM still sees it as a tool call**.  A2A just wraps it in "agent
identity" semantics.  MCP keeps it as what it actually is — a tool with
typed I/O.  Less abstraction, less complexity, same result.

### Where MCP wins

- **Massive ecosystem** — every major LLM platform speaks MCP today
- **Typed contracts between teams** — no "interpret my natural language"
  ambiguity
- **Simpler mental model** — teams expose tools, done

### Where A2A still makes sense

- Cross-organizational federation with unknown third parties
- When you truly can't define schemas upfront

For most enterprise scenarios I've seen?  **MCP is the answer.**
Save A2A for when you actually need it.

## What This Demo Proves

This demo builds the case progressively — each pair of scripts adds one
capability, culminating in a cross-framework multi-agent orchestration
where the MCP boundary is invisible.

### Layer 1: Agent-as-a-Service (Scripts 1–2)

> **Thesis:** Any agent can be exposed as an MCP tool server.  Any other
> agent can consume it.  The caller doesn't know what's behind the tool.

| Script | Role | What it does |
|---|---|---|
| `mcp_server.py` | Server | Wraps a MAF Agent with domain tools (risk analysis, market data, summarization) as an MCP Streamable-HTTP endpoint on port 8002 |
| `mcp_client_agent.py` | Client | A "Coordinator" agent connects to the MCP server and delegates business analysis — it sees the remote agent as just another tool |

**Key takeaway:** The client agent has no idea what framework, model, or
infrastructure powers the remote tool.  It just calls `ask_expert()` and
gets a typed response.  This is the foundation of the entire pattern.

### Layer 2: Stateful Sessions (Scripts 3–4)

> **Thesis:** MCP sessions (`Mcp-Session-Id`) enable multi-turn
> conversations with remote agents.  The server remembers context across
> calls — no client-side history management needed.

| Script | Role | What it does |
|---|---|---|
| `mcp_server_stateful.py` | Server | Each MCP session gets its own `AgentSession` with `InMemoryHistoryProvider` — the agent remembers the full conversation history |
| `mcp_client_stateful.py` | Client | Runs a 3-turn conversation where each follow-up builds on the prior: risks → market data → executive summary |

**Key takeaway:** Session statefulness is a protocol-level feature.
`MCPStreamableHTTPTool` sends the `mcp-session-id` header automatically.
The client doesn't manage history — the server does.  This is exactly
what you need for remote agent conversations.

### Layer 3: Strict + Natural Language Tools (Scripts 5–6)

> **Thesis:** Real enterprise platforms need both machine-consumable
> (strict-schema) and human-consumable (natural-language) tools.  MCP
> supports both in the same endpoint, sharing session state.

| Script | Role | What it does |
|---|---|---|
| `mcp_server_hybrid.py` | Server | Exposes strict-schema tools (`triage_alert` → Pydantic `SecurityAlert`, `assess_threat` → `ThreatAssessment`, `create_response` → `IncidentResponse`) alongside NL tools (`ask_security_advisor`, `explain_for_customer`) — all sharing session state |
| `mcp_client_hybrid.py` | Client | Runs a full SOC incident flow: strict pipeline (triage → assess → respond) then NL advisor & customer notification |

**Key takeaway:** Strict-schema tools drive automation (wrong data =
wrong remediation = customer breach).  NL tools help humans understand
and communicate.  Both coexist in one MCP service, sharing the same
session state.  This is how real MSP platforms work.

### Layer 4: Cross-Framework Interop (Scripts 7–8)

> **Thesis:** MCP is framework-agnostic.  A LangGraph agent behind MCP
> is indistinguishable from a MAF agent behind MCP.  The orchestrator
> doesn't know or care — it just calls tools.

| Script | Role | What it does |
|---|---|---|
| `mcp_server_langgraph.py` | Server | A **LangGraph** ReAct agent (Technical Architect) with architecture tools, exposed via MCP on port 8003.  Uses `MemorySaver` for stateful conversations — MCP `session_id` maps to LangGraph `thread_id` |
| `workflow_group_chat.py` | Orchestrator | MAF `GroupChatBuilder` orchestrates a multi-agent discussion with **4 agents**: 👔 BusinessStrategist (local MAF), 🏗️ TechnicalArchitect (LangGraph via MCP), 📋 Planner (local MAF), 🎯 Facilitator (LLM orchestrator).  Runs a multi-turn conversation — the LangGraph agent remembers prior turns via MemorySaver |

**Key takeaway:** This is the capstone.  Three different execution
models (local MAF agent, remote LangGraph agent via MCP, LLM orchestrator)
participate in the same conversation.  The `MCPProxyAgent` sends only
the latest message — the LangGraph server keeps full history via
`MemorySaver`.  MAF's `GroupChatBuilder` treats all participants
identically.  **MCP made the framework boundary invisible.**

## Architecture

### The Pattern: Teams Expose Capabilities as MCP Tool Servers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATING AGENT                              │
│                    (MAF, LangChain, AutoGen, ...)                        │
│                                                                         │
│   "I need business analysis"     "I need architecture design"           │
│         ↓ call_tool()                  ↓ call_tool()                    │
└─────────┬───────────────────────────────┬───────────────────────────────┘
          │          MCP Protocol         │
          │      (Streamable HTTP)        │
          ▼                               ▼
┌──────────────────────┐    ┌──────────────────────────────────┐
│   MCP Server A       │    │   MCP Server B                   │
│   (Team Alpha)       │    │   (Team Beta)                    │
│                      │    │                                  │
│   Behind the tool:   │    │   Behind the tool:               │
│   • MAF Agent        │    │   • LangGraph ReAct Agent        │
│   • Azure OpenAI     │    │   • MemorySaver checkpointer     │
│   • Domain tools     │    │   • Architecture tools           │
│                      │    │                                  │
│   The caller has     │    │   The caller has                 │
│   no idea.           │    │   no idea.                       │
└──────────────────────┘    └──────────────────────────────────┘
```

### Cross-Framework Group Chat (Scripts 7–8)

```
                              GroupChatBuilder
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                          🎯 Facilitator                                     │
│                     LLM orchestrator — decides who speaks next              │
│                     Terminates after Planner delivers the plan              │
│                                                                             │
│         ┌──────────────────┬──────────────────┬──────────────────┐          │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  │          │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐         │          │
│  │ 👔 Business  │  │ 🏗️  Technical │  │ 📋 Planner   │         │          │
│  │  Strategist  │  │  Architect    │  │              │         │          │
│  │              │  │              │  │ Synthesizes  │         │          │
│  │ Local MAF    │  │ MCPProxyAgent │  │ discussion   │         │          │
│  │ Agent        │  │      │        │  │ into plan    │         │          │
│  │              │  │      │ MCP    │  │              │         │          │
│  │ Business     │  │      ▼        │  │ Local MAF    │         │          │
│  │ impact,      │  │ ┌──────────┐ │  │ Agent        │         │          │
│  │ ROI, risk    │  │ │LangGraph │ │  │              │         │          │
│  │              │  │ │ReAct     │ │  │              │         │          │
│  │              │  │ │Agent     │ │  │              │         │          │
│  │              │  │ │(port     │ │  │              │         │          │
│  │              │  │ │ 8003)    │ │  │              │         │          │
│  │              │  │ └──────────┘ │  │              │         │          │
│  └──────────────┘  └───────────────┘  └──────────────┘         │          │
│                                                                             │
│  Flow: User question → BusinessStrategist → TechnicalArchitect             │
│        → (iterate if needed) → Planner delivers plan → Terminate           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stateful Session Flow

```
  Client                         MCP Server (Stateful)
    │                                  │
    │── call_tool("ask", Q1) ─────────▶│  session_id=abc123
    │◀── Response R1 ─────────────────│  store in AgentSession[abc123]
    │                                  │
    │── call_tool("ask", Q2) ─────────▶│  same session_id=abc123
    │◀── Response R2 (references R1) ─│  history: [Q1, R1, Q2]
    │                                  │
    │── call_tool("ask", Q3) ─────────▶│  same session_id=abc123
    │◀── Response R3 (full context) ──│  history: [Q1, R1, Q2, R2, Q3]
    │                                  │
```

**No client-side history management.** The `mcp-session-id` header ties
all requests to the same server-side session.  The client sends one
message at a time — the server remembers everything.

## The Key Insight

When Team Alpha exposes their agent as an MCP tool server, and Team Beta
calls it from their LangGraph pipeline, and Team Gamma calls it from
their AutoGen workflow — **nobody changed any code**.  The MCP protocol
handles:

- **Discovery** — what tools are available, what schemas they expect
- **Invocation** — typed input → typed output, no ambiguity
- **State** — session IDs for multi-turn conversations
- **Streaming** — SSE for real-time updates

This is what A2A promises.  MCP already delivers it.

## Quick Start

### Prerequisites

- Python 3.12+, `uv`
- Azure OpenAI credentials in `mcp/.env`

### Running the demos

Each layer builds on the previous.  Start with Layer 1 and work up.

```bash
cd agentic_ai/agents/mcp_agent_demo
uv sync
```

#### Layer 1: Basic Agent-as-MCP-Service

```bash
# Terminal 1 — start the server
uv run python mcp_server.py             # port 8002

# Terminal 2 — run the client
uv run python mcp_client_agent.py
```

#### Layer 2: Stateful Multi-Turn Sessions

```bash
# Terminal 1 — start the stateful server (stop Layer 1 first — same port)
uv run python mcp_server_stateful.py    # port 8002

# Terminal 2 — run the stateful client
uv run python mcp_client_stateful.py
```

#### Layer 3: Hybrid Strict + NL Tools

```bash
# Terminal 1 — start the hybrid server (stop Layers 1–2 first — same port)
uv run python mcp_server_hybrid.py      # port 8002

# Terminal 2 — run the hybrid client
uv run python mcp_client_hybrid.py
```

#### Layer 4: Cross-Framework Group Chat

```bash
# Terminal 1 — start the LangGraph MCP server
uv run python mcp_server_langgraph.py   # port 8003

# Terminal 2 — run the group chat orchestration
uv run python workflow_group_chat.py
```

> **Note:** Layers 1–3 share port 8002 — only run one at a time.
> Layer 4 uses port 8003 and can run alongside any of the others.

## Technologies Used

| Package | Purpose |
|---------|---------|
| `agent-framework-core` | Microsoft Agent Framework — agents, tools, MCP client |
| `agent-framework-orchestrations` | GroupChatBuilder for multi-agent workflows |
| `fastmcp` | PrefectHQ FastMCP v3 — stateful MCP server with session support |
| `langgraph` | LangGraph — stateful agent graphs with MemorySaver |
| `langchain-openai` | Azure OpenAI integration for LangGraph agents |
| `python-dotenv` | Load credentials from `mcp/.env` |

## File Inventory

```
mcp_agent_demo/
├── mcp_server.py              # Layer 1: Basic MAF agent as MCP server
├── mcp_client_agent.py        # Layer 1: Client that consumes the MCP service
├── mcp_server_stateful.py     # Layer 2: Stateful MCP server (session memory)
├── mcp_client_stateful.py     # Layer 2: Multi-turn conversation client
├── mcp_server_hybrid.py       # Layer 3: Strict-schema + NL tools in one endpoint
├── mcp_client_hybrid.py       # Layer 3: SOC incident flow using both tool types
├── mcp_server_langgraph.py    # Layer 4: LangGraph agent as MCP server (port 8003)
├── workflow_group_chat.py     # Layer 4: GroupChat — MAF + LangGraph via MCP
├── pyproject.toml             # Dependencies
└── README.md                  # This file
```
