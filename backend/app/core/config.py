"""Application settings, read once from environment variables (or backend/.env).

Why pydantic-settings: one typed object replaces scattered os.getenv calls, and
invalid values fail at startup instead of deep inside a request.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory, so the default DB path doesn't depend on the shell's cwd.
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Lingo API"
    api_prefix: str = "/api/v1"

    # SQLAlchemy URL. Default: backend/lingo.db (a single local SQLite file).
    database_url: str = f"sqlite:///{BACKEND_DIR / 'lingo.db'}"

    # Mocked authentication: every request acts as this seeded learner.
    default_username: str = "learner"

    # One heart regenerates every N minutes (set e.g. 1 for a quick demo).
    heart_regen_minutes: int = Field(default=30, gt=0)

    # Comma-separated list of browser origins allowed to call the API.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,https://duolingo-scalerlabs.vercel.app,https://duolingo-scalerlabs-nfh6rhxo-siddhij1011-5621s-projects.vercel.app"
    @property
    def cors_origin_list(self) -> list[str]:
        # Browsers send Origin without a trailing slash, so "https://x.app/" (as copied from
        # the address bar) must become "https://x.app" or every request would be rejected.
        origins = (origin.strip().rstrip("/") for origin in self.cors_origins.split(","))
        return [origin for origin in origins if origin]


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once; tests can call cache_clear()."""
    return Settings()
