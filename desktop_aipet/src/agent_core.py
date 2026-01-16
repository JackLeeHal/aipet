import json
import asyncio
import datetime
from .memory_service import get_context, get_llm_client, update_session_title, get_session_messages
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

    async def chat_stream(self, user_message: str):
        if not self.session_id:
            yield "Error: No active session."
            return

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
        tool_calls_accumulated = []
        tool_calls_data = None

        try:
             # Check if key is valid
            if not client.api_key or client.api_key == "YOUR_API_KEY_HERE":
                 response_text = "I'm sorry, but I haven't been configured with a valid API key yet."
                 yield response_text
            else:
                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                    stream=True
                )

                async for chunk in stream:
                    delta = chunk.choices[0].delta

                    # Handle Content
                    if delta.content:
                        response_text += delta.content
                        yield delta.content

                    # Handle Tool Calls (Accumulate)
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            if len(tool_calls_accumulated) <= tc.index:
                                tool_calls_accumulated.append({"name": "", "args": "", "id": ""})

                            if tc.function:
                                if tc.function.name:
                                    tool_calls_accumulated[tc.index]["name"] += tc.function.name
                                if tc.function.arguments:
                                    tool_calls_accumulated[tc.index]["args"] += tc.function.arguments
                            if tc.id:
                                tool_calls_accumulated[tc.index]["id"] = tc.id

                # Process Tool Calls after stream
                if tool_calls_accumulated:
                    tool_calls_list = []
                    for tc in tool_calls_accumulated:
                         fname = tc["name"]
                         args = tc["args"]

                         yield f"\n[Executing tool: {fname}...]"
                         result = await self.tool_registry.execute(fname, args)
                         yield f" Done]\nResult: {result}\n"

                         tool_calls_list.append({
                             "name": fname,
                             "args": args,
                             "result": str(result)
                         })

                         response_text += f"\n[Tool {fname} executed: {result}]"

                    tool_calls_data = json.dumps(tool_calls_list)

        except Exception as e:
            err_msg = f"Error communicating with LLM: {str(e)}"
            response_text += err_msg
            yield err_msg

        # 4. Save Assistant Message
        timestamp = datetime.datetime.now().isoformat()
        async with get_db_connection() as db:
            await db.execute('INSERT INTO chat_logs (session_id, role, content, timestamp, tool_calls) VALUES (?, ?, ?, ?, ?)',
                             (self.session_id, 'assistant', response_text, timestamp, tool_calls_data))
            await db.commit()

        # 5. Generate Title if needed (Simple heuristic: if session has 2 messages)
        msgs = await get_session_messages(self.session_id)
        if len(msgs) <= 2:
            # Generate title
            try:
                if client.api_key and client.api_key != "YOUR_API_KEY_HERE":
                    title_response = await client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "user", "content": f"Generate a short (3-5 words) title for this conversation based on this message: {user_message}"}
                        ]
                    )
                    title = title_response.choices[0].message.content.strip().strip('"')
                    await update_session_title(self.session_id, title)
            except Exception:
                pass # Ignore title generation errors
