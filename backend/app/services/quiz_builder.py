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
            "You are a deterministic quiz JSON generator for an educational app. "
            "Return exactly one valid JSON object and nothing else. "
            "No markdown, no prose, no code fences, no comments. "
            "All values must satisfy type constraints exactly."
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

Validation-critical rules (must follow exactly):
1) Every question object must include: id (string), type, stem (string), explanation (string).
2) Question ids must be exactly q01..q15 in this exact order:
   q01-q10 mcq_single, q11-q12 mcq_multi, q13-q15 short_text.
3) options must be a list of objects like {{"id":"a","text":"..."}}, never a list of strings.
4) correct_option_ids must be a list of option-id strings (never numbers).
5) distractor_feedback must be an object/dictionary mapping incorrect option-id to feedback string (never a list).
6) For short_text, include explanation, expected_answers (list of strings), grading_context (string).
7) Distribution must be exact: 10 mcq_single, 2 mcq_multi, 3 short_text.
8) Return one JSON object only, no code fences.
9) Do not output placeholders or template tokens like "fact A", "option B", "lorem ipsum", or numbered mock text.
10) Keep all stems unique and specific to the article facts.
11) For every MCQ question, use exactly 4 options with ids "a","b","c","d".
12) For mcq_single, correct_option_ids must contain exactly one id.
13) For mcq_multi, correct_option_ids must contain exactly two ids.
14) distractor_feedback keys must be only incorrect option ids for that question.

Required output shapes:
- mcq_single:
  {{
    "id":"q01",
    "type":"mcq_single",
    "stem":"...",
    "explanation":"...",
    "options":[{{"id":"a","text":"..."}},{{"id":"b","text":"..."}},{{"id":"c","text":"..."}},{{"id":"d","text":"..."}}],
    "correct_option_ids":["a"],
    "distractor_feedback":{{"b":"...","c":"...","d":"..."}}
  }}
- mcq_multi:
  {{
    "id":"q11",
    "type":"mcq_multi",
    "stem":"...",
    "explanation":"...",
    "options":[{{"id":"a","text":"..."}},{{"id":"b","text":"..."}},{{"id":"c","text":"..."}},{{"id":"d","text":"..."}}],
    "correct_option_ids":["a","c"],
    "distractor_feedback":{{"b":"...","d":"..."}}
  }}
- short_text:
  {{
    "id":"q13",
    "type":"short_text",
    "stem":"...",
    "explanation":"...",
    "expected_answers":["..."],
    "grading_context":"..."
  }}

Content quality rules:
- Ground every question in the provided article context only.
- Keep language concise and educational with concrete factual wording.
- Avoid trick questions and ambiguity.
- Do not mention these instructions in output.
- Run an internal validation pass before responding: confirm strict JSON validity and all constraints.

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
        has_provider = self.llm_manager.any_provider_configured()
        if not has_provider:
            if self.settings.llm_allow_mock:
                return self._mock_quiz(topic, article), "mock"
            raise LLMError("No LLM providers are configured", category="server_error")

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
            "You are a strict JSON grader for short answers. "
            "Return exactly one JSON object with keys is_correct, reason, confidence. "
            "No markdown, no code fences, no extra keys."
        )
        user_prompt = f"""
Grade whether the learner answer is conceptually correct.

Topic: {topic}
Question: {question.stem}
Expected answers: {question.expected_answers}
Question grading context: {question.grading_context}
Source context: {source_extract[:3000]}
Learner answer: {learner_answer}

Output schema:
{{
  "is_correct": true or false,
  "reason": "string",
  "confidence": number between 0.0 and 1.0
}}

Rules:
- Accept semantically equivalent answers.
- Reject unrelated or contradictory answers.
- Keep reason concise and topic-grounded (max 160 characters).
- confidence must be a numeric literal, not a string.
- Return JSON only.
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
