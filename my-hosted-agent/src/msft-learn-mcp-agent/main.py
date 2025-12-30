import os
from agent_framework import ChatAgent, MCPStreamableHTTPTool
from agent_framework_azure_ai import AzureAIAgentClient
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity import DefaultAzureCredential

def get_agent():
    """Create and return a ChatAgent with Bing Grounding search tool."""
    assert "AZURE_AI_PROJECT_ENDPOINT" in os.environ, (
        "AZURE_AI_PROJECT_ENDPOINT environment variable must be set."
    )
    assert "AZURE_AI_MODEL_DEPLOYMENT_NAME" in os.environ, (
        "AZURE_AI_MODEL_DEPLOYMENT_NAME environment variable must be set."
    )

    agent = AzureAIAgentClient(
        endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        credential=DefaultAzureCredential(),
    ).create_agent(
        name="contoso-customer-agent",
        instructions=(
            "You are a helpful customer service assistant for Contoso. "
            "You have access to customer profiles, billing information, orders, subscriptions, "
            "and support capabilities. Help customers with their accounts, billing questions, and issues."
        ),
        tools=MCPStreamableHTTPTool(
            name="Contoso Customer API",
            url="https://contoso-mcp.gentlesky-f07b735a.northcentralus.azurecontainerapps.io/mcp",
        ),
    )
    return agent

if __name__ == "__main__":
    from_agent_framework(lambda _: get_agent()).run()