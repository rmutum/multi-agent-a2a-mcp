"""
A2A Ollama Integration - Main Module

This module provides the main functionality for integrating Ollama with Google's A2A protocol.
"""

import json
import uuid
import time
import re
from typing import Dict, List, Optional, Union, Any, Generator, Iterator

import ollama
from ollama import Client

from a2a.core.agent_card import AgentCard
from a2a.core.task_manager import TaskManager
from a2a.core.message_handler import MessageHandler
from a2a.core.mcp.mcp_client import MCPClient


class A2AOllama:
    """
    Main class for A2A Ollama integration.
    
    This class integrates Ollama with the A2A protocol, allowing Ollama
    to communicate with other A2A-compatible agents.
    """
    
    def __init__(
        self,
        model: str,
        name: str,
        description: str,
        skills: List[Dict[str, Any]],
        host: str = "http://localhost:11434",
        endpoint: str = "http://localhost:8000",
    ):
        """
        Initialize A2AOllama.
        
        Args:
            model: The Ollama model to use
            name: The name of the agent
            description: A description of the agent
            skills: A list of skills the agent has
            host: The Ollama host URL
            endpoint: The endpoint where this agent is accessible
        """
        self.model = model
        self.client = Client(host=host)
        self.agent_card = AgentCard(
            name=name,
            description=description,
            endpoint=endpoint,
            skills=skills,
        )
        self.task_manager = TaskManager()
        self.message_handler = MessageHandler()
        self.mcp_client = None
    
    def configure_mcp_client(self, mcp_client: MCPClient) -> None:
        """
        Configure MCP client for tool access.
        
        Args:
            mcp_client: The MCP client
        """
        self.mcp_client = mcp_client
    
    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an incoming A2A request.
        
        Args:
            request: The A2A request
            
        Returns:
            The response to the request
        """
        method = request.get("method")
        
        if method == "discovery":
            return self.agent_card.to_dict()
        elif method == "create_task":
            task_id = self.task_manager.create_task(request.get("params", {}))
            return {"task_id": task_id}
        elif method == "get_task":
            task_id = request.get("params", {}).get("task_id")
            return self.task_manager.get_task(task_id)
        elif method == "add_message":
            task_id = request.get("params", {}).get("task_id")
            message = request.get("params", {}).get("message")
            return self.message_handler.add_message(task_id, message)
        elif method == "process_task":
            task_id = request.get("params", {}).get("task_id")
            import asyncio
            return asyncio.run(self._process_task(task_id))
        elif method == "process_task_stream":
            task_id = request.get("params", {}).get("task_id")
            return {"error": "Streaming not available via RPC, use HTTP streaming endpoint"}
        else:
            return {"error": f"Unknown method: {method}"}
    
    def _get_ollama_messages(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Convert A2A messages to Ollama message format.
        
        Args:
            task_id: The task ID
            
        Returns:
            List of messages in Ollama format
        """
        messages = self.message_handler.get_messages(task_id)
        ollama_messages = []
        
        for message in messages:
            content = ""
            for part in message.get("parts", []):
                if part.get("type") == "text":
                    content += part.get("content", "")
            
            ollama_messages.append({
                "role": message.get("role", "user"),
                "content": content
            })
            
        return ollama_messages
    
    async def _process_task(self, task_id: str) -> Dict[str, Any]:
        """
        Process a task using Ollama.
        
        Args:
            task_id: The ID of the task to process
            
        Returns:
            The result of processing the task
        """
        task = self.task_manager.get_task(task_id)
        
        if not task:
            return {"error": f"Task not found: {task_id}"}
        
        # Check if this is an MCP task
        if self.task_manager.mcp_bridge and self.task_manager._can_use_mcp_for_task(task):
            try:
                import asyncio
                return asyncio.run(self.task_manager.process_task(task_id))
            except Exception as e:
                print(f"Error processing MCP task: {e}")
                # Fall back to normal processing
        
        ollama_messages = self._get_ollama_messages(task_id)
        
        # Set up retry parameters
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                # Auto-detect if we should use MCP tools directly
                tool_results = []
                if self.mcp_client and self.mcp_client.available_tools:
                    # Get the latest user message to analyze
                    user_message = None
                    for msg in reversed(ollama_messages):
                        if msg.get("role") == "user":
                            user_message = msg.get("content", "")
                            break
                    
                    if user_message:
                        # Check if we should auto-execute tools
                        auto_tool_calls = self._should_use_mcp_tools(user_message)
                        if auto_tool_calls:
                            print(f"🔧 AUTO-DETECTED MCP TOOL CALLS: {[tc['name'] for tc in auto_tool_calls]}")
                            print(f"🎯 User message: '{user_message}'")
                            import asyncio
                            tool_results = await self._execute_auto_detected_tools(auto_tool_calls)
                            print(f"✅ MCP TOOL EXECUTION COMPLETED: {len(tool_results)} results")
                
                # Add available MCP tools to the system message if MCP is configured
                if self.mcp_client and self.mcp_client.available_tools:
                    # Check if we have a system message, if not add one
                    has_system_message = False
                    for msg in ollama_messages:
                        if msg.get("role") == "system":
                            has_system_message = True
                            # Add MCP tools to existing system message
                            msg["content"] += self._get_mcp_tools_description()
                            break
                            
                    if not has_system_message:
                        # Create a new system message with MCP tools
                        ollama_messages.insert(0, {
                            "role": "system",
                            "content": f"You are {self.agent_card.name}, {self.agent_card.description}. {self._get_mcp_tools_description()}"
                        })
                
                # If we already have tool results, format them directly instead of using LLM
                if tool_results:
                    print(f"🔍 TOOL RESULTS DEBUG: {len(tool_results)} results found")
                    for i, result in enumerate(tool_results):
                        print(f"   Result {i+1}: {result}")
                    
                    # Format tool results directly for the user
                    formatted_response = ""
                    for result in tool_results:
                        if result['error']:
                            formatted_response += f"Error executing {result['name']}: {result['error']}\n"
                        else:
                            tool_name = result['name']
                            tool_result = result['result']
                            
                            # Format specific tool results nicely
                            if tool_name == "add_numbers":
                                formatted_response += f"The sum is: {tool_result}\n"
                            elif tool_name == "multiply_numbers":
                                formatted_response += f"The product is: {tool_result}\n"
                            elif tool_name == "get_weather":
                                formatted_response += f"Weather information: {tool_result}\n"
                            else:
                                formatted_response += f"{tool_name} result: {tool_result}\n"
                    
                    print(f"🔍 FORMATTED RESPONSE: '{formatted_response}'")
                    
                    # Return the formatted response directly
                    response_content = formatted_response.strip()
                    
                else:
                    # No tool results, use LLM normally
                    print(f"🔍 OLLAMA MESSAGES DEBUG: {len(ollama_messages)} messages")
                    for i, msg in enumerate(ollama_messages):
                        print(f"   Message {i+1}: {msg['role']} - {msg['content'][:100]}...")
                    
                    response = self.client.chat(
                        model=self.model,
                        messages=ollama_messages
                    )
                    
                    print(f"🔍 OLLAMA RESPONSE DEBUG: {response}")
                    response_content = response.get("message", {}).get("content", "")
                print(f"🔍 RESPONSE CONTENT DEBUG: '{response_content}'")
                
                # Only look for additional tool calls if we didn't already execute tools and format a response
                if not tool_results and response_content:  # Only look for tool calls if we didn't already execute some
                    additional_tool_calls = self._extract_tool_calls(response_content)
                    
                    if additional_tool_calls and self.mcp_client:
                        # Execute the tool calls and append results
                        additional_tool_results = []
                        for tool_call in additional_tool_calls:
                            tool_name = tool_call.get("name")
                            parameters = tool_call.get("parameters", {})
                            
                            try:
                                import asyncio
                                result = await self.mcp_client.execute_tool(tool_name, parameters)
                                additional_tool_results.append({
                                    "name": tool_name,
                                    "result": result.result,
                                    "error": result.error
                                })
                            except Exception as e:
                                additional_tool_results.append({
                                    "name": tool_name,
                                    "result": None,
                                    "error": str(e)
                                })
                        
                        # Format the additional tool results
                        formatted_additional_response = ""
                        for result in additional_tool_results:
                            if result['error']:
                                formatted_additional_response += f"Error executing {result['name']}: {result['error']}\n"
                            else:
                                tool_name = result['name']
                                tool_result = result['result']
                                
                                # Format specific tool results nicely
                                if tool_name == "add_numbers":
                                    formatted_additional_response += f"The sum is: {tool_result}\n"
                                elif tool_name == "multiply_numbers":
                                    formatted_additional_response += f"The product is: {tool_result}\n"
                                elif tool_name == "get_weather":
                                    formatted_additional_response += f"Weather information: {tool_result}\n"
                                else:
                                    formatted_additional_response += f"{tool_name} result: {tool_result}\n"
                        
                        response_content = formatted_additional_response.strip()
                
                # Update task status
                self.task_manager.update_task_status(task_id, "completed")
                
                # Create A2A message from the response
                message_id = str(uuid.uuid4())
                a2a_message = {
                    "id": message_id,
                    "role": "agent",
                    "parts": [
                        {
                            "type": "text",
                            "content": response_content
                        }
                    ]
                }
                
                # Add the message to the task
                self.message_handler.add_message(task_id, a2a_message)
                
                return {
                    "task_id": task_id,
                    "message_id": message_id,
                    "status": "completed",
                    "message": a2a_message
                }
                
            except Exception as e:
                last_error = str(e)
                retry_count += 1
                print(f"Error processing task (attempt {retry_count}): {e}")
                time.sleep(1)  # Wait before retrying
        
        # If we get here, all retries failed
        self.task_manager.update_task_status(task_id, "failed")
        
        return {
            "task_id": task_id,
            "status": "failed",
            "error": last_error
        }
    
    def _extract_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract MCP tool calls from an Ollama response.
        
        Args:
            content: The response content
            
        Returns:
            List of extracted tool calls
        """
        tool_calls = []
        
        # Enhanced parsing for tool calls - handles multiple formats
        
        # Clean up the content first
        content = content.strip()
        
        # Pattern 1: Clean JSON format
        json_pattern = r'\{\s*"name"\s*:\s*"([^"]*)"\s*,\s*"parameters"\s*:\s*(\{[^}]*\})\s*\}'
        matches = re.finditer(json_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                tool_name = match.group(1)
                parameters_str = match.group(2)
                parameters = json.loads(parameters_str)
                
                tool_calls.append({
                    "name": tool_name,
                    "parameters": parameters
                })
            except Exception as e:
                print(f"Error parsing tool call (pattern 1): {e}")
        
        # Pattern 2: Handle cases where the entire response is JSON
        if not tool_calls:
            try:
                # Try to parse the entire content as JSON
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "name" in parsed:
                    tool_calls.append({
                        "name": parsed["name"],
                        "parameters": parsed.get("parameters", {})
                    })
            except:
                pass
        
        # Pattern 3: Look for simple patterns like "get_weather" with "location: Paris"
        if not tool_calls and self.mcp_client and self.mcp_client.available_tools:
            for tool_name in self.mcp_client.available_tools.keys():
                if tool_name.lower() in content.lower():
                    # Try to extract parameters based on tool type
                    if tool_name == "get_weather":
                        # Look for location mentions
                        location_patterns = [
                            r"weather\s+(?:in|for|at)\s+([A-Za-z\s]+?)(?:\?|\.|$|,)",
                            r"(?:location|city):\s*([A-Za-z\s]+?)(?:\?|\.|$|,|\n)",
                            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+weather"
                        ]
                        
                        for pattern in location_patterns:
                            match = re.search(pattern, content, re.IGNORECASE)
                            if match:
                                location = match.group(1).strip()
                                tool_calls.append({
                                    "name": "get_weather",
                                    "parameters": {"location": location}
                                })
                                break
                    
                    elif tool_name == "calculate":
                        # Look for mathematical expressions
                        math_patterns = [
                            r"calculate\s+([0-9+\-*/\(\)\s\.]+)",
                            r"(?:expression|calculation):\s*([0-9+\-*/\(\)\s\.]+)",
                            r"([0-9+\-*/\(\)\s\.]+)(?:\s*=|\s*equals?)"
                        ]
                        
                        for pattern in math_patterns:
                            match = re.search(pattern, content, re.IGNORECASE)
                            if match:
                                expression = match.group(1).strip()
                                tool_calls.append({
                                    "name": "calculate",
                                    "parameters": {"expression": expression}
                                })
                                break
        
        return tool_calls
        
    def _get_mcp_tools_description(self) -> str:
        """
        Get a description of available MCP tools.
        
        Returns:
            Description of MCP tools
        """
        if not self.mcp_client or not self.mcp_client.available_tools:
            return ""
            
        tools_description = "\n\n**IMPORTANT: You have access to the following tools. When users ask for functionality that these tools provide, you MUST use the tools instead of generating responses yourself.**\n\n"
        
        for name, tool in self.mcp_client.available_tools.items():
            tools_description += f"**{name}**: {tool.description}\n"
            
            if tool.parameters:
                tools_description += "  Parameters:\n"
                for param in tool.parameters:
                    required = " (required)" if param.required else ""
                    tools_description += f"  - {param.name}{required}: {param.description}\n"
                    
            tools_description += "\n"
            
        tools_description += """**TOOL USAGE RULES:**
