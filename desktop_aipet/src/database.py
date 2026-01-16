import aiosqlite
import os
import asyncio

# Define the database path relative to this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'aipet.db')

async def init_db():
    """Initializes the database with the required tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp DATETIME,
                tool_calls TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS daily_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                summary_text TEXT,
                key_events TEXT
            )
        ''')
        await db.commit()

def get_db_path():
    return DB_PATH

def get_db_connection():
    """Returns a connection context manager to the database."""
    return aiosqlite.connect(DB_PATH)
