"""Hugging Face Spaces / local Gradio entrypoint for the clinician directory agent."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import gradio as gr

try:
    import spaces  # ZeroGPU runtime on HF Spaces
except ImportError:  # local Gradio without the spaces package
    spaces = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent

# Spaces default to HF Inference Providers unless explicitly overridden.
os.environ.setdefault("LLM_PROVIDER", "hf")


# ZeroGPU requires ≥1 decorated function on free/ZeroGPU Spaces.
# Inference uses HF Inference Providers — do NOT put provider calls in here.
if spaces is not None:

    @spaces.GPU(duration=1)
    def _noop_zerogpu() -> None:
        """Satisfy ZeroGPU runtime; never called for inference."""
        return None


def _ensure_database() -> None:
    """Seed SQLite on first boot (Space or local Gradio)."""
    db_path = ROOT / "data" / "healthcare.db"
    if db_path.exists():
        return
    from scripts.seed_db import seed

    seed()


def _normalize_history(history: list | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in history or []:
        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                normalized.append({"role": role, "content": content})
            continue
        if isinstance(item, (list, tuple)) and len(item) == 2:
            user, assistant = item
            if isinstance(user, str) and user.strip():
                normalized.append({"role": "user", "content": user})
            if isinstance(assistant, str) and assistant.strip():
                normalized.append({"role": "assistant", "content": assistant})
    return normalized


def _parse_history_json(history_json: str | None) -> list[dict[str, str]]:
    if not history_json or not history_json.strip():
        return []
    try:
        raw = json.loads(history_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return _normalize_history(raw)


def chat(message: str, history_json: str = "[]") -> str:
    """Answer clinician-directory questions using SQLite tools + HF Inference Providers."""
    from app.agent.loop import run_chat_with_history
    from app.db import SessionLocal

    user_text = (message or "").strip()
    prior = _parse_history_json(history_json)
    with SessionLocal() as db:
        try:
            return run_chat_with_history(db, user_text, prior)
        except RuntimeError as exc:
            return f"Configuration error: {exc}"
        except Exception as exc:  # noqa: BLE001
            return f"Agent error: {exc}"


def _ui_respond(message: str, history: list[dict[str, Any]] | None):
    prior = _normalize_history(history)
    reply = chat(message, json.dumps(prior))
    updated = prior + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]
    return updated, ""


_ensure_database()

with gr.Blocks(title="Clinician Directory Agent") as demo:
    gr.Markdown(
        """
# Clinician Directory Agent
Multi-turn demo scoped to a synthetic Romanian clinician directory.
Ask about speciality, city, language, rating, or experience.
UI runs on this Space; inference uses Hugging Face Inference Providers.
"""
    )
    chatbot = gr.Chatbot(height=480)
    with gr.Row():
        msg = gr.Textbox(
            placeholder="Ask about clinicians or clinics…",
            show_label=False,
            scale=4,
        )
        send = gr.Button("Send", variant="primary", scale=1)
    gr.Examples(
        examples=[
            "Find a cardiologist in Cluj-Napoca who speaks English",
            "Who are the highest-rated dermatologists in Bucharest?",
            "What specialities are available?",
            "What is the weather in Paris?",
        ],
        inputs=msg,
    )
    send.click(
        _ui_respond,
        inputs=[msg, chatbot],
        outputs=[chatbot, msg],
        api_visibility="private",
    )
    msg.submit(
        _ui_respond,
        inputs=[msg, chatbot],
        outputs=[chatbot, msg],
        api_visibility="private",
    )

    # MCP tool name becomes: clinician_directory_agent_chat
    # (Blocks title slug + function/api name "chat")
    gr.api(chat, api_name="chat")

if __name__ == "__main__":
    demo.launch(mcp_server=True)
