"""PDF upload and management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from smartscroll.models.firestore import PDF, PDFStatus
from smartscroll.services.auth import get_current_user_id
from smartscroll.services.firestore import FirestoreService, get_firestore_service
from smartscroll.services.storage import StorageService, get_storage_service

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
    chunk_count: int
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
                chunk_count=pdf.chunk_count,
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
        chunk_count=pdf.chunk_count,
        error_message=pdf.error_message,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile,
    uid: str = Depends(get_current_user_id),
    storage: StorageService = Depends(get_storage_service),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> UploadResponse:
    """Upload a PDF to GCS and create Firestore record."""
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

    return UploadResponse(
        pdf_id=pdf_id,
        uid=uid,
        gcs_uri=gcs_uri,
        filename=file.filename,
        status=PDFStatus.UPLOADING,
    )
