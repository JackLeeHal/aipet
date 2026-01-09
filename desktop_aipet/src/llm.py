import json
import requests
import os

class LLMClient:
    def __init__(self, config_path='desktop_aipet/config.json'):
        self.config = self._load_config(config_path)
        self.api_key = self.config.get('llm', {}).get('api_key')
        self.base_url = self.config.get('llm', {}).get('base_url')
        self.model = self.config.get('llm', {}).get('model', 'gpt-3.5-turbo')
        self.mock_mode = self.api_key == "YOUR_API_KEY_HERE" or not self.api_key

    def _load_config(self, path):
        if not os.path.exists(path):
            return {}
        with open(path, 'r') as f:
            return json.load(f)

    def chat(self, messages):
        """
        Send chat history to LLM and get response.
        messages format: [{'role': 'user', 'content': '...'}, ...]
        """
        if self.mock_mode:
            return "This is a mock response from the AI pet."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": messages
        }

        try:
            response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=data, timeout=10)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"

    def check_notification_needs(self, recent_history):
        """
        Ask LLM if user needs notification based on recent history.
        Returns: None or notification text.
        """
        if not recent_history:
            return None

        if self.mock_mode:
            # Mock behavior: 10% chance to notify if history exists
            import random
            if random.random() < 0.1:
                 return "Time to stretch!"
            return None

        prompt = "Based on the following chat history, does the user need a reminder or notification right now? If yes, just output the notification message. If no, output exactly 'NO'."
        # Flatten history for prompt
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])

        messages = [
            {"role": "system", "content": "You are a helpful assistant that monitors chat to see if user needs reminders."},
            {"role": "user", "content": f"{prompt}\n\n{history_text}"}
        ]

        response = self.chat(messages)
        if response and response.strip().upper() != "NO":
            return response
        return None

    def summarize_day(self, daily_messages):
        """
        Summarize the day's conversation.
        """
        if not daily_messages:
            return "No messages today."

        if self.mock_mode:
            return f"Mock summary of {len(daily_messages)} messages."

        prompt = "Please summarize the important points from the following daily chat history."
        history_text = "\n".join([f"{role}: {content}" for role, content in daily_messages])

        messages = [
            {"role": "system", "content": "You are a helpful assistant that summarizes daily activities."},
            {"role": "user", "content": f"{prompt}\n\n{history_text}"}
        ]

        return self.chat(messages)
