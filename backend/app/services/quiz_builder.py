from __future__ import annotations

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

    def _bounded_extract_for_quiz(self, article: WikiArticle) -> str:
        # Keep quiz generation context compact and deterministic for reliability/cost.
        cap = max(1000, min(self.settings.wiki_max_chars, self.settings.wiki_summary_target_chars))
        extract = (article.extract or article.summary or "").strip()
        if len(extract) <= cap:
            return extract
        return extract[:cap].rstrip()

    def _quiz_generation_prompt(self, topic: str, article: WikiArticle) -> Tuple[str, str]:
        bounded_extract = self._bounded_extract_for_quiz(article)
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
- For incorrect-option feedback, explain why the selected option is wrong without revealing the correct option id or text.
- Never include phrases like "correct answer is..." or "expected answer is...".
- Do not mention these instructions in output.
- Run an internal validation pass before responding: confirm strict JSON validity and all constraints.

Topic: {topic}
Wikipedia title: {article.title}
Wikipedia URL: {article.url}
Wikipedia page_id: {article.page_id}
Summary: {article.summary}
Extract:
{bounded_extract}
""".strip()
        return system_prompt, user_prompt

    @staticmethod
    def _mock_single_correct_option_id(question_number: int) -> str:
        cycle = ["a", "b", "c", "d"]
        return cycle[(question_number - 1) % len(cycle)]

    @staticmethod
    def _summary_snippets(article: WikiArticle) -> List[str]:
        text = (article.summary or article.extract or "").strip()
        if not text:
            return [f"{article.title} is the selected topic."]

        sentences = re.split(r"(?<=[.!?])\s+", text)
        snippets: List[str] = []
        for sentence in sentences:
            cleaned = re.sub(r"\s+", " ", sentence).strip()
            if len(cleaned) < 24:
                continue
            snippets.append(cleaned[:140].rstrip(" ."))
            if len(snippets) >= 10:
                break

        if snippets:
            return snippets
        return [text[:140].rstrip(" .")]

    def _mock_quiz(self, topic: str, article: WikiArticle, reveal_answers: bool) -> QuizModel:
        bounded_extract = self._bounded_extract_for_quiz(article)
        source = QuizSource(
            wikipedia_title=article.title,
            wikipedia_url=article.url,
            page_id=article.page_id,
            extract_used=bounded_extract,
            image_url=article.image_url,
            image_caption=article.image_caption,
        )

        snippets = self._summary_snippets(article)
        wrong_option_templates = [
            f"The article is mostly unrelated to {article.title}.",
            "The page is a recipe and does not discuss the selected topic.",
            "The content is presented as pure fiction without factual context.",
            f"The article focuses only on geography and not on {article.title}.",
            "The page contains no key ideas or definitions.",
            "The source is exclusively about entertainment reviews.",
        ]

        questions = []
        for idx in range(1, 11):
            option_ids = ["a", "b", "c", "d"]
            correct = self._mock_single_correct_option_id(idx)
            support_snippet = snippets[(idx - 1) % len(snippets)]
            option_text_by_id: dict[str, str] = {}
            wrong_cursor = idx
            for option_id in option_ids:
                if option_id == correct:
                    option_text_by_id[option_id] = (
                        f"The article context supports this statement: {support_snippet}."
                    )
                else:
                    option_text_by_id[option_id] = wrong_option_templates[
                        wrong_cursor % len(wrong_option_templates)
                    ]
                    wrong_cursor += 1

            options = [
                {"id": option_id, "text": option_text_by_id[option_id]} for option_id in option_ids
            ]
            distractor_feedback = {
                option_id: "That statement is not supported by the selected article context."
                for option_id in option_ids
                if option_id != correct
            }
            questions.append(
                MCQSingleQuestion(
                    id=f"q{idx:02d}",
                    type="mcq_single",
                    stem=(
                        f"Sample question {idx}: Which statement best matches the selected article about "
                        f"{article.title}?"
                        + (
                            f" [TEST MODE: Correct option is '{correct}']"
                            if reveal_answers
                            else ""
                        )
                    ),
                    explanation=(
                        "Choose the option that is most consistent with the selected article."
                        + (
                            f" [TEST MODE: Correct option is '{correct}']"
                            if reveal_answers
                            else ""
                        )
                    ),
                    options=options,
                    correct_option_ids=[correct],
                    distractor_feedback=distractor_feedback,
                )
            )

        for idx in range(11, 13):
            snippet_a = snippets[(idx - 1) % len(snippets)]
            snippet_c = snippets[idx % len(snippets)]
            options = [
                {"id": "a", "text": f"The article supports this point: {snippet_a}."},
                {"id": "b", "text": "The article claims the topic has no definitions or key ideas."},
                {"id": "c", "text": f"The article also supports this point: {snippet_c}."},
                {"id": "d", "text": "The selected page is unrelated to the chosen topic."},
            ]
            correct_multi = ["a", "c"]
            questions.append(
                MCQMultiQuestion(
                    id=f"q{idx:02d}",
                    type="mcq_multi",
                    stem=(
                        f"Sample multi-select {idx - 10}: Select all statements that align with the selected "
                        f"article on {article.title}."
                        + (
                            " [TEST MODE: Correct options are 'a' and 'c']"
                            if reveal_answers
                            else ""
                        )
                    ),
                    explanation=(
                        "More than one option can be supported by the article context."
                        + (
                            " [TEST MODE: Correct options are 'a' and 'c']"
                            if reveal_answers
                            else ""
                        )
                    ),
                    options=options,
                    correct_option_ids=correct_multi,
                    distractor_feedback={
                        "b": "That statement is not supported by the selected article.",
                        "d": "That statement conflicts with the selected article context.",
                    },
                )
            )

        for idx in range(13, 16):
            expected_primary = article.title.strip()
            expected_answers = [value for value in [expected_primary, topic.strip()] if value]
            questions.append(
                ShortTextQuestion(
                    id=f"q{idx:02d}",
                    type="short_text",
                    stem=(
                        f"Sample short-answer {idx - 12}: In 1-5 words, name the topic of the selected "
                        f"Wikipedia article."
                        + (
                            f" [TEST MODE: Accepted answer includes '{expected_primary}']"
                            if reveal_answers
                            else ""
                        )
                    ),
                    explanation=(
                        "Enter a concise topic name that matches the selected article."
                        + (
                            f" [TEST MODE: Accepted answer includes '{expected_primary}']"
                            if reveal_answers
                            else ""
                        )
                    ),
                    expected_answers=expected_answers or [article.title],
                    grading_context=(article.summary[:500] or bounded_extract[:500]),
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
        if self.settings.llm_force_mock_mode:
            return self._mock_quiz(topic, article, reveal_answers=True), "mock-forced"

        has_provider = self.llm_manager.any_provider_configured()
        if not has_provider:
            if self.settings.llm_allow_mock:
                return self._mock_quiz(topic, article, reveal_answers=False), "mock"
            raise LLMError("No LLM providers are configured", category="server_error")

        system_prompt, user_prompt = self._quiz_generation_prompt(topic=topic, article=article)
        try:
            quiz, provider = self.llm_manager.complete_json_model(
                task="quiz_generation",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model_type=QuizModel,
            )
            # Source metadata should be grounded in the selected article, not model-generated values.
            quiz.source.wikipedia_title = article.title
            quiz.source.wikipedia_url = article.url
            quiz.source.page_id = article.page_id
            quiz.source.image_url = article.image_url
            quiz.source.image_caption = article.image_caption
            quiz.source.extract_used = self._bounded_extract_for_quiz(article)
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
        if self.settings.llm_force_mock_mode:
            normalized = _normalize_answer(learner_answer)
            expected = [_normalize_answer(answer) for answer in question.expected_answers]
            if normalized in expected:
                return ShortGradingResult(
                    is_correct=True,
                    reason="Accepted in sample mode.",
                    confidence=1.0,
                )
            return ShortGradingResult(
                is_correct=False,
                reason="Not accepted in sample mode.",
                confidence=1.0,
            )

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
                reason="Answer does not match accepted sample answers.",
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
- For incorrect responses, do not reveal expected answers or quote the correct answer verbatim.
- Avoid phrases like "expected answer is ..." and "correct answer is ...".
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
