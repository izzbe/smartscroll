"""
Pipeline orchestrator — connects PDF upload → text extraction → script → TTS.

This is the main entry point for processing a PDF into a video.
"""

import asyncio
import json
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import structlog

from smartscroll.models.firestore import PDFStatus, Video
from smartscroll.pipeline.render import render_video
from smartscroll.services.firestore import FirestoreService, get_firestore_service
from smartscroll.services.ingestion import extract_full_pdf_text
from smartscroll.services.storage import StorageService, get_storage_service
from smartscroll.services.tts import TTSResult, generate_speech_with_timestamps
from smartscroll.services.vertex import generate_video_caption, rewrite_pdf_to_script

logger = structlog.get_logger()


@dataclass
class PipelineResult:
    """Result of the full pipeline."""

    pdf_id: str
    video_id: str
    script: str
    script_prompt_version: int
    word_count: int
    duration_ms: int
    narration_gcs_path: str
    video_gcs_path: str


async def download_pdf_from_gcs(
    storage: StorageService,
    gcs_path: str,
    local_path: Path,
) -> None:
    """Download a PDF from GCS to a local path."""
    # gcs_path format: gs://bucket/path/to/file.pdf
    # Extract blob path (remove gs://bucket/ prefix)
    blob_path = gcs_path.replace(f"gs://{storage.bucket_name}/", "")
    blob = storage.bucket.blob(blob_path)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.download_to_filename(str(local_path)),
    )


async def upload_audio_to_gcs(
    storage: StorageService,
    audio_bytes: bytes,
    destination_path: str,
) -> str:
    """Upload audio bytes to the rendered bucket."""
    from smartscroll.config import get_settings

    settings = get_settings()
    client = storage.client
    bucket = client.bucket(settings.gcs_bucket_rendered)
    blob = bucket.blob(destination_path)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(audio_bytes, content_type="audio/mpeg"),
    )

    return f"gs://{settings.gcs_bucket_rendered}/{destination_path}"


async def upload_text_to_gcs(
    storage: StorageService,
    text: str,
    destination_path: str,
) -> str:
    """Upload a plain-text string to the rendered bucket."""
    from smartscroll.config import get_settings

    settings = get_settings()
    client = storage.client
    bucket = client.bucket(settings.gcs_bucket_rendered)
    blob = bucket.blob(destination_path)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(text.encode("utf-8"), content_type="text/plain; charset=utf-8"),
    )

    return f"gs://{settings.gcs_bucket_rendered}/{destination_path}"


