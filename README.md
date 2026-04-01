# ResMed File Sharing API

A production-oriented FastAPI service for uploading, listing, downloading, and summarizing files.

The project combines:

- Reliable file storage (local disk + SQLite metadata)
- Retrieval-Augmented Generation (RAG) for document summaries
- Graceful fallbacks when remote model inference is unavailable
- Containerized deployment with Docker and docker-compose

## Table of Contents

- [Overview](#overview)
- [Core Capabilities](#core-capabilities)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Summarization and Fallback Strategy](#summarization-and-fallback-strategy)
- [Running Tests](#running-tests)
- [Docker Deployment](#docker-deployment)
- [Troubleshooting](#troubleshooting)

## Overview

This API exposes four file endpoints plus a health endpoint:

- `POST /files/` to upload a file
- `GET /files/` to list metadata for uploaded files
- `GET /files/{file_id}` to download a file stream
- `GET /files/{file_id}/summary` to generate a summary
- `GET /health` for runtime health checks

The summary endpoint is designed to stay useful under degraded conditions.
If full RAG cannot run, the service falls back to extractive or metadata summaries depending on file type and available configuration.

## Core Capabilities

1. File lifecycle management
- Upload files through multipart form data
- Persist metadata in SQLite
- Stream downloads with proper content headers

2. RAG-based summaries
- Extract text from PDF and text-like files
- Chunk content and build per-file FAISS indexes
- Retrieve top relevant chunks and generate model-based summary

3. Graceful degradation
- If HF token is not configured, falls back to local extractive summary
- If file type is unsupported for text extraction, returns metadata summary
- If generation/retrieval fails, applies fallback path instead of hard failure where possible

4. Production readiness
- Structured domain exceptions and consistent error responses
- Async file and database operations
- Multi-stage Docker build with non-root runtime user

## Architecture

High-level request flow:

![System Flow Diagram](doc/ResMed-2026-04-01-212006.png)

1. Router receives request (`app/routers/files.py`)
2. Service layer orchestrates operations (`app/services/files_service.py`)
3. Storage layer handles bytes + metadata (`app/storage.py`)
4. RAG pipeline handles indexing/retrieval/generation (`app/rag/`)
5. Fallback summarizer handles degraded paths (`app/summariser.py`)

### RAG Indexing Lifecycle (Technical)

RAG indexing is triggered in two places:

1. Upload path (eager indexing):
- `FileService.upload_file()` calls `_prepare_rag_index()` immediately after a successful save.
- `_prepare_rag_index()` reads file bytes and calls `RagPipeline.ensure_index(...)`.

2. Summary path (lazy safety check):
- `FileService.summarise_file()` also calls `RagPipeline.ensure_index(...)` before retrieval.
- If index is already present and compatible, `ensure_index(...)` returns quickly.

Implementation sequence inside `RagPipeline.ensure_index(...)`:

1. `DocumentIngestion.extract_text(...)` converts source bytes into text for supported types.
2. `DocumentIngestion.chunk_text(...)` splits text into chunks using `RecursiveCharacterTextSplitter`.
3. `VectorStoreManager.build_index(...)` converts chunks into embeddings and builds FAISS.
4. `FAISS.save_local(...)` persists index artifacts to disk.

On-disk index layout:

- `data/vector_indexes/<file_id>/index.faiss`
- `data/vector_indexes/<file_id>/index.pkl`
- `data/vector_indexes/<file_id>/meta.json`

### Summary Pipeline (GET `/files/{file_id}/summary`)

1. Load metadata and file bytes
2. Ensure vector index exists (build if missing)
3. Retrieve relevant chunks via FAISS
4. Generate summary with Hugging Face Inference API
5. If needed, fallback to extractive summary or metadata summary

## Tech Stack

- Python 3.12
- FastAPI + Uvicorn
- Pydantic v2 + pydantic-settings
- aiofiles + aiosqlite
- LangChain + FAISS (CPU)
- huggingface_hub InferenceClient
- pypdf
- pytest + pytest-asyncio + httpx
- Docker + docker-compose

## Project Structure

```text
.
├── app/
│   ├── main.py                  # FastAPI app factory, middleware, exception wiring
│   ├── config.py                # Runtime settings from environment
│   ├── deps.py                  # Dependency injection factories
│   ├── exceptions.py            # Domain exceptions + JSON handlers
│   ├── models.py                # API contracts
│   ├── storage.py               # Local disk + SQLite storage implementation
│   ├── summariser.py            # LLM + extractive + metadata fallback summarizer
│   ├── routers/
│   │   └── files.py             # File API endpoints
│   ├── services/
│   │   └── files_service.py     # Application service orchestration
│   └── rag/
│       ├── ingestion.py         # File text extraction and chunking
│       ├── vector_store.py      # FAISS index build/search per file
│       ├── generation.py        # Prompting + generation fallback logic
│       ├── pipeline.py          # End-to-end RAG orchestration
│       └── types.py             # RAG result dataclasses
├── tests/
│   ├── conftest.py              # Isolated async test client fixtures
│   └── test_files.py            # Integration tests for all endpoints
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.12+ or Docker
- Optional but recommended: Hugging Face API token

Without `HF_API_TOKEN`, the app still works and will return extractive summaries for text/PDF where possible.

### Local Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` in the project root:

```env
HF_API_TOKEN=
DEBUG=false
```

Run the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open API docs:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Configuration

Settings are defined in `app/config.py` and can be overridden with environment variables.

### Important Variables

Storage and limits:

- `UPLOAD_DIR` (default: `uploads`)
- `DB_PATH` (default: `data/metadata.db`)
- `VECTOR_STORE_DIR` (default: `data/vector_indexes`)
- `MAX_FILE_SIZE_BYTES` (default: 20971520)

Hugging Face and summary behavior:

- `HF_API_TOKEN` (default: empty)
- `HF_MODEL` (default: `facebook/bart-large-cnn`)
- `HF_TIMEOUT_SECONDS` (default: 60)
- `SUMMARY_MAX_INPUT_CHARS` (default: 3000)
- `SUMMARY_MAX_OUTPUT_TOKENS` (default: 150)
- `SUMMARY_MIN_OUTPUT_TOKENS` (default: 40)
- `SUMMARY_STRICT_LLM` (default: false)

RAG configuration:

- `RAG_EMBEDDING_MODEL` (default: `sentence-transformers/all-mpnet-base-v2`)
- `RAG_GENERATION_MODEL` (default: `google/flan-t5-base`)
- `RAG_CHUNK_SIZE` (default: 900)
- `RAG_CHUNK_OVERLAP` (default: 120)
- `RAG_SUMMARY_TOP_K` (default: 10)
- `RAG_MAX_DISTANCE` (default: 1.4)
- `RAG_GENERATION_MAX_TOKENS` (default: 320)

Application metadata:

- `APP_TITLE` (default: `ResMed File Sharing API`)
- `APP_VERSION` (default: `1.0.0`)
- `DEBUG` (default: false)

## API Reference

Base URL examples assume `http://127.0.0.1:8000`.

### Health

`GET /health`

Response:

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### Upload File

`POST /files/`

Request (multipart form-data):

```bash
curl -X POST http://127.0.0.1:8000/files/ \
  -F "file=@notes.txt"
```

Success response (`201`):

```json
{
  "file_id": "uuid",
  "file_name": "notes.txt",
  "size_bytes": 1234,
  "uploaded_at": "2026-04-01T12:00:00+00:00",
  "message": "File uploaded successfully"
}
```

Indexing behavior after upload:

- For supported files, the service attempts to build a per-file FAISS index right after storing metadata.
- For unsupported file types, upload still succeeds; RAG indexing is skipped and summary falls back later.
- If `HF_API_TOKEN` is not configured, RAG embeddings are disabled and summary uses fallback behavior.

### List Files

`GET /files/`

Success response (`200`):

```json
{
  "total": 1,
  "files": [
    {
      "file_id": "uuid",
      "file_name": "notes.txt",
      "size_bytes": 1234,
      "uploaded_at": "2026-04-01T12:00:00+00:00",
      "content_type": "text/plain"
    }
  ]
}
```

### Download File

`GET /files/{file_id}`

```bash
curl http://127.0.0.1:8000/files/<file_id> --output downloaded.bin
```

Returns binary stream with `Content-Disposition` and `Content-Length` headers.

### Get Summary

`GET /files/{file_id}/summary`

Success response (`200`):

```json
{
  "file_id": "uuid",
  "file_name": "notes.txt",
  "content_type": "text/plain",
  "size_bytes": 1234,
  "summary": "...",
  "summary_source": "rag"
}
```

`summary_source` is one of:

- `rag` for successful RAG generation
- `llm` for direct non-RAG Hugging Face summarization path
- `extractive` for local extractive fallback
- `metadata` for unsupported/binary file fallback

### Error Envelope

All domain errors follow this format:

```json
{
  "error": "machine_readable_code",
  "message": "Human-readable message",
  "detail": "Optional detail"
}
```

Common status codes:

- `400` empty upload
- `404` missing file
- `413` upload too large
- `415` unsupported media type for RAG ingestion
- `422` validation errors (e.g. malformed UUID)
- `500` storage/embedding failures
- `502` retrieval/generation downstream failures

## Summarization and Fallback Strategy

The service intentionally supports multiple summarization modes.

### Primary Path

1. Ingest text from file (`pdf` or text-like content)
2. Build/load file-scoped FAISS index
3. Retrieve top relevant chunks
4. Generate concise answer via Hugging Face model

### Chunking and FAISS Details

- Chunking implementation: `app/rag/ingestion.py` via `RecursiveCharacterTextSplitter`.
- Chunk config keys: `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`.
- FAISS build/persist: `app/rag/vector_store.py` (`FAISS.from_documents(...)` + `save_local(...)`).
- Retrieval call: `VectorStoreManager.search(...)` using `similarity_search_with_score(...)`.
- Index compatibility check: `meta.json` stores embedding model; incompatible indexes are rebuilt.

### Fallback Paths

1. If RAG ingestion is unsupported for file type:
- Use `HuggingFaceSummariser` directly (`llm`, `extractive`, or `metadata`)

2. If RAG runtime fails:
- With token configured, propagate retrieval/generation failure (`502`)
- Without token, degrade to local summarizer fallback

3. If direct Hugging Face summarization fails:
- Return extractive summary unless `SUMMARY_STRICT_LLM=true`

4. If content is binary/unsupported:
- Return metadata-based summary

## Running Tests

Run full test suite:

```bash
pytest -q
```

Verbose mode:

```bash
pytest -v
```

The tests use isolated temporary directories and disable Hugging Face access by default.

## Docker Deployment

### docker-compose

```bash
docker compose up --build
```

Service exposure:

- API on `8000`
- Persistent named volumes for uploads and metadata/index data

### Dockerfile Notes

- Multi-stage build for reduced runtime image size
- Non-root runtime user (`appuser`)
- Built-in healthcheck on `/health`

## Troubleshooting

### `413 Payload Too Large`

- Increase `MAX_FILE_SIZE_BYTES` in environment
- Restart service

### Summary returns extractive output unexpectedly

- Confirm `HF_API_TOKEN` is set
- Check outbound network access to Hugging Face
- Inspect logs for model/API errors

### Summary returns metadata output

- File is likely binary or unsupported for text extraction
- Use text or PDF input for richer summarization

### Vector index errors after model change

- Delete file-specific index directory under `data/vector_indexes/<file_id>`
- Re-trigger summary to rebuild index with current embedding model

## Notes

- This repository currently exposes file operations and summarization APIs.
- The RAG pipeline module also includes an internal question-answering capability not currently exposed as an HTTP endpoint.
