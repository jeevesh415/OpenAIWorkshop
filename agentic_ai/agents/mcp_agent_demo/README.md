# MCP Agent Demo — Agent Framework

This demo shows five capabilities of the Microsoft Agent Framework:

| # | What | Script |
|---|------|--------|
| 1 | **Expose an agent as an MCP server** (stateless HTTP) | `mcp_server.py` |
| 2 | **Consume the agent-powered MCP service** from another agent | `mcp_client_agent.py` |
| 3 | **Workflow orchestrating local + remote (MCP) agents** | `workflow_local_remote.py` |
| 4 | **Stateful agent-as-MCP server** (multi-turn sessions) | `mcp_server_stateful.py` |
| 5 | **Stateful multi-turn client agent** conversation via MCP | `mcp_client_stateful.py` |

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

## Dependencies

| Package | Purpose |
|---------|---------|
| `agent-framework-core` | Agent, MCPStreamableHTTPTool, tool decorator |
| `agent-framework-orchestrations` | SequentialBuilder for workflows |
| `mcp` | MCP SDK (used by stateless server via `mcp.server.fastmcp.FastMCP`) |
| `fastmcp` | PrefectHQ FastMCP v3 (used by stateful server — session state support) |
| `python-dotenv` | Load credentials from `mcp/.env` |