async def process_pdf(
    uid: str,
    pdf_id: str,
    gcs_path: str,
    filename: str,
    firestore: FirestoreService | None = None,
    storage: StorageService | None = None,
) -> PipelineResult:
    """
    Full pipeline: PDF → text → script → TTS → stored audio.

    Args:
        uid: User ID
        pdf_id: PDF document ID
        gcs_path: GCS path to the PDF file
        filename: Original filename
        firestore: Firestore service (optional, will create if not provided)
        storage: Storage service (optional, will create if not provided)

    Returns:
        PipelineResult with all generated artifacts

    Raises:
        Exception: If any pipeline step fails
    """
    firestore = firestore or get_firestore_service()
    storage = storage or get_storage_service()

    log = logger.bind(uid=uid, pdf_id=pdf_id, filename=filename)
    log.info("pipeline_started")

    try:
        # Update status to processing
        await firestore.update_pdf_status(uid, pdf_id, PDFStatus.PROCESSING)

        # Step 1: Download PDF from GCS to temp file
        log.info("step_1_downloading_pdf")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        await download_pdf_from_gcs(storage, gcs_path, tmp_path)
        log.info("pdf_downloaded", local_path=str(tmp_path))

        # Step 2: Extract text from PDF
        log.info("step_2_extracting_text")
        pdf_text = extract_full_pdf_text(str(tmp_path))
        input_word_count = len(pdf_text.split())
        log.info("text_extracted", word_count=input_word_count)

        # Clean up temp file
        tmp_path.unlink()

        # Step 2b: Upload extracted text to GCS for later use (e.g. chat context)
        log.info("step_2b_uploading_extracted_text")
        text_path = f"{uid}/{pdf_id}/extracted_text.txt"
        extracted_text_gcs_path = await upload_text_to_gcs(storage, pdf_text, text_path)
        log.info("extracted_text_uploaded", gcs_path=extracted_text_gcs_path)

        # Step 3: Generate script with Gemma
        log.info("step_3_generating_script")
        script, prompt_version = await rewrite_pdf_to_script(pdf_text, pdf_id)
        script_word_count = len(script.split())
        log.info(
            "script_generated",
            word_count=script_word_count,
            prompt_version=prompt_version,
        )

        # Step 3b: Generate short title caption for video overlay
        log.info("step_3b_generating_caption")
        video_caption = await generate_video_caption(script, pdf_id)
        log.info("caption_generated", caption=video_caption)

        # Step 4: Generate TTS with timestamps
        log.info("step_4_generating_tts")
        tts_result: TTSResult = await generate_speech_with_timestamps(script)
        log.info(
            "tts_generated",
            duration_ms=tts_result.duration_ms,
            audio_bytes=len(tts_result.audio),
        )

        # Step 5: Upload audio to GCS
        log.info("step_5_uploading_audio")
        audio_path = f"{uid}/{pdf_id}/narration.mp3"
        narration_gcs_path = await upload_audio_to_gcs(
            storage, tts_result.audio, audio_path
        )
        log.info("audio_uploaded", gcs_path=narration_gcs_path)

        # Step 5b: Save word timings JSON (allows cheap re-render without re-running TTS)
        log.info("step_5b_uploading_timings")
        timings_data = [
            {"word": t.word, "start": t.start_time, "end": t.end_time}
            for t in tts_result.word_timings
        ]
        await upload_text_to_gcs(storage, json.dumps(timings_data), f"{uid}/{pdf_id}/timings.json")

        # Step 6: Render video (gameplay + narration + captions → MP4, no title overlay)
        log.info("step_6_rendering_video")
        video_gcs_path = await render_video(
            uid=uid,
            pdf_id=pdf_id,
            narration_audio=tts_result.audio,
            word_timings=tts_result.word_timings,
            duration_ms=tts_result.duration_ms,
        )
        log.info("video_rendered", gcs_path=video_gcs_path)

        # Step 7: Create video record in Firestore
        log.info("step_7_creating_video_record")
        video_id = uuid.uuid4().hex
        video = Video(
            uid=uid,
            pdf_id=pdf_id,
            pdf_filename=filename,
            video_gcs_path=video_gcs_path,
            duration_ms=tts_result.duration_ms,
            script=script,
            script_prompt_version=prompt_version,
            word_count=script_word_count,
            extracted_text_gcs_path=extracted_text_gcs_path,
            video_caption=video_caption,
        )
        await firestore.create_video(video_id, video)
        log.info("video_record_created", video_id=video_id)

        # Step 8: Update PDF status to ready
        await firestore.update_pdf_status(uid, pdf_id, PDFStatus.READY)
        log.info("pipeline_completed", video_id=video_id)

        return PipelineResult(
            pdf_id=pdf_id,
            video_id=video_id,
            script=script,
            script_prompt_version=prompt_version,
            word_count=script_word_count,
            duration_ms=tts_result.duration_ms,
            narration_gcs_path=narration_gcs_path,
            video_gcs_path=video_gcs_path,
        )

    except Exception as e:
        log.error("pipeline_failed", error=str(e))
        await firestore.update_pdf_status(
            uid, pdf_id, PDFStatus.FAILED, error_message=str(e)
        )
        raise


