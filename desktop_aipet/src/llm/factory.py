from typing import Dict, Any
from .base import LLMProvider
from .openai_provider import OpenAIProvider

def get_provider(config: Dict[str, Any]) -> LLMProvider:
    """
    Returns an LLMProvider instance based on the configuration.
    """
    llm_config = config.get("llm", {})
    api_type = llm_config.get("api_type", "openai")

    if api_type == "openai":
        return OpenAIProvider(
            api_key=llm_config.get("api_key", ""),
            base_url=llm_config.get("base_url", "https://api.openai.com/v1"),
            model=llm_config.get("model", "gpt-3.5-turbo")
        )
    # Easily extensible to anthropic or others
    elif api_type == "anthropic":
        # Placeholder for AnthropicProvider
        raise NotImplementedError("Anthropic provider not yet implemented")
    else:
        # Default fallback
        return OpenAIProvider(
            api_key=llm_config.get("api_key", ""),
            base_url=llm_config.get("base_url", "https://api.openai.com/v1"),
            model=llm_config.get("model", "gpt-3.5-turbo")
        )
