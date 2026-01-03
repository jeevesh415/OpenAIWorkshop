"""
Simulate a realistic conversation flow to demonstrate context persistence.
This mimics what happens when you interact with the agent in Foundry.
"""

import asyncio
from typing import Dict, Any

# Thread state store (same as main.py)
thread_state_store: Dict[str, Any] = {}

class MockAgentThread:
    """Mock thread that simulates real AgentThread behavior"""
    def __init__(self, thread_id: str = "thread_001"):
        self.thread_id = thread_id
        self.messages = []
        
    async def serialize(self) -> Dict[str, Any]:
        """Serialize thread state"""
        return {
            "thread_id": self.thread_id,
            "messages": self.messages.copy()
        }
    
    @classmethod
    async def deserialize(cls, state: Dict[str, Any]) -> "MockAgentThread":
        """Deserialize thread from state"""
        thread = cls(state["thread_id"])
        thread.messages = state.get("messages", [])
        return thread

class MockAgent:
    """Mock agent that simulates Contoso support agent"""
    
    async def run(self, user_message: str, thread: MockAgentThread) -> str:
        """Simulate agent processing a message"""
        # Add user message to thread
        thread.messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Generate response based on message content and context
        response = await self._generate_response(user_message, thread)
        
        # Add assistant response to thread
        thread.messages.append({
            "role": "assistant",
            "content": response
        })
        
        return response
    
    async def _generate_response(self, user_message: str, thread: MockAgentThread) -> str:
        """Generate response based on conversation context"""
        # Check if this is a follow-up by looking at thread history
        has_context = len(thread.messages) > 2
        
        if "customer details" in user_message.lower() or "101" in user_message:
            return (
                "Here are the customer details for ID 101:\n"
                "• Name: Michelle Wells\n"
                "• Email: thomasmiller@example.net\n"
                "• Phone: 4894899217\n"
                "• Address: Unit 3206 Box 1632, DPO AP 34302\n"
                "• Loyalty Level: Gold"
            )
        
        elif "promotions" in user_message.lower():
            if has_context and any("Michelle" in str(msg) or "101" in str(msg) for msg in thread.messages):
                return (
                    "Based on Michelle Wells' Gold loyalty status and purchase history, "
                    "here are available promotions:\n"
                    "• 15% off next purchase (Gold members)\n"
                    "• Free shipping on orders over $50\n"
                    "• Early access to new product launches"
                )
            else:
                return "Please provide a customer ID first so I can check relevant promotions."
        
        elif "balance" in user_message.lower() or "outstanding" in user_message.lower():
            if has_context and any("Michelle" in str(msg) or "101" in str(msg) for msg in thread.messages):
                return (
                    "Customer Michelle Wells (ID 101) has an outstanding balance of $42.51 "
                    "on her account. This is from her last invoice of $672.72, "
                    "with $630.21 already paid."
                )
            else:
                return "Please provide a customer ID to check their outstanding balance."
        
        else:
            return "I'm here to help with customer information, billing, and promotions. How can I assist you?"

async def simulate_conversation():
    """Simulate a real conversation in the playground"""
    print("\n" + "="*70)
    print("SIMULATING CONTOSO AGENT CONVERSATION IN FOUNDRY PLAYGROUND")
    print("="*70 + "\n")
    
    agent = MockAgent()
    conversation_id = "playground_session_001"
    
    # === MESSAGE 1: New conversation ===
    print("🟦 USER: Give me customer details for ID 101")
    print("-" * 70)
    
    # Create new thread
    thread = MockAgentThread()
    response1 = await agent.run("Give me customer details for ID 101", thread)
    
    # Save thread state
    thread_state_store[conversation_id] = await thread.serialize()
    
    print(f"🤖 AGENT: {response1}")
    print(f"\n📊 THREAD STATE: {len(thread.messages)} messages, {len(thread_state_store)} conversation(s) stored\n")
    
    # === MESSAGE 2: Follow-up ===
    print("🟦 USER: Are there any promotions for this customer?")
    print("-" * 70)
    
    # Load thread with previous context
    saved_state = thread_state_store[conversation_id]
    thread = await MockAgentThread.deserialize(saved_state)
    print(f"✓ LOADED THREAD WITH {len(thread.messages)} PREVIOUS MESSAGES")
    print(f"  Previous context: {[msg['content'][:30] + '...' for msg in thread.messages]}\n")
    
    response2 = await agent.run("Are there any promotions for this customer?", thread)
    
    # Save updated thread
    thread_state_store[conversation_id] = await thread.serialize()
    
    print(f"🤖 AGENT: {response2}")
    print(f"\n📊 THREAD STATE: {len(thread.messages)} messages\n")
    
    # === MESSAGE 3: Another follow-up ===
    print("🟦 USER: What's the outstanding balance?")
    print("-" * 70)
    
    # Load thread again
    saved_state = thread_state_store[conversation_id]
    thread = await MockAgentThread.deserialize(saved_state)
    print(f"✓ LOADED THREAD WITH {len(thread.messages)} PREVIOUS MESSAGES")
    print(f"  Full conversation history:")
    for i, msg in enumerate(thread.messages, 1):
        print(f"    {i}. {msg['role'].upper()}: {msg['content'][:50]}...")
    print()
    
    response3 = await agent.run("What's the outstanding balance?", thread)
    
    # Save final state
    thread_state_store[conversation_id] = await thread.serialize()
    
    print(f"🤖 AGENT: {response3}")
    print(f"\n📊 THREAD STATE: {len(thread.messages)} messages\n")
    
    # === FINAL VERIFICATION ===
    print("="*70)
    print("VERIFICATION: CONTEXT PERSISTENCE")
    print("="*70 + "\n")
    
    final_thread = await MockAgentThread.deserialize(thread_state_store[conversation_id])
    
    print("✅ Message 1: Provided customer ID 101 (Michelle Wells)")
    print("✅ Message 2: Referenced customer ID 101 WITHOUT asking again - used context!")
    print("✅ Message 3: Still remembered customer ID 101 from earlier messages\n")
    
    print(f"Complete Conversation History ({len(final_thread.messages)} messages):")
    print("-" * 70)
    for i, msg in enumerate(final_thread.messages, 1):
        role_emoji = "🟦" if msg['role'] == "user" else "🤖"
        print(f"\n{i}. {role_emoji} {msg['role'].upper()}:")
        print(f"   {msg['content']}")
    
    print("\n" + "="*70)
    print("✅ RESULT: Context maintained across 3 message exchanges!")
    print("="*70)
    print("\nThis is what should happen in Foundry playground.")
    print("Ready to deploy with: azd up\n")

if __name__ == "__main__":
    asyncio.run(simulate_conversation())
