"""Application configuration using Pydantic Settings."""

import secrets
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_env: str = "development"
    app_debug: bool = False
    secret_key: str = ""  # Required - no insecure default
    api_url: str = "http://localhost:8000"

    # Database
    database_url: str = ""  # Required - no insecure default
    database_pool_size: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "code_embeddings"

    # GitHub App
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    github_webhook_secret: str = ""

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # JWT
    jwt_secret: str = ""  # Required - no insecure default
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    @field_validator("secret_key", "jwt_secret", mode="after")
    @classmethod
    def validate_secrets(cls, v: str, info) -> str:
        """Ensure secrets are set and not using insecure defaults."""
        insecure_values = {"", "change-me-in-production", "secret", "password"}
        if v.lower() in insecure_values:
            raise ValueError(
                f"{info.field_name} must be set to a secure value via environment variable. "
                f"Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if len(v) < 32:
            raise ValueError(f"{info.field_name} must be at least 32 characters long")
        return v

    @field_validator("database_url", mode="after")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is set."""
        if not v:
            raise ValueError("database_url must be set via DATABASE_URL environment variable")
        return v

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
