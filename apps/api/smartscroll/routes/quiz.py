"""Quiz grading endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from smartscroll.services.auth import get_current_user_id
from smartscroll.services.backboard import judge_free_response
from smartscroll.services.firestore import FirestoreService, get_firestore_service

router = APIRouter()


class JudgeRequest(BaseModel):
    answer: str


class FeedbackItem(BaseModel):
    criterion: str
    hit: bool
    comment: str


class JudgeResponse(BaseModel):
    score: int        # 0–5
    feedback: list[FeedbackItem]


@router.post("/{video_id}/judge", response_model=JudgeResponse)
async def judge_answer(
    video_id: str,
    body: JudgeRequest,
    _uid: str = Depends(get_current_user_id),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> JudgeResponse:
    """Grade a free-response answer for a video's quiz using Backboard AI."""
    video = await firestore.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    fr = video.free_response_question
    if not fr or not fr.get("question") or not fr.get("rubric"):
        raise HTTPException(status_code=404, detail="No free-response question for this video")

    if not body.answer or not body.answer.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty")

    try:
        result = await judge_free_response(
            script=video.script,
            question=fr["question"],
            rubric=fr["rubric"],
            answer=body.answer.strip(),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Grading service error: {e}")

    return JudgeResponse(
        score=result["score"],
        feedback=[FeedbackItem(**f) for f in result["feedback"]],
    )
