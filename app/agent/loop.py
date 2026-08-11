from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agent.constraints import (
    format_search_answer,
    merge_constraints,
    should_use_deterministic_search,
)
from app.agent.llm import LlmClient, get_llm_client
from app.agent.prompts import OUT_OF_SCOPE_REFUSAL, SYSTEM_PROMPT
from app.agent.tools import TOOL_DEFINITIONS, execute_tool
from app.config import get_settings
from app.schemas import ChatMessage
from app.services import clinicians as clinician_service

_conversations: dict[str, list[dict[str, Any]]] = {}

_OUT_OF_SCOPE_HINTS = re.compile(
    r"\b("
    r"diagnos|treatment|prescri|medicin|symptom|cancer|covid|vaccine|"
    r"weather|stock|bitcoin|python|javascript|write code|poem|joke|"
    r"book(ing)?|appointment|insurance|politic|president|recipe"
    r")\b",
    re.IGNORECASE,
)

_DIRECTORY_HINTS = re.compile(
    r"\b("
    r"doctor|clinician|clinic|specialit|cardiolog|dermato|psychiatr|"
    r"location|city|county|language|rating|experience|phone|email|"
    r"availability|find|search|who|near|speaks"
    r")\b",
    re.IGNORECASE,
)


def _looks_out_of_scope(message: str) -> bool:
    if _DIRECTORY_HINTS.search(message):
        return False
    return bool(_OUT_OF_SCOPE_HINTS.search(message))


def _assistant_message_dict(message: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": "assistant",
        "content": message.content or "",
    }
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        payload["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments or "{}",
                },
            }
            for tool_call in tool_calls
        ]
    return payload


def _run_tool_loop(
    db: Session,
    client: LlmClient,
    history: list[dict[str, Any]],
    user_text: str,
) -> tuple[str, bool]:
    settings = get_settings()
    used_tools = False
    force_tools_once = False

    for _ in range(settings.max_agent_tool_rounds):
        tool_choice = "required" if force_tools_once else "auto"
        force_tools_once = False
        completion = client.complete(
            history,
            tools=TOOL_DEFINITIONS,
            tool_choice=tool_choice,
            temperature=0.2,
        )
        choice = completion.choices[0].message
        history.append(_assistant_message_dict(choice))

        tool_calls = getattr(choice, "tool_calls", None)
        if not tool_calls:
            content = (choice.content or "").strip()
            if not used_tools and _DIRECTORY_HINTS.search(user_text):
                history.append(
                    {
                        "role": "system",
                        "content": (
                            "You answered a directory question without tools. "
                            "Call search_clinicians or list_facets now, then answer only from results."
                        ),
                    }
                )
                force_tools_once = True
                continue

            if not content:
                content = OUT_OF_SCOPE_REFUSAL
            return content, content == OUT_OF_SCOPE_REFUSAL

        used_tools = True
        for tool_call in tool_calls:
            try:
                args = json.loads(tool_call.function.arguments or "{}")
                if not isinstance(args, dict):
                    args = {}
            except json.JSONDecodeError:
                args = {}
            result = execute_tool(db, tool_call.function.name, args)
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    completion = client.complete(history, temperature=0.2)
    content = (completion.choices[0].message.content or "").strip() or OUT_OF_SCOPE_REFUSAL
    history.append({"role": "assistant", "content": content})
    return content, content == OUT_OF_SCOPE_REFUSAL


def _deterministic_directory_reply(
    db: Session,
    message: str,
    prior_user_messages: list[dict[str, Any]] | None,
) -> str | None:
    """Reliable progressive search for name/speciality/gender cues (no LLM inventing)."""
    constraints = merge_constraints(prior_user_messages, message)
    if not should_use_deterministic_search(constraints):
        return None

    settings = get_settings()
    items, total, applied = clinician_service.search_clinicians(
        db,
        speciality=constraints.get("speciality"),
        location=constraints.get("location"),
        first_name=constraints.get("first_name"),
        last_name=constraints.get("last_name"),
        likely_gender=constraints.get("likely_gender"),
        language=constraints.get("language"),
        limit=min(8, settings.max_search_limit),
        offset=0,
        sort="rating",
        order="desc",
    )
    return format_search_answer(
        total=total,
        items=[item.model_dump() for item in items],
        applied_filters=applied,
    )


def run_chat(
    db: Session,
    message: str,
    conversation_id: str | None = None,
) -> tuple[str, ChatMessage, bool]:
    conv_id = conversation_id or str(uuid.uuid4())
    history = _conversations.setdefault(
        conv_id,
        [{"role": "system", "content": SYSTEM_PROMPT}],
    )

    user_text = message.strip()
    if not user_text:
        reply = ChatMessage(
            role="assistant",
            content="Please ask a question about clinicians or clinics.",
        )
        return conv_id, reply, True

    if _looks_out_of_scope(user_text):
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": OUT_OF_SCOPE_REFUSAL})
        reply = ChatMessage(role="assistant", content=OUT_OF_SCOPE_REFUSAL)
        return conv_id, reply, True

    prior_users = [m for m in history if m.get("role") == "user"]
    deterministic = _deterministic_directory_reply(db, user_text, prior_users)
    history.append({"role": "user", "content": user_text})
    if deterministic is not None:
        history.append({"role": "assistant", "content": deterministic})
        return conv_id, ChatMessage(role="assistant", content=deterministic), False

    client = get_llm_client()
    content, refused = _run_tool_loop(db, client, history, user_text)
    reply = ChatMessage(role="assistant", content=content)
    return conv_id, reply, refused


def run_chat_with_history(
    db: Session,
    message: str,
    prior_messages: list[dict[str, Any]] | None = None,
) -> str:
    """One agent turn for Gradio / MCP (client-owned history)."""
    user_text = (message or "").strip()
    if not user_text:
        return "Please ask a question about clinicians or clinics."

    if _looks_out_of_scope(user_text):
        return OUT_OF_SCOPE_REFUSAL

    prior_users = [
        item
        for item in (prior_messages or [])
        if item.get("role") == "user" and isinstance(item.get("content"), str)
    ]
    deterministic = _deterministic_directory_reply(db, user_text, prior_users)
    if deterministic is not None:
        return deterministic

    history: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in prior_messages or []:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            history.append({"role": role, "content": content})

    history.append({"role": "user", "content": user_text})
    client = get_llm_client()
    content, _refused = _run_tool_loop(db, client, history, user_text)
    return content
