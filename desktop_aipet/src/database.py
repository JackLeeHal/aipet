import sqlite3
import datetime
import os

DB_PATH = 'desktop_aipet/aipet.db'

def init_db(db_path=DB_PATH):
    """Initialize the database with required tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create messages table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        role TEXT NOT NULL,
        content TEXT NOT NULL
    )
    ''')

    # Create summaries table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE UNIQUE NOT NULL,
        summary TEXT NOT NULL
    )
    ''')

    conn.commit()
    conn.close()

def add_message(role, content, db_path=DB_PATH):
    """Add a new message to the history."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages (role, content) VALUES (?, ?)', (role, content))
    conn.commit()
    conn.close()

def get_history(limit=50, db_path=DB_PATH):
    """Get recent chat history."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT role, content, timestamp FROM messages ORDER BY id DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows[::-1] # Return in chronological order

def get_messages_since(timestamp_str, db_path=DB_PATH):
    """Get messages since a specific timestamp."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT role, content, timestamp FROM messages WHERE timestamp > ? ORDER BY id ASC', (timestamp_str,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_messages_for_date(date_str, db_path=DB_PATH):
    """Get all messages for a specific date (YYYY-MM-DD)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # SQLite datetime is typically 'YYYY-MM-DD HH:MM:SS'
    start = f"{date_str} 00:00:00"
    end = f"{date_str} 23:59:59"
    cursor.execute('SELECT role, content FROM messages WHERE timestamp BETWEEN ? AND ?', (start, end))
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_summary(date_str, summary, db_path=DB_PATH):
    """Save a daily summary."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO summaries (date, summary) VALUES (?, ?)', (date_str, summary))
    conn.commit()
    conn.close()

def get_summary(date_str, db_path=DB_PATH):
    """Get summary for a specific date."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT summary FROM summaries WHERE date = ?', (date_str,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None
