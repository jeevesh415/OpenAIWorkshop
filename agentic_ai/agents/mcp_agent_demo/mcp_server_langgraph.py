"""
Part 8 — Stateful LangGraph Agent as MCP Server (Cross-Framework Interop)

A LangGraph-based Technical Architect agent exposed as a **stateful**
MCP endpoint using PrefectHQ FastMCP v3.  Each MCP session gets its own
LangGraph conversation thread (via MemorySaver checkpointer), so the
agent remembers prior turns without the client resending history.

Cross-framework interoperability: the agent is built entirely with
LangGraph (ReAct loop + tools) but any MCP client can consume it —
MAF, AutoGen, CrewAI — regardless of framework.

Architecture:
  ┌──────────────────────────────────────────────────────┐
  │  FastMCP  (stateful, streamable-http, port 8003)     │
  │                                                      │
  │  MCP session_id  →  LangGraph thread_id              │
  │                      ↓                               │
  │  LangGraph ReAct Agent + MemorySaver (conversation)  │
  │    • evaluate_architecture_pattern                   │
  │    • estimate_migration_effort                       │
  │    • recommend_tech_stack                            │
  │                                                      │
  │  Tools:                                              │
  │    ask_architect       — multi-turn architecture Q&A │
  │    get_session_info    — session metadata             │
  │    reset_conversation  — clear history                │
  └──────────────────────────────────────────────────────┘

Prerequisites:
    uv sync  (installs langgraph, langchain-openai, langchain-core, fastmcp)

Usage:
    cd agentic_ai/agents/mcp_agent_demo
    uv run python mcp_server_langgraph.py
"""

import os
import sys
from typing import Annotated

from dotenv import load_dotenv

# Load credentials from the shared mcp/.env
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp", ".env")
load_dotenv(env_path)

from fastmcp import FastMCP
from fastmcp.server.context import Context
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool as lc_tool
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode


# ═══════════════════════════════════════════════════════════════════════════
#  LangGraph Tools — architecture domain
# ═══════════════════════════════════════════════════════════════════════════


@lc_tool
def evaluate_architecture_pattern(pattern: str) -> str:
    """Evaluate an architecture pattern and return pros, cons, and guidance.
    Supported patterns: microservices, monolith, serverless, event-driven."""
    patterns = {
        "microservices": (
            "Microservices Pattern Evaluation:\n"
            "✓ Independent deployment & scaling per service\n"
            "✓ Technology diversity — polyglot-friendly\n"
            "✓ Fault isolation — one service failure doesn't cascade\n"
            "✗ Distributed system complexity (network latency, partial failures)\n"
            "✗ Data consistency challenges (eventual consistency, saga pattern)\n"
            "✗ Operational overhead — requires mature DevOps practices\n"
            "• Best for: Large teams, complex domains, high scalability needs\n"
            "• Maturity required: HIGH — need CI/CD, observability, service mesh"
        ),
        "monolith": (
            "Monolith Pattern Evaluation:\n"
            "✓ Simple to develop, test, and deploy initially\n"
            "✓ Single codebase — easy to understand end-to-end\n"
            "✓ No inter-service communication overhead\n"
            "✗ Scaling requires scaling the entire application\n"
            "✗ Technology lock-in — one stack for everything\n"
            "✗ Deployment risk — small change requires full redeploy\n"
            "• Best for: Small teams, MVPs, low-complexity domains\n"
            "• Consider: Modular monolith as a stepping stone"
        ),
        "serverless": (
            "Serverless Pattern Evaluation:\n"
            "✓ Zero infrastructure management — cloud handles scaling\n"
            "✓ Pay-per-execution — cost-efficient for variable workloads\n"
            "✓ Rapid development — focus on business logic only\n"
            "✗ Cold start latency — first invocation can be slow\n"
            "✗ Vendor lock-in — tied to cloud provider's runtime\n"
            "✗ Debugging complexity — distributed tracing is essential\n"
            "• Best for: Event-driven workloads, APIs, batch processing\n"
            "• Watch out: Long-running tasks may exceed time limits"
        ),
        "event-driven": (
            "Event-Driven Pattern Evaluation:\n"
            "✓ Loose coupling — producers and consumers are independent\n"
            "✓ Natural fit for async workflows and real-time processing\n"
            "✓ Excellent scalability — consumers scale independently\n"
            "✗ Event ordering and exactly-once delivery are hard\n"
            "✗ Debugging event chains requires correlation IDs\n"
            "✗ Schema evolution needs careful versioning\n"
            "• Best for: Real-time analytics, IoT, workflow orchestration\n"
            "• Key tech: Kafka, Event Hubs, EventGrid, Pub/Sub"
        ),
    }
    key = pattern.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    for k, v in patterns.items():
        if k in key or key in k:
            return v
    return (
        f"Pattern '{pattern}' not in evaluation database.\n"
        f"Available patterns: {', '.join(patterns.keys())}.\n"
        "Provide a general assessment based on the pattern name."
    )


