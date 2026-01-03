"""
Interactive Contoso Agent Simulator
Allows you to have a real conversation with the mock agent and see context persistence in action.
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

class ContosoAgent:
    """Interactive Contoso support agent"""
    
    def __init__(self):
        self.conversation_id = "interactive_session"
        
    async def run(self, user_message: str, thread: MockAgentThread) -> str:
        """Process user message and generate response"""
        # Add user message to thread
        thread.messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Generate response based on context
        response = await self._generate_response(user_message, thread)
        
        # Add assistant response to thread
        thread.messages.append({
            "role": "assistant",
            "content": response
        })
        
        return response
    
    async def _generate_response(self, user_message: str, thread: MockAgentThread) -> str:
        """Generate response based on conversation context"""
        message_lower = user_message.lower()
        has_context = len(thread.messages) > 2
        
        # Extract context from thread history
        customer_info = self._extract_customer_from_context(thread)
        
        # Response logic
        if any(word in message_lower for word in ["customer", "details", "id", "name", "profile"]):
            # Check if customer ID is mentioned in this message
            customer_id = self._extract_customer_id(user_message)
            if not customer_id and customer_info:
                customer_id = customer_info.get("id")
            
            if customer_id == "101":
                return (
                    "Here are the customer details for ID 101:\n"
                    "• Name: Michelle Wells\n"
                    "• Email: thomasmiller@example.net\n"
                    "• Phone: 4894899217\n"
                    "• Address: Unit 3206 Box 1632, DPO AP 34302\n"
                    "• Loyalty Level: Gold"
                )
            elif not customer_id:
                return "Please provide a customer ID so I can look up their details."
        
        elif any(word in message_lower for word in ["promotion", "discount", "offer", "deal"]):
            if has_context and customer_info:
                return (
                    f"Based on {customer_info['name']}'s {customer_info['loyalty']} loyalty status "
                    "and purchase history, here are available promotions:\n"
                    "• 15% off next purchase (Gold members)\n"
                    "• Free shipping on orders over $50\n"
                    "• Early access to new product launches"
                )
            else:
                return "Please provide a customer ID first so I can check their promotions."
        
        elif any(word in message_lower for word in ["balance", "outstanding", "owe", "invoice", "billing"]):
            if has_context and customer_info:
                return (
                    f"Customer {customer_info['name']} (ID {customer_info['id']}) has an outstanding balance "
                    "of $42.51 on her account. This is from her last invoice of $672.72, "
                    "with $630.21 already paid."
                )
            else:
                return "Please provide a customer ID to check their outstanding balance."
        
        elif any(word in message_lower for word in ["order", "purchase", "buy", "history"]):
            if has_context and customer_info:
                return (
                    f"{customer_info['name']} has placed 12 orders in the last year. "
                    "Recent purchases include office supplies and equipment. "
                    "Total spending: $3,450.50"
                )
            else:
                return "Please provide a customer ID to check their order history."
        
        elif any(word in message_lower for word in ["subscription", "plan", "service"]):
            if has_context and customer_info:
                return (
                    f"{customer_info['name']}'s current subscription:\n"
                    "• Plan: Enterprise Plus\n"
                    "• Status: Active\n"
                    "• Renewal Date: March 15, 2026\n"
                    "• Monthly Cost: $299.99"
                )
            else:
                return "Please provide a customer ID to check their subscription details."
        
        else:
            return "I'm here to help with customer information, billing, orders, and subscriptions. What would you like to know?"
    
    def _extract_customer_id(self, message: str) -> str:
        """Extract customer ID from message"""
        import re
        match = re.search(r'id\s+(\d+)|customer\s+(\d+)|(\d+)', message, re.IGNORECASE)
        if match:
            return match.group(1) or match.group(2) or match.group(3)
        return None
    
    def _extract_customer_from_context(self, thread: MockAgentThread) -> Dict[str, str]:
        """Extract customer information from thread history"""
        for msg in reversed(thread.messages):
            content = msg.get("content", "").lower()
            if "michelle wells" in content:
                return {
                    "id": "101",
                    "name": "Michelle Wells",
                    "loyalty": "Gold"
                }
        return None

async def main():
    """Main interactive loop"""
    print("\n" + "="*70)
    print("CONTOSO CUSTOMER SUPPORT AGENT - INTERACTIVE TEST")
    print("="*70)
    print("\nThis is a simulated agent that maintains conversation context.")
    print("Try these interactions:")
    print("  1. 'Give me customer details for ID 101'")
    print("  2. 'Are there any promotions for this customer?'")
    print("  3. 'What's the outstanding balance?'")
    print("\nType 'quit' to exit.\n")
    print("-"*70 + "\n")
    
    agent = ContosoAgent()
    conversation_id = agent.conversation_id
    
    # Create initial thread
    thread = MockAgentThread()
    thread_state_store[conversation_id] = await thread.serialize()
    
    message_count = 0
    
    while True:
        try:
            # Get user input
            user_input = input("🟦 YOU: ").strip()
            
            if user_input.lower() == 'quit':
                print("\n👋 Thank you for testing! Goodbye.\n")
                break
            
            if not user_input:
                print("⚠️  Please enter a message.\n")
                continue
            
            message_count += 1
            
            # Load thread from store (simulating new request)
            saved_state = thread_state_store[conversation_id]
            thread = await MockAgentThread.deserialize(saved_state)
            
            # Show context being loaded
            if message_count > 1:
                print(f"📊 Loading conversation history ({len(thread.messages)} previous messages)...")
                if thread.messages:
                    print(f"   Context: {[msg['content'][:30] + '...' for msg in thread.messages[-2:]]}")
            
            # Get response
            response = await agent.run(user_input, thread)
            
            # Save thread state
            thread_state_store[conversation_id] = await thread.serialize()
            
            print(f"\n🤖 AGENT: {response}\n")
            
            # Show thread info
            print(f"📊 Thread: {len(thread.messages)} total messages stored\n")
            print("-"*70 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Test interrupted. Goodbye.\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")

if __name__ == "__main__":
    asyncio.run(main())
