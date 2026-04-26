"""Messaging endpoints — send and receive shared videos."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from smartscroll.services.auth import get_current_user_id
from smartscroll.services.firestore import FirestoreService, get_firestore_service
from smartscroll.services.storage import StorageService, get_storage_service

router = APIRouter()


class SendMessageRequest(BaseModel):
    to_uid: str
    video_id: str
    video_caption: str = ""
    video_gcs_path: str = ""


class SendMessageResponse(BaseModel):
    message_id: str


class InboxMessage(BaseModel):
    message_id: str
    from_uid: str
    from_display_name: str
    video_id: str
    video_caption: str
    video_url: str
    created_at: datetime
    read: bool


@router.post("", response_model=SendMessageResponse)
async def send_message(
    body: SendMessageRequest,
    uid: str = Depends(get_current_user_id),
    db: FirestoreService = Depends(get_firestore_service),
) -> SendMessageResponse:
    """Send a video to another user."""
    if body.to_uid == uid:
        raise HTTPException(status_code=400, detail="Cannot send a video to yourself")
    target = await db.get_user(body.to_uid)
    if not target:
        raise HTTPException(status_code=404, detail="Recipient not found")

    sender = await db.get_user(uid)
    from_display_name = sender.display_name if sender else ""

    message_id = await db.send_message(
        from_uid=uid,
        from_display_name=from_display_name,
        to_uid=body.to_uid,
        video_id=body.video_id,
        video_caption=body.video_caption,
        video_gcs_path=body.video_gcs_path,
    )
    return SendMessageResponse(message_id=message_id)


@router.get("/inbox", response_model=list[InboxMessage])
async def get_inbox(
    uid: str = Depends(get_current_user_id),
    db: FirestoreService = Depends(get_firestore_service),
    storage: StorageService = Depends(get_storage_service),
) -> list[InboxMessage]:
    """Return the current user's received messages with fresh signed video URLs."""
    messages = await db.list_inbox(uid)
    result = []
    for msg_id, msg in messages:
        try:
            video_url = await storage.get_signed_url(msg.video_gcs_path) if msg.video_gcs_path else ""
        except Exception:
            video_url = ""
        result.append(InboxMessage(
            message_id=msg_id,
            from_uid=msg.from_uid,
            from_display_name=msg.from_display_name,
            video_id=msg.video_id,
            video_caption=msg.video_caption,
            video_url=video_url,
            created_at=msg.created_at,
            read=msg.read,
        ))
    return result


@router.post("/{message_id}/read", status_code=204)
async def mark_read(
    message_id: str,
    uid: str = Depends(get_current_user_id),
    db: FirestoreService = Depends(get_firestore_service),
) -> None:
    """Mark a message as read."""
    await db.mark_message_read(message_id)
