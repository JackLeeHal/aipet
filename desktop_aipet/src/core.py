import threading
import time
import datetime
import schedule
from desktop_aipet.src import database
from desktop_aipet.src.llm import LLMClient

class PetCore:
    def __init__(self, db_path='desktop_aipet/aipet.db'):
        self.db_path = db_path
        database.init_db(self.db_path)
        self.llm = LLMClient()
        self.running = False
        self.notification_callback = None
        self.lock = threading.Lock()

    def set_notification_callback(self, callback):
        self.notification_callback = callback

    def send_user_message(self, content):
        """Handle user message: save, get response, save response."""
        database.add_message('user', content, self.db_path)

        # Build context (last 10 messages)
        history = database.get_history(limit=10, db_path=self.db_path)
        formatted_history = [{'role': row[0], 'content': row[1]} for row in history]

        response = self.llm.chat(formatted_history)
        database.add_message('assistant', response, self.db_path)
        return response

    def _check_notifications(self):
        """Check if notification is needed."""
        # Get messages from last 20 minutes (approx check)
        # Using timestamp string comparison is tricky without exact format match,
        # so we'll just get last 20 messages for simplicity in this POC,
        # or properly query by time.

        # Let's use get_messages_since properly
        # SQLite CURRENT_TIMESTAMP is in UTC, so we must use utcnow
        now = datetime.datetime.now(datetime.timezone.utc)
        ten_mins_ago = now - datetime.timedelta(minutes=20)
        # SQLite uses 'YYYY-MM-DD HH:MM:SS'
        ts_str = ten_mins_ago.strftime('%Y-%m-%d %H:%M:%S')

        recent_msgs = database.get_messages_since(ts_str, self.db_path)

        formatted_msgs = [{'role': r[0], 'content': r[1]} for r in recent_msgs]

        notification = self.llm.check_notification_needs(formatted_msgs)
        if notification and self.notification_callback:
            self.notification_callback(notification)

    def _daily_summary(self):
        """Perform daily summary for yesterday."""
        # Use UTC to align with DB timestamps
        today = datetime.datetime.now(datetime.timezone.utc).date()
        yesterday = today - datetime.timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')

        # Check if already summarized
        if database.get_summary(yesterday_str, self.db_path):
            return

        msgs = database.get_messages_for_date(yesterday_str, self.db_path)
        if msgs:
            summary = self.llm.summarize_day(msgs)
            database.save_summary(yesterday_str, summary, self.db_path)

    def run_scheduler(self):
        """Start the background scheduler."""
        self.running = True

        schedule.every(10).minutes.do(self._check_notifications)
        schedule.every().day.at("00:01").do(self._daily_summary)

        # Run _daily_summary once on startup just in case we missed it
        self._daily_summary()

        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def start(self):
        thread = threading.Thread(target=self.run_scheduler, daemon=True)
        thread.start()

    def stop(self):
        self.running = False
