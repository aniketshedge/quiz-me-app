from __future__ import annotations

import re

from app.providers.base import LLMError
from app.providers.manager import LLMManager
from app.schemas import TopicGuardrailResult


class TopicGuardrailService:
    def __init__(self, llm_manager: LLMManager) -> None:
        self.llm_manager = llm_manager

    def _heuristic(self, topic: str) -> TopicGuardrailResult:
        blocked_patterns = [
            r"\bhow to build a bomb\b",
            r"\bmake meth\b",
            r"\bcredit card fraud\b",
            r"\bchild sexual\b",
            r"\bterror attack\b",
        ]
        normalized = topic.strip().lower()
        for pattern in blocked_patterns:
            if re.search(pattern, normalized):
                return TopicGuardrailResult(
                    decision="disallow",
                    reason="Topic appears to request harmful or illegal guidance.",
                )

        return TopicGuardrailResult(
            decision="allow",
            reason="No obvious policy issue detected by heuristic guardrail.",
        )

    def classify_topic(self, topic: str) -> TopicGuardrailResult:
        if not self.llm_manager.any_provider_configured():
            return self._heuristic(topic)

        system_prompt = (
            "You are a topic safety classifier for an educational quiz app. "
            "Return exactly one JSON object with keys decision and reason. "
            "No markdown, no code fences, no extra keys. "
            "Decision must be one of allow, disallow, uncertain. "
            "Allow mainstream educational topics including war and history."
        )
        user_prompt = (
            "Classify whether this topic can be used to generate a neutral educational quiz. "
            "Disallow only if it clearly requests harmful wrongdoing guidance.\n\n"
            f"Topic: {topic}"
        )

        try:
            result, _provider = self.llm_manager.complete_json_model(
                task="topic_guardrail",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model_type=TopicGuardrailResult,
            )
            return result
        except LLMError:
            return TopicGuardrailResult(
                decision="uncertain",
                reason="Could not confidently classify topic safety.",
            )
