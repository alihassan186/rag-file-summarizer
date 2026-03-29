"""
Service layer for file operations.

This isolates HTTP concerns from storage/LLM details and keeps the API thin.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from fastapi import UploadFile

from app.config import settings
from app.exceptions import EmbeddingGenerationError, InvalidFileTypeError, RetrievalError
from app.models import FileMetadata
from app.rag.pipeline import RagPipeline
from app.storage import StorageProtocol
from app.summariser import SummariserProtocol

logger = logging.getLogger(__name__)


class FileService:
    def __init__(
        self,
        storage: StorageProtocol,
        summariser: SummariserProtocol,
        rag_pipeline: RagPipeline,
    ) -> None:
        self._storage = storage
        self._summariser = summariser
        self._rag_pipeline = rag_pipeline

    async def upload_file(self, upload: UploadFile) -> FileMetadata:
        metadata = await self._storage.save_upload_file(
            upload=upload,
            max_size_bytes=settings.max_file_size_bytes,
            chunk_size_bytes=settings.upload_chunk_size_bytes,
        )
        await self._prepare_rag_index(metadata)
        return metadata

    async def list_files(self) -> list[FileMetadata]:
        return await self._storage.list_files()

    async def get_download_stream(
        self, file_id: str
    ) -> tuple[FileMetadata, AsyncIterator[bytes]]:
        metadata = await self._storage.get_metadata(file_id)
        stream = self._storage.stream_file(
            file_id=file_id,
            chunk_size_bytes=settings.download_chunk_size_bytes,
        )
        return metadata, stream

    async def summarise_file(self, file_id: str) -> tuple[FileMetadata, str, str]:
        metadata = await self._storage.get_metadata(file_id)
        file_bytes = await self._storage.read_file_bytes(
            file_id=file_id,
            max_bytes=settings.summary_max_source_bytes,
        )

        # Preserve graceful metadata fallback for unsupported binary formats.
        try:
            self._rag_pipeline.ensure_index(
                file_id=file_id,
                file_name=metadata.file_name,
                content_type=metadata.content_type,
                file_bytes=file_bytes,
            )
            result = self._rag_pipeline.summarize_file(file_id=file_id)
            return metadata, result.answer, result.source
        except InvalidFileTypeError:
            summary_text, summary_source = await self._summariser.summarise(
                file_bytes=file_bytes,
                file_name=metadata.file_name,
                content_type=metadata.content_type,
                size_bytes=metadata.size_bytes,
            )
            return metadata, summary_text, summary_source
        except Exception as exc:
            logger.exception("RAG summary failed for file_id=%s", file_id)
            if settings.hf_api_token:
                raise RetrievalError(f"RAG summary failed: {exc}") from exc
            # Graceful degradation keeps summary endpoint useful even if vector
            # indexing or retrieval infrastructure is temporarily unavailable.
            summary_text, summary_source = await self._summariser.summarise(
                file_bytes=file_bytes,
                file_name=metadata.file_name,
                content_type=metadata.content_type,
                size_bytes=metadata.size_bytes,
            )
            return metadata, summary_text, summary_source

    async def _prepare_rag_index(self, metadata: FileMetadata) -> None:
        """Build vector index at upload time for supported files.

        This keeps /summary fast and makes RAG readiness explicit.
        """
        file_bytes = await self._storage.read_file_bytes(
            file_id=metadata.file_id,
            max_bytes=settings.summary_max_source_bytes,
        )
        try:
            self._rag_pipeline.ensure_index(
                file_id=metadata.file_id,
                file_name=metadata.file_name,
                content_type=metadata.content_type,
                file_bytes=file_bytes,
            )
        except InvalidFileTypeError:
            # Unsupported file types are still valid uploads; summary endpoint
            # will use metadata/extractive fallback as needed.
            return
        except Exception as exc:
            logger.exception("RAG indexing failed for uploaded file_id=%s", metadata.file_id)
            if settings.hf_api_token:
                raise EmbeddingGenerationError(
                    f"Failed to index uploaded file for RAG: {exc}"
                ) from exc
