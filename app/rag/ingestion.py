from __future__ import annotations

import io
import logging

from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.file_types import is_pdf_file, is_text_file

logger = logging.getLogger(__name__)


class DocumentIngestion:
    """Converts raw files into clean text chunks ready for embedding."""

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
            is_separator_regex=False,
        )

    def extract_text(self, file_bytes: bytes, file_name: str, content_type: str) -> str:
        if is_pdf_file(file_name=file_name, content_type=content_type):
            text = self._extract_pdf_text(file_bytes)
            if text:
                return text
            raise ValueError("pdf_extraction_failed")

        if is_text_file(file_name=file_name, content_type=content_type):
            decoded = file_bytes.decode("utf-8", errors="replace").strip()
            if not decoded:
                raise ValueError("empty_text_after_decoding")
            return decoded

        raise ValueError("unsupported_file_type")

    def chunk_text(self, text: str) -> list[str]:
        chunks = [chunk.strip() for chunk in self._splitter.split_text(text) if chunk.strip()]
        if not chunks:
            raise ValueError("no_chunks_generated")
        return chunks

    @staticmethod
    def _extract_pdf_text(file_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(file_bytes))
            return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception as exc:  # pragma: no cover - parser edge cases vary by document
            logger.warning("PDF extraction failed: %s", exc)
            return ""
