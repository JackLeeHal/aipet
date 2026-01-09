# Desktop AI Pet POC

A desktop pet application with chat, notifications, and daily summaries powered by LLMs.

## Features

1.  **Desktop Pet**: A draggable window with a pet image.
2.  **Chat**: Chat with your pet, powered by OpenAI-compatible LLMs.
3.  **Notifications**: The pet checks chat history every 10 minutes and notifies you if needed.
4.  **Daily Summary**: Automatically summarizes daily conversations and stores them locally.

## Setup

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

2.  Configure `desktop_aipet/config.json` with your LLM API key.

## Running the Application

To run the application, execute the following command from the root directory:

```bash
python -m desktop_aipet.src.main
```

## Testing

Run tests with:

```bash
python -m unittest discover desktop_aipet/tests
```
