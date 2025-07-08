"""
A2A Tool Consumer Agent

This agent connects to another A2A agent (tool provider) and exposes
the tool provider's skills as its own, allowing it to delegate tool
requests to the appropriate agent.
"""

import os
import sys
import asyncio
import argparse
import logging
import httpx
import uuid
import re

# Add the parent directory to sys.path
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from a2a.server import A2AServer
from a2a.client import A2AClient


def configure_logging(log_level="INFO"):
    """Configure logging with appropriate level and format."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    # Set specific loggers of interest to the requested level
    loggers = ["a2a_server", "a2a_client", "tool_consumer"]
    for logger_name in loggers:
        logging.getLogger(logger_name).setLevel(numeric_level)
    
    return logging.getLogger("tool_consumer_agent")


async def check_a2a_server_availability(url, max_retries=10, retry_delay=2):
    """Check if an A2A server is available and responding."""
    logger = logging.getLogger("server_check")
    
    async with httpx.AsyncClient() as client:
        for i in range(max_retries):
            try:
                logger.info(f"Checking A2A server availability: {url} (Attempt {i+1}/{max_retries})")
                response = await client.get(f"{url}/.well-known/agent.json", timeout=5.0)
                if response.status_code == 200:
                    logger.info(f"A2A server at {url} is available")
                    return True
            except Exception as e:
                logger.debug(f"Request failed: {e}")
            
            logger.info(f"A2A server at {url} not ready yet, retrying in {retry_delay}s")
            await asyncio.sleep(retry_delay)
    
    logger.error(f"A2A server at {url} could not be reached after {max_retries} attempts")
    return False


async def discover_and_proxy_skills(tool_provider_url):
    """Discover skills from the tool provider agent and create proxy skills."""
    logger = logging.getLogger("skill_discovery")
    
    try:
        # Create A2A client to connect to tool provider
        logger.info(f"Connecting to tool provider at {tool_provider_url}")
        tool_provider_client = A2AClient(endpoint=tool_provider_url)
        
        # Discover the tool provider's capabilities
        logger.info("Discovering tool provider capabilities...")
        agent_card = tool_provider_client.discover_agent()
        
        logger.info(f"Connected to: {agent_card.get('name', 'Unknown Agent')}")
        logger.info(f"Description: {agent_card.get('description', 'No description')}")
        
        # Get available skills
        provider_skills = agent_card.get('skills', [])
        logger.info(f"Discovered {len(provider_skills)} skills from tool provider:")
        for skill in provider_skills:
            logger.info(f"  • {skill.get('name', 'Unknown')}: {skill.get('description', 'No description')}")
        
        # Create proxy skills that will delegate to the tool provider
        proxy_skills = []
        for skill in provider_skills:
            proxy_skill = {
                "name": skill.get('name', ''),
                "description": f"[Proxied] {skill.get('description', '')}",
                "parameters": skill.get('parameters', [])
            }
            proxy_skills.append(proxy_skill)
        
        return proxy_skills, tool_provider_client
        
    except Exception as e:
        logger.error(f"Failed to discover skills from tool provider: {e}")
        return [], None


class ToolDelegationHandler:
    """Handles delegation of tool calls to the tool provider agent."""
    
    def __init__(self, tool_provider_client, proxy_skills):
        self.tool_provider_client = tool_provider_client
        self.proxy_skills = proxy_skills
        self.skill_names = {skill['name'] for skill in proxy_skills}
        self.logger = logging.getLogger("tool_delegation")
    
    def should_delegate(self, user_message):
        """Determine if a user message should be delegated to the tool provider."""
        # Check for keywords that indicate tool usage
        tool_keywords = [
            # Weather related
            'weather', 'temperature', 'forecast', 'climate',
            
            # Math/calculation related
            'calculate', 'math', 'addition', 'subtraction', 'multiplication', 'division',
            'plus', 'minus', 'times', 'divided by', 'equals', 'compute', 'sum',
            
            # Leave management related
            'leave', 'vacation', 'holiday', 'time off', 'absence', 'pto',
            'leave balance', 'leave history', 'apply leave', 'request leave',
            'days off', 'remaining leave', 'leave application', 'leave status',
            'employee', 'staff', 'worker', 'hr'
        ]
        
        message_lower = user_message.lower()
        for keyword in tool_keywords:
            if keyword in message_lower:
                self.logger.info(f"🎯 Detected tool keyword '{keyword}' in message")
                return True
        
        # Also check for employee ID patterns (e.g., EMP001, emp123, etc.) and known employee names
        if (re.search(r'\bemp\d+\b', message_lower) or 
            re.search(r'\bemployee\s+\d+\b', message_lower) or
            any(name in message_lower for name in ['raghu', 'jake', 'corbin', 'steve'])):
            self.logger.info("🎯 Detected employee ID or name pattern in message")
            return True
        
        return False
    
    def delegate_to_tool_provider(self, user_message):
        """Delegate a message to the tool provider and return the response."""
        try:
            self.logger.info(f"🔄 Delegating to tool provider: {user_message}")
            response = self.tool_provider_client.chat(user_message)
            
            if "message" in response:
                for part in response["message"]["parts"]:
                    if part["type"] == "text" and part["content"]:
                        raw_response = part["content"]
                        self.logger.info(f"✅ Received delegation response: {raw_response[:100]}...")
                        return raw_response
            
            self.logger.warning("⚠️  Tool provider returned empty response")
            return "I was unable to process that request using the available tools."
            
        except Exception as e:
            self.logger.error(f"❌ Delegation failed: {e}")
            return f"I encountered an error while trying to use the tools: {str(e)}"


async def main():
    """Run the A2A Tool Consumer Agent that proxies skills from a tool provider."""
    parser = argparse.ArgumentParser(description="A2A Tool Consumer Agent")
    parser.add_argument("--host", type=str, default="localhost", 
                       help="Host to run this agent on")
    parser.add_argument("--port", type=int, default=8001,
                       help="Port to run this agent on")
    parser.add_argument("--tool-provider-host", type=str, default="localhost",
                       help="Host of the tool provider agent")
    parser.add_argument("--tool-provider-port", type=int, default=8000,
                       help="Port of the tool provider agent")
    parser.add_argument("--model", type=str, default="llama3.1:8b",
                       help="Ollama model to use for this agent")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="Set logging level")
    
    args = parser.parse_args()
    
    # Initialize logging
    logger = configure_logging(args.log_level)
    logger.info("🚀 Starting A2A Tool Consumer Agent")
    
    # Initialize variables for cleanup
    consumer_server = None
    tool_provider_client = None
    
    try:
        # Configuration
        tool_provider_url = f"http://{args.tool_provider_host}:{args.tool_provider_port}"
        consumer_url = f"http://{args.host}:{args.port}"
        
        # Check if tool provider is available
        logger.info(f"🔗 Connecting to tool provider at {tool_provider_url}")
        if not await check_a2a_server_availability(tool_provider_url):
            logger.error("❌ Cannot connect to tool provider agent.")
            logger.error(f"   Expected tool provider at: {tool_provider_url}")
            logger.error("   Please ensure multi_agent_2_tool_provider_agent.py is running.")
            return
        
        # Discover skills from tool provider
        logger.info("🔍 Discovering skills from tool provider...")
        proxy_skills, tool_provider_client = await discover_and_proxy_skills(tool_provider_url)
        
        if not proxy_skills:
            logger.error("❌ No skills discovered from tool provider")
            return
        
        # Add a general chat skill for non-tool requests
        proxy_skills.append({
            "name": "general_chat",
            "description": "Handle general questions and conversations",
            "parameters": [
                {
                    "name": "message",
                    "description": "The user's message",
                    "type": "string",
                    "required": True
                }
            ]
        })
        
        # Agent details
        agent_name = "Tool Consumer Agent"
        agent_description = f"""A2A agent that consumes tools from other agents.

