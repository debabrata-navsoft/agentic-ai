from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every field can be overridden with an AGENT_* env var."""

    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env", extra="ignore")

    model: str = "claude-opus-5"
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    max_tokens: int = 64000
    max_iterations: int = 25

    # Anthropic-hosted web_search / web_fetch tools
    enable_web_tools: bool = True
    # Server-side refusal fallbacks (re-runs a declined request on a recommended model)
    enable_fallbacks: bool = True

    data_dir: Path = Path("./data")
    workspace_dir: Path = Path("./workspace")

    cors_origins: str = "http://localhost:4200"

    # RAG uploads
    max_upload_mb: int = 20

    @property
    def db_path(self) -> Path:
        return self.data_dir / "agent.db"

    @property
    def vector_db_path(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    return settings
