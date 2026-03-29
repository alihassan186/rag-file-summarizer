"""
File-sharing API routes.

Endpoints:
  POST /files/          – Upload a file
  GET  /files/          – List all files (metadata only)
  GET  /files/{file_id} – Download a file
  GET  /files/{file_id}/summary – LLM-generated summary
"""
import logging

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models import (
    FileListResponse,
    FileSummaryResponse,
    UploadResponse,
)
from app.services.files_service import FileService
from app.deps import get_file_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Files"])


# ── POST /files/ ──────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file",
    description=(
        "Accepts a multipart/form-data upload. "
        f"Maximum file size: {settings.max_file_size_bytes // (1024 * 1024)} MB. "
        "Returns a unique file ID that can be used to download or summarise the file."
    ),
)
async def upload_file(
    file: UploadFile = File(...),
    service: FileService = Depends(get_file_service),
) -> UploadResponse:
    """Upload a file and receive its unique ID.

    - **file**: The file to upload (multipart/form-data field name: ``file``)
    """
    metadata = await service.upload_file(file)

    return UploadResponse(
        file_id=metadata.file_id,
        file_name=metadata.file_name,
        size_bytes=metadata.size_bytes,
        uploaded_at=metadata.uploaded_at,
    )


# ── GET /files/ ───────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=FileListResponse,
    summary="List all uploaded files",
    description="Returns metadata for every uploaded file. File content is never included.",
)
async def list_all_files(
    service: FileService = Depends(get_file_service),
) -> FileListResponse:
    """List metadata for all uploaded files, newest first."""
    files = await service.list_files()
    return FileListResponse(total=len(files), files=files)


# ── GET /files/{file_id} ─────────────────────────────────────────────────────

@router.get(
    "/{file_id}",
    summary="Download a file",
    description="Streams the raw file bytes for the given file ID.",
    responses={
        200: {"description": "Raw file content"},
        404: {"description": "File not found"},
    },
)
async def download_file(
    file_id: str,
    service: FileService = Depends(get_file_service),
) -> StreamingResponse:
    """Download the file associated with *file_id*.

    The ``Content-Disposition`` header is set so browsers trigger a download
    with the original filename.
    """
    metadata, stream = await service.get_download_stream(file_id)

    return StreamingResponse(
        content=stream,
        media_type=metadata.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{metadata.file_name}"',
            "Content-Length": str(metadata.size_bytes),
        },
    )


# ── GET /files/{file_id}/summary ─────────────────────────────────────────────

@router.get(
    "/{file_id}/summary",
    response_model=FileSummaryResponse,
    summary="Get a RAG-generated summary of a file",
    description=(
        "Generates a short human-readable summary through the internal RAG "
        "pipeline (ingestion, retrieval, and generation). If RAG is disabled "
        "or unsupported for the file type, the service falls back to "
        "extractive/metadata summarisation."
    ),
)
async def get_file_summary(
    file_id: str,
    service: FileService = Depends(get_file_service),
) -> FileSummaryResponse:
    """Return an LLM-generated summary for the file identified by *file_id*."""
    metadata, summary_text, summary_source = await service.summarise_file(file_id)

    return FileSummaryResponse(
        file_id=metadata.file_id,
        file_name=metadata.file_name,
        content_type=metadata.content_type,
        size_bytes=metadata.size_bytes,
        summary=summary_text,
        summary_source=summary_source,
    )
