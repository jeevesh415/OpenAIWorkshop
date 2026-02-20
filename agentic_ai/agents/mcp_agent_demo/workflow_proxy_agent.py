"""
Part 3 — Proxy Agent Workflow: Direct MCP Tool Invocation Without LLM

Demonstrates a "proxy agent" pattern where a SequentialBuilder workflow
calls a remote MCP agent DIRECTLY — no intermediate LLM reasoning step.

Traditional approach:
    Researcher (LLM) → Expert Agent (LLM reasons → picks tool) → MCP
                             ↑ unnecessary LLM call — extra cost & latency

Proxy agent approach:
    Researcher (LLM) → MCPProxyAgent (direct call_tool()) → MCP
                             ↑ zero LLM overhead — deterministic routing

MCPProxyAgent subclasses BaseAgent (not Agent) — no LLM client.
Its run() directly calls a known MCP tool by name.  The orchestrator
treats it as a normal participant, but internally it's just a
transparent bridge to the MCP endpoint.

When to use:
    - You KNOW which MCP tool to call (no routing decision needed)
    - You want deterministic routing with zero hallucination risk
    - You're optimizing for latency and cost in high-throughput pipelines
    - Cross-team integration where the remote service is a black box

Prerequisites:
    mcp_server.py must be running on http://localhost:8002/mcp

Usage:
    cd agentic_ai/agents/mcp_agent_demo
    uv run python workflow_proxy_agent.py
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
from agent_framework.orchestrations import SequentialBuilder


# ═══════════════════════════════════════════════════════════════════════════
#  MCPProxyAgent — BaseAgent that forwards to a remote MCP tool
# ═══════════════════════════════════════════════════════════════════════════


class MCPProxyAgent(BaseAgent):
    """BaseAgent that forwards messages to a remote MCP tool via call_tool()."""

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

    def run(self, messages: Any = None, *, stream: bool = False, **kwargs: Any) -> Any:
        """Forward input to the MCP tool — no LLM involved.

        Must be a regular def (not async def) because SequentialBuilder
        does ``async for update in agent.run(stream=True)``.
        """
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
        """Extract input text, call the MCP tool, return result as string."""
        input_text = _last_text(messages)
        result = await self._mcp_tool.call_tool(
            self._tool_name, **{self._param_name: input_text}
        )
        # call_tool returns Content objects — extract their .text
        if isinstance(result, (list, tuple)):
            return "\n".join(
                c.text for c in result if hasattr(c, "text") and c.text
            ) or str(result)
        return result.text if hasattr(result, "text") and result.text else str(result)


def _last_text(messages: Any) -> str:
    """Get the last agent's text output from the orchestrator's message list."""
    if isinstance(messages, str):
        return messages
    if isinstance(messages, Message):
        return messages.text or ""
    if isinstance(messages, (list, tuple)):
        for m in reversed(messages):
            text = m.text if isinstance(m, Message) else str(m)
            if text and text.strip():
                return text
    return str(messages) if messages else ""


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN — demonstrate proxy agent in a SequentialBuilder workflow
# ═══════════════════════════════════════════════════════════════════════════


async def main() -> None:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")

    if not endpoint or not api_key:
        print("ERROR: Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in mcp/.env")
        sys.exit(1)

    mcp_server_url = "http://localhost:8002/mcp"

    print("=" * 78)
    print("🔀  Proxy Agent Workflow — Remote MCP Agent Integration")
    print("=" * 78)
    print()

    # ── Connect to the MCP server ───────────────────────────────────────
    async with MCPStreamableHTTPTool(
        name="expert_advisor",
        description="Remote Expert Advisor via MCP",
        url=mcp_server_url,
    ) as mcp_tool:
        print(f"🔗 Connected to MCP server at {mcp_server_url}")
        print(f"   Available tools: {[t.name for t in mcp_tool.functions]}")
        print()

        # ── Set up agents ───────────────────────────────────────────────

        client = AzureOpenAIChatClient(
            api_key=api_key,
            endpoint=endpoint,
            deployment_name=deployment,
            api_version=api_version,
        )

        # Agent 1: Local Researcher (uses LLM)
        researcher = client.as_agent(
            name="researcher",
            instructions=(
                "You are a market researcher. Given a business topic, provide a "
                "concise initial analysis covering opportunity, competition, and "
                "key trends. Keep it to 3-4 paragraphs. Your output will be "
                "reviewed by an expert advisor next."
            ),
        )

        # Agent 2: MCPProxyAgent — forwards to MCP
        proxy_expert = MCPProxyAgent(
            mcp_tool=mcp_tool,
            tool_name="ask_expert",
            param_name="question",
            name="proxy_expert",
            description="Proxy that calls the remote Expert Advisor MCP tool",
        )

        # ── Build workflow ──────────────────────────────────────────────
        workflow = SequentialBuilder(
            participants=[researcher, proxy_expert],
        ).build()

        topic = "Expanding a mid-size SaaS company into the healthcare AI market"

        print("━" * 78)
        print(f"📋 Topic: {topic}")
        print("━" * 78)
        print("  Step 1: Researcher → draft analysis")
        print("  Step 2: MCPProxyAgent → forward to remote expert via MCP")
        print("━" * 78)
        print()

        # ── Run the workflow ────────────────────────────────────────────
        outputs: list[list[Message]] = []
        async for event in workflow.run(topic, stream=True):
            if event.type == "output":
                outputs.append(cast(list[Message], event.data))

        # ── Display results ─────────────────────────────────────────────
        if outputs:
            print("=" * 78)
            print("📊 WORKFLOW RESULTS")
            print("=" * 78)
            for msg in outputs[-1]:
                name = msg.author_name or "unknown"
                if name == "researcher":
                    label = "🔬 Researcher"
                elif name == "proxy_expert":
                    label = "🎯 Proxy Expert (via MCP)"
                else:
                    label = f"👤 {name}"
                print(f"\n{'─' * 78}")
                print(f"{label}:")
                print(f"{'─' * 78}")
                print(msg.text)

        print()
        print("=" * 78)
        print("✅  Workflow complete.")
        print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
