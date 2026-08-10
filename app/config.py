from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "healthcare.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{DEFAULT_DB_PATH}"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    max_search_limit: int = 50
    max_agent_tool_rounds: int = 4

    def model_post_init(self, __context) -> None:  # noqa: ANN001
        # Empty env values (OPENAI_BASE_URL=) must not override the SDK default.
        if self.openai_base_url is not None and not self.openai_base_url.strip():
            object.__setattr__(self, "openai_base_url", None)
        if self.openai_api_key is not None and not self.openai_api_key.strip():
            object.__setattr__(self, "openai_api_key", None)


@lru_cache
def get_settings() -> Settings:
    return Settings()
