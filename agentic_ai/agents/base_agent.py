import os
import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file if needed


class BaseAgent:
    """  
    Base class for all agents.  
    Not intended to be used directly.  
    Handles environment variables, state store, and chat history.  
    """  
  
    def __init__(self, state_store: Dict[str, Any], session_id: str) -> None:
        self.azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        self.azure_openai_key = os.getenv("AZURE_OPENAI_API_KEY")  # May be unused if using Entra ID
        self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        self.mcp_server_uri = os.getenv("MCP_SERVER_URI")
        self.openai_model_name = os.getenv("OPENAI_MODEL_NAME")

        self.session_id = session_id
        self.state_store = state_store

        self.chat_history: List[Dict[str, str]] = self.state_store.get(f"{session_id}_chat_history", [])
        self.state: Optional[Any] = self.state_store.get(session_id, None)
        logging.debug(f"Chat history for session {session_id}: {self.chat_history}")
  
    def _setstate(self, state: Any) -> None:  
        self.state_store[self.session_id] = state  
  
    def append_to_chat_history(self, messages: List[Dict[str, str]]) -> None:  
        self.chat_history.extend(messages)  
        self.state_store[f"{self.session_id}_chat_history"] = self.chat_history  
  
    def set_websocket_manager(self, manager: Any) -> None:
        """Allow backend to inject WebSocket manager for streaming events.

        Override in child class if streaming support is needed.
        """
        pass  # Default: no-op for agents that don't support streaming

    def create_azure_openai_chat_client(self):
        """Create an AzureOpenAIChatClient using Entra ID (RBAC).

        This matches the Azure OpenAI "azure_ad_token_provider" pattern from
        the deployment quickstart, so it works even when key-based auth is
        disabled at the resource level.
        """
        if not all([self.azure_deployment, self.azure_openai_endpoint, self.api_version]):
            raise RuntimeError(
                "Azure OpenAI configuration is incomplete. Ensure AZURE_OPENAI_CHAT_DEPLOYMENT, "
                "AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_API_VERSION are set."
            )

        # Lazy imports to avoid hard dependency if agents aren't used
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from agent_framework.azure import AzureOpenAIChatClient

        # Use the same scope as the official Azure OpenAI Entra ID samples
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )

        return AzureOpenAIChatClient(
            deployment_name=self.azure_deployment,
            endpoint=self.azure_openai_endpoint,
            api_version=self.api_version,
            ad_token_provider=token_provider,
        )

    async def chat_async(self, prompt: str) -> str:
        """Override in child class."""
        raise NotImplementedError("chat_async should be implemented in subclass.")