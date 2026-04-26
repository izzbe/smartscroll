"""Firestore service."""

import asyncio
from datetime import datetime
from functools import lru_cache

from google.cloud import firestore

from smartscroll.models.firestore import PDF, PDFStatus, Follow, Message, User, Video


class FirestoreService:
    """Async wrapper for Firestore operations."""

    def __init__(self, database: str = "smartscroll") -> None:
        self.db = firestore.Client(database=database)

    def _run_sync(self, func):
        """Run a sync function in an executor."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, func)

    # Users

    async def create_user(self, uid: str, email: str, display_name: str = "") -> User:
        """Create a new user document."""
        user = User(email=email, display_name=display_name)
        await self._run_sync(
            lambda: self.db.collection("users").document(uid).set(user.model_dump())
        )
        return user

    async def get_user(self, uid: str) -> User | None:
        """Get a user by ID."""
        doc = await self._run_sync(
            lambda: self.db.collection("users").document(uid).get()
        )
        if not doc.exists:
            return None
        return User(**doc.to_dict())

    # PDFs

    async def create_pdf(
        self, uid: str, pdf_id: str, filename: str, gcs_path: str
    ) -> PDF:
        """Create a new PDF document."""
        pdf = PDF(filename=filename, gcs_path=gcs_path, status=PDFStatus.UPLOADING)
        await self._run_sync(
            lambda: self.db.collection("users")
            .document(uid)
            .collection("pdfs")
            .document(pdf_id)
            .set(pdf.model_dump())
        )
        return pdf

    async def get_pdf(self, uid: str, pdf_id: str) -> PDF | None:
        """Get a PDF by ID."""
        doc = await self._run_sync(
            lambda: self.db.collection("users")
            .document(uid)
            .collection("pdfs")
            .document(pdf_id)
            .get()
        )
        if not doc.exists:
            return None
        return PDF(**doc.to_dict())

    async def update_pdf_status(
        self,
        uid: str,
        pdf_id: str,
        status: PDFStatus,
        error_message: str | None = None,
    ) -> None:
        """Update PDF status."""
        data: dict = {"status": status.value}
        if error_message is not None:
            data["error_message"] = error_message

        await self._run_sync(
            lambda: self.db.collection("users")
            .document(uid)
            .collection("pdfs")
            .document(pdf_id)
            .update(data)
        )

    async def list_pdfs(self, uid: str) -> list[tuple[str, PDF]]:
        """List all PDFs for a user. Returns list of (pdf_id, PDF)."""
        docs = await self._run_sync(
            lambda: list(
                self.db.collection("users")
                .document(uid)
                .collection("pdfs")
                .order_by("uploaded_at", direction=firestore.Query.DESCENDING)
                .stream()
            )
        )
        return [(doc.id, PDF(**doc.to_dict())) for doc in docs]

    # Videos (one per PDF)

    async def create_video(self, video_id: str, video: Video) -> None:
        """Create a denormalized video document."""
        await self._run_sync(
            lambda: self.db.collection("videos").document(video_id).set(video.model_dump())
        )

    async def get_video(self, video_id: str) -> Video | None:
        """Get a video document by its Firestore document ID."""
        doc = await self._run_sync(
            lambda: self.db.collection("videos").document(video_id).get()
        )
        if not doc.exists:
            return None
        return Video(**doc.to_dict())

    async def get_video_by_pdf_id(self, uid: str, pdf_id: str) -> tuple[str, Video] | None:
        """Get a video document by its source pdf_id."""
        # Single-field filter avoids needing a composite Firestore index.
        # Users have few enough videos that filtering pdf_id in Python is fine.
        docs = await self._run_sync(
            lambda: list(
                self.db.collection("videos")
                .where(filter=firestore.FieldFilter("uid", "==", uid))
                .stream()
            )
        )
        for doc in docs:
            if doc.to_dict().get("pdf_id") == pdf_id:
                return doc.id, Video(**doc.to_dict())
        return None

    async def list_videos_for_user(self, uid: str, limit: int = 10) -> list[tuple[str, Video]]:
        """List videos for a user's feed."""
        docs = await self._run_sync(
            lambda: list(
                self.db.collection("videos")
                .where("uid", "==", uid)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
        )
        return [(doc.id, Video(**doc.to_dict())) for doc in docs]

    async def increment_video_stats(
        self, video_id: str, views: int = 0, watch_ms: int = 0
    ) -> None:
        """Increment video view count and watch time."""
        await self._run_sync(
            lambda: self.db.collection("videos").document(video_id).update(
                {
                    "view_count": firestore.Increment(views),
                    "total_watch_ms": firestore.Increment(watch_ms),
                }
            )
        )

    async def list_videos_for_users(
        self, uids: list[str], limit: int = 500
    ) -> list[tuple[str, Video]]:
        """Fetch videos belonging to any of the given UIDs (max 10 UIDs per Firestore IN query)."""
        if not uids:
            return []
        # Firestore IN supports up to 10 values; slice defensively
        chunk = uids[:10]
        docs = await self._run_sync(
            lambda: list(
                self.db.collection("videos")
                .where(filter=firestore.FieldFilter("uid", "in", chunk))
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
        )
        return [(doc.id, Video(**doc.to_dict())) for doc in docs]

    async def list_all_users(self) -> list[tuple[str, User]]:
        """Return all user documents as (uid, User) pairs."""
        docs = await self._run_sync(
            lambda: list(self.db.collection("users").stream())
        )
        return [(doc.id, User(**doc.to_dict())) for doc in docs]

    # Follows

    async def follow_user(self, follower_uid: str, following_uid: str) -> None:
        """Create a follow relationship."""
        doc_id = f"{follower_uid}_{following_uid}"
        follow = Follow(follower_uid=follower_uid, following_uid=following_uid)
        await self._run_sync(
            lambda: self.db.collection("follows").document(doc_id).set(follow.model_dump())
        )

    async def unfollow_user(self, follower_uid: str, following_uid: str) -> None:
        """Delete a follow relationship."""
        doc_id = f"{follower_uid}_{following_uid}"
        await self._run_sync(
            lambda: self.db.collection("follows").document(doc_id).delete()
        )

    async def is_following(self, follower_uid: str, following_uid: str) -> bool:
        """Check if follower_uid follows following_uid."""
        doc_id = f"{follower_uid}_{following_uid}"
        doc = await self._run_sync(
            lambda: self.db.collection("follows").document(doc_id).get()
        )
        return doc.exists

    async def get_following_uids(self, uid: str) -> list[str]:
        """Return list of UIDs that uid is following."""
        docs = await self._run_sync(
            lambda: list(
                self.db.collection("follows")
                .where(filter=firestore.FieldFilter("follower_uid", "==", uid))
                .stream()
            )
        )
        return [doc.to_dict()["following_uid"] for doc in docs]

    # Messages

    async def send_message(
        self,
        from_uid: str,
        from_display_name: str,
        to_uid: str,
        video_id: str,
        video_caption: str,
        video_gcs_path: str,
    ) -> str:
        """Create a message document and return its ID."""
        import uuid
        message_id = uuid.uuid4().hex
        msg = Message(
            from_uid=from_uid,
            from_display_name=from_display_name,
            to_uid=to_uid,
            video_id=video_id,
            video_caption=video_caption,
            video_gcs_path=video_gcs_path,
        )
        await self._run_sync(
            lambda: self.db.collection("messages").document(message_id).set(msg.model_dump())
        )
        return message_id

    async def list_inbox(self, uid: str, limit: int = 50) -> list[tuple[str, Message]]:
        """List messages sent to uid, newest first."""
        docs = await self._run_sync(
            lambda: list(
                self.db.collection("messages")
                .where(filter=firestore.FieldFilter("to_uid", "==", uid))
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
        )
        return [(doc.id, Message(**doc.to_dict())) for doc in docs]

    async def mark_message_read(self, message_id: str) -> None:
        """Mark a message as read."""
        await self._run_sync(
            lambda: self.db.collection("messages").document(message_id).update({"read": True})
        )

    async def upsert_user(self, uid: str, email: str, display_name: str = "") -> User:
        """Create user if not exists, otherwise return existing. Idempotent."""
        existing = await self.get_user(uid)
        if existing:
            return existing
        return await self.create_user(uid, email, display_name)


@lru_cache
def get_firestore_service() -> FirestoreService:
    """Get cached Firestore service instance."""
    # Ensure GOOGLE_APPLICATION_CREDENTIALS is set before the client is created.
    from smartscroll.config import get_settings
    get_settings()
    return FirestoreService()
