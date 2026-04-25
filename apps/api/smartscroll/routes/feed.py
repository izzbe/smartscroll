"""Video feed endpoints."""

import base64
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from smartscroll.services.auth import get_current_user_id
from smartscroll.services.firestore import FirestoreService, get_firestore_service
from smartscroll.services.storage import StorageService, get_storage_service

router = APIRouter()

PAGE_SIZE = 10
HALF_LIFE_SECONDS = 2 * 24 * 3600  # 2 days


class FeedVideo(BaseModel):
    video_id: str
    pdf_id: str
    pdf_filename: str
    video_gcs_path: str
    video_url: str
    duration_ms: int
    video_caption: str
    script: str
    created_at: datetime


class FeedResponse(BaseModel):
    videos: list[FeedVideo]
    next_cursor: str | None


def _recency_score(created_at: datetime, now: datetime) -> float:
    """Exponential decay with 2-day half-life. Returns value in (0, 1]."""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age_s = max(0.0, (now - created_at).total_seconds())
    return math.exp(-math.log(2) * age_s / HALF_LIFE_SECONDS)



def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return 0


@router.get("", response_model=FeedResponse)
async def get_feed(
    cursor: str | None = Query(default=None),
    uid: str = Depends(get_current_user_id),
    firestore: FirestoreService = Depends(get_firestore_service),
    storage: StorageService = Depends(get_storage_service),
) -> FeedResponse:
    """Return a paginated, recency-scored feed of videos for the current user."""
    all_videos = await firestore.list_videos_for_user(uid, limit=500)
    ready_videos = [(vid_id, v) for vid_id, v in all_videos if v.video_gcs_path]

    if not ready_videos:
        return FeedResponse(videos=[], next_cursor=None)

    now = datetime.now(tz=timezone.utc)
    scored = [
        (_recency_score(v.created_at, now), vid_id, v)
        for vid_id, v in ready_videos
    ]

    # Descending score bucket (rounded to 0.1), newest-first within bucket
    scored.sort(key=lambda t: (-round(t[0], 1), -t[2].created_at.timestamp()))

    offset = _decode_cursor(cursor) if cursor else 0
    page = scored[offset : offset + PAGE_SIZE]
    next_cursor = _encode_cursor(offset + PAGE_SIZE) if offset + PAGE_SIZE < len(scored) else None

    feed_items: list[FeedVideo] = []
    for _, vid_id, video in page:
        signed_url = await storage.get_signed_url(video.video_gcs_path)
        feed_items.append(
            FeedVideo(
                video_id=vid_id,
                pdf_id=video.pdf_id,
                pdf_filename=video.pdf_filename,
                video_gcs_path=video.video_gcs_path,
                video_url=signed_url,
                duration_ms=video.duration_ms,
                video_caption=video.video_caption,
                script=video.script,
                created_at=video.created_at,
            )
        )

    return FeedResponse(videos=feed_items, next_cursor=next_cursor)
