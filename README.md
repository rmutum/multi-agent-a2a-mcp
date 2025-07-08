# A2A-Ollama Multi-Agent System with MCP Integration

This repository contains a multi-agent system that demonstrates the integration between Agent-to-Agent (A2A) communication and the Model Context Protocol (MCP). The system consists of three main components that work together to provide a distributed tool execution architecture.

## System Overview

The system creates a chain of communication where:
1. **MCP Server** provides tools and functions
2. **Tool Provider Agent** bridges MCP tools to A2A protocol  
3. **Tool Consumer Agent** delegates user requests to the tool provider

```
User → Tool Consumer Agent → Tool Provider Agent → MCP Server
                    ↓                    ↓              ↓
               A2A Protocol         A2A ↔ MCP      MCP Tools
```

## File Descriptions

### 1. `multi_agent_1_mcp_server.py`

**Purpose**: MCP (Model Context Protocol) Server providing common tools

**Key Features**:
- Implements an MCP server that exposes tools via RESTful API
- Provides 6 different tools for various functionalities
- Includes health checking and graceful shutdown handling
- Mock employee database with leave management

**Available Tools**:
- `get_weather`: Mock weather information for any location
- `calculate`: Mathematical expression evaluator (uses Python eval)
- `get_leave_balance`: Check remaining leave days for employees
- `apply_leave`: Apply leave for specific dates with balance validation
- `get_leave_history`: View complete leave history for employees
- `list_employees`: List all employees and their leave status

**Sample Employees**: Raghu, Jake, Corbin, Steve (each starts with 20 leave days)

**Default Configuration**:
- Host: localhost
- Port: 3000
- Discovery endpoint: `/.well-known/mcp.json`

**Usage**:
```bash
python multi_agent_1_mcp_server.py --host localhost --port 3000 --log-level INFO
```

### 2. `multi_agent_2_tool_provider_agent.py`

**Purpose**: A2A Agent that bridges MCP tools to A2A protocol

**Key Features**:
- Connects to the MCP server and discovers available tools
- Converts MCP tools into A2A skills automatically
- Acts as a bridge between A2A and MCP protocols
- Provides tool execution capabilities to other A2A agents

**Architecture**:
- Uses `MCPClient` to connect to the MCP server
- Uses `A2AMCPBridge` to handle protocol translation
- Registers each MCP tool as an A2A skill
- Configures the A2A server to use MCP tools for execution

**Agent Configuration**:
- Model: llama3.1:8b (configurable)
- Emphasizes tool usage over LLM capabilities
- Instructs the agent to delegate calculations, weather, and leave management to tools

**Default Configuration**:
- A2A Host: localhost:8000
- MCP Server: localhost:3000
- Automatically discovers and exposes all MCP tools

**Usage**:
```bash
python multi_agent_2_tool_provider_agent.py --host localhost --port 8000 --mcp-host localhost --mcp-port 3000
```

### 3. `multi_agent_3_tool_consumer_agent.py`

**Purpose**: A2A Agent that consumes tools from other A2A agents

**Key Features**:
- Connects to the Tool Provider Agent and discovers its skills
- Creates proxy skills that delegate to the tool provider
- Intelligent request routing based on keywords and patterns
- LLM-enhanced response formatting for natural conversations

**Smart Delegation Logic**:
- Detects tool-related keywords (weather, calculate, leave, employee names)
- Identifies employee ID patterns and known employee names
- Routes appropriate requests to the tool provider
- Handles general conversation with its own LLM

**Response Processing**:
- Receives raw tool results from the tool provider
- Uses LLM to format tool responses into natural language
- Maintains conversational flow while leveraging tools

**Default Configuration**:
- Consumer Host: localhost:8001
- Tool Provider: localhost:8000
- Model: llama3.1:8b (configurable)

**Usage**:
```bash
python multi_agent_3_tool_consumer_agent.py --host localhost --port 8001 --tool-provider-host localhost --tool-provider-port 8000
```

## System Startup Sequence

To run the complete system:

1. **Start MCP Server** (Terminal 1):
   ```bash
   python multi_agent_1_mcp_server.py
   ```

2. **Start Tool Provider Agent** (Terminal 2):
   ```bash
   python multi_agent_2_tool_provider_agent.py
   ```

3. **Start Tool Consumer Agent** (Terminal 3):
   ```bash
   python multi_agent_3_tool_consumer_agent.py
   ```

## Example Interactions

Once all components are running, you can interact with the Tool Consumer Agent:

**Weather Query**:
```
User: "What's the weather like in Tokyo?"
→ Delegates to Tool Provider → Uses MCP weather tool → Returns formatted response
```

**Mathematical Calculation**:
```
User: "Calculate 15 * 8 + 32"
→ Delegates to Tool Provider → Uses MCP calculator → Returns "152"
```

**Leave Management**:
```
User: "What's the leave balance for Raghu?"
→ Delegates to Tool Provider → Uses MCP leave balance tool → Returns balance info
```

**General Conversation**:
```
User: "How are you today?"
→ Handled by Consumer Agent's LLM directly → Conversational response
```

## Architecture Benefits

1. **Modularity**: Each component has a single responsibility
2. **Protocol Translation**: Seamless bridge between A2A and MCP
3. **Scalability**: Easy to add more tools or agents
4. **Flexibility**: Tools can be updated without changing consumer agents
5. **Natural Interaction**: LLM formatting makes tool responses conversational

## Dependencies

The system requires the A2A framework with MCP integration support, including:
- A2A Server/Client components
- MCP Client/Server implementations
- A2A-MCP Bridge functionality
- Ollama integration for LLM capabilities

## Error Handling

Each component includes:
- Connection retry logic with exponential backoff
- Graceful shutdown handling
- Comprehensive logging at multiple levels
- Fallback responses for failed tool calls