@lc_tool
def estimate_migration_effort(source: str, target: str, components: int) -> str:
    """Estimate migration effort from source to target architecture.
    source/target: e.g. 'monolith', 'microservices', 'serverless'.
    components: number of major components/modules to migrate."""
    complexity_map = {
        ("monolith", "microservices"): ("HIGH", 18, 45),
        ("monolith", "serverless"): ("MEDIUM-HIGH", 12, 35),
        ("monolith", "event-driven"): ("MEDIUM", 10, 30),
        ("microservices", "serverless"): ("LOW-MEDIUM", 6, 15),
    }
    key = (source.strip().lower(), target.strip().lower())
    complexity, base_weeks, base_cost_k = complexity_map.get(key, ("MEDIUM", 8, 25))
    weeks = base_weeks + (components * 2)
    cost_k = base_cost_k + (components * 8)
    return (
        f"Migration Effort Estimate: {source} → {target}\n"
        f"─────────────────────────────────────────\n"
        f"• Components to migrate: {components}\n"
        f"• Complexity: {complexity}\n"
        f"• Estimated timeline: {weeks} weeks\n"
        f"• Estimated cost: ${cost_k}K–${int(cost_k * 1.4)}K\n"
        f"• Recommended team size: {max(3, components // 2)} engineers\n"
        f"• Phases: Discovery (2w) → Pilot (4w) → Migration ({weeks - 8}w) → Validation (2w)\n"
        f"• Risk factors: Data migration, API compatibility, testing coverage"
    )


@lc_tool
def recommend_tech_stack(domain: str, scale: str) -> str:
    """Recommend a technology stack for a given domain and scale.
    domain: e.g. 'e-commerce', 'fintech', 'healthcare', 'saas'.
    scale: 'small', 'medium', 'large', 'enterprise'."""
    stacks = {
        "e-commerce": {
            "frontend": "Next.js + React + Tailwind CSS",
            "backend": "Node.js / Python FastAPI (microservices)",
            "database": "PostgreSQL (catalog) + Redis (sessions/cache) + Elasticsearch (search)",
            "cloud": "Azure AKS or AWS EKS (Kubernetes)",
            "ai_ml": "Azure OpenAI (personalization) + Azure ML (recommendations)",
            "messaging": "Azure Service Bus / Kafka (order events)",
            "observability": "OpenTelemetry + Grafana + Azure Monitor",
        },
        "fintech": {
            "frontend": "React + TypeScript + Material UI",
            "backend": "Java Spring Boot / .NET (regulatory compliance)",
            "database": "PostgreSQL (ACID) + TimescaleDB (time-series)",
            "cloud": "Azure (compliance certifications) + Azure Confidential Computing",
            "ai_ml": "Azure OpenAI (fraud detection) + custom ML models",
            "messaging": "Kafka (event sourcing, audit trail)",
            "observability": "Datadog + Azure Monitor + custom audit logging",
        },
        "healthcare": {
            "frontend": "React + HIPAA-compliant hosting",
            "backend": "Python FastAPI / .NET (HL7 FHIR support)",
            "database": "Azure Health Data Services (FHIR) + PostgreSQL",
            "cloud": "Azure (HIPAA BAA) + Azure Confidential Ledger",
            "ai_ml": "Azure OpenAI (clinical notes) + Azure Health Bot",
            "messaging": "Azure Service Bus (secure messaging)",
            "observability": "Azure Monitor + HIPAA-compliant logging",
        },
    }
    stack = stacks.get(domain.strip().lower(), stacks["e-commerce"])
    scale_notes = {
        "small": "Start with managed services, minimize ops overhead",
        "medium": "Introduce Kubernetes, add CI/CD automation",
        "large": "Multi-region, auto-scaling, dedicated SRE team",
        "enterprise": "Global deployment, multi-cloud strategy, SOC2/ISO compliance",
    }
    note = scale_notes.get(scale.strip().lower(), scale_notes["medium"])
    lines = [
        f"Tech Stack Recommendation: {domain} ({scale} scale)",
        "─" * 50,
    ]
    for layer, tech in stack.items():
        lines.append(f"  {layer.replace('_', '/').title():20s} → {tech}")
    lines.append(f"\n  Scale guidance: {note}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  Build the LangGraph agent (ReAct loop with MemorySaver)
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = (
    "You are a Technical Architect with deep expertise in cloud-native systems, "
    "distributed architectures, and technology strategy. When asked a question:\n"
    "1. Use your tools to gather concrete data (patterns, estimates, tech stacks)\n"
    "2. Synthesize the tool outputs into a cohesive, actionable recommendation\n"
    "3. Be specific — cite numbers, timelines, and trade-offs\n"
    "4. You are in a multi-turn conversation. Build on prior context rather than "
    "starting fresh — reference earlier discussion points.\n"
    "Keep responses concise and structured."
)

tools = [evaluate_architecture_pattern, estimate_migration_effort, recommend_tech_stack]

# MemorySaver keeps conversation history per thread_id in memory.
# Each MCP session maps to a unique LangGraph thread.
checkpointer = MemorySaver()


def _build_model() -> AzureChatOpenAI:
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview"),
    )


