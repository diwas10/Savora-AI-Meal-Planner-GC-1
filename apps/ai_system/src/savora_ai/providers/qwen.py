"""Qwen HTTP adapters (local Ollama by default, OpenAI-compatible optional) and a test fake.

Team decision (21 Oct 2026, `docs/member3/IMPLEMENTATION_SPEC.md` section 2 item 4): a
small quantized Qwen runs locally in Ollama (`qwen3:0.6b`), with decoding constrained to
the `CravingRequest` JSON schema and thinking off. A hosted OpenAI-compatible endpoint
still works when `QWEN_PROVIDER=openai` and a key is set.

Each client owns one pooled `httpx.Client`; build it once at startup, not per request.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Literal, Protocol

import httpx

QwenProvider = Literal["ollama", "openai"]
MAX_TOKENS = 200  # a valid answer is under 100 tokens; a runaway generation is cut
SEED = 7


class QwenClient(Protocol):
    """A chat model that returns the raw text of one answer."""

    def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        model: str,
        timeout_s: float,
        json_schema: Mapping[str, Any] | None = None,
    ) -> str: ...


class OllamaQwenClient:
    """Local Ollama `/api/chat` with schema-constrained decoding (`format`)."""

    def __init__(self, *, base_url: str = "http://localhost:11434") -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client()

    def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        model: str,
        timeout_s: float,
        json_schema: Mapping[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "seed": SEED, "num_predict": MAX_TOKENS},
            "format": dict(json_schema) if json_schema is not None else "json",
        }
        response = self._http.post(f"{self._base_url}/api/chat", json=payload, timeout=timeout_s)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("Ollama response has no message content")
        return content

    def close(self) -> None:
        self._http.close()


class OpenAICompatibleQwenClient:
    """Hosted OpenAI-compatible chat completions (`response_format` json_schema)."""

    def __init__(self, *, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._http = httpx.Client()

    def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        model: str,
        timeout_s: float,
        json_schema: Mapping[str, Any] | None = None,
    ) -> str:
        response_format: dict[str, Any] = (
            {
                "type": "json_schema",
                "json_schema": {"name": "craving_request", "schema": dict(json_schema)},
            }
            if json_schema is not None
            else {"type": "json_object"}
        )
        payload: dict[str, Any] = {
            "model": model,
            "temperature": 0.0,
            "seed": SEED,
            "max_tokens": MAX_TOKENS,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "response_format": response_format,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        response = self._http.post(
            f"{self._base_url}/chat/completions", json=payload, headers=headers, timeout=timeout_s
        )
        response.raise_for_status()
        choices = response.json().get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Qwen response has no choices")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("Qwen response content is not a string")
        return content

    def close(self) -> None:
        self._http.close()


def build_qwen_client(
    *, provider: QwenProvider, base_url: str, api_key: str = ""
) -> OllamaQwenClient | OpenAICompatibleQwenClient:
    if provider == "openai":
        return OpenAICompatibleQwenClient(base_url=base_url, api_key=api_key)
    return OllamaQwenClient(base_url=base_url)


class FakeQwenClient:
    """Deterministic fake Qwen client for tests (supports scripted and malicious outputs)."""

    def __init__(
        self,
        responses: Sequence[str | Exception] | dict[str, str | Exception] = (),
        *,
        default_response: str | Exception | None = None,
    ) -> None:
        self._script: list[str | Exception] = (
            list(responses) if not isinstance(responses, dict) else []
        )
        self._by_text: dict[str, str | Exception] = (
            dict(responses) if isinstance(responses, dict) else {}
        )
        self._default = default_response
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        model: str,
        timeout_s: float,
        json_schema: Mapping[str, Any] | None = None,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_text": user_text,
                "model": model,
                "timeout_s": timeout_s,
                "json_schema": json_schema,
            }
        )
        if user_text in self._by_text:
            item = self._by_text[user_text]
        elif self._script:
            item = self._script.pop(0)
        elif self._default is not None:
            item = self._default
        else:
            raise TimeoutError("FakeQwenClient has no scripted response")
        if isinstance(item, Exception):
            raise item
        return item
