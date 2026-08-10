from __future__ import annotations

import json
import re
import uuid
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.agent.prompts import OUT_OF_SCOPE_REFUSAL, SYSTEM_PROMPT
from app.agent.tools import TOOL_DEFINITIONS, execute_tool
from app.config import get_settings
from app.schemas import ChatMessage

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


def _get_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your environment or .env file."
        )
    # Avoid empty OPENAI_BASE_URL from the process env breaking URL joins.
    if not (settings.openai_base_url and settings.openai_base_url.strip()):
        import os

        if os.environ.get("OPENAI_BASE_URL", "").strip() == "":
            os.environ.pop("OPENAI_BASE_URL", None)

    kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def _looks_out_of_scope(message: str) -> bool:
    if _DIRECTORY_HINTS.search(message):
        return False
    return bool(_OUT_OF_SCOPE_HINTS.search(message))


def _assistant_message_dict(message: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": "assistant",
        "content": message.content or "",
    }
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments or "{}",
                },
            }
            for tool_call in message.tool_calls
        ]
    return payload


def _run_completion(client: OpenAI, history: list[dict[str, Any]], *, tool_choice: str):
    settings = get_settings()
    return client.chat.completions.create(
        model=settings.openai_model,
        messages=history,
        tools=TOOL_DEFINITIONS,
        tool_choice=tool_choice,
        temperature=0.2,
    )


def run_chat(db: Session, message: str, conversation_id: str | None = None) -> tuple[str, ChatMessage, bool]:
    settings = get_settings()
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

    history.append({"role": "user", "content": user_text})
    client = _get_client()
    used_tools = False
    force_tools_once = False

    for _ in range(settings.max_agent_tool_rounds):
        tool_choice = "required" if force_tools_once else "auto"
        force_tools_once = False
        completion = _run_completion(client, history, tool_choice=tool_choice)
        choice = completion.choices[0].message
        history.append(_assistant_message_dict(choice))

        if not choice.tool_calls:
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
            reply = ChatMessage(role="assistant", content=content)
            return conv_id, reply, content == OUT_OF_SCOPE_REFUSAL

        used_tools = True
        for tool_call in choice.tool_calls:
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

    completion = client.chat.completions.create(
        model=settings.openai_model,
        messages=history,
        temperature=0.2,
    )
    content = (completion.choices[0].message.content or "").strip() or OUT_OF_SCOPE_REFUSAL
    history.append({"role": "assistant", "content": content})
    reply = ChatMessage(role="assistant", content=content)
    return conv_id, reply, content == OUT_OF_SCOPE_REFUSAL
