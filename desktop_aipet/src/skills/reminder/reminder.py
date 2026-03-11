import datetime
from desktop_aipet.src.skills.base import Skill
from desktop_aipet.src.bus.event_bus import EventBus
from desktop_aipet.src.bus.events import ReminderCreated, ReminderUpdated, ReminderDeleted
from desktop_aipet.src.database import get_db_connection

# Standalone functions for UI and Skill usage
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

async def delete_reminder(reminder_id: int, bus: EventBus = None):
    try:
        async with get_db_connection() as db:
            await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            await db.commit()

        if bus:
            await bus.publish(ReminderDeleted(reminder_id=reminder_id))
        return True
    except Exception as e:
        print(f"Error deleting reminder: {e}")
        return False

async def update_reminder(reminder_id: int, message: str, time_iso: str, bus: EventBus = None):
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

        if bus:
            await bus.publish(ReminderUpdated(reminder_id=reminder_id, message=message, run_date=time_iso))
        return True
    except Exception as e:
        print(f"Error updating reminder: {e}")
        return False

class ReminderSkill(Skill):
    def __init__(self, bus: EventBus):
        self.bus = bus

    @property
    def name(self) -> str:
        return "set_reminder"

    @property
    def description(self) -> str:
        return "Set a reminder for a specific time."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The reminder message."},
                "time_iso": {"type": "string", "description": "ISO 8601 format time (e.g., 2023-10-27T14:30:00)."}
            },
            "required": ["message", "time_iso"]
        }

    async def execute(self, message: str, time_iso: str) -> str:
        try:
            run_date = datetime.datetime.fromisoformat(time_iso)
            if run_date < datetime.datetime.now():
                return f"Error: Cannot schedule reminder in the past: {time_iso}"

            async with get_db_connection() as db:
                cursor = await db.execute(
                    "INSERT INTO reminders (message, run_date, status) VALUES (?, ?, 'pending')",
                    (message, time_iso)
                )
                await db.commit()
                reminder_id = cursor.lastrowid

            await self.bus.publish(ReminderCreated(reminder_id=reminder_id, message=message, run_date=time_iso))
            return f"Reminder scheduled for {time_iso}: {message}"
        except ValueError:
            return f"Error: Invalid time format: {time_iso}"
        except Exception as e:
            return f"Error scheduling reminder: {str(e)}"
