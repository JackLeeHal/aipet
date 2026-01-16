# Desktop AI Pet

A modern, transparent desktop pet application featuring an LLM-based agent with long-term memory, tool usage, and automated scheduling. Built with Python, PyQt6, and Asyncio.

## Features

*   **Interactive Desktop Pet**: A transparent, always-on-top window that acts as your AI companion.
*   **LLM-Powered Chat**: Chat with your pet using OpenAI-compatible APIs. The agent maintains context of recent conversations.
*   **Long-Term Memory**: Automatically generates and stores daily summaries of your interactions to maintain continuity over days.
*   **Tool Usage**: The agent can perform actions like setting reminders for you.
*   **Scheduling**:
    *   **Midnight Summary**: Summarizes the day's events at 00:00.
    *   **Dynamic Reminders**: The agent can schedule alerts based on your requests.
*   **Modern Tech Stack**:
    *   **GUI**: PyQt6 (with `qasync` for asyncio integration).
    *   **Database**: Async SQLite (`aiosqlite`).
    *   **Scheduling**: `APScheduler`.

## Project Structure

```
desktop_aipet/
├── assets/          # Images and resources
├── config/          # Configuration files
│   └── config.json  # LLM and Pet settings
├── data/            # SQLite database storage
├── src/             # Source code
│   ├── agent_core.py       # LLM Agent logic and tools
│   ├── database.py         # Async DB handling
│   ├── main.py             # Entry point
│   ├── main_window.py      # GUI implementation
│   ├── memory_service.py   # Context and summary management
│   └── scheduler_service.py# Task scheduling
└── tests/           # Unit tests
```

## Setup

1.  **Install Dependencies**:
    Ensure you have Python 3.10+ installed.
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    Edit `desktop_aipet/config/config.json` to add your LLM API details:
    ```json
    {
        "llm": {
            "api_type": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "YOUR_API_KEY_HERE",
            "model": "gpt-3.5-turbo"
        },
        "pet": {
            "name": "RoboPet"
        }
    }
    ```

## Running the Application

To start the application, run the following command from the project root:

```bash
python -m desktop_aipet.src.main
```

## Testing

Run the test suite to verify functionality:

```bash
python -m unittest discover desktop_aipet/tests
```
