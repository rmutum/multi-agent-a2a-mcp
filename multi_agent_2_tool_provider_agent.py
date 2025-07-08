"""
A2A Tool Provider Agent with MCP Integration

This example demonstrates an A2A agent that connects to an MCP server
(multi_agent_1_mcp_server.py) and exposes the available MCP tools as its own skills.

The agent acts as a bridge between A2A and MCP protocols, allowing other A2A
agents to use MCP tools through standard A2A communication.

Prerequisites:
- Run multi_agent_1_mcp_server.py first to start the MCP server
- MCP server should be running on localhost:3000 (default)
"""

import os
import sys
import asyncio
import argparse
import httpx
import logging
import re

# Add the parent directory to sys.path for local imports
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from a2a.server import A2AServer
from a2a.core.a2a_ollama import A2AOllama
from a2a.core.mcp.mcp_client import MCPClient
from a2a.core.a2a_mcp_bridge import A2AMCPBridge


def configure_logging(log_level="INFO"):
    """Configure logging with appropriate level and format.
    
    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Logger instance for the tool provider agent
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # Configure specific loggers for better debugging
    loggers = [
        "mcp_client", 
        "a2a_mcp_bridge",
        "a2a_server",
        "tool_provider_agent"
    ]
    for logger_name in loggers:
        logging.getLogger(logger_name).setLevel(numeric_level)
    
    return logging.getLogger("tool_provider_agent")


async def check_mcp_server_availability(url, max_retries=5, retry_delay=2):
    """Check if the MCP server is available and responding.
    
    Args:
        url: The MCP server discovery URL to check
        max_retries: Maximum number of retry attempts (default: 5)
        retry_delay: Delay between retries in seconds (default: 2)
        
    Returns:
        True if MCP server is available, False otherwise
    """
    logger = logging.getLogger("mcp_check")
    async with httpx.AsyncClient() as client:
        for i in range(max_retries):
            try:
                logger.info(f"🔍 Checking MCP server: {url} (Attempt {i+1}/{max_retries})")
                response = await client.get(url, timeout=10.0)
                if response.status_code == 200:
                    logger.info("✅ MCP server is available and responding")
                    return True
                else:
                    logger.warning(f"⚠️  MCP server returned status {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️  MCP server check failed: {e}")
            
            if i < max_retries - 1:  # Don't sleep on the last attempt
                logger.info(f"⏳ Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
        
        logger.error("❌ MCP server is not available")
        return False


async def main():
    """Main function to run the A2A Tool Provider Agent."""
    parser = argparse.ArgumentParser(description="A2A Tool Provider Agent with MCP Integration")
    parser.add_argument("--host", type=str, default="localhost", 
                       help="Host to run the A2A server on")
    parser.add_argument("--port", type=int, default=8000,
                       help="Port to run the A2A server on")
    parser.add_argument("--mcp-host", type=str, default="localhost",
                       help="Host of the MCP server")
    parser.add_argument("--mcp-port", type=int, default=3000,
                       help="Port of the MCP server")
    parser.add_argument("--model", type=str, default="llama3.1:8b",
                       help="Ollama model to use for the agent")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="Set logging level")
    
    args = parser.parse_args()
    
    # Initialize logging
    logger = configure_logging(args.log_level)
    logger.info("🚀 Starting A2A Tool Provider Agent with MCP Integration")
    
    # Initialize variables for cleanup
    a2a_server = None
    mcp_client = None
    
    try:
        # Check if MCP server is available
        mcp_server_url = f"http://{args.mcp_host}:{args.mcp_port}"
        discovery_url = f"{mcp_server_url}/.well-known/mcp.json"
        
        logger.info(f"🔗 Connecting to MCP server at {mcp_server_url}")
        if not await check_mcp_server_availability(discovery_url):
            logger.error("❌ Cannot connect to MCP server. Please ensure multi_agent_1_mcp_server.py is running.")
            logger.error(f"   Expected MCP server at: {mcp_server_url}")
            return
        
        # Create MCP client
        logger.info("🔌 Creating MCP client connection")
        mcp_client = MCPClient(server_url=mcp_server_url)
        
        # Connect to MCP server and discover tools
        logger.info("🔍 Connecting to MCP server and discovering tools")
        server_info = await mcp_client.connect()
        logger.info(f"📡 Connected to: {server_info.get('name', 'Unknown MCP Server')}")
        
        # Get available MCP tools
        tools = await mcp_client.list_tools()
        logger.info(f"🛠️  Discovered {len(tools)} MCP tools:")
        for tool in tools:
            logger.info(f"   • {tool.name}: {tool.description}")
        
        if not tools:
            logger.warning("⚠️  No tools found on MCP server")
            return
        
        # Create A2A-MCP bridge
        logger.info("🌉 Creating A2A-MCP bridge")
        bridge = A2AMCPBridge(mcp_client=mcp_client)
        
        # Convert MCP tools to A2A skills
        logger.info("⚙️  Converting MCP tools to A2A skills")
        skills = []
        for tool in tools:
            # Convert MCP tool parameters to A2A skill parameters
            skill_parameters = []
            if hasattr(tool, 'parameters') and tool.parameters:
                for param in tool.parameters:
                    skill_param = {
                        "name": getattr(param, "name", ""),
                        "description": getattr(param, "description", ""),
                        "type": getattr(param, "type", "string"),
                        "required": getattr(param, "required", False)
                    }
                    skill_parameters.append(skill_param)
            
            skill = {
                "name": tool.name,
                "description": tool.description,
                "parameters": skill_parameters
            }
            skills.append(skill)
            logger.info(f"   ✅ Converted '{tool.name}' to A2A skill")
        
        # Define agent details
        agent_name = "MCP Tool Provider Agent"
        agent_description = f"""A2A agent providing {len(skills)} tools from MCP server.

