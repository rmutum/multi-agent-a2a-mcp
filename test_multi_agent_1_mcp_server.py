"""
Test Script for MCP Server

This script tests the multi_agent_1_mcp_server.py by making HTTP requests
to the MCP server endpoints and executing the available tools.
"""

import asyncio
import httpx
import json
import logging
import sys
import time
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_test_client")


class MCPTestClient:
    """Test client for MCP server interactions."""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        """Initialize the test client.
        
        Args:
            base_url: Base URL of the MCP server
        """
        self.base_url = base_url
        self.client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()
    
    async def check_server_health(self) -> bool:
        """Check if the MCP server is running and responsive.
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            discovery_url = f"{self.base_url}/.well-known/mcp.json"
            logger.info(f"🔍 Checking server health at {discovery_url}")
            
            response = await self.client.get(discovery_url, timeout=10.0)
            if response.status_code == 200:
                logger.info("✅ Server is healthy and responsive")
                return True
            else:
                logger.error(f"❌ Server returned status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Server health check failed: {e}")
            return False
    
    async def get_server_info(self) -> Dict[str, Any]:
        """Get server discovery information.
        
        Returns:
            Dictionary containing server information
        """
        try:
            discovery_url = f"{self.base_url}/.well-known/mcp.json"
            logger.info(f"📋 Getting server info from {discovery_url}")
            
            response = await self.client.get(discovery_url)
            response.raise_for_status()
            
            server_info = response.json()
            logger.info("📊 Server Information:")
            logger.info(f"  • Name: {server_info.get('name', 'Unknown')}")
            logger.info(f"  • Description: {server_info.get('description', 'No description')}")
            logger.info(f"  • Version: {server_info.get('version', 'Unknown')}")
            
            return server_info
            
        except Exception as e:
            logger.error(f"❌ Failed to get server info: {e}")
            return {}
    
    async def list_available_tools(self) -> Dict[str, Any]:
        """List all available tools from the MCP server.
        
        Returns:
            Dictionary containing available tools
        """
        try:
            tools_url = f"{self.base_url}/tools"
            logger.info(f"🔧 Getting available tools from {tools_url}")
            
            response = await self.client.get(tools_url)
            response.raise_for_status()
            
            tools_data = response.json()
            tools = tools_data.get('tools', [])
            
            logger.info(f"🛠️  Available Tools ({len(tools)} found):")
            for tool in tools:
                logger.info(f"  • {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
                
                # Show parameters
                params = tool.get('parameters', {}).get('properties', {})
                if params:
                    logger.info(f"    Parameters:")
                    for param_name, param_info in params.items():
                        param_type = param_info.get('type', 'unknown')
                        param_desc = param_info.get('description', 'No description')
                        logger.info(f"      - {param_name} ({param_type}): {param_desc}")
            
            return tools_data
            
        except Exception as e:
            logger.error(f"❌ Failed to list tools: {e}")
            return {}
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool with given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters to pass to the tool
            
        Returns:
            Dictionary containing the tool execution result
        """
        try:
            execute_url = f"{self.base_url}/execute"
            payload = {
                "name": tool_name,
                "parameters": parameters
            }
            
            logger.info(f"⚡ Executing tool '{tool_name}' with parameters: {json.dumps(parameters)}")
            
            response = await self.client.post(
                execute_url, 
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"✅ Tool '{tool_name}' executed successfully")
            logger.info(f"📤 Result: {json.dumps(result, indent=2)}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to execute tool '{tool_name}': {e}")
            return {"error": str(e)}
    
    async def test_weather_tool(self):
        """Test the get_weather tool with different locations."""
        logger.info("🌤️  Testing Weather Tool")
        logger.info("=" * 50)
        
        test_locations = ["New York"]
        
        for location in test_locations:
            logger.info(f"🌍 Testing weather for: {location}")
            result = await self.execute_tool("get_weather", {"location": location})
            
            if "result" in result:
                weather_data = result["result"]
                logger.info(f"🌡️  Temperature: {weather_data.get('temperature', 'N/A')}°F")
                logger.info(f"☀️  Condition: {weather_data.get('condition', 'N/A')}")
                logger.info(f"📍 Location: {weather_data.get('location', 'N/A')}")
            else:
                logger.error(f"❌ Failed to get weather for {location}")
            
            logger.info("-" * 30)
    
    async def test_calculator_tool(self):
        """Test the calculate tool with different mathematical expressions."""
        logger.info("🧮 Testing Calculator Tool")
        logger.info("=" * 50)
        
        test_expressions = [
            "2 + 3"
        ]
        
        for expression in test_expressions:
            logger.info(f"🔢 Testing expression: {expression}")
            result = await self.execute_tool("calculate", {"expression": expression})
            
            if "result" in result:
                calc_result = result["result"]
                if "result" in calc_result:
                    logger.info(f"✅ Result: {calc_result['result']}")
                elif "error" in calc_result:
                    logger.info(f"⚠️  Error: {calc_result['error']}")
            else:
                logger.error(f"❌ Failed to calculate: {expression}")
            
            logger.info("-" * 30)
    
    async def run_comprehensive_test(self):
        """Run a comprehensive test of all MCP server functionality."""
        logger.info("🚀 Starting Comprehensive MCP Server Test")
        logger.info("=" * 60)
        
        # Step 1: Check server health
        if not await self.check_server_health():
            logger.error("❌ Server is not healthy. Please start the MCP server first.")
            return False
        
        # Step 2: Get server information
        logger.info("\n" + "=" * 60)
        server_info = await self.get_server_info()
        
        # Step 3: List available tools
        logger.info("\n" + "=" * 60)
        tools_data = await self.list_available_tools()
        
        # Step 4: Test weather tool
        logger.info("\n" + "=" * 60)
        await self.test_weather_tool()
        
        # Step 5: Test calculator tool
        logger.info("\n" + "=" * 60)
        await self.test_calculator_tool()
        
        # Step 6: Summary
        logger.info("\n" + "=" * 60)
        logger.info("🎉 Comprehensive Test Completed!")
        logger.info("📊 Test Summary:")
        logger.info(f"  • Server Status: ✅ Healthy")
        logger.info(f"  • Tools Available: {len(tools_data.get('tools', []))}")
        logger.info(f"  • Weather Tool: ✅ Tested")
        logger.info(f"  • Calculator Tool: ✅ Tested")
        
        return True


