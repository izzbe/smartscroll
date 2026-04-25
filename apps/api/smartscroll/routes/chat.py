"""Chat endpoint — lets users ask Gemma questions about a PDF's content."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from smartscroll.services.auth import get_current_user_id
from smartscroll.services.firestore import FirestoreService, get_firestore_service
from smartscroll.services.storage import StorageService, get_storage_service
from smartscroll.services.vertex import chat_with_pdf_context

router = APIRouter()


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str
    pdf_id: str


@router.post("/{pdf_id}", response_model=ChatResponse)
async def chat(
    pdf_id: str,
    body: ChatRequest,
    uid: str = Depends(get_current_user_id),
    firestore: FirestoreService = Depends(get_firestore_service),
    storage: StorageService = Depends(get_storage_service),
) -> ChatResponse:
    """Ask Gemma a question about a specific PDF's content.

    Uses the full extracted PDF text as context. Supports multi-turn
    conversation via the optional `history` field.
    """
    result = await firestore.get_video_by_pdf_id(uid, pdf_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No processed video found for this PDF. Make sure the pipeline completed.",
        )

    _, video = result
    if not video.extracted_text_gcs_path:
        raise HTTPException(
            status_code=422,
            detail="Extracted text not available for this PDF. Re-upload to regenerate.",
        )

    pdf_text = await storage.download_blob_text(video.extracted_text_gcs_path)

    reply = await chat_with_pdf_context(
        pdf_text=pdf_text,
        message=body.message,
        history=[h.model_dump() for h in body.history],
        pdf_id=pdf_id,
    )

    return ChatResponse(reply=reply, pdf_id=pdf_id)
