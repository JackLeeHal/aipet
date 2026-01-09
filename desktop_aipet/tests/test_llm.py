import unittest
from unittest.mock import MagicMock, patch
from desktop_aipet.src.llm import LLMClient

class TestLLMClient(unittest.TestCase):
    def setUp(self):
        self.client = LLMClient() # Will default to mock mode because of placeholder config

    def test_mock_chat(self):
        self.assertTrue(self.client.mock_mode)
        response = self.client.chat([{'role': 'user', 'content': 'hi'}])
        self.assertIn("mock response", response)

    def test_mock_summarize(self):
        msgs = [('user', 'hi'), ('assistant', 'hello')]
        summary = self.client.summarize_day(msgs)
        self.assertIn("Mock summary", summary)
        self.assertIn("2 messages", summary)

    @patch('requests.post')
    def test_real_chat_call(self, mock_post):
        # Setup client to not be in mock mode
        self.client.mock_mode = False
        self.client.api_key = "fake_key"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Real response'}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        response = self.client.chat([{'role': 'user', 'content': 'hi'}])
        self.assertEqual(response, 'Real response')
        mock_post.assert_called_once()

    @patch('desktop_aipet.src.llm.LLMClient.chat')
    def test_check_notification_logic(self, mock_chat):
        self.client.mock_mode = False
        # Case 1: "NO" should return None
        mock_chat.return_value = "NO"
        self.assertIsNone(self.client.check_notification_needs([{'role': 'user', 'content': 'hi'}]))

        # Case 2: "Do it NOW" should return message (previously failed)
        mock_chat.return_value = "Do it NOW"
        self.assertEqual(self.client.check_notification_needs([{'role': 'user', 'content': 'hi'}]), "Do it NOW")

if __name__ == '__main__':
    unittest.main()
