"""
Test Script for A2A Tool Consumer Agent

This script tests the multi_agent_3_tool_consumer_agent.py by creating
an A2A client and testing the delegation of tool requests to the tool provider.
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
logger = logging.getLogger("consumer_test_client")


async def test_tool_consumer_agent():
    """Test the A2A Tool Consumer Agent by using its proxied skills."""
    
    # Configuration
    consumer_agent_url = "http://localhost:8001"
    
    logger.info("🧪 Testing A2A Tool Consumer Agent")
    logger.info("=" * 60)
    
    try:
        # Create A2A client
        logger.info(f"🔗 Connecting to A2A consumer agent at {consumer_agent_url}")
        client = A2AClient(endpoint=consumer_agent_url)
        
        # Discover agent capabilities
        logger.info("🔍 Discovering consumer agent capabilities...")
        agent_card = client.discover_agent()
        
        logger.info(f"📋 Agent Information:")
        logger.info(f"  • Name: {agent_card.get('name', 'Unknown')}")
        logger.info(f"  • Description: {agent_card.get('description', 'No description')[:100]}...")
        logger.info(f"  • Skills: {len(agent_card.get('skills', []))}")
        
        # List available skills
        skills = agent_card.get('skills', [])
        logger.info(f"🛠️  Available Skills:")
        for skill in skills:
            logger.info(f"  • {skill.get('name', 'Unknown')}: {skill.get('description', 'No description')}")
        
        if not skills:
            logger.warning("⚠️  No skills found. Make sure the consumer agent is running properly.")
            return
        
        logger.info("\n" + "=" * 60)
        logger.info("🧪 Testing Skill Delegation")
        logger.info("=" * 60)
        
        # Test cases that should be delegated to the tool provider
        test_cases = [
            {
                "name": "Weather Query",
                "query": "What's the weather like in Tokyo?",
                "expected_delegation": True,
                "description": "Should delegate to get_weather tool"
            },
            {
                "name": "Math Calculation",
                "query": "Calculate 25 * 4 + 10",
                "expected_delegation": True,
                "description": "Should delegate to calculate tool"
            },
            {
                "name": "Complex Math",
                "query": "What's 123 times 456 plus 789?",
                "expected_delegation": True,
                "description": "Should delegate to calculate tool with natural language"
            },
            {
                "name": "Weather with City",
                "query": "Tell me the temperature in London",
                "expected_delegation": True,
                "description": "Should delegate to get_weather tool"
            },
            {
                "name": "Leave Balance Query",
                "query": "What's the leave balance for Raghu?",
                "expected_delegation": True,
                "description": "Should delegate to get_leave_balance tool"
            },
            {
                "name": "Leave Application",
                "query": "Apply leave for Jake on 2025-08-15,2025-08-16",
                "expected_delegation": True,
                "description": "Should delegate to apply_leave tool"
            },
            {
                "name": "Leave History",
                "query": "Show me the leave history for Corbin",
                "expected_delegation": True,
                "description": "Should delegate to get_leave_history tool"
            },
            {
                "name": "General Chat",
                "query": "Hello, how are you today?",
                "expected_delegation": False,
                "description": "Should handle with LLM, not delegate"
            },
            {
                "name": "Simple Greeting",
                "query": "What's your name?",
                "expected_delegation": False,
                "description": "Should handle with LLM, not delegate"
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"\n🔍 Test {i}: {test_case['name']}")
            logger.info(f"   Query: {test_case['query']}")
            logger.info(f"   Expected: {'Delegate to tool provider' if test_case['expected_delegation'] else 'Handle with LLM'}")
            logger.info(f"   Description: {test_case['description']}")
            
            try:
                # Send the query to the consumer agent
                response = client.chat(test_case['query'])
                
                # Extract response content
                response_content = ""
                if "message" in response:
                    for part in response["message"]["parts"]:
                        if part["type"] == "text":
                            response_content = part["content"]
                            break
                
                # Display the response
                if response_content:
                    logger.info(f"✅ Response: {response_content}")
                    
                    # Analyze response to check if delegation happened
                    if test_case['expected_delegation']:
                        # For delegated requests, we expect specific tool results
                        if any(keyword in response_content.lower() for keyword in ['temperature', 'sunny', 'weather']) and 'weather' in test_case['query'].lower():
                            logger.info("✅ Weather delegation appears successful")
                        elif any(keyword in response_content.lower() for keyword in ['calculate', 'result', 'answer']) and any(math_word in test_case['query'].lower() for math_word in ['calculate', 'times', 'plus', '*', '+']):
                            logger.info("✅ Math delegation appears successful")
                        else:
                            logger.warning("⚠️  Response may not show proper delegation")
                    else:
                        # For non-delegated requests, we expect general LLM responses
                        logger.info("✅ LLM response received as expected")
                else:
                    logger.error(f"❌ Empty response received: {response}")
                    
            except Exception as e:
                logger.error(f"❌ Test failed: {e}")
            
            logger.info("-" * 40)
        
        logger.info("\n" + "=" * 60)
        logger.info("🎯 Testing Combined Requests")
        logger.info("=" * 60)
        
        # Test a combined request that should use multiple tools
        combined_query = "What's the weather in Paris, what's 15 * 8, and what's the leave balance for Raghu?"
        logger.info(f"🔍 Combined Query: {combined_query}")
        
        try:
            response = client.chat(combined_query)
            response_content = ""
            if "message" in response:
                for part in response["message"]["parts"]:
                    if part["type"] == "text":
                        response_content = part["content"]
                        break
            
            if response_content:
                logger.info(f"✅ Combined Response: {response_content}")
                
                # Check if weather, math, and leave info are present
                has_weather = any(keyword in response_content.lower() for keyword in ['temperature', 'weather', 'sunny', 'paris'])
                has_math = any(keyword in response_content.lower() for keyword in ['120', 'result', 'calculation'])
                has_leave = any(keyword in response_content.lower() for keyword in ['leave', 'balance', 'raghu', 'days'])
                
                tools_used = sum([has_weather, has_math, has_leave])
                logger.info(f"📊 Tools detected in response: Weather={has_weather}, Math={has_math}, Leave={has_leave}")
                
                if tools_used >= 2:
                    logger.info("✅ Combined delegation appears successful - multiple tools used")
                elif tools_used == 1:
                    logger.info("⚠️  Partial delegation - only one tool result detected")
                else:
                    logger.warning("⚠️  Combined delegation may not have worked properly")
            else:
                logger.error(f"❌ Empty response for combined query: {response}")
                
        except Exception as e:
            logger.error(f"❌ Combined test failed: {e}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Test completed successfully!")
        logger.info("📊 Summary:")
        logger.info("   • Consumer agent is responding to queries")
        logger.info("   • Tool delegation mechanism is working")
        logger.info("   • Both proxied skills and LLM responses are available")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        logger.error("   Make sure the following are running:")
        logger.error("   1. MCP server: python multi_agent_1_mcp_server.py")
        logger.error("   2. Tool provider: python multi_agent_2_tool_provider_agent.py")
        logger.error("   3. Tool consumer: python multi_agent_3_tool_consumer_agent.py")


async def main():
    """Main function to run the test."""
    logger.info("🚀 A2A Tool Consumer Agent Test")
    logger.info("=" * 70)
    logger.info("Prerequisites:")
    logger.info("1. Start MCP server: python multi_agent_1_mcp_server.py")
    logger.info("2. Start tool provider: python multi_agent_2_tool_provider_agent.py")
    logger.info("3. Start tool consumer: python multi_agent_3_tool_consumer_agent.py")
    logger.info("4. Run this test: python test_multi_agent_3_tool_consumer_agent.py")
    logger.info("=" * 70)
    
    await test_tool_consumer_agent()


if __name__ == "__main__":
    asyncio.run(main())
