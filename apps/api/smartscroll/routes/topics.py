"""Topic-to-video generation endpoints.

POST /api/topics/generate  — submit a topic, kick off Backboard research + pipeline
GET  /api/topics/{topic_id} — poll processing status (mirrors GET /api/pdfs/{pdf_id})
"""

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from smartscroll.models.firestore import PDFStatus
from smartscroll.pipeline.orchestrator import process_topic_background
from smartscroll.services.auth import get_current_user_id
from smartscroll.services.firestore import FirestoreService, get_firestore_service

logger = structlog.get_logger()
router = APIRouter()


class TopicGenerateRequest(BaseModel):
    topic: str
    gameplay_style: str | None = None


class TopicGenerateResponse(BaseModel):
    topic_id: str
    uid: str
    status: PDFStatus


class TopicStatusResponse(BaseModel):
    topic_id: str
    topic: str
    status: PDFStatus
    error_message: str | None


@router.post("/generate", response_model=TopicGenerateResponse)
async def generate_from_topic(
    body: TopicGenerateRequest,
    background_tasks: BackgroundTasks,
    uid: str = Depends(get_current_user_id),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> TopicGenerateResponse:
    """Submit a topic; Backboard researches it and the full pipeline generates a video.

    Poll GET /api/topics/{topic_id} (or GET /api/pdfs/{topic_id}) until status is
    'ready' or 'failed'. The topic_id is also a valid pdf_id for the feed and chat.
    """
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
    if len(topic) > 500:
        raise HTTPException(status_code=400, detail="Topic too long (max 500 characters)")

    topic_id = uuid.uuid4().hex

    # Reuse the PDF Firestore model — topic videos are indistinguishable from PDF
    # videos in the feed, chat, and signing logic. Filename uses .topic extension so
    # the source type is identifiable in logs.
    await firestore.create_pdf(
        uid=uid,
        pdf_id=topic_id,
        filename=f"{topic[:80]}.topic",
        gcs_path="",
    )

    background_tasks.add_task(
        process_topic_background,
        uid=uid,
        topic_id=topic_id,
        topic=topic,
        gameplay_style=body.gameplay_style,
    )

    logger.info("topic_submitted", uid=uid, topic_id=topic_id, topic=topic[:80])
    return TopicGenerateResponse(topic_id=topic_id, uid=uid, status=PDFStatus.UPLOADING)


@router.get("/{topic_id}", response_model=TopicStatusResponse)
async def get_topic_status(
    topic_id: str,
    uid: str = Depends(get_current_user_id),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> TopicStatusResponse:
    """Get the processing status of a topic submission."""
    pdf = await firestore.get_pdf(uid, topic_id)
    if not pdf:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic = pdf.filename.removesuffix(".topic")
    return TopicStatusResponse(
        topic_id=topic_id,
        topic=topic,
        status=pdf.status,
        error_message=pdf.error_message,
    )
