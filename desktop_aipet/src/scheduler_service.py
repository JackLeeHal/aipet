from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from .memory_service import perform_daily_summary
from .database import get_db_connection
import datetime
import asyncio

scheduler = AsyncIOScheduler()
_alert_callback = None

def set_alert_callback(callback):
    """Sets the callback function to be called when a reminder triggers."""
    global _alert_callback
    _alert_callback = callback

async def trigger_alert(reminder_id: int, message: str):
    print(f"ALERT TRIGGERED: {message} (ID: {reminder_id})")

    # Update status in DB
    try:
        async with get_db_connection() as db:
            await db.execute("UPDATE reminders SET status = 'completed' WHERE id = ?", (reminder_id,))
            await db.commit()
    except Exception as e:
        print(f"Error updating reminder status: {e}")

    if _alert_callback:
        # Check if callback is async or sync
        if asyncio.iscoroutinefunction(_alert_callback):
             await _alert_callback(message)
        else:
             # If it's a Qt slot or normal function
             try:
                 _alert_callback(message)
             except Exception as e:
                 print(f"Error in alert callback: {e}")

async def init_scheduler():
    """Loads pending reminders from DB and starts scheduler."""
    if not scheduler.running:
        scheduler.start()

        # Schedule daily summary
        scheduler.add_job(
            perform_daily_summary,
            CronTrigger(hour=0, minute=0),
            id='daily_summary',
            replace_existing=True
        )

        # Load pending reminders
        try:
            async with get_db_connection() as db:
                async with db.execute("SELECT id, message, run_date FROM reminders WHERE status = 'pending'") as cursor:
                    async for row in cursor:
                        r_id, message, run_date_str = row
                        try:
                            if isinstance(run_date_str, str):
                                run_date = datetime.datetime.fromisoformat(run_date_str)
                            else:
                                run_date = run_date_str

                            if run_date > datetime.datetime.now():
                                scheduler.add_job(
                                    trigger_alert,
                                    DateTrigger(run_date=run_date),
                                    args=[r_id, message],
                                    id=str(r_id),
                                    replace_existing=True
                                )
                            else:
                                print(f"Skipping past reminder {r_id}: {run_date}")
                        except Exception as e:
                            print(f"Error loading reminder {r_id}: {e}")
        except Exception as e:
            print(f"Error initializing scheduler from DB: {e}")

        print("Scheduler started and reminders loaded.")

def start_scheduler():
    """Starts the scheduler (wrapper for init_scheduler)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.create_task(init_scheduler())

async def schedule_reminder(message: str, time_iso: str):
    """
    Schedules a reminder.
    time_iso: ISO format datetime string (e.g. 2023-10-27T14:30:00)
    """
    try:
        run_date = datetime.datetime.fromisoformat(time_iso)
        if run_date < datetime.datetime.now():
            print(f"Cannot schedule reminder in the past: {time_iso}")
            return False

        async with get_db_connection() as db:
            cursor = await db.execute(
                "INSERT INTO reminders (message, run_date, status) VALUES (?, ?, 'pending')",
                (message, time_iso)
            )
            await db.commit()
            reminder_id = cursor.lastrowid

        scheduler.add_job(
            trigger_alert,
            DateTrigger(run_date=run_date),
            args=[reminder_id, message],
            id=str(reminder_id)
        )
        print(f"Reminder scheduled for {time_iso}: {message} (ID: {reminder_id})")
        return True
    except ValueError:
        print(f"Invalid time format: {time_iso}")
        return False
    except Exception as e:
        print(f"Error scheduling reminder: {e}")
        return False

async def delete_reminder(reminder_id: int):
    try:
        async with get_db_connection() as db:
            await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            await db.commit()

        try:
            scheduler.remove_job(str(reminder_id))
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"Error deleting reminder: {e}")
        return False

async def update_reminder(reminder_id: int, message: str, time_iso: str):
    try:
        run_date = datetime.datetime.fromisoformat(time_iso)
        if run_date < datetime.datetime.now():
            return False

        async with get_db_connection() as db:
            await db.execute(
                "UPDATE reminders SET message = ?, run_date = ?, status = 'pending' WHERE id = ?",
                (message, time_iso, reminder_id)
            )
            await db.commit()

        if scheduler.get_job(str(reminder_id)):
            scheduler.reschedule_job(
                str(reminder_id),
                trigger=DateTrigger(run_date=run_date)
            )
            scheduler.modify_job(str(reminder_id), args=[reminder_id, message])
        else:
             scheduler.add_job(
                trigger_alert,
                DateTrigger(run_date=run_date),
                args=[reminder_id, message],
                id=str(reminder_id)
            )

        return True
    except Exception as e:
        print(f"Error updating reminder: {e}")
        return False

async def get_all_reminders():
    reminders = []
    try:
        async with get_db_connection() as db:
            async with db.execute("SELECT id, message, run_date, status FROM reminders ORDER BY run_date ASC") as cursor:
                async for row in cursor:
                    reminders.append({
                        "id": row[0],
                        "message": row[1],
                        "run_date": row[2],
                        "status": row[3]
                    })
    except Exception as e:
        print(f"Error fetching reminders: {e}")
    return reminders
