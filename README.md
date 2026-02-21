# Quiz Me App

A session-based demo quiz app with:
- Topic -> Wikipedia article confirmation -> generated 15-question quiz
- 3 attempts per question with lock-on-correct-or-exhausted
- LLM provider fallback (`openai`, `perplexity`, `gemini`)
- Vue SPA with animated in/out question transitions

## Stack
- Frontend: Vue 3 + TypeScript + Vite + Pinia + GSAP
- Backend: Flask + Pydantic + Flask-Limiter + Flask-CORS
- Runtime: Dockerized frontend and backend

## Project Layout
- `/backend`: Flask API
- `/frontend`: Vue SPA
- `/.env.example`: runtime configuration template

## Local Development
1. Copy `.env.example` to `.env` and set API keys.
2. Backend:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r backend/requirements.txt`
   - `gunicorn --bind 0.0.0.0:5000 app.wsgi:app --chdir backend`
3. Frontend:
   - `cd frontend`
   - `npm install`
   - `npm run dev`

## Docker
- `docker compose up --build`

## API Endpoints
All endpoints are served under `${APP_BASE_PATH}/api`.

- `POST /topic/resolve`
- `POST /quiz/create`
- `POST /quiz/{session_id}/answer`
- `GET /quiz/{session_id}/state`
- `POST /quiz/{session_id}/reset`

## Notes
- If no LLM keys are configured and `LLM_ALLOW_MOCK=true`, the backend falls back to mock quiz generation so the UI flow still works.
- Session state is in-memory only (no persistence).
