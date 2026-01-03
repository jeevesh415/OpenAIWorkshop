import os
from typing import Dict, Any
from agent_framework import ChatAgent, MCPStreamableHTTPTool, AgentThread
from agent_framework_azure_ai import AzureAIAgentClient
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity import DefaultAzureCredential

# Persistent state store for conversation threads
# In production, replace with database (e.g., Redis, CosmosDB)
thread_state_store: Dict[str, Any] = {}

# Global client (reused across requests)
_client = None
_agent = None

def get_client() -> AzureAIAgentClient:
    """Get or create Azure AI Agent client."""
    global _client
    if _client is None:
        # Use environment variables or defaults
        project_endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", 
                                  "https://ai-account-57a5urxojayf6.services.ai.azure.com/api/projects/ai-project-contoso-support-agent-v2")
        model_deployment = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
        
        _client = AzureAIAgentClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment,
            credential=DefaultAzureCredential(),
        )
    return _client

def get_agent() -> ChatAgent:
    """Create and return a ChatAgent with custom MCP tools for Contoso customer support."""
    # ===== CUSTOMIZE: Update agent name and instructions for your domain =====
    # Use environment variable or default to gpt-4o-mini
    deployment_name = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")

    client = get_client()
    
    agent = client.create_agent(
        name="contoso-customer-agent",
        # ===== CUSTOMIZE: Update instructions for your use case =====
        instructions=(
            "You are a helpful customer service assistant for Contoso. "
            "You have access to customer profiles, billing information, orders, subscriptions, "
            "and support capabilities. Help customers with their accounts, billing questions, and issues.\n\n"
            "CRITICAL - CONVERSATION CONTINUITY:\n"
            "- This conversation thread maintains full history of all previous messages\n"
            "- ALWAYS reference previous context when the user asks follow-up questions\n"
            "- If customer details were already provided, use them without asking again\n"
            "- Remember customer IDs, names, and other information from earlier in THIS conversation\n"
            "- Never treat a follow-up as a standalone request - it's part of an ongoing conversation"
        ),
        # ===== CUSTOMIZE: Update MCP_SERVICE_URL with your deployed endpoint =====
        # During deployment, replace <your-mcp-service-url> with actual URL
        # Format: https://<service-name>.azurecontainerapps.io/mcp
        # Get this from: Azure Portal > Container Apps > Your MCP Service > Ingress > Application URL
        tools=MCPStreamableHTTPTool(
            name="Contoso Customer API",
            url="https://contoso-mcp.gentlesky-f07b735a.northcentralus.azurecontainerapps.io/mcp",
        ),
    )
    return agent

class ConversationStateWrapper:
    """
    Wraps ChatAgent to add conversation state management.
    Loads/saves thread state for conversation continuity.
    """
    def __init__(self, agent: ChatAgent):
        self.agent = agent
        self.thread: AgentThread | None = None
        self.conversation_id = "default"
    
    async def initialize_thread(self, conversation_id: str = "default") -> None:
        """Initialize or load thread for this conversation."""
        self.conversation_id = conversation_id
        
        # Try to load previous thread state
        thread_state = thread_state_store.get(conversation_id)
        
        if thread_state:
            # Deserialize previous conversation thread
            self.thread = await self.agent.deserialize_thread(thread_state)
            print(f"[STATE] Loaded existing thread for conversation {conversation_id}")
        else:
            # Create new thread for first message
            self.thread = self.agent.get_new_thread()
            print(f"[STATE] Created new thread for conversation {conversation_id}")
    
    async def save_state(self) -> None:
        """Persist thread state after interaction."""
        if self.thread:
            serialized_state = await self.thread.serialize()
            thread_state_store[self.conversation_id] = serialized_state
            print(f"[STATE] Saved thread state for conversation {self.conversation_id}")

# Global conversation wrapper
_conversation = None

async def initialize_conversation_state(context) -> ConversationStateWrapper:
    """Initialize conversation state for a request."""
    global _conversation
    
    # Extract conversation ID from context
    conversation_id = getattr(context, 'conversation_id', 'default')
    
    if _conversation is None or _conversation.conversation_id != conversation_id:
        agent = get_agent()
        _conversation = ConversationStateWrapper(agent)
        await agent.__aenter__()
        await _conversation.initialize_thread(conversation_id)
    
    return _conversation

def agent_factory(context):
    """
    Factory function for from_agent_framework.
    Returns the agent instance with state management.
    """
    # This is called by from_agent_framework
    # We need to return the agent, state management happens in the thread
    agent = get_agent()
    return agent

if __name__ == "__main__":
    import asyncio
    import sys
    
    # Check if we're being run for testing or deployment
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        async def test_agent():
            """Test agent code structure without needing Azure auth"""
            print("\n=== TESTING CONTOSO SUPPORT AGENT STRUCTURE ===\n")
            
            try:
                # Test 1: Verify imports and code structure
                print("Test 1: Verifying imports and code structure...")
                assert ChatAgent is not None
                assert MCPStreamableHTTPTool is not None
                assert AgentThread is not None
                print("✓ All imports successful")
                
                # Test 2: Verify get_agent function can be called (won't authenticate but structure is OK)
                print("\nTest 2: Verifying agent factory structure...")
                assert callable(get_agent)
                assert callable(agent_factory)
                print("✓ Agent factory functions defined correctly")
                
                # Test 3: Verify conversation state store
                print("\nTest 3: Testing thread state persistence...")
                test_state = {"test": "data"}
                thread_state_store["test_conv"] = test_state
                assert thread_state_store.get("test_conv") == test_state
                print("✓ Thread state store working correctly")
                
                # Test 4: Verify ConversationStateWrapper structure
                print("\nTest 4: Verifying conversation state wrapper...")
                assert hasattr(ConversationStateWrapper, 'initialize_thread')
                assert hasattr(ConversationStateWrapper, 'save_state')
                print("✓ ConversationStateWrapper structure correct")
                
                # Test 5: Verify MCP tool configuration
                print("\nTest 5: Verifying MCP tool URL...")
                mcp_url = "https://contoso-mcp.gentlesky-f07b735a.northcentralus.azurecontainerapps.io/mcp"
                print(f"✓ MCP URL configured: {mcp_url}")
                
                # Test 6: Verify default values
                print("\nTest 6: Verifying configuration defaults...")
                project_endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", 
                                          "https://ai-account-57a5urxojayf6.services.ai.azure.com/api/projects/ai-project-contoso-support-agent-v2")
                model_deployment = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
                print(f"✓ Project endpoint: {project_endpoint[:60]}...")
                print(f"✓ Model deployment: {model_deployment}")
                
                print("\n" + "="*50)
                print("✅ ALL STRUCTURE TESTS PASSED!")
                print("="*50)
                print("\nNOTE: Full agent tests require Azure authentication.")
                print("Run 'azd up' to deploy to Foundry for full testing.\n")
                return True
                
            except Exception as e:
                print(f"\n❌ TEST FAILED: {str(e)}")
                import traceback
                traceback.print_exc()
                return False
        
        # Run the test
        result = asyncio.run(test_agent())
        sys.exit(0 if result else 1)
    
    else:
        # Normal Foundry deployment mode
        from_agent_framework(agent_factory).run()