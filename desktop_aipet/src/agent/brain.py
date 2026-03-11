import asyncio
import json
import datetime
from ..bus.event_bus import EventBus
from ..bus.events import UserMessage, AgentResponseChunk, AgentResponseFinished, SessionChanged
from ..skills.registry import SkillRegistry
from ..skills.reminder import ReminderSkill
from ..memory_service import get_context, update_session_title, get_session_messages, load_config
from ..database import get_db_connection
from ..llm.factory import get_provider

class AgentBrain:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.skill_registry = SkillRegistry()
        self.session_id = None

        # Register default skills
        self.skill_registry.register(ReminderSkill(bus))

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
        config = load_config()
        provider = get_provider(config)
        tool_schemas = self.skill_registry.get_schemas()

        while turn < max_turns:
            turn += 1
            try:
                async def on_chunk(content: str):
                    await self.bus.publish(AgentResponseChunk(content=content, session_id=self.session_id))

                response = await provider.chat_stream(
                    messages=messages,
                    tools=tool_schemas,
                    on_chunk=on_chunk
                )

                # Save assistant message
                timestamp = datetime.datetime.now().isoformat()
                tool_calls_data = None
                if response.tool_calls:
                    tool_calls_data = json.dumps([{
                        "name": tc["function"]["name"],
                        "args": tc["function"]["arguments"]
                    } for tc in response.tool_calls])

                async with get_db_connection() as db:
                    await db.execute('INSERT INTO chat_logs (session_id, role, content, timestamp, tool_calls) VALUES (?, ?, ?, ?, ?)',
                                     (self.session_id, 'assistant', response.content, timestamp, tool_calls_data))
                    await db.commit()

                assistant_msg = {"role": "assistant", "content": response.content}
                if response.tool_calls:
                    assistant_msg["tool_calls"] = [{
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
                    } for tc in response.tool_calls]
                messages.append(assistant_msg)

                if response.stop_reason != "tool_use":
                    break

                for tc in response.tool_calls:
                    fname = tc["function"]["name"]
                    args = tc["function"]["arguments"]
                    tid = tc["id"]

                    await self.bus.publish(AgentResponseChunk(content=f"\n[Executing {fname}...]", session_id=self.session_id))
                    result = await self.skill_registry.execute(fname, args)
                    await self.bus.publish(AgentResponseChunk(content=f" Done]\n", session_id=self.session_id))

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tid,
                        "content": str(result)
                    })

            except ValueError as ve:
                await self.bus.publish(AgentResponseChunk(content=str(ve), session_id=self.session_id))
                break
            except Exception as e:
                err_msg = f"Error communicating with LLM: {str(e)}"
                await self.bus.publish(AgentResponseChunk(content=err_msg, session_id=self.session_id))
                break

        await self.bus.publish(AgentResponseFinished(session_id=self.session_id))

    async def _generate_title_if_needed(self, user_message):
        msgs = await get_session_messages(self.session_id)
        if len(msgs) <= 2:
            try:
                config = load_config()
                provider = get_provider(config)

                # Check for dummy/missing api keys
                try:
                    await provider._check_api_key()
                except ValueError:
                    return

                response = await provider.chat(
                    messages=[
                        {"role": "user", "content": f"Generate a short (3-5 words) title for this conversation based on this message: {user_message}"}
                    ]
                )
                title = response.content.strip().strip('"')
                await update_session_title(self.session_id, title)
            except Exception:
                pass
