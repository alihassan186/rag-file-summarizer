"""
Shared pytest fixtures.

Key design decisions:
  • Each test function gets a fresh temporary directory for uploads and a
    fresh in-memory SQLite database – tests are fully isolated.
  • We override the application Settings before importing the app so no
    real data is ever written to the working-directory paths.
  • The HTTPX AsyncClient drives the FastAPI app in-process (no real server
    needed), making tests fast and deterministic.
"""
import io
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pathlib import Path


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client(tmp_path: Path):
    """Return an async HTTP client wired to a fully isolated app instance.

    The ``tmp_path`` fixture is provided by pytest and is unique per test.
    We monkey-patch ``settings`` before the app is used so every test runs
    against its own empty database and upload directory.
    """
    from app import config
    from app import deps

    # ── Redirect all I/O to tmp_path ─────────────────────────────────────────
    config.settings.upload_dir = tmp_path / "uploads"
    config.settings.db_path = tmp_path / "data" / "metadata.db"
    config.settings.vector_store_dir = tmp_path / "data" / "vector_indexes"
    config.settings.upload_dir.mkdir(parents=True, exist_ok=True)
    config.settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    config.settings.vector_store_dir.mkdir(parents=True, exist_ok=True)

    # Disable HF token so tests never hit external APIs
    config.settings.hf_api_token = ""

    from app.main import app
    deps.get_storage.cache_clear()
    deps.get_rag_pipeline.cache_clear()
    storage = deps.get_storage()
    await storage.init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Reusable file helpers ─────────────────────────────────────────────────────

def make_text_file(content: str = "Hello world. This is a test file.") -> tuple:
    """Return ``(filename, file_bytes, content_type)``."""
    return "test.txt", content.encode(), "text/plain"


def make_pdf_bytes() -> bytes:
    """Return the bytes of a minimal valid PDF with one text page."""
    # Minimal hand-crafted PDF – no external library required
    return b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 100 700 Td (Test PDF content.) Tj ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000274 00000 n
0000000369 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
441
%%EOF"""
