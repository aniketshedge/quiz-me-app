from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.config import Settings
from app.schemas import (
    AnswerState,
    AnswerSubmissionRequest,
    AnswerSubmissionResponse,
    MCQMultiQuestion,
    MCQSingleQuestion,
    QuizModel,
    SessionStateResponse,
    ShortTextQuestion,
)
from app.services.quiz_builder import QuizBuilderService


MAX_ATTEMPTS_PER_QUESTION = 3
GENERIC_INCORRECT_FEEDBACK = (
    "That's not correct. Re-read the question and source context, then try again."
)


@dataclass
class SessionAnswer:
    question_id: str
    attempts_used: int = 0
    is_correct: bool = False
    locked: bool = False
    selected_option_ids: Optional[List[str]] = None
    short_answer: Optional[str] = None
    feedback: Optional[str] = None


@dataclass
class SessionRecord:
    session_id: str
    topic: str
    quiz: QuizModel
    answers: Dict[str, SessionAnswer] = field(default_factory=dict)


class SessionStore:
    def __init__(self, settings: Settings, quiz_builder: QuizBuilderService) -> None:
        self.settings = settings
        self.quiz_builder = quiz_builder
        self._lock = threading.Lock()
        self._sessions: Dict[str, SessionRecord] = {}

    def create_session(self, topic: str, quiz: QuizModel) -> str:
        session_id = uuid.uuid4().hex
        record = SessionRecord(session_id=session_id, topic=topic, quiz=quiz)
        for question in quiz.questions:
            record.answers[question.id] = SessionAnswer(question_id=question.id)

        with self._lock:
            self._sessions[session_id] = record
        return session_id

    def get_session(self, session_id: str) -> SessionRecord:
        with self._lock:
            record = self._sessions.get(session_id)
        if not record:
            raise KeyError("Session not found")
        return record

    def reset_session(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

    def _question_by_id(self, quiz: QuizModel, question_id: str):
        for question in quiz.questions:
            if question.id == question_id:
                return question
        return None

    def _answer_revealed(
        self,
        feedback: str,
        sensitive_tokens: list[str] | None = None,
    ) -> bool:
        text = feedback.strip().lower()
        if not text:
            return True

        reveal_patterns = [
            r"\bcorrect answer\b",
            r"\bexpected answer\b",
            r"\bthe answer is\b",
            r"\boption\s+[a-z0-9]+\s+is correct\b",
            r"\bshould be\b",
            r"\bmust be\b",
            r"\bresponse does not match\b",
            r"\bmatches the expected\b",
        ]
        for pattern in reveal_patterns:
            if re.search(pattern, text):
                return True

        for token in sensitive_tokens or []:
            cleaned = token.strip().lower()
            if len(cleaned) < 2:
                continue
            if cleaned in text:
                return True
        return False

    def _safe_incorrect_feedback(
        self,
        raw_feedback: str,
        sensitive_tokens: list[str] | None = None,
    ) -> str:
        candidate = (raw_feedback or "").strip()
        if not candidate:
            return GENERIC_INCORRECT_FEEDBACK
        if self._answer_revealed(candidate, sensitive_tokens=sensitive_tokens):
            return GENERIC_INCORRECT_FEEDBACK
        return candidate

    def _build_state(self, record: SessionRecord) -> SessionStateResponse:
        score = 0
        answers_payload: Dict[str, AnswerState] = {}
        current_index = 0
        first_unlocked_found = False

        for index, question in enumerate(record.quiz.questions):
            answer = record.answers[question.id]
            if answer.is_correct:
                score += 1
            attempts_remaining = max(0, MAX_ATTEMPTS_PER_QUESTION - answer.attempts_used)
            answers_payload[question.id] = AnswerState(
                question_id=question.id,
                attempts_used=answer.attempts_used,
                attempts_remaining=attempts_remaining,
                is_correct=answer.is_correct,
                locked=answer.locked,
                selected_option_ids=answer.selected_option_ids,
                short_answer=answer.short_answer,
                feedback=answer.feedback,
            )
            if not first_unlocked_found and not answer.locked:
                first_unlocked_found = True
                current_index = index

        if not first_unlocked_found:
            current_index = len(record.quiz.questions) - 1

        return SessionStateResponse(
            session_id=record.session_id,
            score=score,
            total_questions=len(record.quiz.questions),
            current_index=current_index,
            answers=answers_payload,
            quiz=record.quiz,
        )

    def get_state(self, session_id: str) -> SessionStateResponse:
        record = self.get_session(session_id)
        return self._build_state(record)

    def submit_answer(
        self, session_id: str, payload: AnswerSubmissionRequest
    ) -> AnswerSubmissionResponse:
        record = self.get_session(session_id)
        question = self._question_by_id(record.quiz, payload.question_id)
        if question is None:
            return AnswerSubmissionResponse(
                status="invalid",
                attempts_used=0,
                attempts_remaining=0,
                is_correct=False,
                locked=False,
                feedback="Question not found.",
            )

        answer = record.answers[payload.question_id]
        if answer.locked:
            attempts_remaining = max(0, MAX_ATTEMPTS_PER_QUESTION - answer.attempts_used)
            return AnswerSubmissionResponse(
                status="locked",
                attempts_used=answer.attempts_used,
                attempts_remaining=attempts_remaining,
                is_correct=answer.is_correct,
                locked=True,
                feedback=answer.feedback or "Question is locked.",
            )

        if isinstance(question, MCQSingleQuestion):
            selected = payload.selected_option_ids or []
            if len(selected) != 1:
                return AnswerSubmissionResponse(
                    status="invalid",
                    attempts_used=answer.attempts_used,
                    attempts_remaining=max(0, MAX_ATTEMPTS_PER_QUESTION - answer.attempts_used),
                    is_correct=False,
                    locked=False,
                    feedback="Select exactly one option.",
                )

            chosen = selected[0]
            is_correct = chosen in question.correct_option_ids
            correct_option_texts = [
                option.text
                for option in question.options
                if option.id in set(question.correct_option_ids)
            ]
            sensitive_tokens = question.correct_option_ids + correct_option_texts
            feedback = (
                "Correct answer."
                if is_correct
                else self._safe_incorrect_feedback(
                    question.distractor_feedback.get(
                        chosen,
                        "That option is not correct for this question.",
                    ),
                    sensitive_tokens=sensitive_tokens,
                )
            )
            answer.selected_option_ids = selected

        elif isinstance(question, MCQMultiQuestion):
            selected = sorted(set(payload.selected_option_ids or []))
            if not selected:
                return AnswerSubmissionResponse(
                    status="invalid",
                    attempts_used=answer.attempts_used,
                    attempts_remaining=max(0, MAX_ATTEMPTS_PER_QUESTION - answer.attempts_used),
                    is_correct=False,
                    locked=False,
                    feedback="Select one or more options.",
                )

            expected = sorted(set(question.correct_option_ids))
            is_correct = selected == expected
            correct_option_texts = [
                option.text for option in question.options if option.id in set(expected)
            ]
            sensitive_tokens = expected + correct_option_texts
            if is_correct:
                feedback = "Correct answer set selected."
            else:
                wrong_items = [
                    question.distractor_feedback.get(item, "") for item in selected if item not in expected
                ]
                wrong_items = [item for item in wrong_items if item]
                feedback = (
                    self._safe_incorrect_feedback(
                        wrong_items[0],
                        sensitive_tokens=sensitive_tokens,
                    )
                    if wrong_items
                    else self._safe_incorrect_feedback(
                        "The selected set is not correct. Review and try again.",
                        sensitive_tokens=sensitive_tokens,
                    )
                )
            answer.selected_option_ids = selected

        elif isinstance(question, ShortTextQuestion):
            short_answer = (payload.short_answer or "").strip()
            if not short_answer:
                return AnswerSubmissionResponse(
                    status="invalid",
                    attempts_used=answer.attempts_used,
                    attempts_remaining=max(0, MAX_ATTEMPTS_PER_QUESTION - answer.attempts_used),
                    is_correct=False,
                    locked=False,
                    feedback="Enter a short answer before checking.",
                )

            grade = self.quiz_builder.grade_short_answer(
                question=question,
                learner_answer=short_answer,
                topic=record.topic,
                source_extract=record.quiz.source.extract_used,
            )
            is_correct = bool(
                grade.is_correct
                and grade.confidence >= self.settings.short_grade_confidence_threshold
            )
            feedback = (
                grade.reason
                if is_correct
                else self._safe_incorrect_feedback(
                    grade.reason,
                    sensitive_tokens=question.expected_answers,
                )
            )
            answer.short_answer = short_answer

        else:
            return AnswerSubmissionResponse(
                status="error",
                attempts_used=answer.attempts_used,
                attempts_remaining=max(0, MAX_ATTEMPTS_PER_QUESTION - answer.attempts_used),
                is_correct=False,
                locked=False,
                feedback="Unsupported question type.",
            )

        answer.attempts_used += 1
        answer.is_correct = is_correct
        if is_correct or answer.attempts_used >= MAX_ATTEMPTS_PER_QUESTION:
            answer.locked = True
        answer.feedback = feedback

        attempts_remaining = max(0, MAX_ATTEMPTS_PER_QUESTION - answer.attempts_used)
        return AnswerSubmissionResponse(
            status="accepted",
            attempts_used=answer.attempts_used,
            attempts_remaining=attempts_remaining,
            is_correct=answer.is_correct,
            locked=answer.locked,
            feedback=feedback,
        )
