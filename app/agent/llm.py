"""Thin LLM adapters for OpenAI and Hugging Face Inference Providers."""

from __future__ import annotations

import os
from typing import Any, Protocol

from app.config import Settings, get_settings


class LlmClient(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        temperature: float = 0.2,
    ) -> Any: ...


class OpenAILlmClient:
    def __init__(self, settings: Settings) -> None:
        from openai import OpenAI

        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to your environment or .env file."
            )
        if not (settings.openai_base_url and settings.openai_base_url.strip()):
            if os.environ.get("OPENAI_BASE_URL", "").strip() == "":
                os.environ.pop("OPENAI_BASE_URL", None)

        kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        self._client = OpenAI(**kwargs)
        self._model = settings.openai_model

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        temperature: float = 0.2,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools is not None:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
        return self._client.chat.completions.create(**kwargs)


class HuggingFaceLlmClient:
    def __init__(self, settings: Settings) -> None:
        from huggingface_hub import InferenceClient

        token = settings.hf_token or os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError(
                "HF_TOKEN is not set. Add it as a Space secret or environment variable."
            )
        provider = settings.hf_provider or "auto"
        self._client = InferenceClient(token=token, provider=provider)
        self._model = settings.hf_model

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        temperature: float = 0.2,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools is not None:
            kwargs["tools"] = tools
            # HF providers may not honor "required"; prefer auto when unsupported.
            if tool_choice is not None:
                kwargs["tool_choice"] = "auto" if tool_choice == "required" else tool_choice
        return self._client.chat.completions.create(**kwargs)


def get_llm_client(settings: Settings | None = None) -> LlmClient:
    cfg = settings or get_settings()
    if cfg.llm_provider == "hf":
        return HuggingFaceLlmClient(cfg)
    return OpenAILlmClient(cfg)