This agent can:
- Use tools provided by the Tool Provider Agent
- Handle general conversations
- Delegate tool requests to the appropriate agent

Available proxied skills: {', '.join(skill['name'] for skill in proxy_skills if skill['name'] != 'general_chat')}

IMPORTANT INSTRUCTIONS:
- When users ask for calculations, weather, or leave management tasks, delegate to the tool provider
- For general questions, respond directly
- Always try to use the appropriate tool when available
- For leave-related queries (balance, history, applications), use the leave management tools
- For weather queries, use the weather tool
- For math calculations, use the calculation tool"""
        
        # Create A2A server with proxy skills
        logger.info(f"🏗️  Creating A2A server: {agent_name}")
        consumer_server = A2AServer(
            model=args.model,
            name=agent_name,
            description=agent_description,
            skills=proxy_skills,
            port=args.port,
            endpoint=consumer_url
        )
        
        # Configure tool delegation
        logger.info("🔧 Configuring tool delegation to provider agent")
        delegation_handler = ToolDelegationHandler(tool_provider_client, proxy_skills)
        
        # Monkey patch the A2A agent to handle delegation
        original_process_task = consumer_server.a2a_ollama._process_task
        
        async def delegating_process_task(task_id: str):
            """Custom task processor that delegates tool requests."""
            # Get the user message from the task
            task = consumer_server.a2a_ollama.task_manager.get_task(task_id)
            if not task:
                logger.error(f"❌ Task {task_id} not found")
                return await original_process_task(task_id)
            
            # Get the latest user message
            messages = consumer_server.a2a_ollama.message_handler.get_messages(task_id)
            if not messages:
                logger.error(f"❌ No messages found for task {task_id}")
                return await original_process_task(task_id)
            
            # Find the latest user message
            user_message = None
            for msg in reversed(messages):
                if msg.get('role') == 'user':
                    for part in msg.get('parts', []):
                        if part.get('type') == 'text' and part.get('content'):
                            user_message = part['content']
                            break
                    if user_message:
                        break
            
            if not user_message:
                logger.error(f"❌ No user message found for task {task_id}")
                return await original_process_task(task_id)
            
            logger.info(f"🎯 Processing task: {user_message}")
            
            # Check if we should delegate this request
            if delegation_handler.should_delegate(user_message):
                logger.info("🚀 Delegating to tool provider agent")
                delegated_response = delegation_handler.delegate_to_tool_provider(user_message)
                
                # Use LLM to format the tool response into a natural human response
                logger.info("🧠 Using LLM to format tool response for user")
                formatted_response = await consumer_server.a2a_ollama._format_tool_response_with_llm(
                    user_message, delegated_response
                )
                
                # Create A2A response message
                message_id = str(uuid.uuid4())
                a2a_message = {
                    "id": message_id,
                    "role": "agent",
                    "parts": [
                        {
                            "type": "text",
                            "content": formatted_response
                        }
                    ]
                }
                
                # Add the message to the task
                consumer_server.a2a_ollama.message_handler.add_message(task_id, a2a_message)
                consumer_server.a2a_ollama.task_manager.update_task_status(task_id, "completed")
                
                return {
                    "task_id": task_id,
                    "message_id": message_id,
                    "status": "completed",
                    "message": a2a_message
                }
            else:
                # Use the original LLM processing for general chat
                logger.info("💬 Using LLM for general conversation")
                return await original_process_task(task_id)
        
        # Replace the _process_task method with our delegating version
        consumer_server.a2a_ollama._process_task = delegating_process_task
        
        # Add LLM response formatting method to the consumer server
        async def _format_tool_response_with_llm(self, user_question, tool_response):
            """Use LLM to format tool responses into natural human language."""
            try:
                # Create a prompt for the LLM to format the response
                format_prompt = f"""You are a helpful assistant. A user asked: "{user_question}"

