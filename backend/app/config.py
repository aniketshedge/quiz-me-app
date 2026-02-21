from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


ALLOWED_PROVIDERS = {"openai", "perplexity", "gemini"}


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _as_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _csv(value: str | None, default: List[str]) -> List[str]:
    if not value:
        return default
    return [entry.strip() for entry in value.split(",") if entry.strip()]


@dataclass
class Settings:
    app_env: str
    app_base_path: str
    cors_origins: List[str]
    max_content_length_mb: int

    llm_provider_order: List[str]
    llm_timeout_ms: int
    llm_max_retries_per_provider: int
    llm_failover_on: List[str]
    llm_allow_mock: bool
    llm_force_mock_mode: bool
    llm_telemetry_enabled: bool
    llm_telemetry_dir: str

    model_topic_guardrail: str
    model_quiz_generation: str
    model_short_grading: str

    openai_api_key: str
    openai_base_url: str

    perplexity_api_key: str
    perplexity_base_url: str

    gemini_api_key: str
    gemini_base_url: str

    wiki_max_chars: int
    wiki_summary_target_chars: int
    wiki_lang: str
    wiki_user_agent: str

    max_req_per_10min: str
    max_quiz_creations_per_10min: str

    short_grade_confidence_threshold: float

    @classmethod
    def from_env(cls) -> "Settings":
        provider_order = [
            os.getenv("LLM_PROVIDER_1", "openai").strip().lower(),
            os.getenv("LLM_PROVIDER_2", "perplexity").strip().lower(),
            os.getenv("LLM_PROVIDER_3", "gemini").strip().lower(),
        ]
        provider_order = [p for p in provider_order if p in ALLOWED_PROVIDERS]
        if not provider_order:
            provider_order = ["openai", "perplexity", "gemini"]

        app_base_path = os.getenv("APP_BASE_PATH", "").strip()
        if app_base_path and not app_base_path.startswith("/"):
            app_base_path = f"/{app_base_path}"
        if app_base_path.endswith("/"):
            app_base_path = app_base_path.rstrip("/")

        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            app_base_path=app_base_path,
            cors_origins=_csv(os.getenv("CORS_ORIGINS"), ["*"]),
            max_content_length_mb=_as_int(os.getenv("MAX_CONTENT_LENGTH_MB"), 2),
            llm_provider_order=provider_order,
            llm_timeout_ms=_as_int(os.getenv("LLM_TIMEOUT_MS"), 90000),
            llm_max_retries_per_provider=_as_int(
                os.getenv("LLM_MAX_RETRIES_PER_PROVIDER"), 0
            ),
            llm_failover_on=_csv(
                os.getenv("LLM_FAILOVER_ON"),
                ["all"],
            ),
            llm_allow_mock=_as_bool(os.getenv("LLM_ALLOW_MOCK"), True),
            llm_force_mock_mode=_as_bool(os.getenv("LLM_FORCE_MOCK_MODE"), False),
            llm_telemetry_enabled=_as_bool(os.getenv("LLM_TELEMETRY_ENABLED"), True),
            llm_telemetry_dir=os.getenv("LLM_TELEMETRY_DIR", "runtime/llm_telemetry"),
            model_topic_guardrail=os.getenv("MODEL_TOPIC_GUARDRAIL", "gpt-5-nano"),
            model_quiz_generation=os.getenv("MODEL_QUIZ_GENERATION", "gpt-5-mini"),
            model_short_grading=os.getenv("MODEL_SHORT_GRADING", "gpt-5-mini"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            perplexity_api_key=os.getenv("PERPLEXITY_API_KEY", ""),
            perplexity_base_url=os.getenv(
                "PERPLEXITY_BASE_URL", "https://api.perplexity.ai"
            ),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_base_url=os.getenv(
                "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
            ),
            wiki_max_chars=_as_int(os.getenv("WIKI_MAX_CHARS"), 24000),
            wiki_summary_target_chars=_as_int(
                os.getenv("WIKI_SUMMARY_TARGET_CHARS"), 8000
            ),
            wiki_lang=os.getenv("WIKI_LANG", "en"),
            wiki_user_agent=os.getenv(
                "WIKI_USER_AGENT",
                "quiz-me-app/0.1 (https://apps.aniketshedge.com/quiz-me/; quiz-me-demo)",
            ),
            max_req_per_10min=os.getenv("MAX_REQ_PER_10MIN", "60"),
            max_quiz_creations_per_10min=os.getenv("MAX_QUIZ_CREATIONS_PER_10MIN", "5"),
            short_grade_confidence_threshold=_as_float(
                os.getenv("SHORT_GRADE_CONFIDENCE_THRESHOLD"), 0.60
            ),
        )

    def get_task_model(self, provider: str, task: str) -> str:
        provider_key = provider.upper()
        task_key = task.upper()
        specific = os.getenv(f"{provider_key}_MODEL_{task_key}")
        if specific:
            return specific

        if task_key == "TOPIC_GUARDRAIL":
            return self.model_topic_guardrail
        if task_key == "QUIZ_GENERATION":
            return self.model_quiz_generation
        if task_key == "SHORT_GRADING":
            return self.model_short_grading
        return self.model_quiz_generation
