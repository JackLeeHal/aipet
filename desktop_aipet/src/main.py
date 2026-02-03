import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop
from .database import init_db
from .bus.event_bus import EventBus
from .agent.brain import AgentBrain
from .cron.scheduler import CronService
from .channels.desktop import DesktopChannel
from .main_window import MainWindow

async def main_async():
    # Initialize DB
    await init_db()

    # Initialize Components
    bus = EventBus()
    agent = AgentBrain(bus)
    cron = CronService(bus)
    channel = DesktopChannel(bus)

    # Start Services
    await cron.start()

    # Start a default session
    await agent.start_session(session_id="default_session")
    channel.set_session_id("default_session")

    # Initialize GUI
    window = MainWindow(channel)
    window.show()

    # Keep the application running
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass

def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        try:
            loop.run_until_complete(main_async())
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
