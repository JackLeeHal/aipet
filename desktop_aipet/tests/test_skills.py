import unittest
import asyncio
import tempfile
import os
import shutil
from unittest.mock import patch
from desktop_aipet.src.skills.reminder import ReminderSkill, get_all_reminders
from desktop_aipet.src.bus.event_bus import EventBus
from desktop_aipet.src.database import init_db
import aiosqlite

class TestReminderSkill(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, 'test_aipet.db')

        # Patch the database path in the module where get_db_connection is used/defined
        # But actually get_db_connection is imported in reminder.py
        # We need to patch get_db_connection to return connection to our test db
        self.patcher = patch('desktop_aipet.src.skills.reminder.reminder.get_db_connection')
        self.mock_get_db = self.patcher.start()
        self.mock_get_db.side_effect = lambda: aiosqlite.connect(self.db_path)

        self.bus = EventBus()
        self.skill = ReminderSkill(self.bus)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Init DB
        self.loop.run_until_complete(self._init_test_db())

    def tearDown(self):
        self.patcher.stop()
        self.loop.close()
        shutil.rmtree(self.test_dir)

    async def _init_test_db(self):
        # We need to run the CREATE TABLE statements
        async with aiosqlite.connect(self.db_path) as db:
             await db.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT,
                    run_date DATETIME,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
             await db.commit()

    def test_execute_success(self):
        time_iso = "2099-01-01T12:00:00"
        result = self.loop.run_until_complete(self.skill.execute(message="Test", time_iso=time_iso))

        self.assertIn("Reminder scheduled", result)

        # Verify in DB
        reminders = self.loop.run_until_complete(get_all_reminders())
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0]['message'], "Test")

    def test_execute_past_date(self):
        time_iso = "2000-01-01T12:00:00"
        result = self.loop.run_until_complete(self.skill.execute(message="Test", time_iso=time_iso))
        self.assertIn("Error: Cannot schedule reminder in the past", result)
