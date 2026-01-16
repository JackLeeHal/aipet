import unittest
import asyncio
import os
import shutil
from desktop_aipet.src.database import init_db, get_db_path, get_db_connection
import desktop_aipet.src.scheduler_service as scheduler_service
from desktop_aipet.src.agent_core import ChatAgent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class TestWorkflow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Ensure DB is clean.
        if os.path.exists(get_db_path()):
            try:
                os.remove(get_db_path())
            except:
                pass
        await init_db()

        # Reset scheduler for the new loop
        scheduler_service.scheduler = AsyncIOScheduler()
        scheduler_service.start_scheduler()

    async def asyncTearDown(self):
        if scheduler_service.scheduler.running:
            try:
                scheduler_service.scheduler.shutdown()
            except RuntimeError:
                pass # Loop closed

    async def test_agent_workflow(self):
        agent = ChatAgent()
        await agent.start_session("test_session")

        response = ""
        async for chunk in agent.chat_stream("Hello"):
            response += chunk

        # We expect a response (even if it's the missing API key message)
        self.assertTrue(len(response) > 0)

        # Verify logs
        async with get_db_connection() as db:
             async with db.execute("SELECT content FROM chat_logs WHERE session_id='test_session'") as cursor:
                 logs = await cursor.fetchall()
                 self.assertGreaterEqual(len(logs), 2)

    async def test_scheduler_jobs(self):
        # Use a small delay to allow scheduler to start jobs if any (init_scheduler is async task)
        await asyncio.sleep(0.1)
        jobs = scheduler_service.scheduler.get_jobs()
        job_ids = [j.id for j in jobs]
        self.assertIn('daily_summary', job_ids)

    async def test_reminder_tool(self):
        agent = ChatAgent()
        import datetime
        future_time = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()
        args_json = f'{{"message": "Test", "time_iso": "{future_time}"}}'

        res = await agent.tool_registry.execute("set_reminder", args_json)
        self.assertTrue(res)

        jobs = scheduler_service.scheduler.get_jobs()
        reminder_jobs = [j for j in jobs if "reminder" in str(j.id) or "reminder" in str(j.name)]
        # Our reminder ID is "1" (auto increment), function is trigger_alert.
        # Check if any job exists that is not daily_summary
        other_jobs = [j for j in jobs if j.id != 'daily_summary']
        self.assertTrue(len(other_jobs) > 0)

if __name__ == '__main__':
    unittest.main()
