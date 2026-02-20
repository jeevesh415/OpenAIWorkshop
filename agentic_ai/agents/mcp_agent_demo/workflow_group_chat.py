"""
Part 9 — Group Chat: Local Agent + LangGraph Agent + LLM Planner

Demonstrates MAF's GroupChatBuilder orchestrating a multi-agent
discussion between:

  👔 BusinessStrategist  — local MAF agent (Azure OpenAI)
  🏗️  TechnicalArchitect  — LangGraph agent served via MCP (port 8003)
  🎯 Planner             — LLM orchestrator that decides who speaks next

The Planner examines the conversation after each turn and routes to
the participant whose expertise is most relevant.  Each turn is printed
so you can follow the flow of the discussion.

This is a cross-framework orchestration:
  • The BusinessStrategist is a native MAF Agent
  • The TechnicalArchitect is a LangGraph ReAct agent exposed via MCP
  • MAF's GroupChatBuilder treats both identically — it doesn't know
    (or care) that one participant is running LangGraph behind the scenes

Prerequisites:
    mcp_server_langgraph.py must be running on http://localhost:8003/mcp

Usage:
    cd agentic_ai/agents/mcp_agent_demo
    uv run python workflow_group_chat.py
"""

import asyncio
import os
import sys
import uuid
from typing import Any, cast

from dotenv import load_dotenv

# Load credentials from the shared mcp/.env
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp", ".env")
load_dotenv(env_path)

from agent_framework import (
    AgentResponse,
    AgentResponseUpdate,
    BaseAgent,
    Content,
    MCPStreamableHTTPTool,
    Message,
)
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework.orchestrations import GroupChatBuilder


# ═══════════════════════════════════════════════════════════════════════════
#  MCPProxyAgent — BaseAgent that bridges to a remote MCP tool
# ═══════════════════════════════════════════════════════════════════════════


class MCPProxyAgent(BaseAgent):
    """BaseAgent that forwards conversation context to a remote MCP tool.

    Unlike a normal Agent (which needs an LLM client), this proxy calls
    a remote MCP tool directly via call_tool().  The orchestrator treats
    it as a regular participant.
    """

    def __init__(
        self,
        *,
        mcp_tool: MCPStreamableHTTPTool,
        tool_name: str,
        name: str = "mcp_proxy",
        description: str | None = None,
        param_name: str = "question",
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, description=description, **kwargs)
        self._mcp_tool = mcp_tool
        self._tool_name = tool_name
        self._param_name = param_name

    # Must be a regular def — GroupChatBuilder iterates with
    # ``async for update in agent.run(stream=True)``
    def run(self, messages: Any = None, *, stream: bool = False, **kwargs: Any) -> Any:
        if stream:
            return self._run_stream(messages)
        return self._run_impl(messages)

    async def _run_impl(self, messages: Any) -> AgentResponse:
        result_text = await self._call(messages)
        return AgentResponse(
            messages=[Message("assistant", [result_text], author_name=self.name)],
            response_id=f"proxy-{uuid.uuid4().hex[:8]}",
            agent_id=self.id,
        )

    async def _run_stream(self, messages: Any):
        result_text = await self._call(messages)
        yield AgentResponseUpdate(
            contents=[Content.from_text(result_text)],
            role="assistant",
            author_name=self.name,
            agent_id=self.id,
            response_id=f"proxy-{uuid.uuid4().hex[:8]}",
        )

    async def _call(self, messages: Any) -> str:
        """Build conversation context and forward to the MCP tool."""
        input_text = _conversation_context(messages)
        result = await self._mcp_tool.call_tool(
            self._tool_name, **{self._param_name: input_text}
        )
        if isinstance(result, (list, tuple)):
            return "\n".join(
                c.text for c in result if hasattr(c, "text") and c.text
            ) or str(result)
        return result.text if hasattr(result, "text") and result.text else str(result)


def _conversation_context(messages: Any) -> str:
    """Build a conversation context string for the MCP tool.

    In a group chat the orchestrator passes the FULL conversation as a
    list[Message].  We format it so the remote agent has full context
    and can build on prior turns.
    """
    if isinstance(messages, str):
        return messages
    if isinstance(messages, Message):
        return messages.text or ""
    if isinstance(messages, (list, tuple)):
        parts: list[str] = []
        for m in messages:
            if isinstance(m, Message):
                name = m.author_name or m.role or "unknown"
                text = m.text or ""
                if text.strip():
                    parts.append(f"[{name}]: {text}")
            elif isinstance(m, str) and m.strip():
                parts.append(m)
        return "\n\n".join(parts) if parts else str(messages)
    return str(messages) if messages else ""


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN — Group Chat with LLM Planner
# ═══════════════════════════════════════════════════════════════════════════


