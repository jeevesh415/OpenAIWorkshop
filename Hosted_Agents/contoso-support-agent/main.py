import os
from agent_framework import ChatAgent, MCPStreamableHTTPTool
from agent_framework_azure_ai import AzureAIAgentClient
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
_project_root_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=_project_root_env)

def get_agent():
    """Create and return a contoso support chat agent instance."""
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
        name="contoso_support_agent",
        instructions="You are a helpful assistant that can help with microsoft documentation questions.",
        tools=MCPStreamableHTTPTool(
            name="Contoso_chatbot_tools",
            url=os.environ.get("MCP_SERVICE_URL", "https://<your-mcp-service-url>/mcp"),
        ),
    )
    return agent

if __name__ == "__main__":
    from_agent_framework(lambda _: get_agent()).run()