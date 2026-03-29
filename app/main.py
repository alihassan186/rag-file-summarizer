"""
Application factory.

Wires together:
  • FastAPI app with OpenAPI metadata
  • Lifespan context (DB init on startup)
  • Custom exception handlers
  • Structured request logging middleware
  • API router
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import (
    EmbeddingGenerationError,
    FileNotFoundError,
    FileStorageError,
    FileTooLargeError,
    InvalidFileTypeError,
    RetrievalError,
    SummaryGenerationError,
    embedding_error_handler,
    file_not_found_handler,
    file_too_large_handler,
    invalid_file_type_handler,
    retrieval_error_handler,
    storage_error_handler,
    summary_error_handler,
)
from app.routers.files import router as files_router
from app.deps import get_storage

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup / shutdown tasks.

    Startup:  initialise the SQLite database (create table if absent).
    Shutdown: nothing needed – aiosqlite connections are closed after each request.
    """
    logger.info("Starting %s v%s", settings.app_title, settings.app_version)
    storage = get_storage()
    await storage.init_db()
    yield
    logger.info("Shutting down")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        description=(
            "A lightweight file-sharing API that allows uploading, downloading, "
            "listing, and AI-powered summarisation of files. "
            "Built for ResMed's Cloud & AI Engineer take-home assignment."
        ),
        contact={"name": "Ali Hassan", "email": "alihasanuos@gmail.com"},
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request / response logging middleware ─────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s  →  %d  (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    # ── Exception handlers ────────────────────────────────────────────────────
    app.add_exception_handler(FileNotFoundError, file_not_found_handler)
    app.add_exception_handler(FileTooLargeError, file_too_large_handler)
    app.add_exception_handler(FileStorageError, storage_error_handler)
    app.add_exception_handler(SummaryGenerationError, summary_error_handler)
    app.add_exception_handler(InvalidFileTypeError, invalid_file_type_handler)
    app.add_exception_handler(EmbeddingGenerationError, embedding_error_handler)
    app.add_exception_handler(RetrievalError, retrieval_error_handler)

    # Generic catch-all so unhandled errors still return structured JSON
    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "detail": str(exc) if settings.debug else None,
            },
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(files_router)

    # Health-check – useful for Docker / k8s probes
    @app.get("/health", tags=["Health"], summary="Health check")
    async def health() -> dict:
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
