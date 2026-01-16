from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from .memory_service import perform_daily_summary
import datetime
import asyncio

scheduler = AsyncIOScheduler()
_alert_callback = None

def set_alert_callback(callback):
    """Sets the callback function to be called when a reminder triggers."""
    global _alert_callback
    _alert_callback = callback

def trigger_alert(message: str):
    print(f"ALERT TRIGGERED: {message}")
    if _alert_callback:
        # Check if callback is async or sync
        if asyncio.iscoroutinefunction(_alert_callback):
             asyncio.create_task(_alert_callback(message))
        else:
             # If it's a Qt slot or normal function
             try:
                 _alert_callback(message)
             except Exception as e:
                 print(f"Error in alert callback: {e}")

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        # Schedule daily summary at 00:00
        scheduler.add_job(
            perform_daily_summary,
            CronTrigger(hour=0, minute=0),
            id='daily_summary',
            replace_existing=True
        )
        print("Scheduler started. Daily summary scheduled for 00:00.")

def schedule_reminder(message: str, time_iso: str):
    """
    Schedules a reminder.
    time_iso: ISO format datetime string (e.g. 2023-10-27T14:30:00)
    """
    try:
        run_date = datetime.datetime.fromisoformat(time_iso)
        # Check if time is in future
        if run_date < datetime.datetime.now():
            print(f"Cannot schedule reminder in the past: {time_iso}")
            return False

        scheduler.add_job(
            trigger_alert,
            DateTrigger(run_date=run_date),
            args=[message],
            name=f"reminder_{time_iso}"
        )
        print(f"Reminder scheduled for {time_iso}: {message}")
        return True
    except ValueError:
        print(f"Invalid time format: {time_iso}")
        return False
