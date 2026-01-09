import unittest
import threading
import time
import os
from desktop_aipet.src.core import PetCore
from desktop_aipet.src import database

class TestCore(unittest.TestCase):
    def setUp(self):
        self.test_db = 'test_core.db'
        self.core = PetCore(self.test_db)
        # Mock LLM to avoid external calls and allow testing logic
        self.core.llm.mock_mode = True

    def tearDown(self):
        self.core.stop()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_message_flow(self):
        response = self.core.send_user_message("Hello")
        self.assertIn("mock response", response)

        history = database.get_history(db_path=self.test_db)
        self.assertEqual(len(history), 2) # User msg + Assistant msg

    def test_notification_callback(self):
        # We need to trick the LLM client or force a condition where notification returns
        # The mock LLM has random 10% chance. Let's patch it.
        from unittest.mock import MagicMock
        self.core.llm.check_notification_needs = MagicMock(return_value="Wake up!")

        callback = MagicMock()
        self.core.set_notification_callback(callback)

        self.core._check_notifications()

        callback.assert_called_with("Wake up!")

if __name__ == '__main__':
    unittest.main()
