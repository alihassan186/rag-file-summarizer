from __future__ import annotations

from app.config import settings
from app.exceptions import EmbeddingGenerationError, InvalidFileTypeError, RetrievalError
from app.rag.generation import RagGenerator
from app.rag.ingestion import DocumentIngestion
from app.rag.types import RagResult, RetrievedChunk
from app.rag.vector_store import VectorStoreManager


class RagPipeline:
    """Coordinates ingestion, indexing, retrieval, and generation per file."""

    def __init__(self, ingestion: DocumentIngestion, vector_store: VectorStoreManager, generator: RagGenerator) -> None:
        self._ingestion = ingestion
        self._vector_store = vector_store
        self._generator = generator

    def ensure_index(self, file_id: str, file_name: str, content_type: str, file_bytes: bytes) -> None:
        if self._vector_store.has_index(file_id):
            return

        try:
            text = self._ingestion.extract_text(file_bytes=file_bytes, file_name=file_name, content_type=content_type)
            chunks = self._ingestion.chunk_text(text)
            self._vector_store.build_index(file_id=file_id, chunks=chunks, file_name=file_name)
        except ValueError as exc:
            if str(exc) == "unsupported_file_type":
                raise InvalidFileTypeError(file_name=file_name, content_type=content_type) from exc
            raise EmbeddingGenerationError(f"Failed to ingest file '{file_name}': {exc}") from exc
        except Exception as exc:
            raise EmbeddingGenerationError(f"Failed to create embeddings for file '{file_name}': {exc}") from exc

    def summarize_file(self, file_id: str) -> RagResult:
        try:
            matches = self._vector_store.search(file_id=file_id, query=settings.rag_summary_query, top_k=settings.rag_summary_top_k)
            filtered = [match for match in matches if match[1] <= settings.rag_max_distance]
            if not filtered:
                filtered = matches
            chunks = [
                RetrievedChunk(
                    text=doc.page_content,
                    score=float(score),
                    chunk_index=int(doc.metadata.get("chunk_index", -1)),
                )
                for doc, score in filtered
            ]
            answer, source = self._generator.generate_summary(chunk.text for chunk in chunks)
            return RagResult(answer=answer, retrieved_chunks=chunks, source=source)
        except Exception as exc:
            raise RetrievalError(f"Summary retrieval failed: {exc}") from exc

    def answer_question(self, file_id: str, question: str) -> RagResult:
        try:
            matches = self._vector_store.search(file_id=file_id, query=question, top_k=settings.rag_question_top_k)
            filtered = [match for match in matches if match[1] <= settings.rag_max_distance]
            if not filtered:
                filtered = matches
            chunks = [
                RetrievedChunk(
                    text=doc.page_content,
                    score=float(score),
                    chunk_index=int(doc.metadata.get("chunk_index", -1)),
                )
                for doc, score in filtered
            ]
            answer, source = self._generator.answer_question(question=question, contexts=(chunk.text for chunk in chunks))
            return RagResult(answer=answer, retrieved_chunks=chunks, source=source)
        except Exception as exc:
            raise RetrievalError(f"Question retrieval failed: {exc}") from exc


def build_rag_pipeline() -> RagPipeline:
    ingestion = DocumentIngestion(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )
    vector_store = VectorStoreManager(
        vector_dir=settings.vector_store_dir,
        embedding_model=settings.rag_embedding_model,
    )
    generator = RagGenerator()
    return RagPipeline(ingestion=ingestion, vector_store=vector_store, generator=generator)
