"""
MCP Integration Example - Multi-Agent System with MCP Bridge

This example demonstrates how to create and run an MCP server that provides
common tools (weather, calculator, and employee leave management) to agents. 
The server exposes these tools via the Model Context Protocol (MCP) for use by AI agents.

Features:
- MCP server with RESTful API
- Weather information tool (mock implementation)
- Mathematical calculator tool
- Employee leave management tools (balance, apply, history)
- Server health checking with retries
- Graceful shutdown handling

Available Tools:
- get_weather: Get weather information for any location
- calculate: Perform mathematical calculations
- get_leave_balance: Check remaining leave days for employees
- apply_leave: Apply leave for specific dates
- get_leave_history: View complete leave history

Sample Employees: Raghu, Jake, Corbin, Steve
"""

import os
import sys
import asyncio
import argparse
import httpx
import logging
from typing import List

# Add the parent directory to sys.path for local imports
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from a2a.server import A2AServer
from a2a.client import A2AClient
from a2a.core.a2a_ollama import A2AOllama
from a2a.core.mcp.mcp_client import MCPClient
from a2a.core.mcp.mcp_server import MCPServer
from a2a.core.a2a_mcp_bridge import A2AMCPBridge

# In-memory mock database with 20 leave days to start
employee_leaves = {
    "Raghu": {"balance": 18, "history": ["2025-05-13", "2025-07-03"]},
    "Jake": {"balance": 15, "history": ["2025-04-01","2025-04-02","2025-04-03","2025-04-04", "2025-07-03"]},
    "Corbin": {"balance": 17, "history": ["2025-01-10","2025-04-02", "2025-03-03"]},
    "Steve": {"balance": 20, "history": []}
}

