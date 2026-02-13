from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class TopicResolveRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)


class TopicCandidate(BaseModel):
    title: str
    page_id: int
    url: str
    summary: str
    image_url: Optional[str] = None
    image_caption: Optional[str] = None


class TopicResolveResponse(BaseModel):
    status: Literal["ok", "blocked", "no_match", "ambiguous", "error"]
    message: Optional[str] = None
    primary_candidate: Optional[TopicCandidate] = None
    alternatives: Optional[List[TopicCandidate]] = None


class OptionModel(BaseModel):
    id: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=500)


class QuestionBase(BaseModel):
    id: str = Field(min_length=1, max_length=20)
    type: Literal["mcq_single", "mcq_multi", "short_text"]
    stem: str = Field(min_length=5, max_length=2000)
    explanation: str = Field(min_length=5, max_length=2000)


class MCQSingleQuestion(QuestionBase):
    type: Literal["mcq_single"]
    options: List[OptionModel] = Field(min_length=4, max_length=4)
    correct_option_ids: List[str] = Field(min_length=1, max_length=1)
    distractor_feedback: Dict[str, str]

    @model_validator(mode="after")
    def validate_single(self) -> "MCQSingleQuestion":
        option_ids = {option.id for option in self.options}
        correct_ids = set(self.correct_option_ids)
        if not correct_ids.issubset(option_ids):
            raise ValueError("mcq_single correct_option_ids must exist in options")
        for key in self.distractor_feedback.keys():
            if key not in option_ids:
                raise ValueError("mcq_single distractor_feedback keys must exist in options")
        return self


class MCQMultiQuestion(QuestionBase):
    type: Literal["mcq_multi"]
    options: List[OptionModel] = Field(min_length=4, max_length=6)
    correct_option_ids: List[str] = Field(min_length=2, max_length=3)
    distractor_feedback: Dict[str, str]

    @model_validator(mode="after")
    def validate_multi(self) -> "MCQMultiQuestion":
        option_ids = {option.id for option in self.options}
        correct_ids = set(self.correct_option_ids)
        if not correct_ids.issubset(option_ids):
            raise ValueError("mcq_multi correct_option_ids must exist in options")
        for key in self.distractor_feedback.keys():
            if key not in option_ids:
                raise ValueError("mcq_multi distractor_feedback keys must exist in options")
        return self


class ShortTextQuestion(QuestionBase):
    type: Literal["short_text"]
    expected_answers: List[str] = Field(min_length=1, max_length=5)
    grading_context: str = Field(min_length=1, max_length=3000)

    @field_validator("expected_answers")
    @classmethod
    def answers_not_blank(cls, value: List[str]) -> List[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("expected_answers must contain non-empty strings")
        return cleaned


QuestionModel = Annotated[
    Union[MCQSingleQuestion, MCQMultiQuestion, ShortTextQuestion],
    Field(discriminator="type"),
]


class QuizSource(BaseModel):
    wikipedia_title: str
    wikipedia_url: str
    page_id: int
    extract_used: str
    image_url: Optional[str] = None
    image_caption: Optional[str] = None


class QuizModel(BaseModel):
    quiz_id: str
    topic: str
    source: QuizSource
    questions: List[QuestionModel] = Field(min_length=15, max_length=15)

    @model_validator(mode="after")
    def validate_distribution(self) -> "QuizModel":
        type_counts = {"mcq_single": 0, "mcq_multi": 0, "short_text": 0}
        ids = set()
        for question in self.questions:
            if question.id in ids:
                raise ValueError("question ids must be unique")
            ids.add(question.id)
            type_counts[question.type] += 1
        if type_counts["mcq_single"] != 10:
            raise ValueError("quiz must contain exactly 10 mcq_single questions")
        if type_counts["mcq_multi"] != 2:
            raise ValueError("quiz must contain exactly 2 mcq_multi questions")
        if type_counts["short_text"] != 3:
            raise ValueError("quiz must contain exactly 3 short_text questions")
        return self


class CreateQuizRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    selected_page_id: int


class CreateQuizResponse(BaseModel):
    session_id: str
    quiz: QuizModel
    source: QuizSource


class AnswerSubmissionRequest(BaseModel):
    question_id: str
    selected_option_ids: Optional[List[str]] = None
    short_answer: Optional[str] = None


class AnswerSubmissionResponse(BaseModel):
    status: Literal["accepted", "locked", "invalid", "error"]
    attempts_used: int
    attempts_remaining: int
    is_correct: bool
    locked: bool
    feedback: str


class AnswerState(BaseModel):
    question_id: str
    attempts_used: int
    attempts_remaining: int
    is_correct: bool
    locked: bool
    selected_option_ids: Optional[List[str]] = None
    short_answer: Optional[str] = None
    feedback: Optional[str] = None


class SessionStateResponse(BaseModel):
    session_id: str
    score: int
    correct_count: int
    total_questions: int
    current_index: int
    answers: Dict[str, AnswerState]
    quiz: QuizModel


class ShortGradingResult(BaseModel):
    is_correct: bool
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class TopicGuardrailResult(BaseModel):
    decision: Literal["allow", "disallow", "uncertain"]
    reason: str
