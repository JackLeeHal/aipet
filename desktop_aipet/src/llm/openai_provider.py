import json
from typing import Any, Dict, List, Callable
from openai import AsyncOpenAI
from .base import LLMProvider

class OpenAILikeResponse:
    def __init__(self, content: str = "", tool_calls: List[Dict[str, Any]] = None):
        self.content = content
        self.tool_calls = tool_calls or []

    @property
    def stop_reason(self) -> str:
        if self.tool_calls:
            return "tool_use"
        return "stop"

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

        # We instantiate it but if api_key is missing, we handle it gracefully during chat
        self.client = AsyncOpenAI(
            api_key=self.api_key or "DUMMY",
            base_url=self.base_url
        )

    async def _check_api_key(self):
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            raise ValueError("I'm sorry, but I haven't been configured with a valid API key yet.")

    async def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> OpenAILikeResponse:
        await self._check_api_key()

        kwargs = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        msg = choice.message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })

        return OpenAILikeResponse(content=msg.content or "", tool_calls=tool_calls)

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        on_chunk: Callable[[str], Any] = None
    ) -> OpenAILikeResponse:
        await self._check_api_key()

        kwargs = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = await self.client.chat.completions.create(**kwargs)

        response_text = ""
        tool_calls_accumulated = []

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                response_text += delta.content
                if on_chunk:
                    await on_chunk(delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if len(tool_calls_accumulated) <= tc.index:
                        tool_calls_accumulated.append({"name": "", "arguments": "", "id": ""})

                    if tc.id:
                        tool_calls_accumulated[tc.index]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_accumulated[tc.index]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_accumulated[tc.index]["arguments"] += tc.function.arguments

        final_tool_calls = []
        for tc in tool_calls_accumulated:
            final_tool_calls.append({
                "id": tc["id"],
                "function": {
                    "name": tc["name"],
                    "arguments": tc["arguments"]
                }
            })

        return OpenAILikeResponse(content=response_text, tool_calls=final_tool_calls)
