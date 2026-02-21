from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class LLMError(Exception):
    def __init__(self, message: str, category: str = "server_error") -> None:
        super().__init__(message)
        self.category = category


@dataclass
class LLMCallInput:
    task: str
    model: str
    system_prompt: str
    user_prompt: str
    json_schema: dict[str, Any] | None = None


@dataclass
class LLMCallOutput:
    text: str
    cost_usd: float | None = None
    usage: dict[str, Any] | None = None


class LLMProvider(Protocol):
    name: str

    def is_configured(self) -> bool:
        ...

    def generate_text(self, request: LLMCallInput) -> LLMCallOutput:
        ...