IMPORTANT INSTRUCTIONS:
- You are an agent who is allowed to use MCP tools that have been exposed as skills
- When users ask to "calculate" or perform any mathematical calculation, you MUST use the calculate tool
- When users ask for weather information, you MUST use the get_weather tool
- When users ask for leave balance of an employee, you MUST use the get_leave_balance tool
- get_leave_history and apply_leave tools are also available for leave management
- When users ask for leave history, you MUST use the get_leave_history tool
- When users ask to apply leave, you MUST use the apply_leave tool
- DO NOT use your LLM capabilities to perform calculations - always delegate to the appropriate MCP tool
- Your role is to identify when tools should be used and execute them, not to perform the tasks yourself
- Always use the available tools when the user's request matches their functionality
- When using tools, always mention that you are using the MCP tool to provide accurate results"""
        
        # Create A2A server
        logger.info(f"🏗️  Creating A2A server: {agent_name}")
        a2a_server = A2AServer(
            model=args.model,
            name=agent_name,
            description=agent_description,
            skills=skills,
            port=args.port,
            endpoint=f"http://{args.host}:{args.port}"
        )
        
        # Configure MCP integration on the server's agent
        logger.info("🔗 Configuring MCP integration on A2A server's agent")
        
        # Enable MCP in the task manager
        if hasattr(a2a_server.a2a_ollama, 'task_manager') and a2a_server.a2a_ollama.task_manager:
            logger.info("🔧 Enabling MCP in server's task manager")
            a2a_server.a2a_ollama.task_manager.enable_mcp(bridge)
        
        # Configure MCP client directly on the server's agent
        if hasattr(a2a_server.a2a_ollama, 'configure_mcp_client'):
            logger.info("🔌 Configuring MCP client on server's A2A agent")
            a2a_server.a2a_ollama.configure_mcp_client(mcp_client)
        
        # Register MCP tools as A2A skills with the bridge
        logger.info("📝 Registering MCP tools as A2A skills with bridge")
        for tool in tools:
            try:
                logger.info(f"🔗 Registering MCP tool '{tool.name}' with bridge")
                await bridge.register_a2a_skill_for_mcp_tool(tool.name, tool.description)
                logger.info(f"✅ Successfully registered '{tool.name}'")
            except Exception as e:
                logger.warning(f"⚠️  Failed to register '{tool.name}': {e}")
        
        # Start the A2A server
        logger.info(f"🚀 Starting A2A server at http://{args.host}:{args.port}")
        await a2a_server.start()
        
        # Server is ready
        logger.info("✅ A2A Tool Provider Agent is running!")
        logger.info(f"📍 A2A Server URL: http://{args.host}:{args.port}")
        logger.info(f"🔗 Connected to MCP Server: {mcp_server_url}")
        logger.info(f"🛠️  Available Skills: {', '.join(skill['name'] for skill in skills)}")
        logger.info("💡 Other A2A agents can now use these tools by communicating with this agent")
        logger.info("⏹️  Press Ctrl+C to stop the agent")
        
        # Keep server running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown signal received")
    except Exception as e:
        logger.error(f"❌ Agent error: {e}")
        import traceback
        logger.debug("Error details:")
        logger.debug(traceback.format_exc())
        raise
    finally:
        # Cleanup
        if a2a_server:
            logger.info("🔄 Shutting down A2A server...")
            await a2a_server.stop()
            logger.info("✅ A2A server stopped")
        if mcp_client:
            logger.info("🔄 Cleaning up MCP client...")
            # Note: MCPClient doesn't have a disconnect method, so we just log the cleanup
            logger.info("✅ MCP client cleanup completed")


if __name__ == "__main__":
    asyncio.run(main()) 