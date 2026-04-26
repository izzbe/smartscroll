"""User discovery and social (follow/unfollow) endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from smartscroll.services.auth import get_current_user_id
from smartscroll.services.firestore import FirestoreService, get_firestore_service

router = APIRouter()


class UserProfile(BaseModel):
    uid: str
    email: str
    display_name: str
    is_following: bool = False


class MeRequest(BaseModel):
    email: str
    display_name: str = ""


@router.post("/me", response_model=UserProfile)
async def upsert_me(
    body: MeRequest,
    uid: str = Depends(get_current_user_id),
    db: FirestoreService = Depends(get_firestore_service),
) -> UserProfile:
    """Create or return the current user's Firestore profile. Call once after login/signup."""
    user = await db.upsert_user(uid, body.email, body.display_name)
    return UserProfile(uid=uid, email=user.email, display_name=user.display_name)


@router.get("/me", response_model=UserProfile)
async def get_me(
    uid: str = Depends(get_current_user_id),
    db: FirestoreService = Depends(get_firestore_service),
) -> UserProfile:
    """Get the current user's profile."""
    user = await db.get_user(uid)
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found. Call POST /api/users/me first.")
    return UserProfile(uid=uid, email=user.email, display_name=user.display_name)


@router.get("", response_model=list[UserProfile])
async def list_users(
    uid: str = Depends(get_current_user_id),
    db: FirestoreService = Depends(get_firestore_service),
) -> list[UserProfile]:
    """List all users. For the demo this is intentionally unfiltered (2 users total)."""
    all_users = await db.list_all_users()
    following_uids = set(await db.get_following_uids(uid))

    return [
        UserProfile(
            uid=user_uid,
            email=user.email,
            display_name=user.display_name,
            is_following=(user_uid in following_uids),
        )
        for user_uid, user in all_users
        if user_uid != uid  # exclude self
    ]


@router.post("/{target_uid}/follow", status_code=204)
async def follow_user(
    target_uid: str,
    uid: str = Depends(get_current_user_id),
    db: FirestoreService = Depends(get_firestore_service),
) -> None:
    """Follow another user."""
    if target_uid == uid:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    target = await db.get_user(target_uid)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await db.follow_user(uid, target_uid)


@router.delete("/{target_uid}/follow", status_code=204)
async def unfollow_user(
    target_uid: str,
    uid: str = Depends(get_current_user_id),
    db: FirestoreService = Depends(get_firestore_service),
) -> None:
    """Unfollow a user."""
    await db.unfollow_user(uid, target_uid)
