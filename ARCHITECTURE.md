# Demo Hosting Architecture

Architecture for hosting a **multi-turn clinician-directory conversational agent** demo. This document is the source of truth for how the demo is assembled and where each concern lives.

## Recommendation (v1 demo)

| Layer | Choice | Why |
|---|---|---|
| App runtime | **FastAPI + Uvicorn** (Python) | Already owns Data API + agent tools in one process |
| Demo UI | **Same-origin static chat** at `/` | Zero frontend deploy; one URL for stakeholders |
| Data store | **SQLite** (`data/healthcare.db`) | 7k structured rows; filters/indexes; zero ops |
| Agent model | **OpenAI-compatible Chat Completions + tools** | Lightweight tool loop; `gpt-4o-mini` default |
| Packaging | **Docker + Compose** | One command demo; portable to Railway/Render/Fly |
| Concurrency | **Single Uvicorn worker** | In-memory `conversation_id` history is process-local |
| Auth | **None (demo)** | Synthetic directory data; protect with network access only |

Rejected for this demo pass: separate Next.js frontend, Postgres, vector DB, multi-replica sticky sessions, voice/TTS.

## System diagram

```text
Browser (Demo UI at /)
        │
        │  POST /chat  { message, conversation_id? }
        ▼
┌───────────────────────────────────────────┐
│  FastAPI container (Uvicorn, 1 worker)    │
│                                           │
│  Static UI ──► /chat router               │
│                    │                      │
│                    ▼                      │
│            Scoped agent loop              │
│         (system prompt + tool calls)      │
│                    │                      │
│         list_facets / search / get        │
│                    │                      │
│                    ▼                      │
│           Clinician query service         │
│                    │                      │
│                    ▼                      │
│              SQLite healthcare.db         │
└───────────────────────────────────────────┘
                    ▲
                    │  also exposed as REST
                    │  /health /meta /clinicians
External agents / curl / OpenAPI clients
                    │
                    ▼
            OpenAI-compatible API
         (OPENAI_API_KEY / MODEL)
```

## Request path (multi-turn)

1. Browser loads `/` (static demo UI).
2. First user message → `POST /chat` without `conversation_id`.
3. Server creates `conversation_id`, stores `[system, user, …]` in memory, runs tool loop against SQLite.
4. UI keeps `conversation_id` and sends it on every follow-up.
5. Out-of-scope prompts are refused before or without inventing directory facts.
6. Directory answers must come from tool results (`list_facets`, `search_clinicians`, `get_clinician`).

## Hosting components

### Required

- **Container image** built from `Dockerfile`
  - Installs Python deps
  - Copies app + `healthcare_data.json`
  - Entrypoint seeds SQLite if missing, then starts Uvicorn on `:8000`
- **Environment**
  - `OPENAI_API_KEY` (required for in-scope chat)
  - `OPENAI_MODEL` (default `gpt-4o-mini`)
  - optional `OPENAI_BASE_URL` for compatible gateways
  - optional `DATABASE_URL`
- **Port** `8000` published to the host / platform

### Optional

- **Named volume** for `data/` if you want the DB to survive container rebuilds
- **Platform** (Railway, Render, Fly.io, Cloud Run): point at the same Dockerfile, set env vars, expose 8000
- **Basic access control** via platform private networking or an edge password (not built into the app)

## Demo surfaces

| URL | Audience |
|---|---|
| `/` | Stakeholder chat demo (multi-turn UI) |
| `/docs` | API explorers / engineers |
| `/health` | Uptime checks |
| `/meta`, `/clinicians` | External agents / scripts |

## Operational constraints (demo)

- **Memory conversations**: lost on restart; not shared across workers/replicas. Keep `--workers 1`.
- **No PHI assumptions**: treat dataset as synthetic demo data.
- **LLM cost/latency**: each turn may issue 1–N tool-calling round trips; cap is `max_agent_tool_rounds`.
- **Scope**: directory lookup only — no booking, diagnosis, or general knowledge answers.

## Local demo

```bash
cp .env.example .env   # set OPENAI_API_KEY
docker compose up --build
# open http://127.0.0.1:8000
```

Without Docker:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/seed_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Public demo (same image)

1. Build/push the Docker image (or connect the repo to Railway/Render/Fly).
2. Set `OPENAI_API_KEY` (+ optional model/base URL).
3. Expose container port `8000`.
4. Share the public URL; users land on `/` chat.

For container registry, Terraform, and Rancher/Kubernetes next steps, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Failure modes to expect

| Symptom | Cause | Mitigation |
|---|---|---|
| Chat returns 503 | Missing `OPENAI_API_KEY` | Set env / `.env` |
| Empty search answers | Filters too narrow / facet mismatch | Agent should call `list_facets` |
| Lost multi-turn context | Restart or multiple workers | Single worker; warn that history is ephemeral |
| Stale clinicians | DB not re-seeded after JSON change | Re-run `python scripts/seed_db.py` or recreate volume |
