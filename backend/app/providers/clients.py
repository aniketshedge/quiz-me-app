from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

import requests

from .base import LLMCallInput, LLMCallOutput, LLMError


def _as_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _extract_cost_usd(data: dict[str, Any]) -> float | None:
    usage = data.get("usage")
    cost_candidates: list[Any] = []
    if isinstance(usage, dict):
        usage_cost = usage.get("cost")
        if isinstance(usage_cost, dict):
            cost_candidates.extend(
                [
                    usage_cost.get("total_cost"),
                    usage_cost.get("total"),
                    usage_cost.get("usd"),
                ]
            )
        cost_candidates.extend([usage.get("total_cost"), usage.get("cost_usd")])

    top_level_cost = data.get("cost")
    if isinstance(top_level_cost, dict):
        cost_candidates.extend(
            [
                top_level_cost.get("total_cost"),
                top_level_cost.get("total"),
                top_level_cost.get("usd"),
            ]
        )
    cost_candidates.append(data.get("cost_usd"))

    for candidate in cost_candidates:
        parsed = _as_float_or_none(candidate)
        if parsed is not None and parsed >= 0:
            return parsed
    return None


def _to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    def convert(node: Any) -> Any:
        if isinstance(node, dict):
            converted: dict[str, Any] = {}
            for key, value in node.items():
                if key == "type" and isinstance(value, str):
                    converted[key] = value.upper()
                elif key in {"properties", "definitions", "$defs"} and isinstance(value, dict):
                    converted[key] = {inner_key: convert(inner_value) for inner_key, inner_value in value.items()}
                elif key in {"items", "additionalProperties"}:
                    converted[key] = convert(value)
                elif key in {"anyOf", "oneOf", "allOf"} and isinstance(value, list):
                    converted[key] = [convert(item) for item in value]
                elif key == "$ref":
                    # Gemini schema does not accept JSON Schema refs.
                    continue
                else:
                    converted[key] = convert(value)
            return converted
        if isinstance(node, list):
            return [convert(item) for item in node]
        return node

    return convert(schema)


@dataclass
class OpenAICompatibleProvider:
    name: str
    api_key: str
    base_url: str
    timeout_ms: int
    supports_json_schema_response: bool = False

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_text(self, request: LLMCallInput) -> LLMCallOutput:
        if not self.is_configured():
            raise LLMError(f"Provider {self.name} is not configured", category="server_error")

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        if request.json_schema and self.supports_json_schema_response:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{request.task}_response",
                    "strict": True,
                    "schema": request.json_schema,
                },
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
        return LLMCallOutput(
            text=content.strip(),
            cost_usd=_extract_cost_usd(data),
            usage=data.get("usage") if isinstance(data.get("usage"), dict) else None,
        )


@dataclass
class GeminiProvider:
    name: str
    api_key: str
    base_url: str
    timeout_ms: int

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_text(self, request: LLMCallInput) -> LLMCallOutput:
        if not self.is_configured():
            raise LLMError(f"Provider {self.name} is not configured", category="server_error")

        model = request.model
        endpoint = f"{self.base_url.rstrip('/')}/models/{model}:generateContent"

        payload = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"parts": [{"text": request.user_prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        if request.json_schema:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = _to_gemini_schema(request.json_schema)

        try:
            response = requests.post(
                endpoint,
                headers={
                    "x-goog-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
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
        usage_metadata = data.get("usageMetadata")
        usage = usage_metadata if isinstance(usage_metadata, dict) else None
        return LLMCallOutput(text=content, cost_usd=_extract_cost_usd(data), usage=usage)
