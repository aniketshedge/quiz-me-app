from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

import requests

from .base import LLMCallInput, LLMError


@dataclass
class OpenAICompatibleProvider:
    name: str
    api_key: str
    base_url: str
    timeout_ms: int

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_text(self, request: LLMCallInput) -> str:
        if not self.is_configured():
            raise LLMError(f"Provider {self.name} is not configured", category="server_error")

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": 0.2,
        }

        try:
            response = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_ms / 1000,
            )
        except requests.Timeout as exc:
            raise LLMError(f"Provider {self.name} timed out", category="timeout") from exc
        except requests.RequestException as exc:
            raise LLMError(
                f"Provider {self.name} network error: {exc}", category="server_error"
            ) from exc

        if response.status_code == 429:
            raise LLMError(f"Provider {self.name} rate limited", category="rate_limit")
        if response.status_code >= 500:
            raise LLMError(f"Provider {self.name} server error", category="server_error")
        if response.status_code >= 400:
            raise LLMError(
                f"Provider {self.name} request error: {response.text[:200]}",
                category="server_error",
            )

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise LLMError(f"Provider {self.name} returned no choices", category="server_error")

        content = choices[0].get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise LLMError(
                f"Provider {self.name} returned empty content", category="server_error"
            )
        return content.strip()


@dataclass
class GeminiProvider:
    name: str
    api_key: str
    base_url: str
    timeout_ms: int

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_text(self, request: LLMCallInput) -> str:
        if not self.is_configured():
            raise LLMError(f"Provider {self.name} is not configured", category="server_error")

        model = request.model
        endpoint = (
            f"{self.base_url.rstrip('/')}/models/{model}:generateContent?key={self.api_key}"
        )

        payload = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"parts": [{"text": request.user_prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        try:
            response = requests.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=self.timeout_ms / 1000,
            )
        except requests.Timeout as exc:
            raise LLMError(f"Provider {self.name} timed out", category="timeout") from exc
        except requests.RequestException as exc:
            raise LLMError(
                f"Provider {self.name} network error: {exc}", category="server_error"
            ) from exc

        if response.status_code == 429:
            raise LLMError(f"Provider {self.name} rate limited", category="rate_limit")
        if response.status_code >= 500:
            raise LLMError(f"Provider {self.name} server error", category="server_error")
        if response.status_code >= 400:
            raise LLMError(
                f"Provider {self.name} request error: {response.text[:200]}",
                category="server_error",
            )

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise LLMError(f"Provider {self.name} returned no candidates", category="server_error")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        content = "\n".join(text_parts).strip()
        if not content:
            raise LLMError(
                f"Provider {self.name} returned empty content", category="server_error"
            )
        return content
