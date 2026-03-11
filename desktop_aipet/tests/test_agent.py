import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from desktop_aipet.src.agent.brain import AgentBrain
from desktop_aipet.src.bus.event_bus import EventBus
from desktop_aipet.src.bus.events import UserMessage, AgentResponseChunk, AgentResponseFinished, SessionChanged

class TestAgentBrain(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.agent = AgentBrain(self.bus)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @patch('desktop_aipet.src.agent.brain.get_provider')
    @patch('desktop_aipet.src.agent.brain.load_config')
    @patch('desktop_aipet.src.agent.brain.get_context')
    @patch('desktop_aipet.src.agent.brain.get_db_connection')
    @patch('desktop_aipet.src.agent.brain.update_session_title')
    @patch('desktop_aipet.src.agent.brain.get_session_messages')
    def test_on_user_message_simple_chat(self, mock_get_msgs, mock_update_title, mock_get_db, mock_get_context, mock_load_config, mock_get_provider):
        # Mock DB
        mock_db_ctx = AsyncMock()
        mock_get_db.return_value = mock_db_ctx

        # Mock Context
        mock_get_context.return_value = "Context"

        mock_load_config.return_value = {"llm": {"api_type": "openai"}}

        # Mock Provider
        mock_provider = AsyncMock()
        mock_get_provider.return_value = mock_provider

        # Mock chat stream response
        from desktop_aipet.src.llm.openai_provider import OpenAILikeResponse
        response = OpenAILikeResponse(content="Hello", tool_calls=[])

        async def mock_chat_stream(*args, **kwargs):
            on_chunk = kwargs.get('on_chunk')
            if on_chunk:
                await on_chunk("Hello")
            return response

        mock_provider.chat_stream.side_effect = mock_chat_stream

        # Mock session messages for title generation
        mock_get_msgs.return_value = [] # Emptylist implies new session

        # Run
        async def run_test():
            await self.agent.start_session("test_session")

            received_chunks = []
            async def chunk_handler(event):
                received_chunks.append(event.content)
            self.bus.subscribe(AgentResponseChunk, chunk_handler)

            await self.bus.publish(UserMessage(content="Hi", session_id="test_session"))

            # Allow loop to process
            await asyncio.sleep(0.1)
            return received_chunks

        chunks = self.loop.run_until_complete(run_test())
        self.assertIn("Hello", chunks)

    @patch('desktop_aipet.src.agent.brain.get_provider')
    @patch('desktop_aipet.src.agent.brain.load_config')
    @patch('desktop_aipet.src.agent.brain.get_context')
    @patch('desktop_aipet.src.agent.brain.get_db_connection')
    @patch('desktop_aipet.src.agent.brain.update_session_title')
    @patch('desktop_aipet.src.agent.brain.get_session_messages')
    def test_session_change(self, mock_get_msgs, mock_update_title, mock_get_db, mock_get_context, mock_load_config, mock_get_provider):
        # Mock DB
        mock_db_ctx = AsyncMock()
        mock_get_db.return_value = mock_db_ctx

        async def run_test():
            await self.agent.start_session("session_1")
            self.assertEqual(self.agent.session_id, "session_1")

            await self.bus.publish(SessionChanged(session_id="session_2"))
            await asyncio.sleep(0.01)
            self.assertEqual(self.agent.session_id, "session_2")

        self.loop.run_until_complete(run_test())
