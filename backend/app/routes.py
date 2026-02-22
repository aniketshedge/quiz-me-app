from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from pydantic import ValidationError

from app.extensions import limiter
from app.schemas import (
    AnswerSubmissionRequest,
    CreateQuizRequest,
    CreateQuizResponse,
    TopicCandidate,
    TopicResolveRequest,
    TopicResolveResponse,
)

api_bp = Blueprint("api", __name__)


def _services():
    return current_app.extensions["services"]


def _settings():
    return current_app.extensions["settings"]


@api_bp.get("/health")
def health() -> tuple:
    settings = _settings()
    return jsonify({"status": "ok", "mock_mode": bool(settings.llm_force_mock_mode)}), 200


@api_bp.post("/topic/resolve")
@limiter.limit(lambda: _settings().max_req_per_10min + " per 10 minutes")
def resolve_topic() -> tuple:
    try:
        payload = TopicResolveRequest.model_validate(request.get_json(force=True, silent=False))
    except ValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    services = _services()
    guardrail = services["topic_guardrail"]
    wiki = services["wikipedia"]

    guard = guardrail.classify_topic(payload.topic)
    if guard.decision in {"disallow", "uncertain"}:
        response = TopicResolveResponse(
            status="blocked",
            message="Please try another topic.",
        )
        return jsonify(response.model_dump()), 200

    try:
        candidates = wiki.resolve_topic(payload.topic)
    except Exception:
        response = TopicResolveResponse(
            status="error",
            message="Could not resolve topic at the moment.",
        )
        return jsonify(response.model_dump()), 500

    if not candidates:
        response = TopicResolveResponse(
            status="no_match",
            message="No matching Wikipedia article found. Try another topic.",
        )
        return jsonify(response.model_dump()), 200

    # Prefer a non-disambiguation page as the recommended primary candidate.
    ranked = [item for item in candidates if not item.is_disambiguation] + [
        item for item in candidates if item.is_disambiguation
    ]
    primary = ranked[0]
    alternatives = ranked[1:6]
    status = "ambiguous" if primary.is_disambiguation else "ok"

    response = TopicResolveResponse(
        status=status,
        message=(
            "Top result is a disambiguation page. Pick a specific alternative."
            if status == "ambiguous"
            else None
        ),
        primary_candidate=TopicCandidate(
            title=primary.title,
            page_id=primary.page_id,
            url=primary.url,
            summary=primary.summary,
            image_url=primary.image_url,
            image_caption=primary.image_caption,
        ),
        alternatives=[
            TopicCandidate(
                title=item.title,
                page_id=item.page_id,
                url=item.url,
                summary=item.summary,
                image_url=item.image_url,
                image_caption=item.image_caption,
            )
            for item in alternatives
        ]
        or None,
    )
    return jsonify(response.model_dump()), 200


@api_bp.post("/quiz/create")
@limiter.limit(lambda: _settings().max_quiz_creations_per_10min + " per 10 minutes")
def create_quiz() -> tuple:
    try:
        payload = CreateQuizRequest.model_validate(request.get_json(force=True, silent=False))
    except ValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    services = _services()
    wiki = services["wikipedia"]
    quiz_builder = services["quiz_builder"]
    session_store = services["session_store"]

    try:
        article = wiki.get_article(payload.selected_page_id)
        quiz, provider = quiz_builder.build_quiz(topic=payload.topic, article=article)
        session_id = session_store.create_session(topic=payload.topic, quiz=quiz)
    except ValidationError as exc:
        return jsonify(
            {
                "status": "error",
                "message": "Quiz generation returned invalid schema.",
                "details": str(exc),
            }
        ), 502
    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": "Failed to create quiz. Try another topic.",
                "details": str(exc),
            }
        ), 500

    response = CreateQuizResponse(session_id=session_id, quiz=quiz, source=quiz.source)
    payload = response.model_dump()
    payload["provider"] = provider
    return jsonify(payload), 200


@api_bp.post("/quiz/<session_id>/answer")
@limiter.limit(lambda: _settings().max_req_per_10min + " per 10 minutes")
def submit_answer(session_id: str) -> tuple:
    services = _services()
    session_store = services["session_store"]

    try:
        payload = AnswerSubmissionRequest.model_validate(
            request.get_json(force=True, silent=False)
        )
    except ValidationError as exc:
        return jsonify({"status": "invalid", "message": str(exc)}), 400

    try:
        result = session_store.submit_answer(session_id=session_id, payload=payload)
    except KeyError:
        return jsonify(
            {
                "status": "error",
                "attempts_used": 0,
                "attempts_remaining": 0,
                "is_correct": False,
                "locked": False,
                "feedback": "Session not found.",
            }
        ), 404

    return jsonify(result.model_dump()), 200


@api_bp.get("/quiz/<session_id>/state")
@limiter.limit(lambda: _settings().max_req_per_10min + " per 10 minutes")
def quiz_state(session_id: str) -> tuple:
    services = _services()
    session_store = services["session_store"]
    try:
        state = session_store.get_state(session_id=session_id)
    except KeyError:
        return jsonify({"status": "error", "message": "Session not found."}), 404
    return jsonify(state.model_dump()), 200


@api_bp.post("/quiz/<session_id>/reset")
@limiter.limit(lambda: _settings().max_req_per_10min + " per 10 minutes")
def reset_session(session_id: str) -> tuple:
    services = _services()
    session_store = services["session_store"]
    session_store.reset_session(session_id=session_id)
    return jsonify({"status": "ok", "message": "Session reset."}), 200
