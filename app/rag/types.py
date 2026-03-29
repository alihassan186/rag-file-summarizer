from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    """A single retrieved chunk with similarity distance metadata."""

    text: str
    score: float
    chunk_index: int


@dataclass(frozen=True)
class RagResult:
    """Structured RAG result returned by summary and QA generation."""

    answer: str
    retrieved_chunks: list[RetrievedChunk]
    source: str
