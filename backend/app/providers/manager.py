from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings

from .base import LLMCallInput, LLMError
from .clients import GeminiProvider, OpenAICompatibleProvider

T = TypeVar("T")


@dataclass
class LLMExecutionResult:
    provider: str
    raw_text: str


class LLMManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        timeout_ms = settings.llm_timeout_ms
        self.providers: Dict[str, Any] = {
            "openai": OpenAICompatibleProvider(
                name="openai",
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout_ms=timeout_ms,
            ),
            "perplexity": OpenAICompatibleProvider(
                name="perplexity",
                api_key=settings.perplexity_api_key,
                base_url=settings.perplexity_base_url,
                timeout_ms=timeout_ms,
            ),
            "gemini": GeminiProvider(
                name="gemini",
                api_key=settings.gemini_api_key,
                base_url=settings.gemini_base_url,
                timeout_ms=timeout_ms,
            ),
        }

    def any_provider_configured(self) -> bool:
        for provider_name in self.settings.llm_provider_order:
            provider = self.providers.get(provider_name)
            if provider and provider.is_configured():
                return True
        return False

    def _extract_json_text(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.DOTALL)
        if match:
            return match.group(1)

        first = stripped.find("{")
        last = stripped.rfind("}")
        if first != -1 and last != -1 and first < last:
            return stripped[first : last + 1]
        raise LLMError("Could not extract JSON object from model output", category="invalid_json")

    def _repair_json(
        self,
        provider_name: str,
        task: str,
        model: str,
        broken_payload: str,
    ) -> str:
        provider = self.providers[provider_name]
        repair_system = "You repair malformed JSON. Return valid JSON only."
        repair_user = (
            "Fix this payload so that it is valid JSON without changing semantic meaning. "
            "Return only the corrected JSON object.\n\n"
            f"{broken_payload}"
        )
        return provider.generate_text(
            LLMCallInput(
                task=f"{task}_repair",
                model=model,
                system_prompt=repair_system,
                user_prompt=repair_user,
            )
        )

    def complete_text(self, task: str, system_prompt: str, user_prompt: str) -> LLMExecutionResult:
        failover_categories = set(self.settings.llm_failover_on)
        errors: list[str] = []

        for provider_name in self.settings.llm_provider_order:
            provider = self.providers[provider_name]
            if not provider.is_configured():
                errors.append(f"{provider_name}: not configured")
                continue

            model = self.settings.get_task_model(provider_name, task)
            attempts = max(0, self.settings.llm_max_retries_per_provider)
            for _ in range(attempts + 1):
                try:
                    output = provider.generate_text(
                        LLMCallInput(
                            task=task,
                            model=model,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                        )
                    )
                    return LLMExecutionResult(provider=provider_name, raw_text=output)
                except LLMError as exc:
                    errors.append(f"{provider_name}: {exc}")
                    if exc.category not in failover_categories:
                        raise

        raise LLMError(
            "All providers failed for text completion. " + " | ".join(errors),
            category="server_error",
        )

    def complete_json_model(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
        model_type: type[BaseModel],
    ) -> Tuple[BaseModel, str]:
        failover_categories = set(self.settings.llm_failover_on)
        errors: list[str] = []

        for provider_name in self.settings.llm_provider_order:
            provider = self.providers[provider_name]
            if not provider.is_configured():
                errors.append(f"{provider_name}: not configured")
                continue

            model = self.settings.get_task_model(provider_name, task)
            attempts = max(0, self.settings.llm_max_retries_per_provider)
            for _ in range(attempts + 1):
                try:
                    raw = provider.generate_text(
                        LLMCallInput(
                            task=task,
                            model=model,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                        )
                    )

                    try:
                        extracted = self._extract_json_text(raw)
                        parsed = model_type.model_validate_json(extracted)
                        return parsed, provider_name
                    except (json.JSONDecodeError, ValidationError, LLMError):
                        repaired = self._repair_json(provider_name, task, model, raw)
                        extracted = self._extract_json_text(repaired)
                        parsed = model_type.model_validate_json(extracted)
                        return parsed, provider_name
                except LLMError as exc:
                    errors.append(f"{provider_name}: {exc}")
                    if exc.category not in failover_categories:
                        raise
                except ValidationError as exc:
                    errors.append(f"{provider_name}: invalid_json {exc}")
                    if "invalid_json" not in failover_categories:
                        raise LLMError(str(exc), category="invalid_json") from exc

        raise LLMError(
            "All providers failed for JSON completion. " + " | ".join(errors),
            category="invalid_json",
        )

    def complete_json_dict(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
    ) -> Tuple[dict[str, Any], str]:
        result = self.complete_text(task=task, system_prompt=system_prompt, user_prompt=user_prompt)
        extracted = self._extract_json_text(result.raw_text)
        try:
            parsed = json.loads(extracted)
        except json.JSONDecodeError as exc:
            repaired = self._repair_json(
                provider_name=result.provider,
                task=task,
                model=self.settings.get_task_model(result.provider, task),
                broken_payload=result.raw_text,
            )
            extracted = self._extract_json_text(repaired)
            parsed = json.loads(extracted)
        return parsed, result.provider
