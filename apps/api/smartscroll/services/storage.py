"""Google Cloud Storage service."""

import asyncio
from functools import lru_cache

from google.cloud import storage
from pydantic import BaseModel

from smartscroll.config import get_settings


class PDFInfo(BaseModel):
    """Info about a stored PDF."""

    pdf_id: str
    filename: str
    gcs_uri: str
    size_bytes: int


class StorageService:
    """Async wrapper for GCS operations."""

    def __init__(self, bucket_name: str) -> None:
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.bucket_name = bucket_name

    async def upload_pdf(self, content: bytes, destination_path: str) -> str:
        """Upload PDF bytes to GCS.

        Args:
            content: PDF file bytes
            destination_path: Path within the bucket (e.g., "user123/abc.pdf")

        Returns:
            GCS URI (gs://bucket/path)
        """
        blob = self.bucket.blob(destination_path)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: blob.upload_from_string(content, content_type="application/pdf"),
        )

        return f"gs://{self.bucket.name}/{destination_path}"

    async def list_pdfs(self, uid: str) -> list[PDFInfo]:
        """List all PDFs for a user.

        Args:
            uid: User ID

        Returns:
            List of PDFInfo objects
        """
        loop = asyncio.get_event_loop()

        def _list() -> list[PDFInfo]:
            prefix = f"{uid}/"
            blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
            pdfs = []
            for blob in blobs:
                if blob.name.endswith(".pdf"):
                    # Path format: {uid}/{pdf_id}/{filename}.pdf
                    parts = blob.name.split("/")
                    if len(parts) >= 3:
                        pdf_id = parts[1]
                        filename = parts[2]
                        pdfs.append(
                            PDFInfo(
                                pdf_id=pdf_id,
                                filename=filename,
                                gcs_uri=f"gs://{self.bucket_name}/{blob.name}",
                                size_bytes=blob.size or 0,
                            )
                        )
            return pdfs

        return await loop.run_in_executor(None, _list)


    async def get_signed_url(self, gcs_uri: str, expiration_seconds: int = 3600) -> str:
        """Generate a signed URL for a GCS object so clients can stream it directly.

        Args:
            gcs_uri: Full GCS URI, e.g. gs://smartscroll-rendered/uid/pdf_id/video.mp4
            expiration_seconds: URL validity window in seconds (default 1 hour)

        Returns:
            HTTPS signed URL.
        """
        import datetime

        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        without_scheme = gcs_uri[len("gs://"):]
        bucket_name, _, blob_path = without_scheme.partition("/")
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        loop = asyncio.get_event_loop()
        url: str = await loop.run_in_executor(
            None,
            lambda: blob.generate_signed_url(
                expiration=datetime.timedelta(seconds=expiration_seconds),
                method="GET",
                version="v4",
            ),
        )
        return url

    async def download_blob_text(self, gcs_uri: str) -> str:
        """Download a text blob from any GCS URI (gs://bucket/path).

        Args:
            gcs_uri: Full GCS URI, e.g. gs://smartscroll-rendered/uid/pdf_id/extracted_text.txt

        Returns:
            Decoded text content.
        """
        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        without_scheme = gcs_uri[len("gs://"):]
        bucket_name, _, blob_path = without_scheme.partition("/")
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        loop = asyncio.get_event_loop()
        data: bytes = await loop.run_in_executor(None, blob.download_as_bytes)
        return data.decode("utf-8")


@lru_cache
def get_storage_service() -> StorageService:
    """Get cached storage service instance."""
    settings = get_settings()
    return StorageService(bucket_name=settings.gcs_bucket_pdfs)