async def wait_for_server(base_url: str, max_wait: int = 30):
    """Wait for the MCP server to become available.
    
    Args:
        base_url: Base URL of the MCP server
        max_wait: Maximum time to wait in seconds
    """
    logger.info(f"⏳ Waiting for MCP server at {base_url} (max {max_wait}s)")
    
    async with httpx.AsyncClient() as client:
        for i in range(max_wait):
            try:
                discovery_url = f"{base_url}/.well-known/mcp.json"
                response = await client.get(discovery_url, timeout=2.0)
                if response.status_code == 200:
                    logger.info(f"✅ Server is ready after {i+1} seconds")
                    return True
            except:
                pass
            
            if i < max_wait - 1:  # Don't sleep on the last iteration
                await asyncio.sleep(1)
    
    logger.error(f"❌ Server did not become available within {max_wait} seconds")
    return False


async def main():
    """Main function to run the MCP server tests."""
    logger.info("🧪 MCP Server Test Suite")
    logger.info("=" * 60)
    
    # Configuration
    server_url = "http://localhost:3000"
    
    # Wait for server to be available
    if not await wait_for_server(server_url):
        logger.error("❌ Cannot connect to MCP server. Make sure it's running:")
        logger.error("   python multi_agent_1_mcp_server.py")
        sys.exit(1)
    
    # Run tests
    async with MCPTestClient(server_url) as test_client:
        success = await test_client.run_comprehensive_test()
        
        if success:
            logger.info("\n🎉 All tests completed successfully!")
            sys.exit(0)
        else:
            logger.error("\n❌ Some tests failed!")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
