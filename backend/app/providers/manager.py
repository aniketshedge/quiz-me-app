from __future__ import annotations

import json
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Dict, Tuple, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.telemetry import LLMTelemetryStore

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
        self.telemetry = LLMTelemetryStore(
            enabled=settings.llm_telemetry_enabled,
            base_dir=settings.llm_telemetry_dir,
        )
        timeout_ms = settings.llm_timeout_ms
        self.providers: Dict[str, Any] = {
            "openai": OpenAICompatibleProvider(
                name="openai",
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout_ms=timeout_ms,
                supports_json_schema_response=True,
            ),
            "perplexity": OpenAICompatibleProvider(
                name="perplexity",
                api_key=settings.perplexity_api_key,
                base_url=settings.perplexity_base_url,
                timeout_ms=timeout_ms,
                supports_json_schema_response=False,
            ),
            "gemini": GeminiProvider(
                name="gemini",
                api_key=settings.gemini_api_key,
                base_url=settings.gemini_base_url,
                timeout_ms=timeout_ms,
            ),
        }

    def _should_failover(self, category: str) -> bool:
        failover_categories = set(self.settings.llm_failover_on)
        return "all" in failover_categories or category in failover_categories

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

    @staticmethod
    def _prompt_with_truncation_guard(user_prompt: str) -> str:
        return (
            user_prompt
            + "\n\nCRITICAL: Return one COMPLETE JSON object with all required fields and all 15 questions. "
            + "Do not truncate. Ensure all arrays/objects are fully closed."
        )

    @staticmethod
    def _extra_invalid_json_retry_limit(provider_name: str, task: str) -> int:
        if provider_name == "perplexity" and task == "quiz_generation":
            return 1
        return 0

    @staticmethod
    def _max_output_tokens(provider_name: str, task: str) -> int | None:
        if provider_name != "perplexity":
            return None
        if task.startswith("quiz_generation"):
            return 8000
        return None

    def _repair_json(
        self,
        provider_name: str,
        task: str,
        model: str,
        broken_payload: str,
        json_schema: dict[str, Any] | None = None,
        validation_error: str | None = None,
    ) -> str:
        provider = self.providers[provider_name]
        repair_system = (
            "You are a deterministic JSON repair engine. "
            "Return exactly one valid JSON object. "
            "No markdown, no comments, no code fences, no extra text."
        )
        repair_sections = [
            "Fix the payload so it parses as valid JSON and matches the target constraints.",
            "Preserve original semantic meaning as much as possible.",
            "Use proper JSON types: booleans true/false, numbers unquoted, strings quoted.",
            "Return only the corrected JSON object and nothing else.",
        ]
        if validation_error:
            repair_sections.append(
                "Validation error details:\n"
                f"{validation_error[:4000]}"
            )
        if json_schema:
            repair_sections.append(
                "Target JSON schema:\n"
                f"{json.dumps(json_schema)[:12000]}"
            )
        repair_sections.append("Broken payload:\n" + broken_payload[:24000])
        repair_user = "\n\n".join(repair_sections)
        started_at = perf_counter()
        attempt = 1
        try:
            repaired = provider.generate_text(
                LLMCallInput(
                    task=f"{task}_repair",
                    model=model,
                    system_prompt=repair_system,
                    user_prompt=repair_user,
                    max_output_tokens=self._max_output_tokens(provider_name, f"{task}_repair"),
                )
            )
            self.telemetry.measure_and_record(
                operation="repair_json",
                task=f"{task}_repair",
                provider=provider_name,
                model=model,
                attempt=attempt,
                started_at=started_at,
                outcome="success",
                category="success",
                cost_usd=repaired.cost_usd,
            )
            return repaired.text
        except LLMError as exc:
            self.telemetry.measure_and_record(
                operation="repair_json",
                task=f"{task}_repair",
                provider=provider_name,
                model=model,
                attempt=attempt,
                started_at=started_at,
                outcome="error",
                category=exc.category,
                error_message=str(exc),
            )
            raise
        except Exception as exc:
            self.telemetry.measure_and_record(
                operation="repair_json",
                task=f"{task}_repair",
                provider=provider_name,
                model=model,
                attempt=attempt,
                started_at=started_at,
                outcome="error",
                category="server_error",
                error_message=str(exc),
            )
            raise

    def complete_text(self, task: str, system_prompt: str, user_prompt: str) -> LLMExecutionResult:
        errors: list[str] = []

        for provider_name in self.settings.llm_provider_order:
            provider = self.providers[provider_name]
            if not provider.is_configured():
                errors.append(f"{provider_name}: not configured")
                continue

            model = self.settings.get_task_model(provider_name, task)
            attempts = max(0, self.settings.llm_max_retries_per_provider)
            for attempt_index in range(attempts + 1):
                attempt_number = attempt_index + 1
                started_at = perf_counter()
                try:
                    output = provider.generate_text(
                        LLMCallInput(
                            task=task,
                            model=model,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                        )
                    )
                    self.telemetry.measure_and_record(
                        operation="complete_text",
                        task=task,
                        provider=provider_name,
                        model=model,
                        attempt=attempt_number,
                        started_at=started_at,
                        outcome="success",
                        category="success",
                        cost_usd=output.cost_usd,
                    )
                    return LLMExecutionResult(provider=provider_name, raw_text=output.text)
                except LLMError as exc:
                    self.telemetry.measure_and_record(
                        operation="complete_text",
                        task=task,
                        provider=provider_name,
                        model=model,
                        attempt=attempt_number,
                        started_at=started_at,
                        outcome="error",
                        category=exc.category,
                        error_message=str(exc),
                    )
                    errors.append(f"{provider_name}: {exc}")
                    if not self._should_failover(exc.category):
                        raise
                except Exception as exc:
                    self.telemetry.measure_and_record(
                        operation="complete_text",
                        task=task,
                        provider=provider_name,
                        model=model,
                        attempt=attempt_number,
                        started_at=started_at,
                        outcome="error",
                        category="server_error",
                        error_message=str(exc),
                    )
                    errors.append(f"{provider_name}: unexpected error {exc}")
                    if not self._should_failover("server_error"):
                        raise LLMError(
                            f"Unexpected provider error: {exc}",
                            category="server_error",
                        ) from exc

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
        errors: list[str] = []

        for provider_name in self.settings.llm_provider_order:
            provider = self.providers[provider_name]
            if not provider.is_configured():
                errors.append(f"{provider_name}: not configured")
                continue

            model = self.settings.get_task_model(provider_name, task)
            json_schema = model_type.model_json_schema()
            attempts = max(0, self.settings.llm_max_retries_per_provider)
            extra_invalid_json_retries = self._extra_invalid_json_retry_limit(provider_name, task)
            total_attempts = attempts + 1 + extra_invalid_json_retries
            for attempt_index in range(total_attempts):
                attempt_number = attempt_index + 1
                started_at = perf_counter()
                prompt_for_attempt = user_prompt
                if attempt_index >= (attempts + 1):
                    prompt_for_attempt = self._prompt_with_truncation_guard(user_prompt)
                try:
                    raw = provider.generate_text(
                        LLMCallInput(
                            task=task,
                            model=model,
                            system_prompt=system_prompt,
                            user_prompt=prompt_for_attempt,
                            json_schema=json_schema,
                            max_output_tokens=self._max_output_tokens(provider_name, task),
                        )
                    )
                    raw_text = raw.text

                    try:
                        extracted = self._extract_json_text(raw_text)
                        parsed = model_type.model_validate_json(extracted)
                        self.telemetry.measure_and_record(
                            operation="complete_json_model",
                            task=task,
                            provider=provider_name,
                            model=model,
                            attempt=attempt_number,
                            started_at=started_at,
                            outcome="success",
                            category="success",
                            cost_usd=raw.cost_usd,
                        )
                        return parsed, provider_name
                    except ValidationError as validation_exc:
                        repaired = self._repair_json(
                            provider_name,
                            task,
                            model,
                            raw_text,
                            json_schema=json_schema,
                            validation_error=str(validation_exc),
                        )
                        extracted = self._extract_json_text(repaired)
                        parsed = model_type.model_validate_json(extracted)
                        self.telemetry.measure_and_record(
                            operation="complete_json_model",
                            task=task,
                            provider=provider_name,
                            model=model,
                            attempt=attempt_number,
                            started_at=started_at,
                            outcome="success",
                            category="success",
                            cost_usd=raw.cost_usd,
                        )
                        return parsed, provider_name
                    except (json.JSONDecodeError, LLMError) as parse_exc:
                        repaired = self._repair_json(
                            provider_name,
                            task,
                            model,
                            raw_text,
                            json_schema=json_schema,
                            validation_error=str(parse_exc),
                        )
                        extracted = self._extract_json_text(repaired)
                        parsed = model_type.model_validate_json(extracted)
                        self.telemetry.measure_and_record(
                            operation="complete_json_model",
                            task=task,
                            provider=provider_name,
                            model=model,
                            attempt=attempt_number,
                            started_at=started_at,
                            outcome="success",
                            category="success",
                            cost_usd=raw.cost_usd,
                        )
                        return parsed, provider_name
                except LLMError as exc:
                    self.telemetry.measure_and_record(
                        operation="complete_json_model",
                        task=task,
                        provider=provider_name,
                        model=model,
                        attempt=attempt_number,
                        started_at=started_at,
                        outcome="error",
                        category=exc.category,
                        error_message=str(exc),
                    )
                    is_retryable_invalid_json = (
                        exc.category == "invalid_json" and attempt_index < (total_attempts - 1)
                    )
                    if is_retryable_invalid_json:
                        continue
                    errors.append(f"{provider_name}: {exc}")
                    if not self._should_failover(exc.category):
                        raise
                except ValidationError as exc:
                    self.telemetry.measure_and_record(
                        operation="complete_json_model",
                        task=task,
                        provider=provider_name,
                        model=model,
                        attempt=attempt_number,
                        started_at=started_at,
                        outcome="error",
                        category="invalid_json",
                        error_message=str(exc),
                    )
                    if attempt_index < (total_attempts - 1):
                        continue
                    errors.append(f"{provider_name}: invalid_json {exc}")
                    if not self._should_failover("invalid_json"):
                        raise LLMError(str(exc), category="invalid_json") from exc
                except Exception as exc:
                    self.telemetry.measure_and_record(
                        operation="complete_json_model",
                        task=task,
                        provider=provider_name,
                        model=model,
                        attempt=attempt_number,
                        started_at=started_at,
                        outcome="error",
                        category="server_error",
                        error_message=str(exc),
                    )
                    errors.append(f"{provider_name}: unexpected error {exc}")
                    if not self._should_failover("server_error"):
                        raise LLMError(
                            f"Unexpected provider error: {exc}",
                            category="server_error",
                        ) from exc

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
