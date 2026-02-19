"""
Part 3 — Workflow orchestrating a local agent + remote agent (via MCP).

Demonstrates a SequentialBuilder workflow where:
  Step 1: Local "Researcher" agent drafts an initial analysis (in-process)
  Step 2: Remote "Expert Advisor" agent (via MCP) reviews and enhances it

Prerequisites:
    mcp_server.py must be running on http://localhost:8002/mcp

Usage:
    cd agentic_ai/agents/mcp_agent_demo
    uv run python workflow_local_remote.py
"""

import asyncio
import os
import sys
from typing import Any, cast

from dotenv import load_dotenv

# Load credentials from the shared mcp/.env
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp", ".env")
load_dotenv(env_path)

from agent_framework import Agent, MCPStreamableHTTPTool, Message
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework.orchestrations import SequentialBuilder


async def main() -> None:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")

    if not endpoint or not api_key:
        print("ERROR: Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in mcp/.env")
        sys.exit(1)

    mcp_server_url = "http://localhost:8002/mcp"
    print(f"🔗 Connecting to remote Expert Advisor MCP server at {mcp_server_url} ...")

    # ── Set up the MCP connection to the remote agent ───────────────────────
    async with MCPStreamableHTTPTool(
        name="expert_advisor",
        description="Remote Expert Advisor accessible via MCP — can analyze risk, look up market data, and summarize findings.",
        url=mcp_server_url,
    ) as mcp_tool:
        print(f"✅ MCP connected. Remote tools: {[t.name for t in mcp_tool.functions]}")

        # ── Create the two agents ───────────────────────────────────────────

        client = AzureOpenAIChatClient(
            api_key=api_key,
            endpoint=endpoint,
            deployment_name=deployment,
            api_version=api_version,
        )

        # Agent 1: Local Researcher (runs entirely in-process, no MCP)
        researcher = client.as_agent(
            name="researcher",
            instructions=(
                "You are a market researcher. Given a business topic, provide a "
                "concise initial analysis covering opportunity, competition, and "
                "key trends. Keep it to 3-4 paragraphs. Your output will be "
                "reviewed by an expert advisor next."
            ),
        )

        # Agent 2: Remote Expert (enhanced with MCP tools from the server)
        expert = Agent(
            client=client,
            name="expert_reviewer",
            instructions=(
                "You are a senior business strategy expert. You will receive a "
                "researcher's initial analysis as context. Use your expert_advisor "
                "MCP tools (ask_expert) to run risk analysis and get market data, "
                "then provide an enhanced, final recommendation that combines "
                "the researcher's draft with your expert tools' output."
            ),
            tools=mcp_tool,
        )

        # ── Build the Sequential Workflow ───────────────────────────────────
        # Researcher drafts → Expert reviews and enhances
        workflow = SequentialBuilder(participants=[researcher, expert]).build()

        # ── Run the workflow ────────────────────────────────────────────────
        topic = "Expanding a mid-size SaaS company into the healthcare AI market"
        print(f"\n{'='*70}")
        print(f"📋 Workflow Topic: {topic}")
        print(f"{'='*70}")
        print("   Step 1: Local Researcher → draft analysis")
        print("   Step 2: Remote Expert (MCP) → enhanced recommendation")
        print(f"{'='*70}\n")

        outputs: list[list[Message]] = []
        async for event in workflow.run(topic, stream=True):
            if event.type == "output":
                outputs.append(cast(list[Message], event.data))

        # ── Display results ─────────────────────────────────────────────────
        if outputs:
            print("\n" + "="*70)
            print("📊 WORKFLOW RESULTS")
            print("="*70)
            for msg in outputs[-1]:
                name = msg.author_name or ("assistant" if msg.role == "assistant" else "user")
                role_label = "🔬 Researcher" if name == "researcher" else "🎓 Expert Reviewer" if name == "expert_reviewer" else f"👤 {name}"
                print(f"\n{'─'*70}")
                print(f"{role_label}:")
                print(f"{'─'*70}")
                print(msg.text)

        print(f"\n{'='*70}")
        print("✅ Workflow complete — local agent + remote MCP agent orchestrated!")
        print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