async def main() -> None:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")

    if not endpoint or not api_key:
        print("ERROR: Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in mcp/.env")
        sys.exit(1)

    mcp_server_url = "http://localhost:8003/mcp"

    print("=" * 78)
    print("🗣️  Group Chat — Local MAF Agent + LangGraph Agent + LLM Planner")
    print("=" * 78)
    print()

    # ── Connect to the LangGraph MCP server ──────────────────────────────
    async with MCPStreamableHTTPTool(
        name="technical_architect",
        description="Remote Technical Architect (LangGraph) via MCP",
        url=mcp_server_url,
    ) as mcp_tool:
        print(f"🔗 Connected to LangGraph MCP server at {mcp_server_url}")
        print(f"   Available tools: {[t.name for t in mcp_tool.functions]}")
        print()

        client = AzureOpenAIChatClient(
            api_key=api_key,
            endpoint=endpoint,
            deployment_name=deployment,
            api_version=api_version,
        )

        # ── Participant 1: Local Business Strategist (MAF Agent) ─────────
        strategist = client.as_agent(
            name="BusinessStrategist",
            instructions=(
                "You are a Business Strategist specializing in digital "
                "transformation and cloud migration. Focus on:\n"
                "• Business impact and ROI analysis\n"
                "• Customer experience implications\n"
                "• Risk mitigation and change management\n"
                "• Competitive advantage and market positioning\n"
                "• Timeline and budget considerations\n\n"
                "Build on what others have said in the conversation. "
                "Be concise but insightful — 2-3 paragraphs max."
            ),
        )

        # ── Participant 2: Remote Technical Architect (LangGraph via MCP) ─
        architect = MCPProxyAgent(
            mcp_tool=mcp_tool,
            tool_name="ask_architect",
            param_name="question",
            name="TechnicalArchitect",
            description=(
                "Technical Architect providing architecture design, "
                "technology stack recommendations, cloud infrastructure "
                "planning, and migration strategies. Built with LangGraph, "
                "served via MCP."
            ),
        )

        # ── Orchestrator: LLM-based Planner ──────────────────────────────
        planner = client.as_agent(
            name="Planner",
            instructions=(
                "You are a discussion facilitator for a strategy meeting "
                "about cloud migration. Two experts are available:\n\n"
                "  • BusinessStrategist — business impact, ROI, risk, "
                "go-to-market\n"
                "  • TechnicalArchitect — architecture, tech stack, "
                "migration patterns, infrastructure\n\n"
                "After each turn, decide who should speak next based on "
                "what the conversation needs. Alternate between them to "
                "build a comprehensive plan. If both have contributed "
                "enough, terminate the discussion."
            ),
        )

        # ── Build the GroupChat workflow ──────────────────────────────────
        workflow = GroupChatBuilder(
            participants=[strategist, architect],
            orchestrator_agent=planner,
            max_rounds=4,
            intermediate_outputs=True,
        ).build()

        topic = (
            "Our company is a mid-size e-commerce retailer with a legacy "
            "on-premise monolithic Java application serving 2M monthly users. "
            "We want to migrate to a cloud-native architecture to improve "
            "scalability, reduce operational costs, and enable AI-powered "
            "personalization. We have a $500K budget and 12-month timeline. "
            "Discuss the strategy, architecture, and implementation approach."
        )

        print("━" * 78)
        print("📋 TOPIC")
        print("━" * 78)
        print(f"   {topic}")
        print()
        print("━" * 78)
        print("👥 PARTICIPANTS")
        print("━" * 78)
        print("   👔 BusinessStrategist — local MAF agent (Azure OpenAI)")
        print("   🏗️  TechnicalArchitect — LangGraph agent via MCP (port 8003)")
        print("   🎯 Planner           — LLM orchestrator (decides who speaks)")
        print("━" * 78)
        print()

        # ── Run the group chat ───────────────────────────────────────────
        round_num = 0
        async for event in workflow.run(topic, stream=True):
            if event.type == "output":
                data = event.data
                if not isinstance(data, list):
                    continue
                for msg in cast(list[Message], data):
                    name = msg.author_name or ""
                    text = msg.text or ""
                    if not text.strip():
                        continue

                    # Skip the initial user message echo
                    if not name or msg.role == "user":
                        continue

                    # Pick the right icon
                    if name == "BusinessStrategist":
                        icon = "👔"
                        framework = "MAF Agent"
                    elif name == "TechnicalArchitect":
                        icon = "🏗️"
                        framework = "LangGraph via MCP"
                    elif name == "Planner":
                        icon = "🎯"
                        framework = "Orchestrator"
                    else:
                        icon = "💬"
                        framework = name

                    round_num += 1
                    print(f"{'═' * 78}")
                    print(f"  Round {round_num} — {icon} {name}  [{framework}]")
                    print(f"{'═' * 78}")
                    print()
                    print(text)
                    print()

        print("━" * 78)
        print(f"✅  Group Chat complete — {round_num} rounds.")
        print("━" * 78)


if __name__ == "__main__":
    asyncio.run(main())
