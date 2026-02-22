from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter.errors import RateLimitExceeded

from app.config import Settings
from app.extensions import limiter
from app.providers.manager import LLMManager
from app.routes import api_bp
from app.services.quiz_builder import QuizBuilderService
from app.services.session_store import SessionStore
from app.services.topic_guardrail import TopicGuardrailService
from app.services.wikipedia import WikipediaService


def create_app() -> Flask:
    settings = Settings.from_env()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_content_length_mb * 1024 * 1024

    limiter.init_app(app)
    CORS(app, resources={r"*": {"origins": settings.cors_origins}})

    llm_manager = LLMManager(settings=settings)
    wikipedia = WikipediaService(settings=settings)
    quiz_builder = QuizBuilderService(settings=settings, llm_manager=llm_manager)
    topic_guardrail = TopicGuardrailService(settings=settings, llm_manager=llm_manager)
    session_store = SessionStore(settings=settings, quiz_builder=quiz_builder)

    app.extensions["settings"] = settings
    app.extensions["services"] = {
        "llm_manager": llm_manager,
        "wikipedia": wikipedia,
        "quiz_builder": quiz_builder,
        "topic_guardrail": topic_guardrail,
        "session_store": session_store,
    }

    api_prefix = f"{settings.app_base_path}/api"
    app.register_blueprint(api_bp, url_prefix=api_prefix)

    @app.get("/")
    def root() -> tuple:
        return jsonify(
            {
                "name": "quiz-me-api",
                "status": "ok",
                "api_base": api_prefix,
            }
        ), 200

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"status": "error", "message": "Request payload too large."}), 413

    @app.errorhandler(RateLimitExceeded)
    def rate_limit_exceeded(error):
        message = str(getattr(error, "description", "")).strip() or "Rate limit exceeded."
        return jsonify({"status": "error", "message": message}), 429

    return app
