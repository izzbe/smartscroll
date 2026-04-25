"""Firestore service."""

import asyncio
from datetime import datetime
from functools import lru_cache

from google.cloud import firestore

from smartscroll.models.firestore import PDF, PDFStatus, User, Video


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


@lru_cache
def get_firestore_service() -> FirestoreService:
    """Get cached Firestore service instance."""
    return FirestoreService()