The tools provided this result: {tool_response}

Please provide a natural, human-friendly response to the user based on this tool result. Be conversational and helpful.

Response:"""

                # Use Ollama to generate a natural response
                ollama_response = self.client.chat(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that formats tool results into natural conversation responses."
                        },
                        {
                            "role": "user", 
                            "content": format_prompt
                        }
                    ]
                )
                
                formatted_content = ollama_response.get("message", {}).get("content", "")
                if formatted_content:
                    return formatted_content
                else:
                    # Fallback to the original tool response if LLM fails
                    return tool_response
                    
            except Exception as e:
                logger.error(f"❌ LLM formatting failed: {e}")
                return tool_response
        
        # Bind the method to the consumer server's A2A instance
        consumer_server.a2a_ollama._format_tool_response_with_llm = _format_tool_response_with_llm.__get__(
            consumer_server.a2a_ollama, consumer_server.a2a_ollama.__class__
        )
        
        # Start the consumer server
        logger.info(f"🚀 Starting A2A consumer server at {consumer_url}")
        await consumer_server.start()
        
        # Server is ready
        logger.info("✅ A2A Tool Consumer Agent is running!")
        logger.info(f"📍 Consumer Server URL: {consumer_url}")
        logger.info(f"🔗 Connected to Tool Provider: {tool_provider_url}")
        logger.info(f"🛠️  Available Proxy Skills: {', '.join(skill['name'] for skill in proxy_skills)}")
        logger.info("💡 This agent will delegate tool requests to the tool provider")
        logger.info("⏹️  Press Ctrl+C to stop the agent")
        
        # Test the connection by running some sample queries
        # logger.info("\n" + "=" * 60)
        # logger.info("🧪 Testing Consumer Agent")
        # logger.info("=" * 60)
        
        # Create a test client
        # test_client = A2AClient(endpoint=consumer_url)
        
        # Test queries
        # test_queries = [
        #     # "What's the weather like in Tokyo?",
        #     # "Calculate 15 * 8 + 32",
        #     "What's the leave balance for Raghu?"
        #     # "Hello, how are you today?"
        # ]
        
        # for query in test_queries:
        #     logger.info(f"\n🔍 Testing: {query}")
        #     try:
        #         response = test_client.chat(query)
        #         if "message" in response:
        #             for part in response["message"]["parts"]:
        #                 if part["type"] == "text" and part["content"]:
        #                     logger.info(f"✅ Response: {part['content']}")
        #                 else:
        #                     logger.warning(f"⚠️  Empty response: {response}")
        #         else:
        #             logger.warning(f"⚠️  Unexpected response format: {response}")
        #     except Exception as e:
        #         logger.error(f"❌ Test failed: {e}")
        
        # logger.info("\n" + "=" * 60)
        # logger.info("🎯 Consumer agent is ready for use!")
        # logger.info("=" * 60)
        
        # Keep server running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown signal received")
    except Exception as e:
        logger.error(f"❌ Consumer agent error: {e}")
        import traceback
        logger.debug("Error details:")
        logger.debug(traceback.format_exc())
        raise
    finally:
        # Cleanup
        if consumer_server:
            logger.info("🔄 Shutting down consumer server...")
            await consumer_server.stop()
            logger.info("✅ Consumer server stopped")
        if tool_provider_client:
            logger.info("🔄 Cleaning up tool provider client...")
            # A2AClient doesn't have a disconnect method, so we just log the cleanup
            logger.info("✅ Tool provider client cleanup completed")


if __name__ == "__main__":
    asyncio.run(main())