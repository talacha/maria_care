---
title: Clinician Directory Agent
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: 6.22.0
app_file: gradio_app.py
python_version: "3.12"
short_description: Scoped clinician directory chat agent demo
pinned: false
---

# Healthcare Data API + Scoped Chat Agent

Lightweight FastAPI service that:

1. Loads the clinician directory from `healthcare_data.json` into **SQLite**
2. Exposes structured query endpoints for agents/clients
3. Hosts a scoped multi-turn conversational agent (FastAPI UI and **Hugging Face Gradio Space**)

Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)  
Deploy (Docker / Terraform / Rancher / **HF Space**): [DEPLOYMENT.md](DEPLOYMENT.md)

## Why SQLite

The payload is ~7k flat, filterable clinician records (~3MB). Queries are structured (speciality, city, language, rating, experience), not long-document RAG. SQLite gives indexed filters/sorts with zero ops and fits the whole corpus in a single local file.

## Assumptions

- Data is synthetic/demo clinician directory data (Romanian clinics), not live PHI
- No auth in v1
- Agent is text-only; TTS/STT can wrap `/chat` later
- LLM: OpenAI-compatible API **or** Hugging Face Inference Providers (`LLM_PROVIDER=openai|hf`)
- Conversation history is in-memory (FastAPI) or Gradio client-owned (Space)
- Scope is directory lookup only — no booking, EHR, or clinical advice

## Cheapest public demo (Hugging Face Space)

Free CPU Space hosts Gradio; inference goes to HF Inference Providers (free monthly credit).

1. Create a public **Gradio** Space (CPU basic).
2. Settings → Secrets: `HF_TOKEN` = token with Inference permission.
3. Settings → Variables: `LLM_PROVIDER=hf`, `HF_MODEL=Qwen/Qwen2.5-7B-Instruct` (optional; defaults apply).
4. Push this repo to the Space git remote (`app_file` is `gradio_app.py`).
5. Open `https://huggingface.co/spaces/<user>/<space>`.

Local Gradio smoke:

```bash
pip install -r requirements-space.txt
export LLM_PROVIDER=hf HF_TOKEN=hf_xxx
python scripts/seed_db.py
python gradio_app.py
```

## Demo (Docker / FastAPI)

```bash
cp .env.example .env   # set OPENAI_API_KEY for openai provider
docker compose up --build
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Local setup (FastAPI without Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
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

Tools: `list_facets`, `search_clinicians`, `get_clinician` — same query layer as the Data API.

## Vercel MCP client (TypeScript)

Lightweight Next.js UI in [`web/`](web/) that calls the Space MCP tool over Streamable HTTP:

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
# deploy: npx vercel  (Root Directory = web)
```

## Project layout

```
gradio_app.py          # HF Space / Gradio + MCP entry
web/                   # Vercel Next.js MCP client
app/
  main.py              # FastAPI + static demo UI
  agent/llm.py         # openai | hf adapters
  static/demo.html
scripts/seed_db.py
requirements.txt
requirements-space.txt
Dockerfile
DEPLOYMENT.md
healthcare_data.json
```
