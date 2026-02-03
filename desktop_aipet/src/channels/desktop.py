from PyQt6.QtCore import QObject, pyqtSignal
from ..bus.event_bus import EventBus
from ..bus.events import UserMessage, AgentResponseChunk, AgentResponseFinished, ReminderTriggered, SessionChanged
import asyncio

class DesktopChannel(QObject):
    response_chunk = pyqtSignal(str)
    response_finished = pyqtSignal()
    reminder_triggered = pyqtSignal(str) # message

    def __init__(self, bus: EventBus):
        super().__init__()
        self.bus = bus
        self.bus.subscribe(AgentResponseChunk, self.on_agent_chunk)
        self.bus.subscribe(AgentResponseFinished, self.on_agent_finished)
        self.bus.subscribe(ReminderTriggered, self.on_reminder_triggered)

        self.current_session_id = None

    def set_session_id(self, session_id):
        self.current_session_id = session_id

    async def switch_session(self, session_id: str):
        self.current_session_id = session_id
        await self.bus.publish(SessionChanged(session_id=session_id))

    async def send_user_message(self, content: str):
        if self.current_session_id:
            await self.bus.publish(UserMessage(content=content, session_id=self.current_session_id))

    async def on_agent_chunk(self, event: AgentResponseChunk):
        if event.session_id == self.current_session_id:
            self.response_chunk.emit(event.content)

    async def on_agent_finished(self, event: AgentResponseFinished):
        if event.session_id == self.current_session_id:
            self.response_finished.emit()

    async def on_reminder_triggered(self, event: ReminderTriggered):
        self.reminder_triggered.emit(event.message)
