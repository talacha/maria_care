from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import chat, clinicians

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Healthcare Data API + Scoped Chat Agent",
    description=(
        "SQLite-backed clinician directory API and a multi-turn chat agent "
        "scoped exclusively to that dataset. Demo UI at /."
    ),
    version="0.1.0",
)

app.include_router(clinicians.router)
app.include_router(chat.router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def demo_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "demo.html")


@app.get("/demo", include_in_schema=False)
def demo_ui_alias() -> FileResponse:
    return FileResponse(STATIC_DIR / "demo.html")
