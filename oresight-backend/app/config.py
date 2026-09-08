"""Application configuration, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object for OreSight backend.

    All values can be overridden via environment variables or a `.env`
    file in the project root (see `.env.example`).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "dev"

    DATABASE_URL: str = (
        "postgresql+psycopg://oresight:oresight@localhost:5432/oresight"
    )

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "oresight123"

    # Field Intake Hardening Phase 1 — hours after a production record's
    # creation during which PATCH /production/{id} is allowed without a
    # supervisor override (supervisor bypass ships in Phase 8 / auth, not
    # implemented yet — see IMPLEMENTATION_NOTES.md).
    PRODUCTION_EDIT_WINDOW_HOURS: int = 48

    # Field Intake Hardening Phase 4 — flap detection (§2.2). A status change
    # that pushes an equipment's log-row count within the trailing window
    # above the threshold opens one `equipment_flapping` risk event.
    EQUIPMENT_FLAP_WINDOW_HOURS: int = 24
    EQUIPMENT_FLAP_THRESHOLD: int = 4

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:19825",
        "http://127.0.0.1:19825",
    ]


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance."""
    return Settings()