def _build_graph():
    """Build a LangGraph ReAct agent with architecture tools and checkpointer."""
    llm = _build_model()
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: MessagesState):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: MessagesState):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    # Compile WITH checkpointer — state persisted per thread_id
    return graph.compile(checkpointer=checkpointer)


# Compile the graph at module level
langgraph_agent = _build_graph()

# Track turn count per session
session_turns: dict[str, int] = {}


# ═══════════════════════════════════════════════════════════════════════════
#  Expose via stateful MCP (port 8003, PrefectHQ FastMCP)
# ═══════════════════════════════════════════════════════════════════════════

mcp_server = FastMCP("TechnicalArchitect")


@mcp_server.tool
async def ask_architect(
    question: Annotated[str, "Architecture question or follow-up message"],
    ctx: Context,
) -> str:
    """Ask the Technical Architect for architecture advice. The conversation
    is maintained across calls within the same MCP session — just send the
    new message, no need to resend history."""
    session_id = ctx.session_id
    await ctx.info(f"Session {session_id[:8]}… — processing message")

    if session_id not in session_turns:
        session_turns[session_id] = 0
        await ctx.info("New conversation thread started")

    session_turns[session_id] += 1
    turn = session_turns[session_id]
    await ctx.info(f"Processing turn {turn}")

    # Use the MCP session_id as the LangGraph thread_id.
    # The MemorySaver checkpointer accumulates messages per thread,
    # so the agent sees full conversation history automatically.
    config = {"configurable": {"thread_id": session_id}}
    result = await langgraph_agent.ainvoke(
        {"messages": [HumanMessage(content=question)]},
        config=config,
    )
    # Extract the last AI message (skip tool-call messages)
    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", None)
        if content and not getattr(msg, "tool_calls", None):
            return content if isinstance(content, str) else str(content)
    return "No response generated."


@mcp_server.tool
async def get_session_info(ctx: Context) -> dict:
    """Get metadata about the current conversation session."""
    session_id = ctx.session_id
    turn_count = session_turns.get(session_id, 0)
    return {
        "session_id": session_id,
        "turn_count": turn_count,
        "has_history": turn_count > 0,
    }


@mcp_server.tool
async def reset_conversation(ctx: Context) -> str:
    """Clear the conversation history for the current session."""
    session_id = ctx.session_id
    if session_id in session_turns:
        del session_turns[session_id]
        return f"Conversation cleared for session {session_id[:8]}…"
    return "No conversation history to clear."


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("🏗️  LangGraph Technical Architect — Stateful MCP Server (port 8003)")
    print("=" * 70)
    print("   Endpoint:  http://localhost:8003/mcp")
    print("   Transport: Streamable HTTP (stateful sessions)")
    print("   Tools:     ask_architect, get_session_info, reset_conversation")
    print("   Framework: LangGraph (cross-framework interop via MCP)")
    print()
    print("   Architecture tools available to the agent:")
    print("     • evaluate_architecture_pattern")
    print("     • estimate_migration_effort")
    print("     • recommend_tech_stack")
    print()
    print("   Session memory: MCP session_id → LangGraph thread_id")
    print("     → conversation history maintained server-side")
    print("     → clients send only the new message each turn")
    print("=" * 70)
    mcp_server.run(transport="streamable-http", host="0.0.0.0", port=8003)
