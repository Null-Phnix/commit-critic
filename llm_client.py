"""
LLM Client Abstraction Layer

Provides a clean, first-class interface for both local (Ollama) and remote
API-based LLM providers. Both backends are treated equally and expose the
same public API.

This module is designed to be provider-agnostic so the rest of the application
does not need to know which LLM backend is being used.

Environment Variables:
    LLM_PROVIDER     - "ollama" or "openai" (default: ollama)
    OLLAMA_MODEL     - Model name when using Ollama (default: llama3.1:8b)
    OPENAI_API_KEY   - Required when using API provider
    OPENAI_MODEL     - Model name when using API (default: gpt-4o-mini)
    OPENAI_BASE_URL  - Optional base URL for OpenRouter, Grok, Together, etc.
"""

import os
import json
from abc import ABC, abstractmethod
from typing import Any, Optional


class LLMError(RuntimeError):
    """Base exception for all LLM-related failures."""
    pass


def _parse_json_response(content: str) -> Any:
    """Parse JSON from a model response, tolerating accidental code fences."""
    text = content.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char not in "[{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[index:])
                return parsed
            except json.JSONDecodeError:
                continue
        raise


class LLMClient(ABC):
    """
    Abstract base class defining the interface all LLM providers must implement.

    This ensures both Ollama and API clients can be used interchangeably.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        """
        Generate a free-form text response from the LLM.

        Args:
            prompt: The main user prompt.
            system_prompt: Optional system instruction.
            temperature: Controls randomness (0.0 = deterministic, 1.0 = creative).

        Returns:
            The generated text response.
        """
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Any:
        """
        Generate a structured JSON response.

        Useful for tasks that require parsing (e.g., commit scoring, critique).

        Args:
            prompt: The main user prompt.
            system_prompt: Optional system instruction.
            temperature: Lower values are recommended for structured output.

        Returns:
            Parsed JSON as Python data.
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return a human-readable string describing the current provider."""
        pass


class OllamaClient(LLMClient):
    """
    Client for local Ollama models.

    Uses the official `ollama` Python package and supports both regular
    text generation and structured JSON output via Ollama's native format mode.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self._client = None

    def _get_client(self):
        """Lazily import and cache the ollama client."""
        if self._client is None:
            try:
                import ollama
                self._client = ollama
            except ImportError as e:
                raise LLMError(
                    "Ollama Python package is not installed. "
                    "Install it with: pip install ollama"
                ) from e
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat(
                model=self.model,
                messages=messages,
                options={"temperature": temperature},
            )
            return response["message"]["content"].strip()
        except Exception as e:
            raise LLMError(f"Ollama generation failed: {e}") from e

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Any:
        """
        Request JSON output using Ollama's native JSON mode.

        Note: Not all models respect JSON mode reliably. Stronger models
        (qwen, deepseek, etc.) tend to perform better than llama3.1.
        """
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat(
                model=self.model,
                messages=messages,
                format="json",
                options={"temperature": temperature},
            )
            content = response["message"]["content"].strip()
            return _parse_json_response(content)
        except json.JSONDecodeError as e:
            raise LLMError("Model did not return valid JSON") from e
        except Exception as e:
            raise LLMError(f"Ollama JSON generation failed: {e}") from e

    def get_provider_name(self) -> str:
        return f"ollama ({self.model})"


class OpenAIClient(LLMClient):
    """
    Client for OpenAI-compatible APIs.

    Works with official OpenAI as well as compatible providers such as
    OpenRouter, Grok, Together AI, etc. by using the `base_url` parameter.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = os.getenv("OPENAI_BASE_URL")

        if not self.api_key:
            raise LLMError("OPENAI_API_KEY environment variable is required")

        self._client = None

    def _get_client(self):
        """Lazily import and cache the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError as e:
                raise LLMError(
                    "OpenAI Python package is not installed. "
                    "Install it with: pip install openai"
                ) from e
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise LLMError(f"API generation failed: {e}") from e

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Any:
        """
        Request structured JSON output using OpenAI's response_format feature.

        This is generally more reliable than Ollama's JSON mode on weaker models.
        """
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()
            return _parse_json_response(content)
        except json.JSONDecodeError as e:
            raise LLMError("Model did not return valid JSON") from e
        except Exception as e:
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                )
                content = response.choices[0].message.content.strip()
                return _parse_json_response(content)
            except json.JSONDecodeError as json_error:
                raise LLMError("Model did not return valid JSON") from json_error
            except Exception:
                raise LLMError(f"API JSON generation failed: {e}") from e

    def get_provider_name(self) -> str:
        provider = self.base_url or "openai"
        return f"{provider} ({self.model})"


def get_llm_client() -> LLMClient:
    """
    Factory function that returns the appropriate LLM client.

    Selection is controlled by the LLM_PROVIDER environment variable.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()

    if provider == "ollama":
        return OllamaClient()
    elif provider in ("openai", "api"):
        return OpenAIClient()
    else:
        raise LLMError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            "Valid options are 'ollama' or 'openai'."
        )


if __name__ == "__main__":
    """Quick manual test of the LLM client."""
    client = get_llm_client()
    print(f"Active provider: {client.get_provider_name()}")

    text_response = client.generate("Reply with exactly one short sentence.")
    print(f"Text response: {text_response}")

    try:
        json_response = client.generate_json(
            "Return a JSON object with keys 'score' (integer 1-10) and 'reason' "
            "for this commit message: 'fixed bug'"
        )
        print(f"JSON response: {json_response}")
    except LLMError as e:
        print(f"JSON test note: {e}")