def configure_logging(log_level="INFO"):
    """Configure logging with appropriate level and format.
    
    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Logger instance for the multi-agent example
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
        "mcp_server", 
        "a2a_mcp_bridge",
        "a2a_server",
        "a2a_client"
    ]
    for logger_name in loggers:
        logging.getLogger(logger_name).setLevel(numeric_level)
    
    return logging.getLogger("multi_agent_example")


def get_weather(location: str) -> dict:
    """Mock weather tool that returns sample weather data.
    
    Args:
        location: City name to get weather for
        
    Returns:
        Dictionary containing weather information
    """
    return {
        "temperature": 72,
        "condition": "sunny",
        "location": location
    }

def calculate(expression: str) -> dict:
    """Calculator tool that evaluates mathematical expressions.
    
    Args:
        expression: Mathematical expression to evaluate
        
    Returns:
        Dictionary containing the result or error message
    """
    try:
        result = eval(expression)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

def get_leave_balance(employee_id: str) -> dict:
    """
    Check how many leave days are left for the employee.
    
    Args:
        employee_id: The employee's ID/name to check balance for
        
    Returns:
        Dictionary containing the leave balance information
    """
    data = employee_leaves.get(employee_id)
    if data:
        return {
            "employee_id": employee_id,
            "balance": data['balance'],
            "message": f"{employee_id} has {data['balance']} leave days remaining."
        }
    return {
        "employee_id": employee_id,
        "balance": None,
        "error": "Employee ID not found."
    }


def apply_leave(employee_id: str, leave_dates: str) -> dict:
    """
    Apply leave for specific dates.
    
    Args:
        employee_id: The employee's ID/name
        leave_dates: Comma-separated list of dates (e.g., "2025-04-17,2025-05-01")
        
    Returns:
        Dictionary containing the leave application result
    """
    if employee_id not in employee_leaves:
        return {
            "employee_id": employee_id,
            "success": False,
            "error": "Employee ID not found."
        }

    # Parse the comma-separated dates
    try:
        dates_list = [date.strip() for date in leave_dates.split(',') if date.strip()]
        if not dates_list:
            return {
                "employee_id": employee_id,
                "success": False,
                "error": "No valid dates provided."
            }
    except Exception as e:
        return {
            "employee_id": employee_id,
            "success": False,
            "error": f"Invalid date format: {str(e)}"
        }

    requested_days = len(dates_list)
    available_balance = employee_leaves[employee_id]["balance"]

    if available_balance < requested_days:
        return {
            "employee_id": employee_id,
            "success": False,
            "requested_days": requested_days,
            "available_balance": available_balance,
            "error": f"Insufficient leave balance. You requested {requested_days} day(s) but have only {available_balance}."
        }

    # Deduct balance and add to history
    employee_leaves[employee_id]["balance"] -= requested_days
    employee_leaves[employee_id]["history"].extend(dates_list)

    return {
        "employee_id": employee_id,
        "success": True,
        "applied_dates": dates_list,
        "days_applied": requested_days,
        "remaining_balance": employee_leaves[employee_id]['balance'],
        "message": f"Leave applied for {requested_days} day(s). Remaining balance: {employee_leaves[employee_id]['balance']}."
    }


def get_leave_history(employee_id: str) -> dict:
    """
    Get leave history for the employee.
    
    Args:
        employee_id: The employee's ID/name
        
    Returns:
        Dictionary containing the employee's leave history
    """
    data = employee_leaves.get(employee_id)
    if data:
        history_dates = data['history']
        return {
            "employee_id": employee_id,
            "total_leaves_taken": len(history_dates),
            "leave_dates": history_dates,
            "message": f"Leave history for {employee_id}: {', '.join(history_dates) if history_dates else 'No leaves taken.'}"
        }
    return {
        "employee_id": employee_id,
        "total_leaves_taken": 0,
        "leave_dates": [],
        "error": "Employee ID not found."
    }

def list_employees() -> dict:
    """
    List all employees and their current leave status.
    
    Returns:
        Dictionary containing all employee information
    """
    return {
        "employees": employee_leaves,
        "total_employees": len(employee_leaves),
        "message": "Current employee leave database"
    }

async def check_server_availability(url, max_retries=10, retry_delay=3):
    """Check if a server is available by making HTTP requests with retries.
    
    Args:
        url: The URL to check for availability
        max_retries: Maximum number of retry attempts (default: 10)
        retry_delay: Delay between retries in seconds (default: 3)
        
    Returns:
        True if server is available, False otherwise
    """
    logger = logging.getLogger("server_check")
    async with httpx.AsyncClient() as client:
        for i in range(max_retries):
            try:
                logger.info(f"Checking server availability: {url} (Attempt {i+1}/{max_retries})")
                response = await client.get(url, timeout=30.0)
                if response.status_code < 500:  # Accept any non-5xx response as available
                    logger.info(f"Server at {url} is available (status {response.status_code})")
                    return True
            except httpx.RequestError as e:
                logger.warning(f"Request failed: {e}")
            
            logger.info(f"Server at {url} not ready yet, retrying in {retry_delay}s")
            await asyncio.sleep(retry_delay)
        
        logger.error(f"Server at {url} could not be reached after {max_retries} attempts")
        return False


async def main():
    """Main function to run the MCP server with tools."""
    parser = argparse.ArgumentParser(description="MCP Server with Common Tools")
    parser.add_argument("--host", type=str, default="localhost", 
                       help="Host to run the server on")
    parser.add_argument("--port", type=int, default=3000,
                       help="Port to run the server on")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="Set logging level")
    
    args = parser.parse_args()
    
    # Initialize logging
    logger = configure_logging(args.log_level)
    logger.info("Starting MCP server with common tools")
    
    # Initialize server variable for cleanup
    mcp_server = None

    try:
        # Create and configure MCP server
        logger.info(f"Creating MCP server on {args.host}:{args.port}")
        mcp_server = MCPServer(
            host=args.host,
            port=args.port,
            name="Tool Provider MCP Server",
            description="MCP server providing common tools",
            version="1.0.0"
        )
        
        # Register available tools
        logger.info("Registering weather tool")
        mcp_server.register_tool(
            name="get_weather",
            description="Get weather for a location",
            function=get_weather,
            parameters=[
                {
                    "name": "location",
                    "description": "City name",
                    "type": "string",
                    "required": True
                }
            ]
        )
        
        logger.info("Registering calculator tool")
        mcp_server.register_tool(
            name="calculate",
            description="Calculate a mathematical expression",
            function=calculate,
            parameters=[
                {
                    "name": "expression",
                    "description": "Mathematical expression to evaluate",
                    "type": "string",
                    "required": True
                }
            ]
        )
        
        logger.info("Registering leave balance tool")
        mcp_server.register_tool(
            name="get_leave_balance",
            description="Check how many leave days are remaining for an employee",
            function=get_leave_balance,
            parameters=[
                {
                    "name": "employee_id",
                    "description": "Employee ID or name (e.g., 'Raghu', 'Jake', 'Corbin', 'Steve')",
                    "type": "string",
                    "required": True
                }
            ]
        )
        
        logger.info("Registering apply leave tool")
        mcp_server.register_tool(
            name="apply_leave",
            description="Apply leave for specific dates for an employee",
            function=apply_leave,
            parameters=[
                {
                    "name": "employee_id",
                    "description": "Employee ID or name (e.g., 'Raghu', 'Jake', 'Corbin', 'Steve')",
                    "type": "string",
                    "required": True
                },
                {
                    "name": "leave_dates",
                    "description": "Comma-separated list of dates in YYYY-MM-DD format (e.g., '2025-04-17,2025-05-01')",
                    "type": "string",
                    "required": True
                }
            ]
        )
        
        logger.info("Registering leave history tool")
        mcp_server.register_tool(
            name="get_leave_history",
            description="Get the complete leave history for an employee",
            function=get_leave_history,
            parameters=[
                {
                    "name": "employee_id",
                    "description": "Employee ID or name (e.g., 'Raghu', 'Jake', 'Corbin', 'Steve')",
                    "type": "string",
                    "required": True
                }
            ]
        )
        
        logger.info("Registering list employees tool")
        mcp_server.register_tool(
            name="list_employees",
            description="List all employees and their current leave status",
            function=list_employees,
            parameters=[]
        )
        
        logger.info("Registering list employees tool")
        mcp_server.register_tool(
            name="list_employees",
            description="List all employees and their leave status",
            function=list_employees,
            parameters=[]
        )
        
        # Start the MCP server
        logger.info(f"Starting MCP server at http://{args.host}:{args.port}")
        await mcp_server.start()
        logger.info("MCP server started successfully")
        
        # Wait for server initialization
        logger.info("Waiting for server initialization...")
        await asyncio.sleep(3)
        
        # Verify server is responding
        logger.info("Verifying server availability...")
        server_url = f"http://{args.host}:{args.port}"
        discovery_url = f"{server_url}/.well-known/mcp.json"
        
        if not await check_server_availability(discovery_url):
            logger.error("MCP server failed to start properly")
            raise RuntimeError("Failed to start MCP server")
        
        # Server is ready
        logger.info("🚀 MCP server is running and ready!")
        logger.info(f"📍 Server URL: {server_url}")
        logger.info(f"🔍 Discovery endpoint: {discovery_url}")
        logger.info("💡 Available tools:")
        logger.info("   • get_weather - Get weather information for a location")
        logger.info("   • calculate - Perform mathematical calculations")
        logger.info("   • get_leave_balance - Check employee leave balance")
        logger.info("   • apply_leave - Apply leave for specific dates")
        logger.info("   • get_leave_history - Get employee leave history")
        logger.info("   • list_employees - List all employees and their leave status")
        logger.info("   • list_employees - List all employees and their leave status")
        logger.info("👥 Available employees: Raghu, Jake, Corbin, Steve")
        logger.info("⏹️  Press Ctrl+C to stop the server")
        
        # Keep server running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown signal received")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        raise
    finally:
        # Cleanup
        if mcp_server:
            logger.info("🔄 Shutting down MCP server...")
            await mcp_server.stop()
            logger.info("✅ MCP server stopped successfully")


if __name__ == "__main__":
    asyncio.run(main())