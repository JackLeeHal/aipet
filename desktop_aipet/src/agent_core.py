import json
import asyncio
import datetime
from .memory_service import get_context, get_llm_client
from .scheduler_service import schedule_reminder
from .database import get_db_connection

class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, name, func, schema):
        self.tools[name] = {"func": func, "schema": schema}

    def get_schemas(self):
        return [t["schema"] for t in self.tools.values()]

    async def execute(self, name, arguments_json):
        if name in self.tools:
            try:
                # arguments_json is a string (JSON)
                args = json.loads(arguments_json)
                func = self.tools[name]["func"]
                if asyncio.iscoroutinefunction(func):
                    return await func(**args)
                else:
                    return func(**args)
            except Exception as e:
                return f"Error executing tool {name}: {str(e)}"
        return f"Tool {name} not found."

class MCPClient:
    """Placeholder for MCP Client."""
    def __init__(self):
        self.servers = []

    def load_config(self, config_path):
        pass

class ChatAgent:
    def __init__(self):
        self.tool_registry = ToolRegistry()
        self.mcp_client = MCPClient()
        self.session_id = None
        self._register_native_tools()

    def _register_native_tools(self):
        self.tool_registry.register(
            "set_reminder",
            schedule_reminder,
            {
                "type": "function",
                "function": {
                    "name": "set_reminder",
                    "description": "Set a reminder for a specific time.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "The reminder message."},
                            "time_iso": {"type": "string", "description": "ISO 8601 format time (e.g., 2023-10-27T14:30:00)."}
                        },
                        "required": ["message", "time_iso"]
                    }
                }
            }
        )

    async def start_session(self, session_id):
        self.session_id = session_id

    async def chat(self, user_message: str):
        if not self.session_id:
            return "Error: No active session."

        # 1. Save User Message
        timestamp = datetime.datetime.now().isoformat()
        async with get_db_connection() as db:
            await db.execute('INSERT INTO chat_logs (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
                             (self.session_id, 'user', user_message, timestamp))
            await db.commit()

        # 2. Get Context
        context = await get_context(self.session_id)

        # 3. Call LLM
        client, model = await get_llm_client()

        messages = [
            {"role": "system", "content": f"You are a helpful desktop pet assistant. Context:\n{context}"},
            {"role": "user", "content": user_message}
        ]

        tool_schemas = self.tool_registry.get_schemas()

        response_text = ""
        tool_calls_data = None

        try:
             # Check if key is valid
            if not client.api_key or client.api_key == "YOUR_API_KEY_HERE":
                 response_text = "I'm sorry, but I haven't been configured with a valid API key yet."
            else:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto"
                )

                msg = response.choices[0].message
                response_text = msg.content

                if msg.tool_calls:
                    tool_calls_list = []
                    for tool_call in msg.tool_calls:
                         # Execute tool
                         fname = tool_call.function.name
                         args = tool_call.function.arguments
                         result = await self.tool_registry.execute(fname, args)

                         tool_calls_list.append({
                             "name": fname,
                             "args": args,
                             "result": str(result)
                         })

                         if response_text is None: response_text = ""
                         response_text += f"\n[Tool {fname} executed: {result}]"

                    tool_calls_data = json.dumps(tool_calls_list)

        except Exception as e:
            response_text = f"Error communicating with LLM: {str(e)}"

        # 4. Save Assistant Message
        timestamp = datetime.datetime.now().isoformat()
        async with get_db_connection() as db:
            await db.execute('INSERT INTO chat_logs (session_id, role, content, timestamp, tool_calls) VALUES (?, ?, ?, ?, ?)',
                             (self.session_id, 'assistant', response_text, timestamp, tool_calls_data))
            await db.commit()

        return response_text
