"""
Test Script for A2A Tool Provider Agent

This script tests the multi_agent_2_tool_provider_agent.py by creating
an A2A client and using the available skills (MCP tools exposed as A2A skills).
"""

import asyncio
import logging
import sys
import os

# Add the parent directory to sys.path for local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from a2a.client import A2AClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("a2a_test_client")


async def test_tool_provider_agent():
    """Test the A2A Tool Provider Agent by using its skills."""
    
    # Configuration
    agent_url = "http://localhost:8000"
    
    # logger.info("🧪 Testing A2A Tool Provider Agent")
    # logger.info("=" * 50)
    
    try:
        # Create A2A client
        logger.info(f"🔗 Connecting to A2A agent at {agent_url}")
        client = A2AClient(endpoint=agent_url)
        
        # Discover agent capabilities
        logger.info("🔍 Discovering agent capabilities...")
        agent_card = client.discover_agent()
        
        # logger.info(f"📋 Agent Information:")
        # logger.info(f"  • Name: {agent_card.get('name', 'Unknown')}")
        # logger.info(f"  • Description: {agent_card.get('description', 'No description')}")
        # logger.info(f"  • Skills: {len(agent_card.get('skills', []))}")
        
        # List available skills
        skills = agent_card.get('skills', [])
        logger.info(f"🛠️  Available Skills:")
        for skill in skills:
            logger.info(f"  • {skill.get('name', 'Unknown')}: {skill.get('description', 'No description')}")
        
        if not skills:
            logger.warning("⚠️  No skills found. Make sure the tool provider agent is running.")
            return
        
        logger.info("\n" + "=" * 50)
        logger.info("🧪 Testing Skills")
        logger.info("=" * 50)
        
        # Test weather skill
        logger.info("🌤️  Testing Weather Skill")
        try:
            weather_response = client.chat("What's the weather like in Tokyo?")
            logger.info(f"🌍 Weather Response:")
            logger.info(f"  {weather_response}")
            if "message" in weather_response:
                for part in weather_response["message"]["parts"]:
                    if part["type"] == "text":
                        logger.info(f"  {part['content']}")
            else:
                logger.info(f"  {weather_response}")
        except Exception as e:
            logger.error(f"❌ Weather test failed: {e}")
        
        logger.info("-" * 30)
        
        # Test calculator skill
        logger.info("🧮 Testing Calculator Skill")
        try:
            calc_response = client.chat("Use MCP tools to calculate 25 * 4 + 10")
            logger.info(f"🔢 Calculator Response:")
            logger.info(f"  {calc_response}")
            if "message" in calc_response:
                for part in calc_response["message"]["parts"]:
                    if part["type"] == "text":
                        logger.info(f"  {part['content']}")
            else:
                logger.info(f"  {calc_response}")
        except Exception as e:
            logger.error(f"❌ Calculator test failed: {e}")
        
        logger.info("-" * 30)
        
        # Test combined request
        # logger.info("🔄 Testing Combined Request")
        # try:
        #     combined_response = client.chat("What's the weather in London and what's 15 * 8?")
        #     logger.info(f"🔗 Combined Response:")
        #     if "message" in combined_response:
        #         for part in combined_response["message"]["parts"]:
        #             if part["type"] == "text":
        #                 logger.info(f"  {part['content']}")
        #     else:
        #         logger.info(f"  {combined_response}")
        # except Exception as e:
        #     logger.error(f"❌ Combined test failed: {e}")
        
        # logger.info("\n" + "=" * 50)
        # logger.info("✅ Test completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        logger.error("   Make sure multi_agent_2_tool_provider_agent.py is running on localhost:8000")
        logger.error("   And that multi_agent_1_mcp_server.py is running on localhost:3000")


async def main():
    """Main function to run the test."""
    logger.info("🚀 A2A Tool Provider Agent Test")
    logger.info("=" * 60)
    logger.info("Prerequisites:")
    logger.info("1. Start MCP server: python multi_agent_1_mcp_server.py")
    logger.info("2. Start A2A agent: python multi_agent_2_tool_provider_agent.py")
    logger.info("3. Run this test: python test_multi_agent_2_tool_provider.py")
    logger.info("=" * 60)
    
    await test_tool_provider_agent()


if __name__ == "__main__":
    asyncio.run(main())
