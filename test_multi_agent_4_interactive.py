# =============================================================================
# Interactive CLI for A2A Multi-Agent System
# =============================================================================
# Purpose:
# This file is a command-line interface (CLI) that lets users interact with
# the A2A Tool Consumer Agent running on an A2A server.
#
# It sends simple text messages to the consumer agent, which will delegate
# tool requests to the tool provider agent when appropriate.
#
# This version supports:
# - Interactive chat with the consumer agent
# - Tool delegation testing
# - Conversation history
# =============================================================================

import asyncio                    # Built-in Python module to run async event loops
import sys
import os
from uuid import uuid4            # Used to generate unique task and session IDs

# Add the parent directory to sys.path for local imports
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the A2AClient from your client module (it handles request/response logic)
from a2a.client import A2AClient


async def interactive_cli(agent_url="http://localhost:8001", show_history=False):
    """
    Interactive CLI to chat with an A2A agent.

    Args:
        agent_url (str): The base URL of the A2A agent server
        show_history (bool): If true, prints the conversation history
    """
    
    print("🚀 A2A Interactive CLI")
    print("=" * 50)
    print(f"🔗 Connecting to agent at: {agent_url}")
    print("💡 Type 'quit', 'exit', or ':q' to exit")
    print("💡 Type 'help' for example queries")
    print("=" * 50)
    
    try:
        # Initialize the A2A client
        client = A2AClient(endpoint=agent_url)
        
        # Discover agent capabilities
        print("🔍 Discovering agent capabilities...")
        agent_card = client.discover_agent()
        
        print(f"📋 Connected to: {agent_card.get('name', 'Unknown Agent')}")
        print(f"📝 Description: {agent_card.get('description', 'No description')[:100]}...")
        
        # List available skills
        skills = agent_card.get('skills', [])
        if skills:
            print(f"🛠️  Available Skills ({len(skills)}):")
            for skill in skills:
                print(f"   • {skill.get('name', 'Unknown')}")
        else:
            print("⚠️  No skills found")
        
        print("\n" + "=" * 50)
        print("🎯 Ready to chat! Send a message to the agent:")
        print("=" * 50)
        
        # Conversation history for this session
        conversation_history = []
        
        # Start the main input loop
        while True:
            try:
                # Prompt user for input
                print("\n" + "-" * 30)
                user_input = input("👤 You: ").strip()
                
                # Check for exit commands
                if user_input.lower() in [":q", "quit", "exit"]:
                    print("👋 Goodbye!")
                    break
                
                # Check for help command
                if user_input.lower() == "help":
                    print_help()
                    continue
                
                # Check for history command
                if user_input.lower() == "history":
                    print_conversation_history(conversation_history)
                    continue
                
                # Skip empty input
                if not user_input:
                    continue
                
                # Show thinking indicator and send message to agent
                print("🤖 Agent: ", end="", flush=True)
                
                # Start thinking animation in background
                thinking_task = asyncio.create_task(show_thinking_animation())
                
                try:
                    # Send message to agent
                    response = client.chat(user_input)
                    
                    # Stop thinking animation
                    thinking_task.cancel()
                    
                    # Clear the thinking dots and move to start of line
                    print("\r🤖 Agent: ", end="", flush=True)
                    
                    # Extract and display response
                    response_text = ""
                    if "message" in response:
                        for part in response["message"]["parts"]:
                            if part["type"] == "text":
                                response_text = part["content"]
                                break
                    
                    if response_text:
                        print(response_text)
                        
                        # Add to conversation history
                        conversation_history.append({
                            "user": user_input,
                            "agent": response_text,
                            "timestamp": response["message"].get("timestamp", "")
                        })
                        
                        # Show history if requested
                        if show_history:
                            print(f"\n📊 Response details: {response}")
                    else:
                        print("⚠️  No response received or empty response")
                        print(f"   Raw response: {response}")
                        
                except Exception as e:
                    # Stop thinking animation on error
                    thinking_task.cancel()
                    print(f"\r❌ Error: {e}")
                    print("   Please check that the agent is running and accessible.")
                
            except KeyboardInterrupt:
                # Stop thinking animation if running
                if 'thinking_task' in locals() and not thinking_task.done():
                    thinking_task.cancel()
                print("\n👋 Interrupted by user. Goodbye!")
                break
            except Exception as e:
                # Stop thinking animation if running
                if 'thinking_task' in locals() and not thinking_task.done():
                    thinking_task.cancel()
                print(f"\r❌ Error: {e}")
                print("   Please check that the agent is running and accessible.")
                
    except Exception as e:
        print(f"❌ Failed to connect to agent: {e}")
        print("   Make sure the agent is running at the specified URL.")


def print_help():
    """Print helpful example queries."""
    print("\n📚 Example Queries:")
    print("   🌤️  Weather: 'What's the weather in Tokyo?'")
    print("   🧮 Math: 'Calculate 25 * 4 + 10'")
    print("   🧮 Math: 'What's 123 times 456?'")
    print("   � Leave: 'What's the leave balance for EMP001?'")
    print("   📝 Leave: 'Apply leave for EMP002 on 2025-08-15'")
    print("   📝 Leave: 'Show leave history for EMP003'")
    print("   �💬 Chat: 'Hello, how are you?'")
    print("   💬 Chat: 'Tell me a joke'")
    print("   🔄 Combined: 'What's the weather in London and what's 15 * 8?'")
    print("\n📖 Special Commands:")
    print("   • 'help' - Show this help")
    print("   • 'history' - Show conversation history")
    print("   • 'quit' or ':q' - Exit the CLI")


def print_conversation_history(history):
    """Print the conversation history."""
    if not history:
        print("📭 No conversation history yet.")
        return
    
    print(f"\n📚 Conversation History ({len(history)} exchanges):")
    print("=" * 50)
    
    for i, exchange in enumerate(history, 1):
        print(f"\n[{i}] 👤 You: {exchange['user']}")
        print(f"    🤖 Agent: {exchange['agent']}")
        if exchange['timestamp']:
            print(f"    ⏰ Time: {exchange['timestamp']}")
    
    print("=" * 50)


async def show_thinking_animation():
    """Show animated thinking dots while waiting for response."""
    dots = ""
    while True:
        try:
            for i in range(4):  # Show up to 3 dots, then reset
                if i < 3:
                    dots += "."
                else:
                    dots = ""
                
                # Update the thinking indicator
                print(f"\r🤖 Agent: thinking{dots}   ", end="", flush=True)
                await asyncio.sleep(0.5)  # Wait half a second between updates
        except asyncio.CancelledError:
            break


# -----------------------------------------------------------------------------
# Entrypoint: This ensures the CLI only runs when executing this file directly
# -----------------------------------------------------------------------------

async def main():
    """Main function that handles command line arguments and starts the CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Interactive CLI for A2A Multi-Agent System")
    parser.add_argument("--agent", type=str, default="http://localhost:8001",
                       help="Base URL of the A2A agent server (default: http://localhost:8001)")
    parser.add_argument("--history", action="store_true",
                       help="Show detailed response information")
    
    args = parser.parse_args()
    
    # Start the interactive CLI
    await interactive_cli(agent_url=args.agent, show_history=args.history)


if __name__ == "__main__":
    # Run the async main function inside the event loop
    asyncio.run(main())
