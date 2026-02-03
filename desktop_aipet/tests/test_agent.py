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

    @patch('desktop_aipet.src.agent.brain.get_llm_client')
    @patch('desktop_aipet.src.agent.brain.get_context')
    @patch('desktop_aipet.src.agent.brain.get_db_connection')
    @patch('desktop_aipet.src.agent.brain.update_session_title')
    @patch('desktop_aipet.src.agent.brain.get_session_messages')
    def test_on_user_message_simple_chat(self, mock_get_msgs, mock_update_title, mock_get_db, mock_get_context, mock_get_client):
        # Mock DB
        mock_db_ctx = AsyncMock()
        mock_get_db.return_value = mock_db_ctx

        # Mock Context
        mock_get_context.return_value = "Context"

        # Mock LLM
        mock_client = MagicMock()
        mock_client.api_key = "test_key"
        mock_get_client.return_value = (mock_client, "gpt-3.5-turbo")

        # Mock Stream
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Hello"
        mock_chunk.choices[0].delta.tool_calls = None

        async def mock_stream_gen():
            yield mock_chunk

        async def create_mock(*args, **kwargs):
            return mock_stream_gen()

        mock_client.chat.completions.create.side_effect = create_mock

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

    @patch('desktop_aipet.src.agent.brain.get_llm_client')
    @patch('desktop_aipet.src.agent.brain.get_context')
    @patch('desktop_aipet.src.agent.brain.get_db_connection')
    @patch('desktop_aipet.src.agent.brain.update_session_title')
    @patch('desktop_aipet.src.agent.brain.get_session_messages')
    def test_session_change(self, mock_get_msgs, mock_update_title, mock_get_db, mock_get_context, mock_get_client):
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
