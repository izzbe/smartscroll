"""Application configuration loaded from environment variables."""

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
