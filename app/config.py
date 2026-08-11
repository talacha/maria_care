from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "healthcare.db"

LlmProvider = Literal["openai", "hf"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{DEFAULT_DB_PATH}"
    llm_provider: LlmProvider = "openai"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None

    hf_token: str | None = None
    hf_model: str = "Qwen/Qwen2.5-7B-Instruct"
    hf_provider: str = "auto"

    max_search_limit: int = 50
    max_agent_tool_rounds: int = 4

    def model_post_init(self, __context) -> None:  # noqa: ANN001
        # Empty env values must not override SDK defaults.
        if self.openai_base_url is not None and not self.openai_base_url.strip():
            object.__setattr__(self, "openai_base_url", None)
        if self.openai_api_key is not None and not self.openai_api_key.strip():
            object.__setattr__(self, "openai_api_key", None)
        if self.hf_token is not None and not self.hf_token.strip():
            object.__setattr__(self, "hf_token", None)
        if self.hf_provider is not None and not self.hf_provider.strip():
            object.__setattr__(self, "hf_provider", "auto")

    @property
    def chat_ready(self) -> bool:
        if self.llm_provider == "hf":
            return bool(self.hf_token)
        return bool(self.openai_api_key)

    @property
    def active_model(self) -> str:
        if self.llm_provider == "hf":
            return self.hf_model
        return self.openai_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
