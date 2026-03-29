# ResMed File Sharing API with Intelligent RAG-Powered Summarization

A production-grade file management and intelligent summarization service built with FastAPI and Retrieval-Augmented Generation (RAG). Designed for educational document management with automatic intelligent summaries powered by free, open-source AI models.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Overview

ResMed File Sharing API provides a secure, scalable file management system with built-in intelligent summarization capabilities. It implements a complete REST API for:

- **File Management**: Upload, download, and list files with automatic metadata tracking
- **Intelligent Summarization**: Automatic document summaries powered by RAG (Retrieval-Augmented Generation)
- **Multi-format Support**: Text files (.txt) and PDF documents (.pdf)
- **Robust Error Handling**: Structured error responses with actionable error codes
- **Production Ready**: Docker containerization, comprehensive testing, and monitoring endpoints

## Features

✅ **RESTful File API**
- Upload files with automatic unique ID generation
- Download files with streaming support
- List all uploaded files with metadata
- Vector-based document search and retrieval

✅ **RAG-Powered Summarization**
- Intelligent document understanding using modern language models
- Automatic chunking and semantic search
- Multi-step fallback pipeline for reliability
- Section-aware extraction for structured documents

✅ **Production Features**
- Async/await throughout for high performance
- Structured error handling with consistent error contracts
- SQLite metadata storage with persisted state
- Local FAISS vector indexes for semantic search
- Docker containerization for easy deployment
- Comprehensive test coverage with 15+ test scenarios

✅ **Developer Friendly**
- Automatic API documentation via Swagger UI
- Clear separation of concerns with layered architecture
- Type hints throughout (Python 3.12+)
- Environment-based configuration
- Pre-built docker-compose setup

## Prerequisites

