import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop
from .database import init_db
from .scheduler_service import start_scheduler
from .agent_core import ChatAgent
from .main_window import MainWindow

async def main_async():
    # Initialize DB
    await init_db()

    # Initialize Scheduler
    start_scheduler()

    # Initialize Agent
    agent = ChatAgent()
    # Start a default session
    await agent.start_session(session_id="default_session")

    # Initialize GUI
    window = MainWindow(agent)
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
