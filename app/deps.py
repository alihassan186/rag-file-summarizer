"""Dependency wiring for FastAPI."""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from app.services.files_service import FileService
from app.rag.pipeline import RagPipeline, build_rag_pipeline
from app.storage import LocalDiskStorage, build_storage
from app.summariser import HuggingFaceSummariser, build_summariser


@lru_cache
def get_storage() -> LocalDiskStorage:
    return build_storage()


@lru_cache
def get_summariser() -> HuggingFaceSummariser:
    return build_summariser()


@lru_cache
def get_rag_pipeline() -> RagPipeline:
    return build_rag_pipeline()


def get_file_service(
    storage: LocalDiskStorage = Depends(get_storage),
    summariser: HuggingFaceSummariser = Depends(get_summariser),
    rag_pipeline: RagPipeline = Depends(get_rag_pipeline),
) -> FileService:
    return FileService(storage=storage, summariser=summariser, rag_pipeline=rag_pipeline)
