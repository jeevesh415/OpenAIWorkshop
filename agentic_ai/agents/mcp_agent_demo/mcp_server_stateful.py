"""
Stateful Agent-as-MCP Server — multi-turn conversations with session memory.

This script exposes an agent-framework Agent as a stateful MCP HTTP server
using PrefectHQ's FastMCP v3.  Each MCP client session gets its own
AgentSession, so conversation history is preserved across tool calls.

The server exposes three MCP tools:
  • chat_with_expert  — send a message; the expert remembers prior turns
  • get_session_info  — inspect turn count / session metadata
  • reset_conversation — clear history for the current session

Architecture:
  ┌────────────────────────────────────────────┐
  │  FastMCP  (stateful, streamable-http)      │
  │                                            │
  │  MCP session_id → AgentSession (history)   │
  │                    ↓                       │
  │  Agent("ExpertAdvisor") + domain tools     │
  │    • analyze_risk                          │
  │    • get_market_data                       │
  │    • summarize_findings                    │
  └────────────────────────────────────────────┘

Usage:
    cd agentic_ai/agents/mcp_agent_demo
    uv run python mcp_server_stateful.py
"""

import os
import sys
from typing import Annotated

from dotenv import load_dotenv

# ── Load credentials ────────────────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp", ".env")
load_dotenv(env_path)

from agent_framework import Agent, tool
from agent_framework._sessions import AgentSession
from agent_framework.azure import AzureOpenAIChatClient
from fastmcp import FastMCP
from fastmcp.server.context import Context

# ── Domain tools the agent can use ──────────────────────────────────────────


@tool(approval_mode="never_require")
def analyze_risk(
    scenario: Annotated[str, "A brief description of the business scenario to assess"],
) -> Annotated[str, "A risk analysis summary"]:
    """Analyze business risk for a given scenario and return a structured assessment."""
    return (
        f"Risk Analysis for: {scenario}\n"
        "─────────────────────────────\n"
        "• Market Risk: MEDIUM — competitive landscape is evolving\n"
        "• Financial Risk: LOW — strong cash position\n"
        "• Operational Risk: MEDIUM — supply chain dependencies noted\n"
        "• Regulatory Risk: LOW — compliant with current frameworks\n"
        "• Overall Rating: MEDIUM\n"
        "• Recommendation: Proceed with standard due diligence."
    )


@tool(approval_mode="never_require")
def get_market_data(
    sector: Annotated[str, "Industry sector to look up, e.g. 'technology', 'healthcare'"],
) -> Annotated[str, "Market data summary for the sector"]:
    """Retrieve current market data for a given industry sector."""
    data = {
        "technology": "Tech sector: YTD +18%, P/E 28x, top movers: AI infrastructure, cloud security.",
        "healthcare": "Healthcare sector: YTD +8%, P/E 22x, top movers: GLP-1 drugs, digital health.",
        "energy": "Energy sector: YTD +5%, P/E 14x, top movers: renewables, grid storage.",
        "finance": "Finance sector: YTD +12%, P/E 16x, top movers: fintech, digital payments.",
    }
    return data.get(
        sector.lower(),
        f"No data available for sector '{sector}'. Known sectors: {', '.join(data.keys())}",
    )


@tool(approval_mode="never_require")
def summarize_findings(
    text: Annotated[str, "The text to summarize"],
    max_sentences: Annotated[int, "Maximum number of sentences in the summary"] = 3,
) -> Annotated[str, "A concise summary"]:
    """Produce a concise summary of the provided text."""
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    summary = ". ".join(sentences[:max_sentences]) + "."
    return f"Summary ({max_sentences} sentences max): {summary}"


# ── Build agent and server ──────────────────────────────────────────────────


def main() -> None:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")

    if not endpoint or not api_key:
        print("ERROR: Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in mcp/.env")
        sys.exit(1)

    print(f"🔧 Azure OpenAI endpoint : {endpoint}")
    print(f"🔧 Deployment            : {deployment}")

    # 1) Create the agent-framework Agent
    llm_client = AzureOpenAIChatClient(
        api_key=api_key,
        endpoint=endpoint,
        deployment_name=deployment,
        api_version=api_version,
    )

    agent = Agent(
        client=llm_client,
        name="ExpertAdvisor",
        description=(
            "An expert business advisor that can analyze risk, retrieve market data, "
            "and summarize findings. Remembers the full conversation history."
        ),
        instructions=(
            "You are an expert business strategy advisor. Use your tools to provide "
            "thorough, data-backed analysis. Always call analyze_risk for risk questions, "
            "get_market_data for sector insights, and summarize_findings to condense results.\n\n"
            "IMPORTANT: You are in a multi-turn conversation. Reference and build upon "
            "earlier turns. If the user asks you to summarize or follow up, recall "
            "what was discussed previously."
        ),
        tools=[analyze_risk, get_market_data, summarize_findings],
    )

    # 2) Session store: MCP session_id → AgentSession
    #    Each MCP client gets its own conversation thread.
    agent_sessions: dict[str, AgentSession] = {}
    # Track turn count per session (simple counter)
    session_turns: dict[str, int] = {}

    # 3) Create the FastMCP server (stateful by default — sessions persist)
    mcp_server = FastMCP("StatefulExpertAdvisor")

    # ── MCP tools ───────────────────────────────────────────────────────

    @mcp_server.tool
    async def chat_with_expert(
        message: Annotated[str, "Your message to the expert advisor"],
        ctx: Context,
    ) -> str:
        """Send a message to the Expert Advisor. The conversation history is
        maintained across calls within the same MCP session, enabling
        multi-turn follow-ups and context-aware responses."""
        session_id = ctx.session_id
        await ctx.info(f"Session {session_id[:8]}… — processing message")

        # Get-or-create AgentSession for this MCP session
        if session_id not in agent_sessions:
            agent_sessions[session_id] = AgentSession()
            session_turns[session_id] = 0
            await ctx.info("New conversation started")

        session_turns[session_id] += 1
        turn = session_turns[session_id]
        await ctx.info(f"Processing turn {turn}")

        session = agent_sessions[session_id]

        # Run the agent with session history
        async with agent:
            response = await agent.run(message, session=session)

        return response.text

    @mcp_server.tool
    async def get_session_info(ctx: Context) -> dict:
        """Get metadata about the current MCP session and conversation state."""
        session_id = ctx.session_id
        turn_count = session_turns.get(session_id, 0)
        return {
            "session_id": session_id,
            "turn_count": turn_count,
            "has_history": session_id in agent_sessions,
        }

    @mcp_server.tool
    async def reset_conversation(ctx: Context) -> str:
        """Clear the conversation history for the current MCP session."""
        session_id = ctx.session_id
        if session_id in agent_sessions:
            del agent_sessions[session_id]
            session_turns.pop(session_id, None)
            return f"Conversation history cleared for session {session_id[:8]}…"
        return "No conversation history to clear."

    # ── Launch ──────────────────────────────────────────────────────────

    print("──────────────────────────────────────────────────")
    print("🚀 Stateful MCP Agent Server")
    print("   URL:       http://localhost:8002/mcp")
    print("   Transport: Streamable HTTP (stateful sessions)")
    print("   Tools:     chat_with_expert, get_session_info, reset_conversation")
    print("──────────────────────────────────────────────────")

    mcp_server.run(transport="streamable-http", host="0.0.0.0", port=8002)


if __name__ == "__main__":
    main()
