# Quiz Me

Demo quiz app that builds a 15-question quiz from a selected Wikipedia article.

## Status

This is a showcase app, not a production-grade service.

## What It Does

- Topic input -> Wikipedia article confirmation -> quiz generation -> scoring.
- Fixed quiz format:
  - 10 single-correct MCQ
  - 2 multi-correct MCQ
  - 3 short-text
- 3 attempts per question; a question locks when:
  - the answer is correct, or
  - attempts are exhausted.
- Provider failover (`openai`, `perplexity`, `gemini`) with strict schema validation.
- Optional mock mode (sample quiz data, no LLM calls when forced).
- Session restore on reload/screen lock (if backend session still exists).
- Animated UI transitions and floating paper-shape background.
- Day/night theme toggle (default follows local time: night from 6 PM to 6 AM).

## Tech Stack

- Frontend: Vue 3 + TypeScript + Vite + Pinia + `motion-v`
- Backend: Flask + Pydantic + Flask-Limiter + Flask-CORS + requests
- Runtime: Docker Compose (`frontend` + `backend`)

## Repository Layout

- `backend/`: Flask API, provider manager, Wikipedia retrieval, in-memory session store
- `frontend/`: Vue SPA, animations, quiz flow UI
- `.env.example`: source-of-truth runtime configuration template
- `notes/`: planning/deployment notes (ignored by git in current repo settings)

## API Surface

All API routes are mounted under:

- `${APP_BASE_PATH}/api`

Endpoints:

- `GET /health`
- `POST /topic/resolve`
- `POST /quiz/create`
- `POST /quiz/{session_id}/answer`
- `GET /quiz/{session_id}/state`
- `POST /quiz/{session_id}/reset`

Backend root route (`/`) is a metadata route that returns API base info.

## Quick Start (Docker)

1. Copy env template:
   - `cp .env.example .env`
2. Fill API keys as needed:
   - `OPENAI_API_KEY`
   - `PERPLEXITY_API_KEY`
   - `GEMINI_API_KEY`
3. Start containers:
   - `docker compose up --build -d`

Default ports:

- Frontend: `5173`
- Backend: `5000`

Then open:

- Frontend: `http://<host>:5173${VITE_APP_BASE_PATH}`
- API health: `http://<host>:5000${APP_BASE_PATH}/api/health`

## Key Environment Variables

Use `.env.example` as canonical reference.

### Base path and origin

- `APP_BASE_PATH=/quiz-me`
- `VITE_APP_BASE_PATH=/quiz-me/`
- `CORS_ORIGINS=...`

### Provider order and failover

- `LLM_PROVIDER_1=openai`
- `LLM_PROVIDER_2=perplexity`
- `LLM_PROVIDER_3=gemini`
- `LLM_TIMEOUT_MS=90000`
- `LLM_MAX_RETRIES_PER_PROVIDER=0`
- `LLM_FAILOVER_ON=all`

### Mock behavior

- `LLM_ALLOW_MOCK=true`
  - If no providers are configured, app may use sample quiz generation.
- `LLM_FORCE_MOCK_MODE=false`
  - If `true`, no LLM calls are made and deterministic sample flow is used.

### Rate limits

- `MAX_REQ_PER_10MIN=60`
- `MAX_QUIZ_CREATIONS_PER_10MIN=5`
- `MAX_QUIZ_CREATIONS_PER_DAY=1`
- `MAX_CONTENT_LENGTH_MB=2`

Notes:

- One `POST /quiz/create` request counts as one create attempt.
- Internal provider failover inside that request does not consume extra quiz-create attempts.

### Wikipedia bounds

- `WIKI_MAX_CHARS=24000`
- `WIKI_SUMMARY_TARGET_CHARS=8000`
- `WIKI_USER_AGENT=...`

## Non-Docker Local Run

Backend:

1. `python -m venv .venv`
2. `source .venv/bin/activate`
3. `pip install -r backend/requirements.txt`
4. `gunicorn --bind 0.0.0.0:5000 --chdir backend app.wsgi:app`

Frontend:

1. `cd frontend`
2. `npm install`
3. `npm run dev`

## Diagnostics and Logs

Container logs:

- `docker compose logs backend --tail 200`
- `docker compose logs frontend --tail 200`

LLM telemetry files (if enabled):

- `backend/runtime/llm_telemetry/llm_calls.jsonl`
- `backend/runtime/llm_telemetry/llm_counters.json`

Quick invalid-json inspection example:

- `tail -n 1000 backend/runtime/llm_telemetry/llm_calls.jsonl | jq -c 'select(.task=="quiz_generation" and .outcome=="error") | {ts, provider, model, category, error_message, duration_ms}'`

## Test Commands

- Backend tests: `python3 -m pytest backend/tests -q`
- Frontend type/build check: `npm --prefix frontend run build`

## Useful URL Parameters

- `?theme=day` or `?theme=night`
- `?motion=on` or `?motion=off`

These are helpful for visual QA and demos.
