"""Typed application configuration (architecture doc section 6: pydantic-settings).

Values come from environment variables prefixed ``OKAPI_`` or a local ``.env``.
Secrets are never hard-coded; the defaults here are safe for local dev only.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OKAPI_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://okapi:okapi@localhost:5432/okapi"
    opa_url: str = "http://localhost:8181"
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    anthropic_api_key: str = ""
    # Separate from jwt_secret on purpose: session auth and anti-tamper proof are
    # unrelated security purposes, and a leaked JWT secret shouldn't also mean
    # every Merkle signature is forgeable.
    merkle_secret: str = "change-me-in-env-too"


@lru_cache
def get_settings() -> Settings:
    return Settings()
