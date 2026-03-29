"""
Summarisation service.

Provides an LLM-backed summariser with chunking and graceful fallbacks.
"""
from __future__ import annotations

import logging
from typing import Protocol, Tuple

import httpx

from app.config import settings
from app.exceptions import SummaryGenerationError
from app.file_types import is_pdf_file, is_text_file

logger = logging.getLogger(__name__)

_HF_API_URL = "https://api-inference.huggingface.co/models/{model}"


class SummariserProtocol(Protocol):
    async def summarise(
        self,
        file_bytes: bytes,
        file_name: str,
        content_type: str,
        size_bytes: int,
    ) -> Tuple[str, str]:
        ...


class HuggingFaceSummariser:
    """LLM summariser with chunking and extractive fallback."""

    async def summarise(
        self,
        file_bytes: bytes,
        file_name: str,
        content_type: str,
        size_bytes: int,
    ) -> Tuple[str, str]:
        if is_pdf_file(file_name=file_name, content_type=content_type):
            text = _extract_pdf_text(file_bytes)
            if text:
                return await self._summarise_text(text, file_name)
            return _metadata_summary(file_name, content_type, size_bytes), "metadata"

        if is_text_file(file_name=file_name, content_type=content_type):
            text = _decode_text(file_bytes)
            if text.strip():
                return await self._summarise_text(text, file_name)

        return _metadata_summary(file_name, content_type, size_bytes), "metadata"

    async def _summarise_text(self, text: str, file_name: str) -> Tuple[str, str]:
        if not settings.hf_api_token:
            return _extractive_summary(text), "extractive"

        try:
            chunks = _chunk_text(
                text,
                chunk_size=settings.summary_chunk_chars,
                overlap=settings.summary_chunk_overlap_chars,
                max_chars=settings.summary_max_input_chars,
            )
            summaries = []
            for chunk in chunks:
                summaries.append(await _call_hf_inference_api(chunk))

            if len(summaries) == 1:
                logger.info("LLM summary generated for '%s'", file_name)
                return summaries[0], "llm"

            combined = "\n".join(summaries)
            final_summary = await _call_hf_inference_api(combined)
            logger.info("LLM summary generated for '%s' (chunked)", file_name)
            return final_summary, "llm"
        except Exception as exc:
            if settings.summary_strict_llm:
                raise SummaryGenerationError(str(exc)) from exc
            logger.warning(
                "HuggingFace API call failed for '%s': %s – falling back to extractive",
                file_name,
                exc,
            )
            return _extractive_summary(text), "extractive"


async def _call_hf_inference_api(text: str) -> str:
    url = _HF_API_URL.format(model=settings.hf_model)
    headers = {"Authorization": f"Bearer {settings.hf_api_token}"}
    payload = {
        "inputs": text,
        "parameters": {
            "max_length": settings.summary_max_output_tokens,
            "min_length": settings.summary_min_output_tokens,
            "do_sample": False,
        },
        "options": {"wait_for_model": True},
    }

    async with httpx.AsyncClient(timeout=settings.hf_timeout_seconds) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()

    result = response.json()
    if isinstance(result, list) and result:
        return result[0].get("summary_text", "")

    raise SummaryGenerationError(f"Unexpected API response format: {result}")


def _extract_pdf_text(file_bytes: bytes) -> str:
    try:
        import io
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for page in reader.pages:
            pages_text.append(page.extract_text() or "")
        return "\n".join(pages_text).strip()
    except ImportError:
        logger.warning("pypdf not installed – PDF text extraction unavailable")
        return ""
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return ""


def _decode_text(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _chunk_text(text: str, chunk_size: int, overlap: int, max_chars: int) -> list[str]:
    trimmed = text[:max_chars]
    if len(trimmed) <= chunk_size:
        return [trimmed]

    if overlap >= chunk_size:
        overlap = 0

    chunks = []
    start = 0
    while start < len(trimmed):
        end = min(start + chunk_size, len(trimmed))
        chunks.append(trimmed[start:end])
        start = end - overlap
        if start < 0:
            start = 0
        if end == len(trimmed):
            break
    return chunks


def _extractive_summary(text: str) -> str:
    words = text.split()
    extract = " ".join(words[:settings.summary_extractive_words])
    if len(words) > settings.summary_extractive_words:
        extract += " …"
    note = (
        "[Extractive summary – set HF_API_TOKEN in .env for full LLM summarisation] "
    )
    return note + extract


def _metadata_summary(file_name: str, content_type: str, size_bytes: int) -> str:
    size_str = _human_readable_size(size_bytes)
    return (
        f"This is a binary file named '{file_name}' "
        f"of type '{content_type}' with a size of {size_str}. "
        "Automatic text summarisation is not available for this file type."
    )

def _human_readable_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def build_summariser() -> HuggingFaceSummariser:
    return HuggingFaceSummariser()
