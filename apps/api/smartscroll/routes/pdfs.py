"""PDF upload and management endpoints."""

import json
import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel

from smartscroll.models.firestore import PDF, PDFStatus
from smartscroll.pipeline.orchestrator import process_pdf_background
from smartscroll.pipeline.render import render_video
from smartscroll.services.auth import get_current_user_id
from smartscroll.services.firestore import FirestoreService, get_firestore_service
from smartscroll.services.storage import StorageService, get_storage_service
from smartscroll.services.tts import WordTiming, generate_speech_with_timestamps

logger = structlog.get_logger()

router = APIRouter()


class UploadResponse(BaseModel):
    """Response for PDF upload."""

    pdf_id: str
    uid: str
    gcs_uri: str
    filename: str
    status: PDFStatus


class PDFResponse(BaseModel):
    """Response for a single PDF."""

    pdf_id: str
    filename: str
    gcs_path: str
    status: PDFStatus
    error_message: str | None


class ListPDFsResponse(BaseModel):
    """Response for listing PDFs."""

    uid: str
    pdfs: list[PDFResponse]


@router.get("", response_model=ListPDFsResponse)
async def list_pdfs(
    uid: str = Depends(get_current_user_id),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> ListPDFsResponse:
    """List all PDFs for the current user."""
    pdfs = await firestore.list_pdfs(uid)
    return ListPDFsResponse(
        uid=uid,
        pdfs=[
            PDFResponse(
                pdf_id=pdf_id,
                filename=pdf.filename,
                gcs_path=pdf.gcs_path,
                status=pdf.status,
                error_message=pdf.error_message,
            )
            for pdf_id, pdf in pdfs
        ],
    )


@router.get("/{pdf_id}", response_model=PDFResponse)
async def get_pdf(
    pdf_id: str,
    uid: str = Depends(get_current_user_id),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> PDFResponse:
    """Get a single PDF by ID."""
    pdf = await firestore.get_pdf(uid, pdf_id)
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    return PDFResponse(
        pdf_id=pdf_id,
        filename=pdf.filename,
        gcs_path=pdf.gcs_path,
        status=pdf.status,
        error_message=pdf.error_message,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    gameplay_style: str | None = Form(None),
    uid: str = Depends(get_current_user_id),
    storage: StorageService = Depends(get_storage_service),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> UploadResponse:
    """Upload a PDF to GCS and start background processing.

    The PDF is uploaded to GCS and a Firestore record is created.
    Background processing is then triggered to:
    1. Extract text from the PDF
    2. Generate a TikTok-style script with Gemma
    3. Generate narration audio with ElevenLabs TTS
    Poll GET /api/pdfs/{pdf_id} to check processing status.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    pdf_id = uuid.uuid4().hex
    destination_path = f"{uid}/{pdf_id}/{file.filename}"

    # Upload to GCS
    gcs_uri = await storage.upload_pdf(content, destination_path)

    # Create Firestore record
    await firestore.create_pdf(
        uid=uid,
        pdf_id=pdf_id,
        filename=file.filename,
        gcs_path=gcs_uri,
    )

    # Start background processing pipeline
    background_tasks.add_task(
        process_pdf_background,
        uid=uid,
        pdf_id=pdf_id,
        gcs_path=gcs_uri,
        filename=file.filename,
        gameplay_style=gameplay_style,
    )

    return UploadResponse(
        pdf_id=pdf_id,
        uid=uid,
        gcs_uri=gcs_uri,
        filename=file.filename,
        status=PDFStatus.UPLOADING,
    )


async def _rerender_background(uid: str, pdf_id: str, storage: StorageService) -> None:
    """Re-render an existing video without the title overlay.

    Downloads the stored narration.mp3 and timings.json from GCS, then
    re-runs FFmpeg. If timings.json is missing (old upload), falls back to
    re-calling ElevenLabs with the stored script.
    """
    log = logger.bind(uid=uid, pdf_id=pdf_id)
    from smartscroll.config import get_settings
    settings = get_settings()
    rendered_bucket = settings.gcs_bucket_rendered

    narration_uri = f"gs://{rendered_bucket}/{uid}/{pdf_id}/narration.mp3"
    timings_uri   = f"gs://{rendered_bucket}/{uid}/{pdf_id}/timings.json"

    log.info("rerender_downloading_narration")
    narration_bytes = await storage.download_blob_bytes(narration_uri)

    try:
        log.info("rerender_downloading_timings")
        timings_json = await storage.download_blob_text(timings_uri)
        raw = json.loads(timings_json)
        word_timings = [WordTiming(word=w["word"], start_time=w["start"], end_time=w["end"]) for w in raw]
        duration_ms = int(raw[-1]["end"] * 1000) if raw else 0
        log.info("rerender_timings_loaded", words=len(word_timings))
    except Exception:
        log.info("rerender_timings_missing_falling_back_to_tts")
        firestore = get_firestore_service()
        result = await firestore.get_video_by_pdf_id(uid, pdf_id)
        if not result:
            log.error("rerender_no_video_record")
            return
        _, video = result
        tts = await generate_speech_with_timestamps(video.script)
        word_timings = tts.word_timings
        narration_bytes = tts.audio
        duration_ms = tts.duration_ms

    log.info("rerender_running_ffmpeg")
    await render_video(
        uid=uid,
        pdf_id=pdf_id,
        narration_audio=narration_bytes,
        word_timings=word_timings,
        duration_ms=duration_ms,
    )
    log.info("rerender_complete")


@router.post("/{pdf_id}/rerender")
async def rerender_video(
    pdf_id: str,
    background_tasks: BackgroundTasks,
    uid: str = Depends(get_current_user_id),
    firestore: FirestoreService = Depends(get_firestore_service),
    storage: StorageService = Depends(get_storage_service),
) -> dict:
    """Re-render an existing video to remove the burned-in title overlay.

    Kicks off a background FFmpeg re-render using the stored narration.mp3
    and timings.json. The new video.mp4 overwrites the old one in GCS.
    Refresh the feed after ~30s to see the updated video.
    """
    result = await firestore.get_video_by_pdf_id(uid, pdf_id)
    if not result:
        raise HTTPException(status_code=404, detail="No video found for this PDF")

    background_tasks.add_task(_rerender_background, uid, pdf_id, storage)
    return {"status": "rerendering", "pdf_id": pdf_id}