- **Python 3.12+** or **Docker** (recommended)
- **Hugging Face API Token** (free tier): [Get token](https://huggingface.co/settings/tokens)
- **4GB RAM** minimum (for embeddings model)
- **500MB disk space** for vector indexes and uploads

## Quick Start

### Using Docker (Recommended)

```bash
# 1. Clone the repository
git clone <repository-url>
cd <project-directory>

# 2. Create .env file with your Hugging Face token
echo "HF_API_TOKEN=hf_your_token_here" > .env

# 3. Start the service
docker compose up --build

# 4. Test the API
curl -X POST http://127.0.0.1:8000/files/ \
  -F "file=@/path/to/document.pdf"
```

Visit [API Documentation](http://127.0.0.1:8000/docs) to explore interactive endpoints.

### Local Development

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
export HF_API_TOKEN=hf_your_token_here

# 4. Run the server
python -m app.main
```

## Installation

### From Source

```bash
# Clone repository
git clone git@github.com:alihassan186/intelligent-doc-hub.git
cd <project-directory>

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify installation
pytest -q
```

### Docker Installation

```bash
# Build image
docker build -t resmed-api .

# Run container
docker run -it \
  -e HF_API_TOKEN=hf_your_token \
  -p 8000:8000 \
  -v uploads:/app/uploads \
  -v data:/app/data \
  resmed-api
```

## Usage

### Upload a File

```bash
curl -X POST http://127.0.0.1:8000/files/ \
  -F "file=@lecture-notes.pdf"
```

**Response (201 Created):**
```json
{
  "file_id": "3c384f6d-cffd-460f-8e06-77c2b102baac",
  "file_name": "lecture-notes.pdf",
  "size_bytes": 463266,
  "uploaded_at": "2026-03-29T11:35:22.123456+00:00",
  "message": "File uploaded successfully"
}
```

### List All Files

```bash
curl http://127.0.0.1:8000/files/
```

**Response (200 OK):**
```json
{
  "total": 1,
  "files": [
    {
      "file_id": "3c384f6d-cffd-460f-8e06-77c2b102baac",
      "file_name": "lecture-notes.pdf",
      "size_bytes": 463266,
      "uploaded_at": "2026-03-29T11:35:22.123456+00:00",
      "content_type": "application/pdf"
    }
  ]
}
```

### Download a File

```bash
curl http://127.0.0.1:8000/files/3c384f6d-cffd-460f-8e06-77c2b102baac \
  --output downloaded-notes.pdf
```

### Generate Summary

```bash
curl http://127.0.0.1:8000/files/3c384f6d-cffd-460f-8e06-77c2b102baac/summary
```

**Response (200 OK):**
```json
{
  "file_id": "3c384f6d-cffd-460f-8e06-77c2b102baac",
  "file_name": "lecture-notes.pdf",
  "content_type": "application/pdf",
  "size_bytes": 463266,
  "summary": "- Key topic A\n- Key topic B\n- Key topic C",
  "summary_source": "rag"
}
```

## API Reference

### File Management Endpoints

#### POST `/files/`

Upload a new file to the system.

**Parameters:**
- `file` (FormData, required): Binary file content (max 20MB)

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/files/ \
  -F "file=@document.pdf"
```

**Response (201 Created):**
```json
{
  "file_id": "uuid",
  "file_name": "document.pdf",
  "size_bytes": 123456,
  "uploaded_at": "2026-03-29T11:35:22.123456+00:00",
  "message": "File uploaded successfully"
}
```

**Error Responses:**
- `400 Bad Request`: No file provided
- `413 Payload Too Large`: File exceeds 20MB limit
- `500 Internal Server Error`: Storage or indexing failed

---

#### GET `/files/`

List all uploaded files with pagination support.

**Query Parameters:**
- `skip` (integer, default: 0): Pagination offset
- `limit` (integer, default: 100): Maximum results to return

**Request:**
```bash
curl "http://127.0.0.1:8000/files/?skip=0&limit=10"
```

**Response (200 OK):**
```json
{
  "total": 42,
  "files": [
    {
      "file_id": "uuid",
      "file_name": "lecture-notes.pdf",
      "size_bytes": 463266,
      "uploaded_at": "2026-03-29T11:35:22.123456+00:00",
      "content_type": "application/pdf"
    }
  ],
  "skip": 0,
  "limit": 10
}
```

---

#### GET `/files/{file_id}`

Download a file by ID with streaming support.

**Path Parameters:**
- `file_id` (string, required): Unique file identifier

**Request:**
```bash
curl http://127.0.0.1:8000/files/3c384f6d-cffd-460f-8e06-77c2b102baac \
  --output downloaded.pdf
```

**Response (200 OK):**
- Binary file content with appropriate `Content-Type` and `Content-Disposition` headers

**Error Responses:**
- `404 Not Found`: File ID does not exist

---

#### GET `/files/{file_id}/summary`

Generate an intelligent summary of a file using RAG pipeline.

**Path Parameters:**
- `file_id` (string, required): Unique file identifier

**Request:**
```bash
curl http://127.0.0.1:8000/files/3c384f6d-cffd-460f-8e06-77c2b102baac/summary
```

**Response (200 OK):**
```json
{
  "file_id": "3c384f6d-cffd-460f-8e06-77c2b102baac",
  "file_name": "lecture-notes.pdf",
  "content_type": "application/pdf",
  "size_bytes": 463266,
  "summary": "Structured bullet-point summary of key topics",
  "summary_source": "rag"
}
```

**Response (200 OK) - Fallback Mode:**
```json
{
  "file_id": "3c384f6d-cffd-460f-8e06-77c2b102baac",
  "file_name": "presentation.pptx",
  "content_type": "application/vnd.ms-powerpoint",
  "size_bytes": 1234567,
  "summary": "File metadata summary (format not supported for full RAG)",
  "summary_source": "metadata"
}
```

**Error Responses:**
- `404 Not Found`: File ID does not exist
- `500 Internal Server Error`: Summarization pipeline failed

---

### Error Response Format

All error responses follow a consistent structure:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "detail": "Additional context or debugging information"
}
```

**Common Error Codes:**
- `file_not_found`: Requested file does not exist
- `file_too_large`: Uploaded file exceeds size limit
- `invalid_file_type`: File format not supported
- `storage_error`: Failed to store file
- `retrieval_error`: RAG pipeline retrieval failed
- `generation_error`: Summary generation failed
- `embedding_error`: Vector embedding generation failed



## Architecture

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                         Client Layer                              │
│                  (Swagger UI / cURL / SDK)                        │
└────────────────────────┬─────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────┐
│                      FastAPI Router                               │
│            (Automatic OpenAPI documentation)                      │
└────────────────────────┬─────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────┐
│                   Service Layer (Orchestration)                   │
│                      FileService                                  │
└──────────┬──────────────────────────────────────────┬─────────────┘
           │                                          │
    ┌──────▼──────────┐                    ┌──────────▼──────────┐
    │ Storage Layer   │                    │ RAG Pipeline        │
    ├─────────────────┤                    ├────────────────────┤
    │ Local Disk I/O  │                    │ 1. Ingestion       │
    │ SQLite DB       │                    │    - PDF extraction │
    │ - File bytes    │                    │    - Text parsing   │
    │ - Metadata      │                    │                    │
    │ - Type info     │                    │ 2. Chunking        │
    │                 │                    │    - Token aware    │
    │                 │                    │    - Context aware  │
    └─────────────────┘                    │                    │
                                           │ 3. Embeddings      │
                                           │    - HF Inference   │
                                           │    - all-mpnet-v2   │
                                           │                    │
                                           │ 4. Vector Store    │
                                           │    - FAISS (CPU)    │
                                           │    - Local indexes  │
                                           │                    │
                                           │ 5. Generation      │
                                           │    - text_generation│
                                           │    - flan-t5-base   │
                                           │    - Fallback logic │
                                           │                    │
                                           │ 6. Fallback        │
                                           │    - Extractive    │
                                           │    - Section-aware  │
                                           └────────────────────┘
```

### Data Flow for Summary Generation

```
User Request (GET /files/{file_id}/summary)
    │
    ├─→ [1] Load file metadata from SQLite
    │   └─→ Verify file exists
    │
    ├─→ [2] Ensure vector index exists
    │   ├─→ Check FAISS index compatibility
    │   └─→ Rebuild if embedding model changed
    │
    ├─→ [3] Retrieve relevant chunks
    │   ├─→ Query FAISS for top-k similar chunks
    │   ├─→ Filter by relevance threshold
    │   └─→ Return top chunks for context
    │
    ├─→ [4] Generate summary
    │   ├─→ Format context with prompt
    │   ├─→ Call HF text_generation endpoint
    │   └─→ Retry with shrinking payloads if needed
    │
    ├─→ [5] Fallback paths (if generation fails)
    │   ├─→ Try HF summarization task
    │   ├─→ Extractive bullet-point summary
    │   └─→ Return metadata fallback
    │
    └─→ Return JSON response with summary + source
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | FastAPI 0.115+ | High-performance async web framework |
| **Server** | Uvicorn 0.32+ | ASGI application server |
| **Language** | Python 3.12+ | Modern Python with type hints |
| **Database** | SQLite + aiosqlite | Lightweight async metadata store |
| **File I/O** | aiofiles | Non-blocking file operations |
| **Vector Search** | FAISS (CPU) | Efficient semantic search |
| **LLM Client** | huggingface_hub | Free HF Inference API client |
| **Embeddings** | sentence-transformers | Semantic vector generation |
| **PDF Processing** | pypdf | Cross-platform PDF parsing |
| **Validation** | Pydantic v2 | Type-safe request/response validation |
| **Testing** | pytest + pytest-asyncio | Comprehensive test coverage |
| **Container** | Docker | Production deployment |
| **Orchestration** | docker-compose | Local development stack |

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Hugging Face API Token (get from https://huggingface.co/settings/tokens)
HF_API_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxx

# RAG Configuration
RAG_EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
RAG_GENERATION_MODEL=google/flan-t5-base
RAG_SUMMARY_TOP_K=10
RAG_GENERATION_MAX_TOKENS=320

# Server Configuration
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Storage Configuration
MAX_UPLOAD_SIZE_MB=20
STORAGE_PATH=/app/data
UPLOADS_PATH=/app/uploads
```

### Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_API_TOKEN` | N/A | **Required**. Hugging Face API token for inference |
| `RAG_EMBEDDING_MODEL` | sentence-transformers/all-mpnet-base-v2 | HF model for semantic embeddings |
| `RAG_GENERATION_MODEL` | google/flan-t5-base | HF model for text generation |
| `RAG_SUMMARY_TOP_K` | 10 | Number of chunks to retrieve for context |
| `RAG_GENERATION_MAX_TOKENS` | 320 | Maximum tokens in generated summary |
| `DEBUG` | false | Enable verbose logging and debug endpoints |
| `HOST` | 0.0.0.0 | Server bind address |
| `PORT` | 8000 | Server port |
| `MAX_UPLOAD_SIZE_MB` | 20 | Maximum upload file size |

### Storage Paths

The system uses the following directory structure:

```
project_root/
├── uploads/                    # Raw uploaded file bytes
│   └── {file_id}              # One file per ID
├── data/
│   ├── metadata.db            # SQLite metadata store
│   └── vector_indexes/        # FAISS vector indexes
│       └── {file_id}/
│           ├── index.faiss    # Binary FAISS index
│           ├── index.pkl      # Pickle serialized index
│           └── meta.json      # Metadata & model info
```

All paths are configurable via environment variables and persist across container restarts.

## Deployment

### Docker Deployment

The project includes a production-grade Dockerfile with multi-stage build:

```bash
# Build and run with docker-compose
docker compose up --build

# Or build manually
docker build -t resmed-api .
docker run -d \
  --name resmed-api \
  -p 8000:8000 \
  -e HF_API_TOKEN=hf_xxx \
  -v uploads:/app/uploads \
  -v data:/app/data \
  resmed-api
```

### Production Checklist

- [ ] Rotate HF_API_TOKEN from .env to CI/CD secret manager
- [ ] Enable DEBUG=false in production
- [ ] Configure persistent volumes for uploads/ and data/
- [ ] Set up log aggregation (e.g., ELK, Datadog)
- [ ] Enable HTTPS/TLS termination at load balancer
- [ ] Configure rate limiting for /files/ endpoint
- [ ] Set up alerting on /health endpoint
- [ ] Use container's built-in security context (non-root user)
- [ ] Enable database backups for metadata.db

### Health Check

The API includes a health endpoint for monitoring:

```bash
curl http://127.0.0.1:8000/health
# Response: {"status": "ok"}
```

## Testing

### Run All Tests

```bash
# Quick test run
pytest -q

# Verbose output with coverage
pytest -v --cov=app

# Run specific test file
pytest tests/test_files.py -v

# Run with markers
pytest -m "not slow" -v
```

### Test Coverage

The test suite includes 15+ test scenarios covering:

- ✅ File upload (valid file, oversized file, unique IDs)
- ✅ File listing (empty list, pagination, multiple files)
- ✅ File download (byte accuracy, content-type headers, 404)
- ✅ Summary generation (RAG mode, fallback mode, error handling)
- ✅ Metadata integrity (stored vs retrieved)
- ✅ Error contracts (structured error responses)
- ✅ Storage persistence (SQLite, FAISS indexes)

### Test Isolation

Tests use temporary directories and mocked HF tokens to ensure:
- No interference between test runs
- No external API dependencies
- Fast, repeatable test execution
- Safe cleanup after failure

```bash
# Run tests with verbose fixture output
pytest -v -s tests/test_files.py

# Run with custom temporary directory
TMPDIR=/tmp pytest tests/test_files.py
```

## Troubleshooting

### Common Issues

#### Issue: "File too large" error on upload

**Error:** `413 Payload Too Large` 

**Solution:**
```bash
# Check current limit in .env
grep MAX_UPLOAD_SIZE_MB .env

# Increase to 50MB
echo "MAX_UPLOAD_SIZE_MB=50" >> .env
docker compose restart
```

---

#### Issue: Summary generation times out

**Error:** `Response timeout from Hugging Face API`

**Solution:**
1. Verify HF_API_TOKEN is valid: https://huggingface.co/settings/tokens
2. Check HF service status: https://status.huggingface.co
3. Reduce RAG_SUMMARY_TOP_K (fewer chunks):
   ```env
   RAG_SUMMARY_TOP_K=5
   ```
4. Reduce RAG_GENERATION_MAX_TOKENS:
   ```env
   RAG_GENERATION_MAX_TOKENS=200
   ```

---

#### Issue: Vector index rebuild fails

**Error:** `Embedding generation failed`

**Solution:**
- Stale indexes are auto-detected and rebuilt on next summary request
- Force rebuild by deleting index:
  ```bash
  rm -rf data/vector_indexes/{file_id}
  ```
- Verify embedding model is available on HuggingFace:
  ```bash
  curl https://api-inference.huggingface.co/models/sentence-transformers/all-mpnet-base-v2 \
    -H "Authorization: Bearer $HF_API_TOKEN"
  ```

---

#### Issue: PDF parsing errors

**Error:** `Failed to extract text from PDF`

**Solution:**
1. Verify PDF is not corrupted:
   ```bash
   file your-document.pdf
   ```
2. Check if scanned PDF (requires OCR - not supported):
   - Use extracted text instead
   - Use online OCR service first
3. Check PDF version compatibility (pypdf supports most versions)

---

#### Issue: Swagger UI not loading

**Error:** `Cannot GET /docs`

**Solution:**
```bash
# Verify server is running
curl http://127.0.0.1:8000/health

# Check logs
docker logs resmed-api

# Restart service
docker compose restart api
```

---

### Debug Mode

Enable verbose logging:

```bash
# Set DEBUG environment variable
export DEBUG=true

# Restart service
docker compose restart

# View logs
docker compose logs -f api
```

Debug output includes:
- Full API request/response payloads
- RAG pipeline step timings
- Model loading events
- File I/O operations

## Repository Structure

```
project_root/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory & exception handlers
│   ├── config.py               # Pydantic Settings configuration
│   ├── deps.py                 # Dependency injection setup
│   ├── exceptions.py           # Domain exception definitions
│   ├── models.py               # Pydantic request/response models
│   ├── storage.py              # LocalDiskStorage implementation
│   ├── summariser.py           # Fallback summarization logic
│   ├── routers/
│   │   └── files.py            # 4 file management endpoints
│   ├── services/
│   │   └── files_service.py    # Orchestration layer
│   └── rag/
│       ├── __init__.py
│       ├── ingestion.py        # PDF/text extraction & chunking
│       ├── vector_store.py     # FAISS index management
│       ├── generation.py       # LLM summary generation
│       ├── pipeline.py         # RAG orchestration
│       └── types.py            # Type definitions
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # pytest fixtures
│   └── test_files.py           # 15+ integration tests
├── Dockerfile                  # Multi-stage production build
├── docker-compose.yml          # Local dev orchestration
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
└── README.md                   # This file
```

## Performance & Optimization

### Summary Generation Performance

- **Typical latency**: 2-8 seconds (depends on file size and HF API latency)
- **Vector search**: < 100ms (local FAISS)
- **Bottleneck**: Usually HF API response time (free tier ~3-5s)

### Optimization Tips

1. **Increase chunk retrieval efficiency:**
   ```env
   RAG_SUMMARY_TOP_K=5  # Fewer chunks = faster generation
   ```

2. **Reduce generation time:**
   ```env
   RAG_GENERATION_MAX_TOKENS=150  # Shorter summaries
   ```

3. **Cache vector indexes:**
   - Indexes persist in `data/vector_indexes/`
   - Reuse across requests (no re-embedding needed)

4. **Use smaller files for testing:**
   - PDF < 10MB recommended
   - Large files may timeout on free HF tier

## Contributing

### Development Setup

```bash

# Create feature branch
git checkout -b feature/your-feature

# Install dev dependencies
pip install -r requirements.txt
pip install pytest-cov black ruff mypy

# Run tests before committing
pytest -v

# Format code
black app/ tests/
ruff check app/ tests/

# Type check
mypy app/
```

### Pull Request Checklist

- [ ] Tests pass: `pytest -v`
- [ ] Code formatted: `black .`
- [ ] Lints pass: `ruff check .`
- [ ] Types validated: `mypy app/`
- [ ] Updated README if needed
- [ ] Descriptive commit message
- [ ] No credentials in code

### Reporting Issues

Use GitHub Issues with:
- Clear reproduction steps
- Expected vs actual behavior
- Python version and OS
- Relevant logs (with credentials redacted)

## License

This project is provided as-is for educational purposes. See LICENSE file for details.

## Support

- 📖 **Documentation**: See this README
- 💬 **Issues**: GitHub Issues
- 📧 **Email Support**: Available upon request
- 🔗 **Related Projects**: [FastAPI Docs](https://fastapi.tiangolo.com/), [LangChain](https://python.langchain.com/)