1. When users ask for weather information, you MUST use the get_weather tool
2. When users ask for mathematical calculations, you MUST use the calculate tool
3. Always use tools when the user's request matches their functionality
4. To use a tool, respond with JSON in this exact format: {"name": "tool_name", "parameters": {"param1": "value1"}}
5. Do not add explanatory text before or after the JSON - just return the JSON

**Examples:**
- User asks "What's the weather in Paris?" → Response: {"name": "get_weather", "parameters": {"location": "Paris"}}
- User asks "Calculate 25 * 16" → Response: {"name": "calculate", "parameters": {"expression": "25 * 16"}}
"""
        
        return tools_description
        
    def _process_task_stream(self, task_id: str) -> Iterator[Dict[str, Any]]:
        """
        Process a task using Ollama with streaming.
        
        Args:
            task_id: The ID of the task to process
            
        Returns:
            Iterator of streaming chunks
        """
        task = self.task_manager.get_task(task_id)
        
        if not task:
            yield {
                "task_id": task_id,
                "error": f"Task not found: {task_id}",
                "done": True
            }
            return
            
        # If this is an MCP task, we don't support streaming yet
        if self.task_manager.mcp_bridge and self.task_manager._can_use_mcp_for_task(task):
            yield {
                "task_id": task_id,
                "error": "Streaming not supported for MCP tasks",
                "done": True
            }
            return
        
        ollama_messages = self._get_ollama_messages(task_id)
        
        # Update task status
        self.task_manager.update_task_status(task_id, "working")
        
        # Generate a message ID
        message_id = str(uuid.uuid4())
        
        # Initialize content buffer
        full_content = ""
        
        # Add available MCP tools to the system message if MCP is configured
        if self.mcp_client and self.mcp_client.available_tools:
            # Check if we have a system message, if not add one
            has_system_message = False
            for msg in ollama_messages:
                if msg.get("role") == "system":
                    has_system_message = True
                    # Add MCP tools to existing system message
                    msg["content"] += self._get_mcp_tools_description()
                    break
                    
            if not has_system_message:
                # Create a new system message with MCP tools
                ollama_messages.insert(0, {
                    "role": "system",
                    "content": f"You are {self.agent_card.name}, {self.agent_card.description}. {self._get_mcp_tools_description()}"
                })
        
        try:
            # Stream response from Ollama
            for chunk in self.client.chat(
                model=self.model,
                messages=ollama_messages,
                stream=True
            ):
                content = chunk.get("message", {}).get("content", "")
                
                if content:
                    full_content += content
                    
                    # Send chunk
                    yield {
                        "task_id": task_id,
                        "message_id": message_id,
                        "chunk": {
                            "type": "text",
                            "content": content
                        },
                        "done": False
                    }
        except Exception as e:
            # Handle error
            error_message = str(e)
            self.task_manager.update_task_status(task_id, "failed")
            
            yield {
                "task_id": task_id,
                "message_id": message_id,
                "error": error_message,
                "status": "failed",
                "done": True
            }
            return
        
        # Check for MCP tool calls in the response
        tool_calls = self._extract_tool_calls(full_content)
        
        if tool_calls and self.mcp_client:
            # Execute the tool calls and append results
            yield {
                "task_id": task_id,
                "message_id": message_id,
                "chunk": {
                    "type": "text",
                    "content": "\n\nExecuting tool calls..."
                },
                "done": False
            }
            
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                parameters = tool_call.get("parameters", {})
                
                try:
                    import asyncio
                    result = asyncio.run(self.mcp_client.execute_tool(tool_name, parameters))
                    tool_results.append({
                        "name": tool_name,
                        "result": result.result,
                        "error": result.error
                    })
                    
                    # Send a chunk with the tool result
                    yield {
                        "task_id": task_id,
                        "message_id": message_id,
                        "chunk": {
                            "type": "text",
                            "content": f"\nTool '{tool_name}' result: {json.dumps(result.result)}"
                        },
                        "done": False
                    }
                except Exception as e:
                    error_msg = str(e)
                    tool_results.append({
                        "name": tool_name,
                        "result": None,
                        "error": error_msg
                    })
                    
                    # Send a chunk with the tool error
                    yield {
                        "task_id": task_id,
                        "message_id": message_id,
                        "chunk": {
                            "type": "text",
                            "content": f"\nTool '{tool_name}' error: {error_msg}"
                        },
                        "done": False
                    }
            
            # Add the tool results to the messages
            ollama_messages.append({
                "role": "assistant",
                "content": full_content
            })
            
            # Add tool results message
            ollama_messages.append({
                "role": "system",
                "content": f"Tool results: {json.dumps(tool_results)}"
            })
            
            # Generate a final response that incorporates the tool results
            yield {
                "task_id": task_id,
                "message_id": message_id,
                "chunk": {
                    "type": "text",
                    "content": "\n\nGenerating final response with tool results..."
                },
                "done": False
            }
            
            final_content = ""
            try:
                # Stream final response
                for chunk in self.client.chat(
                    model=self.model,
                    messages=ollama_messages,
                    stream=True
                ):
                    content = chunk.get("message", {}).get("content", "")
                    
                    if content:
                        final_content += content
                        
                        # Send chunk
                        yield {
                            "task_id": task_id,
                            "message_id": message_id,
                            "chunk": {
                                "type": "text",
                                "content": content
                            },
                            "done": False
                        }
            except Exception as e:
                # Handle error in final response
                error_message = str(e)
                yield {
                    "task_id": task_id,
                    "message_id": message_id,
                    "chunk": {
                        "type": "text",
                        "content": f"\n\nError generating final response: {error_message}"
                    },
                    "done": False
                }
                
            # Update the full content to include the final response
            full_content += "\n\n" + final_content
        
        # Create the full A2A message
        a2a_message = {
            "id": message_id,
            "role": "agent",
            "parts": [
                {
                    "type": "text",
                    "content": full_content
                }
            ]
        }
        
        # Store the complete message
        self.message_handler.add_message(task_id, a2a_message)
        
        # Update task status
        self.task_manager.update_task_status(task_id, "completed")
        
        # Send final message
        yield {
            "task_id": task_id,
            "message_id": message_id,
            "status": "completed",
            "done": True,
            "message": a2a_message
        }
    
    def _should_use_mcp_tools(self, user_input: str) -> List[Dict[str, Any]]:
        """
        Analyze user input to determine if MCP tools should be used directly.
        
        Args:
            user_input: The user's input text
            
        Returns:
            List of tool calls that should be executed
        """
        if not self.mcp_client or not self.mcp_client.available_tools:
            return []
        
        tool_calls = []
        input_lower = user_input.lower()
        
        # Weather detection
        weather_keywords = ["weather", "temperature", "forecast", "climate"]
        location_patterns = [
            r"weather\s+(?:in|for|at)\s+([A-Za-z\s]+?)(?:\?|\.|$|,)",
            r"(?:in|for|at)\s+([A-Za-z\s]+?)(?:\s+weather|\?|\.|$)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+weather"
        ]
        
        if any(keyword in input_lower for keyword in weather_keywords):
            for pattern in location_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    location = match.group(1).strip()
                    if location and len(location) > 1:  # Valid location
                        tool_calls.append({
                            "name": "get_weather",
                            "parameters": {"location": location}
                        })
                        break
        
        # Math calculation detection
        math_keywords = ["calculate", "compute", "math", "multiply", "divide", "add", "subtract"]
        math_patterns = [
            r"(\d+\s*[\+\-\*\/]\s*\d+(?:\s*[\+\-\*\/]\s*\d+)*)",
            r"calculate\s+([0-9+\-*/\(\)\s\.]+)",
            r"what\s+is\s+([0-9+\-*/\(\)\s\.]+)"
        ]
        
        if any(keyword in input_lower for keyword in math_keywords) or re.search(r'\d+\s*[\+\-\*\/]\s*\d+', user_input):
            for pattern in math_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    expression = match.group(1).strip()
                    if expression:
                        tool_calls.append({
                            "name": "calculate",
                            "parameters": {"expression": expression}
                        })
                        break
        
        return tool_calls
    
    async def _execute_auto_detected_tools(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute auto-detected tool calls.
        
        Args:
            tool_calls: List of tool calls to execute
            
        Returns:
            List of tool results
        """
        tool_results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            parameters = tool_call.get("parameters", {})
            
            print(f"🔧 EXECUTING TOOL: {tool_name} with {parameters}")
            
            try:
                result = await self.mcp_client.execute_tool(tool_name, parameters)
                print(f"✅ TOOL RESULT: {result}")
                print(f"   - result.result: {result.result}")
                print(f"   - result.error: {result.error}")
                
                tool_results.append({
                    "name": tool_name,
                    "result": result.result,
                    "error": result.error,
                    "parameters": parameters
                })
            except Exception as e:
                print(f"❌ TOOL EXECUTION ERROR: {e}")
                tool_results.append({
                    "name": tool_name,
                    "result": None,
                    "error": str(e),
                    "parameters": parameters
                })
        
        print(f"🔍 FINAL TOOL RESULTS: {tool_results}")
        return tool_results