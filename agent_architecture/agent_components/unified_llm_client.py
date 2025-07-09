"""
Unified LLM Client
This module provides a single client to interact with multiple LLM providers,
mimicking the OpenAI client's API for compatibility.
"""
import json
from config import LLMConfig

class MockCompletions:
    """A mock completions object to mimic the OpenAI client structure."""
    def __init__(self, client_instance):
        self._client = client_instance

    def create(self, model: str, messages: list[dict], response_format: dict = None, temperature: float = 0.0):
        """The unified method that calls the appropriate provider."""
        return self._client._invoke(messages=messages, response_format=response_format)

class UnifiedLLMClient:
    """
    A unified client that wraps multiple LLM providers under an OpenAI-compatible API.
    """
    def __init__(self, config: LLMConfig):
        self.provider = config.provider
        self.model = config.model
        self.api_key = config.api_key
        self._client = self._initialize_client()
        # Expose the chat.completions.create() structure
        self.chat = type("Chat", (), {"completions": MockCompletions(self)})()

    def _initialize_client(self):
        if self.provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            from anthropic import Anthropic
            return Anthropic(api_key=self.api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _invoke(self, messages: list[dict], response_format: dict = None):
        """Internal method to call the correct provider."""
        if self.provider == "openai":
            return self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format
            )
        elif self.provider == "anthropic":
            system_message = ""
            if messages and messages[0]['role'] == 'system':
                system_message = messages[0]['content']
                messages = messages[1:]
            
            # Anthropic doesn't have a direct JSON mode via an API param,
            # so we instruct it in the prompt.
            if response_format and response_format.get("type") == "json_object":
                 if messages and messages[-1]['role'] == 'user':
                    messages[-1]['content'] += "\n\nYou MUST respond with a single, valid JSON object and nothing else."
                 else:
                    messages.append({"role": "user", "content": "You MUST respond with a single, valid JSON object and nothing else."})


            response = self._client.messages.create(
                model=self.model,
                system=system_message,
                messages=messages,
                max_tokens=4000
            )
            # We need to wrap the response in a mock object to be compatible
            content = response.content[0].text
            return self._create_mock_response(content)
            
    def _create_mock_response(self, content: str):
        """Creates a mock response object that mimics the OpenAI structure."""
        class MockChoice:
            def __init__(self, content):
                self.message = type("Message", (), {"content": content})()
        
        class MockResponse:
            def __init__(self, content):
                self.choices = [MockChoice(content)]
        
        return MockResponse(content)
        
    def get_provider_info(self) -> dict:
        return {"provider": self.provider, "model": self.model} 