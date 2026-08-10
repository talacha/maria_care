# Healthcare Data API + Scoped Chat Agent

Lightweight FastAPI service that:

1. Loads the clinician directory from `healthcare_data.json` into **SQLite**
2. Exposes structured query endpoints for agents/clients
3. Hosts a scoped multi-turn conversational agent with a demo UI at `/`

Architecture for hosting the demo: see [ARCHITECTURE.md](ARCHITECTURE.md).  
Deploy anywhere (Docker + Terraform / Rancher): see [DEPLOYMENT.md](DEPLOYMENT.md).

## Why SQLite

The payload is ~7k flat, filterable clinician records (~3MB). Queries are structured (speciality, city, language, rating, experience), not long-document RAG. SQLite gives indexed filters/sorts with zero ops and fits the whole corpus in a single local file.

## Assumptions

- Data is synthetic/demo clinician directory data (Romanian clinics), not live PHI
- No auth in v1
- Agent is text-only; TTS/STT can wrap `/chat` later
- LLM uses an OpenAI-compatible Chat Completions API (`OPENAI_API_KEY`, `OPENAI_MODEL`)
- Conversation history is in-memory only (single Uvicorn worker)
- Scope is directory lookup only — no booking, EHR, or clinical advice

## Demo (recommended)

```bash
cp .env.example .env   # set OPENAI_API_KEY
docker compose up --build
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) for the multi-turn chat demo.

Public hosting: deploy the same Docker image to Railway, Render, Fly.io, or Cloud Run; set `OPENAI_API_KEY` and expose port `8000`.

## Local setup (without Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set OPENAI_API_KEY for /chat
python scripts/seed_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Demo UI: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Data API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness, DB count, chat readiness |
| GET | `/meta` | Facets: specialities, locations, counties, languages, availability |
| GET | `/clinicians` | Filter/sort/paginate clinicians |
| GET | `/clinicians/{id}` | Single clinician |

### Example filters

```bash
curl "http://127.0.0.1:8000/clinicians?speciality=Cardiology&location=Cluj-Napoca&language=English&sort=rating&order=desc&limit=5"
```

## Chat API

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Find a cardiologist in Cluj-Napoca who speaks English"}'
```

Multi-turn: pass back `conversation_id` from the response.

The agent uses tools (`list_facets`, `search_clinicians`, `get_clinician`) over the same query layer as the Data API and refuses out-of-scope questions.

## Project layout

```
app/
  main.py              # API + demo UI
  static/demo.html     # multi-turn chat UI
  db.py / models.py / schemas.py
  routers/ services/ agent/
scripts/seed_db.py
scripts/entrypoint.sh  # Docker seed + uvicorn
Dockerfile
docker-compose.yml
ARCHITECTURE.md
data/healthcare.db     # generated, gitignored
healthcare_data.json
```
