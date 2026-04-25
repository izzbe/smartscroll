"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    gcs_bucket_pdfs: str = "smartscroll_pdfs"
    gcs_bucket_gameplay: str = "smartscroll-gameplay"
    gcs_bucket_rendered: str = "smartscroll-rendered"

    # Vertex AI / Gemma 4
    vertex_gemma_endpoint: str = ""
    vertex_gemma_location: str = "us-central1"

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # App settings
    debug: bool = False
    log_level: str = "INFO"


def _apply_gcp_credentials_from_env_file() -> None:
    """Override GOOGLE_APPLICATION_CREDENTIALS from .env so the project key always wins.

    pydantic-settings lets system env vars take precedence over .env, but the GCP SDK
    reads GOOGLE_APPLICATION_CREDENTIALS directly from os.environ. Reading .env here
    ensures the project-specific key is used regardless of any stale system env var.
    """
    from pathlib import Path

    env_file = Path(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith("GOOGLE_APPLICATION_CREDENTIALS="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = value
            return


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    _apply_gcp_credentials_from_env_file()
    return Settings()
