from __future__ import annotations

import random
import re
import uuid
from typing import List, Tuple

from pydantic import ValidationError

from app.config import Settings
from app.providers.base import LLMError
from app.providers.manager import LLMManager
from app.schemas import (
    MCQMultiQuestion,
    MCQSingleQuestion,
    QuizModel,
    QuizSource,
    ShortGradingResult,
    ShortTextQuestion,
)
from app.services.wikipedia import WikiArticle


def _normalize_answer(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


class QuizBuilderService:
    def __init__(self, settings: Settings, llm_manager: LLMManager) -> None:
        self.settings = settings
        self.llm_manager = llm_manager

    def _quiz_generation_prompt(self, topic: str, article: WikiArticle) -> Tuple[str, str]:
        system_prompt = (
            "You generate strict JSON quizzes from Wikipedia content. "
            "Return valid JSON only. No markdown. Follow schema exactly."
        )
        user_prompt = f"""
Generate one quiz JSON object with exactly 15 questions from the provided article context.

Required schema:
{{
  "quiz_id": "string",
  "topic": "string",
  "source": {{
    "wikipedia_title": "string",
    "wikipedia_url": "string",
    "page_id": number,
    "extract_used": "string",
    "image_url": "string|null",
    "image_caption": "string|null"
  }},
  "questions": [
    (10 x mcq_single + 2 x mcq_multi + 3 x short_text)
  ]
}}

Question rules:
- Common fields for all: id, type, stem, explanation.
- mcq_single: options (4), correct_option_ids (exactly 1), distractor_feedback.
- mcq_multi: options (4-6), correct_option_ids (2-3), distractor_feedback.
- short_text: expected_answers (1-5), grading_context.
- Keep language concise and educational.
- Avoid trick questions and ambiguity.

Topic: {topic}
Wikipedia title: {article.title}
Wikipedia URL: {article.url}
Wikipedia page_id: {article.page_id}
Summary: {article.summary}
Extract:
{article.extract}
""".strip()
        return system_prompt, user_prompt

    def _mock_quiz(self, topic: str, article: WikiArticle) -> QuizModel:
        source = QuizSource(
            wikipedia_title=article.title,
            wikipedia_url=article.url,
            page_id=article.page_id,
            extract_used=article.extract[: self.settings.wiki_summary_target_chars],
            image_url=article.image_url,
            image_caption=article.image_caption,
        )

        questions = []
        for idx in range(1, 11):
            option_ids = ["a", "b", "c", "d"]
            correct = random.choice(option_ids)
            options = [
                {"id": "a", "text": f"{article.title} fact A {idx}"},
                {"id": "b", "text": f"{article.title} fact B {idx}"},
                {"id": "c", "text": f"{article.title} fact C {idx}"},
                {"id": "d", "text": f"{article.title} fact D {idx}"},
            ]
            distractor_feedback = {
                option_id: f"This choice is not aligned with the source context for question {idx}."
                for option_id in option_ids
                if option_id != correct
            }
            questions.append(
                MCQSingleQuestion(
                    id=f"q{idx:02d}",
                    type="mcq_single",
                    stem=f"Which statement is most supported by the article about {article.title}?",
                    explanation="The correct option best matches the article context.",
                    options=options,
                    correct_option_ids=[correct],
                    distractor_feedback=distractor_feedback,
                )
            )

        for idx in range(11, 13):
            options = [
                {"id": "a", "text": "Supported point 1"},
                {"id": "b", "text": "Supported point 2"},
                {"id": "c", "text": "Unsupported point 1"},
                {"id": "d", "text": "Unsupported point 2"},
                {"id": "e", "text": "Unsupported point 3"},
            ]
            questions.append(
                MCQMultiQuestion(
                    id=f"q{idx:02d}",
                    type="mcq_multi",
                    stem=f"Select all statements that align with the article on {article.title}.",
                    explanation="Multiple answers are correct for this question.",
                    options=options,
                    correct_option_ids=["a", "b"],
                    distractor_feedback={
                        "c": "This statement is not supported by the article.",
                        "d": "This statement is not supported by the article.",
                        "e": "This statement is not supported by the article.",
                    },
                )
            )

        for idx in range(13, 16):
            questions.append(
                ShortTextQuestion(
                    id=f"q{idx:02d}",
                    type="short_text",
                    stem=f"In 1-5 words, name one key idea associated with {article.title}.",
                    explanation="A short factual concept from the article is expected.",
                    expected_answers=[article.title, topic],
                    grading_context=article.summary[:500] or article.extract[:500],
                )
            )

        quiz = QuizModel(
            quiz_id=f"quiz-{uuid.uuid4().hex[:10]}",
            topic=topic,
            source=source,
            questions=questions,
        )
        return quiz

    def build_quiz(self, topic: str, article: WikiArticle) -> Tuple[QuizModel, str]:
        if not self.llm_manager.any_provider_configured():
            return self._mock_quiz(topic, article), "mock"

        system_prompt, user_prompt = self._quiz_generation_prompt(topic=topic, article=article)
        try:
            quiz, provider = self.llm_manager.complete_json_model(
                task="quiz_generation",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model_type=QuizModel,
            )
            return quiz, provider
        except (LLMError, ValidationError):
            if self.settings.llm_allow_mock:
                return self._mock_quiz(topic, article), "mock"
            raise

    def grade_short_answer(
        self,
        question: ShortTextQuestion,
        learner_answer: str,
        topic: str,
        source_extract: str,
    ) -> ShortGradingResult:
        normalized = _normalize_answer(learner_answer)
        expected = [_normalize_answer(answer) for answer in question.expected_answers]

        if normalized in expected:
            return ShortGradingResult(
                is_correct=True,
                reason="Your answer matches an accepted expected answer.",
                confidence=1.0,
            )

        if not self.llm_manager.any_provider_configured():
            return ShortGradingResult(
                is_correct=False,
                reason="Answer does not match expected concepts in mock mode.",
                confidence=0.3,
            )

        system_prompt = (
            "You are grading a short learner response against topic context. "
            "Return strict JSON with keys is_correct, reason, confidence."
        )
        user_prompt = f"""
Grade whether the learner answer is conceptually correct.

Topic: {topic}
Question: {question.stem}
Expected answers: {question.expected_answers}
Question grading context: {question.grading_context}
Source context: {source_extract[:3000]}
Learner answer: {learner_answer}

Rules:
- Accept semantically equivalent answers.
- Reject unrelated or contradictory answers.
- Keep reason concise and topic-grounded.
""".strip()

        try:
            result, _provider = self.llm_manager.complete_json_model(
                task="short_grading",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model_type=ShortGradingResult,
            )
            return result
        except (LLMError, ValidationError):
            return ShortGradingResult(
                is_correct=False,
                reason="Could not confirm answer as correct with available grading service.",
                confidence=0.2,
            )