async def process_topic(
    uid: str,
    topic_id: str,
    topic: str,
    firestore: FirestoreService | None = None,
    storage: StorageService | None = None,
) -> PipelineResult:
    """Full pipeline: topic → Backboard research → Gemma script → TTS → video.

    Identical to process_pdf from step 3 onward; steps 1-2 are replaced by a
    Backboard API call that returns a research article for the given topic.
    """
    from smartscroll.services.backboard import research_topic

    firestore = firestore or get_firestore_service()
    storage = storage or get_storage_service()

    log = logger.bind(uid=uid, topic_id=topic_id, topic=topic[:80])
    log.info("topic_pipeline_started")

    try:
        await firestore.update_pdf_status(uid, topic_id, PDFStatus.PROCESSING)

        # Step 1: Research via Backboard (replaces PDF download + text extraction)
        log.info("step_1_researching_topic")
        research_text = await research_topic(topic)
        log.info("topic_researched", word_count=len(research_text.split()))

        # Step 1b: Upload research text to GCS (used as chat context + audit trail)
        text_path = f"{uid}/{topic_id}/extracted_text.txt"
        extracted_text_gcs_path = await upload_text_to_gcs(storage, research_text, text_path)

        # Step 2: Generate Gemma script from research text
        log.info("step_2_generating_script")
        script, prompt_version = await rewrite_pdf_to_script(research_text, topic_id)
        script_word_count = len(script.split())
        log.info("script_generated", word_count=script_word_count, prompt_version=prompt_version)

        # Step 2b: Generate short title caption
        log.info("step_2b_generating_caption")
        video_caption = await generate_video_caption(script, topic_id)
        log.info("caption_generated", caption=video_caption)

        # Step 3: TTS
        log.info("step_3_generating_tts")
        tts_result: TTSResult = await generate_speech_with_timestamps(script)
        log.info("tts_generated", duration_ms=tts_result.duration_ms)

        # Step 4: Upload narration
        audio_path = f"{uid}/{topic_id}/narration.mp3"
        narration_gcs_path = await upload_audio_to_gcs(storage, tts_result.audio, audio_path)

        # Step 4b: Upload word timings
        timings_data = [
            {"word": t.word, "start": t.start_time, "end": t.end_time}
            for t in tts_result.word_timings
        ]
        await upload_text_to_gcs(storage, json.dumps(timings_data), f"{uid}/{topic_id}/timings.json")

        # Step 5: Render video
        log.info("step_5_rendering_video")
        video_gcs_path = await render_video(
            uid=uid,
            pdf_id=topic_id,
            narration_audio=tts_result.audio,
            word_timings=tts_result.word_timings,
            duration_ms=tts_result.duration_ms,
        )
        log.info("video_rendered", gcs_path=video_gcs_path)

        # Step 6: Create Firestore video record
        video_id = uuid.uuid4().hex
        video = Video(
            uid=uid,
            pdf_id=topic_id,
            pdf_filename=f"{topic[:80]}.topic",
            video_gcs_path=video_gcs_path,
            duration_ms=tts_result.duration_ms,
            script=script,
            script_prompt_version=prompt_version,
            word_count=script_word_count,
            extracted_text_gcs_path=extracted_text_gcs_path,
            video_caption=video_caption,
        )
        await firestore.create_video(video_id, video)

        # Step 7: Mark as ready
        await firestore.update_pdf_status(uid, topic_id, PDFStatus.READY)
        log.info("topic_pipeline_completed", video_id=video_id)

        return PipelineResult(
            pdf_id=topic_id,
            video_id=video_id,
            script=script,
            script_prompt_version=prompt_version,
            word_count=script_word_count,
            duration_ms=tts_result.duration_ms,
            narration_gcs_path=narration_gcs_path,
            video_gcs_path=video_gcs_path,
        )

    except Exception as e:
        log.error("topic_pipeline_failed", error=str(e))
        await firestore.update_pdf_status(uid, topic_id, PDFStatus.FAILED, error_message=str(e))
        raise


async def process_topic_background(uid: str, topic_id: str, topic: str) -> None:
    """Background task wrapper for process_topic."""
    try:
        await process_topic(uid, topic_id, topic)
    except Exception as e:
        logger.error("background_topic_pipeline_failed", uid=uid, topic_id=topic_id, error=str(e))


async def process_pdf_background(
    uid: str,
    pdf_id: str,
    gcs_path: str,
    filename: str,
) -> None:
    """
    Background task wrapper for process_pdf.

    This is the entry point called from FastAPI BackgroundTasks.
    Errors are logged and stored in Firestore, not raised.
    """
    try:
        await process_pdf(uid, pdf_id, gcs_path, filename)
    except Exception as e:
        # Error already logged and stored in Firestore by process_pdf
        logger.error(
            "background_pipeline_failed",
            uid=uid,
            pdf_id=pdf_id,
            error=str(e),
        )
