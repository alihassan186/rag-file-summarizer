"""
Pydantic models for API request and response contracts.

Keeping these in one place makes the API surface easy to audit and keeps
FastAPI's auto-generated OpenAPI docs accurate.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Base model that rejects unexpected fields in API contracts."""

    model_config = ConfigDict(extra="forbid")


# ── Upload ────────────────────────────────────────────────────────────────────

class UploadResponse(ApiModel):
    """Returned immediately after a successful file upload."""

    file_id: str = Field(..., description="UUID that uniquely identifies this file")
    file_name: str = Field(..., description="Original filename as provided by the client")
    size_bytes: int = Field(..., description="File size in bytes")
    uploaded_at: datetime = Field(..., description="UTC timestamp of upload")
    message: str = Field(default="File uploaded successfully")


# ── Metadata ──────────────────────────────────────────────────────────────────

class FileMetadata(ApiModel):
    """Metadata record stored for every uploaded file – no binary content."""

    file_id: str
    file_name: str
    size_bytes: int
    uploaded_at: datetime
    content_type: str = Field(..., description="MIME type detected at upload time")


class FileListResponse(ApiModel):
    """Response body for the list-all-files endpoint."""

    total: int = Field(..., description="Total number of files currently stored")
    files: list[FileMetadata]


# ── Summary ───────────────────────────────────────────────────────────────────

class FileSummaryResponse(ApiModel):
    """LLM-generated human-readable summary for a given file."""

    file_id: str
    file_name: str
    content_type: str
    size_bytes: int
    summary: str = Field(..., description="Human-readable summary produced by the LLM")
    summary_source: Literal["rag", "llm", "extractive", "metadata"] = Field(
        ...,
        description=(
            "'rag' for retrieval-augmented generation, "
            "'llm' for direct HF summarisation, "
            "'extractive' for local fallback summaries, "
            "'metadata' for binary/unsupported file types"
        ),
    )


# ── Error ─────────────────────────────────────────────────────────────────────

class ErrorResponse(ApiModel):
    """Standard error envelope returned on all 4xx / 5xx responses."""

    error: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable description")
    detail: str | None = Field(default=None, description="Optional extra context")
