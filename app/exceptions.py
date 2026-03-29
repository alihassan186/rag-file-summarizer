"""
Custom exception classes and their FastAPI exception handlers.

Design principle: every failure mode has its own typed exception so that
handlers can return the correct HTTP status code and a structured JSON body
that clients can parse reliably.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse


# ── Domain exceptions ─────────────────────────────────────────────────────────

class FileNotFoundError(Exception):
    """Raised when a requested file_id does not exist in the metadata store."""

    def __init__(self, file_id: str) -> None:
        self.file_id = file_id
        super().__init__(f"File '{file_id}' not found")


class FileTooLargeError(Exception):
    """Raised when an uploaded file exceeds the configured size limit."""

    def __init__(self, received_bytes: int, max_bytes: int) -> None:
        self.received_bytes = received_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"File size {received_bytes:,} bytes exceeds maximum {max_bytes:,} bytes"
        )


class FileStorageError(Exception):
    """Raised when writing to or reading from disk fails unexpectedly."""
    pass


class SummaryGenerationError(Exception):
    """Raised when the LLM summarisation call fails."""
    pass


class InvalidFileTypeError(Exception):
    """Raised when a file type is not supported for text extraction/RAG."""

    def __init__(self, file_name: str, content_type: str) -> None:
        self.file_name = file_name
        self.content_type = content_type
        super().__init__(
            f"File '{file_name}' with content type '{content_type}' is not supported for RAG"
        )


class EmbeddingGenerationError(Exception):
    """Raised when embedding/index generation fails."""


class RetrievalError(Exception):
    """Raised when vector retrieval or answer generation fails."""


# ── Handlers ──────────────────────────────────────────────────────────────────

async def file_not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "file_not_found",
            "message": str(exc),
            "detail": f"No file with id='{exc.file_id}' exists in the store",
        },
    )


async def file_too_large_handler(request: Request, exc: FileTooLargeError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={
            "error": "file_too_large",
            "message": str(exc),
            "detail": f"Maximum allowed size is {exc.max_bytes / (1024 * 1024):.0f} MB",
        },
    )


async def storage_error_handler(request: Request, exc: FileStorageError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "storage_error",
            "message": str(exc),
            "detail": "An unexpected error occurred while accessing the file store",
        },
    )


async def summary_error_handler(
    request: Request, exc: SummaryGenerationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "error": "summary_generation_failed",
            "message": str(exc),
            "detail": "The LLM summarisation service returned an unexpected response",
        },
    )


async def invalid_file_type_handler(
    request: Request, exc: InvalidFileTypeError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        content={
            "error": "unsupported_file_type",
            "message": str(exc),
            "detail": "Supported types currently include text files and PDFs",
        },
    )


async def embedding_error_handler(
    request: Request, exc: EmbeddingGenerationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "embedding_generation_failed",
            "message": str(exc),
            "detail": "Failed to process and index the document for retrieval",
        },
    )


async def retrieval_error_handler(request: Request, exc: RetrievalError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "error": "retrieval_generation_failed",
            "message": str(exc),
            "detail": "Failed while retrieving context chunks or generating response",
        },
    )
