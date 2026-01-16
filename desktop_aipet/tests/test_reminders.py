import unittest
import asyncio
import os
from desktop_aipet.src.database import init_db, get_db_connection
from desktop_aipet.src.scheduler_service import schedule_reminder, get_all_reminders, delete_reminder, update_reminder, init_scheduler
from datetime import datetime, timedelta

class TestReminders(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    async def async_test_crud(self):
        # Initialize DB
        await init_db()

        # Clear reminders table to ensure clean state
        async with get_db_connection() as db:
            await db.execute("DELETE FROM reminders")
            await db.commit()

        await init_scheduler()

        # Create
        now_plus_1h = (datetime.now() + timedelta(hours=1)).isoformat()
        res = await schedule_reminder("Test Reminder", now_plus_1h)
        self.assertTrue(res, "Failed to schedule reminder")

        reminders = await get_all_reminders()
        self.assertEqual(len(reminders), 1, "Should have 1 reminder")
        self.assertEqual(reminders[0]['message'], "Test Reminder")
        r_id = reminders[0]['id']

        # Update
        now_plus_2h = (datetime.now() + timedelta(hours=2)).isoformat()
        res = await update_reminder(r_id, "Updated Reminder", now_plus_2h)
        self.assertTrue(res, "Failed to update reminder")

        reminders = await get_all_reminders()
        self.assertEqual(reminders[0]['message'], "Updated Reminder")
        self.assertEqual(reminders[0]['run_date'], now_plus_2h)

        # Delete
        res = await delete_reminder(r_id)
        self.assertTrue(res, "Failed to delete reminder")

        reminders = await get_all_reminders()
        self.assertEqual(len(reminders), 0, "Should have 0 reminders")

    def test_crud(self):
        self.loop.run_until_complete(self.async_test_crud())

if __name__ == '__main__':
    unittest.main()
