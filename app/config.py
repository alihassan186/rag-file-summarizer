"""
Application configuration.

All values can be overridden via environment variables or a .env file.
Example:  HF_API_TOKEN=hf_xxx  MAX_FILE_SIZE_BYTES=5242880
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object.  Loaded once at startup and injected wherever needed."""

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    # ── Storage ──────────────────────────────────────────────────────────────
    upload_dir: Path = Path("uploads")
    db_path: Path = Path("data/metadata.db")
    vector_store_dir: Path = Path("data/vector_indexes")
    max_file_size_bytes: int = 20 * 1024 * 1024  # 20 MB
    upload_chunk_size_bytes: int = 1024 * 1024   # 1 MB
    download_chunk_size_bytes: int = 1024 * 1024

    # ── LLM / Summarisation ───────────────────────────────────────────────────
    hf_api_token: str = ""                              # Free HuggingFace token
    hf_model: str = "facebook/bart-large-cnn"           # Free summarisation model
    summary_max_input_chars: int = 3_000                # Chars fed to the model
    summary_chunk_chars: int = 2_000
    summary_chunk_overlap_chars: int = 200
    summary_extractive_words: int = 60
    summary_strict_llm: bool = False
    summary_max_source_bytes: int = 2 * 1024 * 1024      # 2 MB of source text max
    summary_max_output_tokens: int = 150
    summary_min_output_tokens: int = 40
    hf_timeout_seconds: float = 60.0

    # ── RAG pipeline ──────────────────────────────────────────────────────────
    rag_chunk_size: int = 900
    rag_chunk_overlap: int = 120
    rag_embedding_model: str = "sentence-transformers/all-mpnet-base-v2"
    rag_generation_model: str = "distilgpt2"
    rag_summary_query: str = (
        "Provide the most important concepts, definitions, and conclusions "
        "from this document"
    )
    rag_summary_top_k: int = 10
    rag_question_top_k: int = 5
    rag_max_distance: float = 1.4
    rag_generation_max_tokens: int = 320

    # ── Application ──────────────────────────────────────────────────────────
    app_title: str = "ResMed File Sharing API"
    app_version: str = "1.0.0"
    debug: bool = False


# Single shared instance – import this everywhere instead of re-instantiating.
settings = Settings()
