from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
import datetime
import asyncio
from ..bus.event_bus import EventBus
from ..bus.events import ReminderCreated, ReminderUpdated, ReminderDeleted, ReminderTriggered
from ..database import get_db_connection
from ..memory_service import perform_daily_summary

class CronService:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.scheduler = AsyncIOScheduler()

    async def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

            # Subscribe to events
            self.bus.subscribe(ReminderCreated, self.on_reminder_created)
            self.bus.subscribe(ReminderUpdated, self.on_reminder_updated)
            self.bus.subscribe(ReminderDeleted, self.on_reminder_deleted)

            # Daily summary
            self.scheduler.add_job(
                perform_daily_summary,
                CronTrigger(hour=0, minute=0),
                id='daily_summary',
                replace_existing=True
            )

            await self.load_reminders()

    async def load_reminders(self):
        try:
            async with get_db_connection() as db:
                async with db.execute("SELECT id, message, run_date FROM reminders WHERE status = 'pending'") as cursor:
                    async for row in cursor:
                        r_id, message, run_date_str = row
                        await self._schedule_job(r_id, message, run_date_str)
        except Exception as e:
            print(f"Error loading reminders: {e}")

    async def _schedule_job(self, r_id, message, run_date_str):
        try:
            if isinstance(run_date_str, str):
                run_date = datetime.datetime.fromisoformat(run_date_str)
            else:
                run_date = run_date_str

            if run_date > datetime.datetime.now():
                self.scheduler.add_job(
                    self._trigger_alert,
                    DateTrigger(run_date=run_date),
                    args=[r_id, message],
                    id=str(r_id),
                    replace_existing=True
                )
            else:
                # If it's already passed but still pending, maybe we should mark it as missed or run it immediately?
                # For now, matching existing logic: ignore/skip.
                pass
        except Exception as e:
            print(f"Error scheduling reminder {r_id}: {e}")

    async def _trigger_alert(self, reminder_id, message):
        # Update DB
        try:
            async with get_db_connection() as db:
                await db.execute("UPDATE reminders SET status = 'completed' WHERE id = ?", (reminder_id,))
                await db.commit()
        except Exception as e:
            print(f"Error updating reminder status: {e}")

        # Publish event
        await self.bus.publish(ReminderTriggered(reminder_id=reminder_id, message=message))

    async def on_reminder_created(self, event: ReminderCreated):
        await self._schedule_job(event.reminder_id, event.message, event.run_date)

    async def on_reminder_updated(self, event: ReminderUpdated):
        await self._schedule_job(event.reminder_id, event.message, event.run_date)

    async def on_reminder_deleted(self, event: ReminderDeleted):
        try:
            self.scheduler.remove_job(str(event.reminder_id))
        except Exception:
            pass
