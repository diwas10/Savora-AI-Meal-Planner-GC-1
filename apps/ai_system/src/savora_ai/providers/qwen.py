"""HTTP client adapter and deterministic test fake for Qwen structured NLU."""

from collections.abc import Sequence
from typing import Protocol

import httpx


class QwenClient(Protocol):
    """Minimal protocol for a chat-completion provider returning raw model text."""

    def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        model: str,
        timeout_s: float,
    ) -> str: ...


class HttpxQwenClient:
    """OpenAI-compatible chat completions client using httpx with explicit timeout."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        use_json_mode: bool = True,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._use_json_mode = use_json_mode

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key) and not self._api_key.startswith("<")

    def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        model: str,
        timeout_s: float,
    ) -> str:
        if not self.is_configured:
            raise RuntimeError("QWEN_API_KEY is not configured")
        url = f"{self._base_url}/chat/completions"
        payload: dict[str, object] = {
            "model": model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        }
        if self._use_json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=timeout_s) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Qwen response missing choices")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("Qwen response content is not a string")
        return content


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
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_text": user_text,
                "model": model,
                "timeout_s": timeout_s,
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
