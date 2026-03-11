from abc import ABC, abstractmethod
from typing import Any, Dict, List, Callable, AsyncGenerator

class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Any:
        """
        Send a chat completion request to the LLM.
        Should return an object that contains the response content and tool calls.
        """
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        on_chunk: Callable[[str], Any] = None
    ) -> Any:
        """
        Send a chat completion request to the LLM and stream the response.
        The `on_chunk` callback will be called with each text chunk received.
        Should return the final response object, similar to `chat()`.
        """
        pass
