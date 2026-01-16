import json
import os
import datetime
from .database import get_db_connection
from openai import AsyncOpenAI

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'config.json')

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

async def get_llm_client():
    config = load_config()
    api_key = config['llm'].get('api_key')
    base_url = config['llm'].get('base_url')
    model = config['llm'].get('model', 'gpt-3.5-turbo')

    if not api_key or api_key == "YOUR_API_KEY_HERE":
        pass

    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url
    ), model

async def get_context(session_id: str):
    """
    1. Fetch the last 5 daily_summaries (descending by date).
    2. Fetch the last 20 messages from chat_logs for the current session.
    3. Combine them into a formatted System Prompt context.
    """
    async with get_db_connection() as db:
        # Fetch last 5 daily summaries
        async with db.execute('SELECT date, summary_text, key_events FROM daily_summaries ORDER BY date DESC LIMIT 5') as cursor:
            summaries = await cursor.fetchall()

        # Fetch last 20 messages
        async with db.execute('SELECT role, content, timestamp FROM chat_logs WHERE session_id = ? ORDER BY timestamp DESC LIMIT 20', (session_id,)) as cursor:
            logs = await cursor.fetchall()
            logs.reverse() # We want chronological order (oldest first)

    context = "=== System Context ===\n"

    if summaries:
        context += "--- Previous Days Summaries ---\n"
        for s in summaries:
            context += f"Date: {s[0]}\nSummary: {s[1]}\nKey Events: {s[2]}\n\n"

    if logs:
        context += "--- Recent Chat History ---\n"
        for log in logs:
            # log[2] is timestamp
            context += f"[{log[2]}] {log[0]}: {log[1]}\n"

    return context

async def perform_daily_summary():
    """
    1. Query chat_logs where timestamp is today.
    2. If logs exist, call LLM to summarize and extract key events.
    3. Insert into daily_summaries.
    """
    today = datetime.date.today().isoformat()

    async with get_db_connection() as db:
        # Check if summary already exists for today
        async with db.execute('SELECT id FROM daily_summaries WHERE date = ?', (today,)) as cursor:
            if await cursor.fetchone():
                print(f"Summary for {today} already exists.")
                return

        # Fetch logs for today. Assumes timestamp is ISO format YYYY-MM-DD...
        # SQLite function date() works on such strings.
        async with db.execute("SELECT role, content FROM chat_logs WHERE date(timestamp) = ?", (today,)) as cursor:
            logs = await cursor.fetchall()

    if not logs:
        print("No logs for today to summarize.")
        return

    log_text = "\n".join([f"{role}: {content}" for role, content in logs])

    # Call LLM
    try:
        client, model = await get_llm_client()
        if not client.api_key or client.api_key == "YOUR_API_KEY_HERE":
             print("Skipping LLM summary due to missing API Key.")
             return

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Summarize the following chat logs and extract key events (facts/todos) as a JSON list."},
                {"role": "user", "content": f"Chat Logs:\n{log_text}\n\nProvide response in JSON format: {{'summary': 'text', 'key_events': ['event1', 'event2']}}"}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        summary_text = data.get('summary', '')
        key_events = json.dumps(data.get('key_events', []))

        async with get_db_connection() as db:
            await db.execute('INSERT INTO daily_summaries (date, summary_text, key_events) VALUES (?, ?, ?)', (today, summary_text, key_events))
            await db.commit()
            print(f"Daily summary for {today} created.")

    except Exception as e:
        print(f"Error generating summary: {e}")
