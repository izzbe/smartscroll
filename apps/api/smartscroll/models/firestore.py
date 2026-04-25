"""Firestore document models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PDFStatus(str, Enum):
    """PDF processing status."""

    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class User(BaseModel):
    """User document."""

    email: str
    display_name: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PDF(BaseModel):
    """PDF document."""

    filename: str
    gcs_path: str
    status: PDFStatus = PDFStatus.UPLOADING
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: str | None = None


class Video(BaseModel):
    """Video document - one video per PDF, denormalized for fast feed reads."""

    uid: str
    pdf_id: str
    pdf_filename: str
    video_gcs_path: str
    duration_ms: int
    script: str = ""
    script_prompt_version: int = 0
    word_count: int = 0
    extracted_text_gcs_path: str = ""
    video_caption: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    view_count: int = 0
    total_watch_ms: int = 0
