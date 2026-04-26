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
    display_name: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    view_count: int = 0
    total_watch_ms: int = 0


class Follow(BaseModel):
    """Follow relationship between two users."""

    follower_uid: str
    following_uid: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Message(BaseModel):
    """A video share sent from one user to another."""

    from_uid: str
    from_display_name: str = ""
    to_uid: str
    video_id: str
    video_caption: str = ""
    video_gcs_path: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    read: bool = False
