"""Shared file-type classification helpers used by ingestion and summaries."""
from __future__ import annotations

from pathlib import Path

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".py",
    ".js",
    ".ts",
    ".yaml",
    ".yml",
    ".log",
    ".ini",
    ".cfg",
}

PDF_EXTENSIONS = {".pdf"}


def get_extension(file_name: str) -> str:
    return Path(file_name).suffix.lower()


def is_pdf_file(file_name: str, content_type: str) -> bool:
    return get_extension(file_name) in PDF_EXTENSIONS or content_type == "application/pdf"


def is_text_file(file_name: str, content_type: str) -> bool:
    return get_extension(file_name) in TEXT_EXTENSIONS or content_type.startswith("text/")
