"""
Pydantic models for API request and response contracts.

Keeping these in one place makes the API surface easy to audit and keeps
FastAPI's auto-generated OpenAPI docs accurate.
"""
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


# ── Upload ────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Returned immediately after a successful file upload."""

    file_id: str = Field(..., description="UUID that uniquely identifies this file")
    file_name: str = Field(..., description="Original filename as provided by the client")
    size_bytes: int = Field(..., description="File size in bytes")
    uploaded_at: datetime = Field(..., description="UTC timestamp of upload")
    message: str = Field(default="File uploaded successfully")


# ── Metadata ──────────────────────────────────────────────────────────────────

class FileMetadata(BaseModel):
    """Metadata record stored for every uploaded file – no binary content."""

    file_id: str
    file_name: str
    size_bytes: int
    uploaded_at: datetime
    content_type: str = Field(..., description="MIME type detected at upload time")


class FileListResponse(BaseModel):
    """Response body for the list-all-files endpoint."""

    total: int = Field(..., description="Total number of files currently stored")
    files: List[FileMetadata]


# ── Summary ───────────────────────────────────────────────────────────────────

class FileSummaryResponse(BaseModel):
    """LLM-generated human-readable summary for a given file."""

    file_id: str
    file_name: str
    content_type: str
    size_bytes: int
    summary: str = Field(..., description="Human-readable summary produced by the LLM")
    summary_source: str = Field(
        ...,
        description=(
            "'rag' if generated via retrieval-augmented generation, "
            "'extractive' if the HF token was not configured, "
            "'metadata' for binary/unsupported file types"
        ),
    )


# ── Error ─────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error envelope returned on all 4xx / 5xx responses."""

    error: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable description")
    detail: str | None = Field(default=None, description="Optional extra context")
