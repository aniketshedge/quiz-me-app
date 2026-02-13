from app.config import Settings
from app.schemas import AnswerSubmissionRequest
from app.services.quiz_builder import QuizBuilderService
from app.services.session_store import SessionStore
from app.services.wikipedia import WikiArticle
from app.providers.manager import LLMManager


def test_lock_after_three_attempts_mcq_single():
    settings = Settings.from_env()
    llm_manager = LLMManager(settings)
    quiz_builder = QuizBuilderService(settings=settings, llm_manager=llm_manager)
    store = SessionStore(settings=settings, quiz_builder=quiz_builder)

    article = WikiArticle(
        title="Python",
        page_id=1,
        url="https://example.com",
        summary="Python summary",
        image_url=None,
        image_caption=None,
        extract="Python extract",
    )
    quiz, _provider = quiz_builder.build_quiz(topic="Python", article=article)
    session_id = store.create_session(topic="Python", quiz=quiz)

    question_id = "q01"
    for _ in range(3):
        result = store.submit_answer(
            session_id,
            AnswerSubmissionRequest(question_id=question_id, selected_option_ids=["z"]),
        )

    assert result.locked is True
    assert result.attempts_used == 3
