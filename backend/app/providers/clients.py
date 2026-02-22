from __future__ import annotations

import json
from copy import deepcopy
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


def _looks_like_gemini_schema_error(response_text: str) -> bool:
    lowered = response_text.lower()
    has_schema_path = (
        "response_schema" in lowered
        or "responseschema" in lowered
        or "generation_config.responseschema" in lowered
        or "generation_config.response_schema" in lowered
    )
    has_schema_keyword = (
        "$defs" in response_text
        or "$ref" in response_text
        or "cannot find field" in lowered
        or "unknown name" in lowered
    )
    return has_schema_path or (("invalid json payload" in lowered) and has_schema_keyword)


def _to_openai_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    root = deepcopy(schema)

    def normalize(node: Any) -> Any:
        if isinstance(node, dict):
            normalized = {key: normalize(value) for key, value in node.items()}

            if normalized.get("type") == "object":
                properties = normalized.get("properties")
                if isinstance(properties, dict):
                    normalized.setdefault("additionalProperties", False)
                    required = normalized.get("required")
                    if isinstance(required, list):
                        missing = [key for key in properties.keys() if key not in required]
                        if missing:
                            normalized["required"] = [*required, *missing]
                    else:
                        normalized["required"] = list(properties.keys())
            return normalized

        if isinstance(node, list):
            return [normalize(item) for item in node]
        return node

    normalized_root = normalize(root)
    if isinstance(normalized_root, dict):
        return normalized_root
    return {"type": "object", "additionalProperties": False}


def _to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    root = deepcopy(schema)
    definitions: dict[str, Any] = {}

    for key in ("$defs", "definitions"):
        candidate = root.get(key)
        if isinstance(candidate, dict):
            definitions.update(candidate)

    def resolve_ref(ref: str) -> dict[str, Any] | None:
        if ref.startswith("#/$defs/"):
            return definitions.get(ref[len("#/$defs/") :])
        if ref.startswith("#/definitions/"):
            return definitions.get(ref[len("#/definitions/") :])
        return None

    def convert(node: Any, depth: int = 0) -> Any:
        if depth > 80:
            return node

        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str):
                target = resolve_ref(node["$ref"])
                if isinstance(target, dict):
                    merged = deepcopy(target)
                    for k, v in node.items():
                        if k != "$ref":
                            merged[k] = v
                    return convert(merged, depth + 1)

            if "anyOf" in node and isinstance(node["anyOf"], list):
                non_null_items = []
                has_null = False
                for item in node["anyOf"]:
                    if isinstance(item, dict) and item.get("type") == "null":
                        has_null = True
                    else:
                        non_null_items.append(item)

                passthrough_keys = {"anyOf", "title", "description", "default", "examples", "example"}
                if has_null and len(non_null_items) == 1 and all(k in passthrough_keys for k in node):
                    base = convert(non_null_items[0], depth + 1)
                    if isinstance(base, dict):
                        base["nullable"] = True
                        if "description" in node and "description" not in base:
                            base["description"] = node["description"]
                        return base

            converted: dict[str, Any] = {}
            for key, value in node.items():
                if key in {
                    "$defs",
                    "definitions",
                    "$schema",
                    "$id",
                    "$anchor",
                    "$ref",
                    "title",
                    "examples",
                    "example",
                    "default",
                    "const",
                    "discriminator",
                }:
                    continue
                if key == "type" and isinstance(value, str):
                    if value == "null":
                        continue
                    converted[key] = value.upper()
                    continue
                if key in {"properties"} and isinstance(value, dict):
                    converted[key] = {
                        inner_key: convert(inner_value, depth + 1)
                        for inner_key, inner_value in value.items()
                    }
                    continue
                if key in {"items", "additionalProperties"}:
                    converted[key] = convert(value, depth + 1)
                    continue
                if key in {"anyOf", "oneOf", "allOf"} and isinstance(value, list):
                    converted[key] = [convert(item, depth + 1) for item in value]
                    continue
                converted[key] = convert(value, depth + 1)
            return converted

        if isinstance(node, list):
            return [convert(item, depth + 1) for item in node]
        return node

    converted_root = convert(root)
    if not isinstance(converted_root, dict):
        return {"type": "OBJECT"}
    return converted_root


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
            strict_schema = _to_openai_strict_schema(request.json_schema)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{request.task}_response",
                    "strict": True,
                    "schema": strict_schema,
                },
            }
        if request.max_output_tokens and self.name == "perplexity":
            payload["max_tokens"] = request.max_output_tokens

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

        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"parts": [{"text": request.user_prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        schema_requested = False
        if request.json_schema:
            schema_requested = True
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = _to_gemini_schema(request.json_schema)

        def post_payload(active_payload: dict[str, Any]) -> requests.Response:
            try:
                return requests.post(
                    endpoint,
                    headers={
                        "x-goog-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(active_payload),
                    timeout=self.timeout_ms / 1000,
                )
            except requests.Timeout as exc:
                raise LLMError(f"Provider {self.name} timed out", category="timeout") from exc
            except requests.RequestException as exc:
                raise LLMError(
                    f"Provider {self.name} network error: {exc}", category="server_error"
                ) from exc

        response = post_payload(payload)

        # Gemini may reject responseSchema for some JSON-Schema constructs even after conversion.
        # Retry once without responseSchema so provider fallback can still succeed with JSON-only prompting.
        if (
            schema_requested
            and response.status_code == 400
            and _looks_like_gemini_schema_error(response.text)
        ):
            generation_config = dict(payload.get("generationConfig", {}))
            generation_config.pop("responseSchema", None)
            payload_without_schema = dict(payload)
            payload_without_schema["generationConfig"] = generation_config
            response = post_payload(payload_without_schema)

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
