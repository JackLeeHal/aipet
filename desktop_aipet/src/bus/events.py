from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class Event:
    pass

@dataclass
class UserMessage(Event):
    content: str
    session_id: str

@dataclass
class AgentResponseChunk(Event):
    content: str
    session_id: str

@dataclass
class AgentResponseFinished(Event):
    session_id: str

@dataclass
class ReminderTriggered(Event):
    reminder_id: int
    message: str

@dataclass
class SystemNotification(Event):
    message: str

@dataclass
class ReminderCreated(Event):
    reminder_id: int
    message: str
    run_date: str # ISO string

@dataclass
class ReminderUpdated(Event):
    reminder_id: int
    message: str
    run_date: str

@dataclass
class ReminderDeleted(Event):
    reminder_id: int

@dataclass
class SessionChanged(Event):
    session_id: str
