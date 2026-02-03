import asyncio
import json
import datetime
from ..bus.event_bus import EventBus
from ..bus.events import UserMessage, AgentResponseChunk, AgentResponseFinished, SessionChanged
from ..skills.registry import SkillRegistry
from ..skills.loader import SkillLoader
from ..memory_service import get_context, get_llm_client, update_session_title, get_session_messages
from ..database import get_db_connection

class AgentBrain:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.skill_registry = SkillRegistry()
        self.session_id = None

        # Load skills dynamically
        loader = SkillLoader(bus)
        skills = loader.load_skills()
        for skill in skills:
            print(f"Loading skill: {skill.name}")
            self.skill_registry.register(skill)

        # Subscribe
        self.bus.subscribe(UserMessage, self.on_user_message)
        self.bus.subscribe(SessionChanged, self.on_session_changed)

    async def start_session(self, session_id):
        self.session_id = session_id

    async def on_session_changed(self, event: SessionChanged):
        self.session_id = event.session_id

    async def on_user_message(self, event: UserMessage):
        if not self.session_id:
            return

        if event.session_id != self.session_id:
             self.session_id = event.session_id

        user_message = event.content

        # 1. Save User Message
        timestamp = datetime.datetime.now().isoformat()
        async with get_db_connection() as db:
            await db.execute('INSERT INTO chat_logs (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
                             (self.session_id, 'user', user_message, timestamp))
            await db.commit()

        # 2. Get Context
        context = await get_context(self.session_id)

        messages = [
            {"role": "system", "content": f"You are a helpful desktop pet assistant. Context:\n{context}"},
            {"role": "user", "content": user_message}
        ]

        await self._run_react_loop(messages)

        # Generate Title (Fire and forget)
        asyncio.create_task(self._generate_title_if_needed(user_message))

    async def _run_react_loop(self, messages, max_turns=5):
        turn = 0
        while turn < max_turns:
            turn += 1
            client, model = await get_llm_client()
            tool_schemas = self.skill_registry.get_schemas()

            response_text = ""
            tool_calls_accumulated = []
            tool_calls_data = None

            try:
                if not client.api_key or client.api_key == "YOUR_API_KEY_HERE":
                     err = "I'm sorry, but I haven't been configured with a valid API key yet."
                     await self.bus.publish(AgentResponseChunk(content=err, session_id=self.session_id))
                     response_text = err
                     break

                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                    stream=True
                )

                async for chunk in stream:
                    delta = chunk.choices[0].delta

                    if delta.content:
                        response_text += delta.content
                        await self.bus.publish(AgentResponseChunk(content=delta.content, session_id=self.session_id))

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

                # Save assistant message
                timestamp = datetime.datetime.now().isoformat()

                # Prepare tool calls data for DB
                if tool_calls_accumulated:
                    tool_calls_list = []
                    for tc in tool_calls_accumulated:
                        tool_calls_list.append({
                             "name": tc["name"],
                             "args": tc["args"]
                        })
                    tool_calls_data = json.dumps(tool_calls_list)

                async with get_db_connection() as db:
                    await db.execute('INSERT INTO chat_logs (session_id, role, content, timestamp, tool_calls) VALUES (?, ?, ?, ?, ?)',
                                     (self.session_id, 'assistant', response_text, timestamp, tool_calls_data))
                    await db.commit()

                # Add assistant response to messages for next turn
                assistant_msg = {"role": "assistant", "content": response_text}
                if tool_calls_accumulated:
                     assistant_msg["tool_calls"] = []
                     for tc in tool_calls_accumulated:
                         assistant_msg["tool_calls"].append({
                             "id": tc["id"],
                             "type": "function",
                             "function": {"name": tc["name"], "arguments": tc["args"]}
                         })
                messages.append(assistant_msg)

                # Process Tools
                if tool_calls_accumulated:
                    for tc in tool_calls_accumulated:
                        fname = tc["name"]
                        args = tc["args"]
                        tid = tc["id"]

                        # Notify UI we are executing
                        await self.bus.publish(AgentResponseChunk(content=f"\n[Executing {fname}...]", session_id=self.session_id))

                        result = await self.skill_registry.execute(fname, args)

                        await self.bus.publish(AgentResponseChunk(content=f" Done]\n", session_id=self.session_id))

                        # Append tool result
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tid,
                            "content": str(result)
                        })

                    # Continue loop to let LLM respond to tool output
                    continue

                # If no tool calls, we are done
                break

            except Exception as e:
                err_msg = f"Error communicating with LLM: {str(e)}"
                await self.bus.publish(AgentResponseChunk(content=err_msg, session_id=self.session_id))
                response_text += err_msg
                break

        await self.bus.publish(AgentResponseFinished(session_id=self.session_id))

    async def _generate_title_if_needed(self, user_message):
        msgs = await get_session_messages(self.session_id)
        if len(msgs) <= 2:
            try:
                client, model = await get_llm_client()
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
                pass
