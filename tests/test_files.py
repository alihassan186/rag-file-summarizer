"""
Test suite for the ResMed File Sharing API.

Coverage:
  ✔ POST /files/       – happy path, oversized file, empty filename
  ✔ GET  /files/       – empty list, list after uploads
  ✔ GET  /files/{id}   – download happy path, unknown ID
  ✔ GET  /files/{id}/summary – text file, unknown ID
  ✔ GET  /health       – always returns ok

Each test is independent – the ``client`` fixture provides a fresh
temporary database and upload directory via pytest's ``tmp_path``.
"""
import io
import pytest

from tests.conftest import make_pdf_bytes, make_text_file


# ── Health ────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_health_check(client):
    """The health endpoint must always return HTTP 200 with status=ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


# ── Upload ────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_upload_text_file_returns_201(client):
    """Uploading a valid text file must return HTTP 201 and a file_id."""
    name, data, ctype = make_text_file()
    response = await client.post(
        "/files/",
        files={"file": (name, io.BytesIO(data), ctype)},
    )
    assert response.status_code == 201
    body = response.json()
    assert "file_id" in body
    assert body["file_name"] == name
    assert body["size_bytes"] == len(data)
    assert "uploaded_at" in body


@pytest.mark.anyio
async def test_upload_oversized_file_returns_413(client):
    """A file exceeding the 20 MB limit must be rejected with HTTP 413."""
    from app import config

    oversized = b"x" * (config.settings.max_file_size_bytes + 1)
    response = await client.post(
        "/files/",
        files={"file": ("big.bin", io.BytesIO(oversized), "application/octet-stream")},
    )
    assert response.status_code == 413
    body = response.json()
    assert body["error"] == "file_too_large"
    assert "20 MB" in body["detail"]


@pytest.mark.anyio
async def test_upload_pdf_file(client):
    """PDF files must be accepted and stored like any other file."""
    pdf_bytes = make_pdf_bytes()
    response = await client.post(
        "/files/",
        files={"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 201
    assert response.json()["file_name"] == "report.pdf"


@pytest.mark.anyio
async def test_upload_multiple_files_get_unique_ids(client):
    """Each uploaded file must receive a distinct UUID."""
    name, data, ctype = make_text_file()
    ids = set()
    for _ in range(3):
        r = await client.post("/files/", files={"file": (name, io.BytesIO(data), ctype)})
        assert r.status_code == 201
        ids.add(r.json()["file_id"])
    assert len(ids) == 3, "Duplicate file IDs detected"


@pytest.mark.anyio
async def test_upload_missing_file_field_returns_422(client):
    """Missing multipart file field should return FastAPI validation error."""
    response = await client.post(
        "/files/",
        data={"note": "no file part provided"},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_upload_empty_file_returns_400(client):
    """Zero-byte uploads should be rejected as invalid input."""
    response = await client.post(
        "/files/",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "empty_file"


# ── List ──────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_files_empty_store(client):
    """List endpoint on an empty store must return total=0 and an empty list."""
    response = await client.get("/files/")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["files"] == []


@pytest.mark.anyio
async def test_list_files_after_upload(client):
    """After uploading N files the list must contain exactly N records."""
    name, data, ctype = make_text_file()
    for i in range(3):
        await client.post(
            "/files/",
            files={"file": (f"file_{i}.txt", io.BytesIO(data), ctype)},
        )

    response = await client.get("/files/")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["files"]) == 3

    # Verify each record has required metadata fields
    for record in body["files"]:
        assert "file_id" in record
        assert "file_name" in record
        assert "size_bytes" in record
        assert "uploaded_at" in record
        assert "content_type" in record
        # Content must NOT be present
        assert "content" not in record


# ── Download ──────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_download_returns_original_bytes(client):
    """Downloading a file must return the exact bytes that were uploaded."""
    name, data, ctype = make_text_file("Exact content check.")
    upload = await client.post("/files/", files={"file": (name, io.BytesIO(data), ctype)})
    file_id = upload.json()["file_id"]

    response = await client.get(f"/files/{file_id}")
    assert response.status_code == 200
    assert response.content == data


@pytest.mark.anyio
async def test_download_sets_content_disposition(client):
    """The download response must include a Content-Disposition header."""
    name, data, ctype = make_text_file()
    upload = await client.post("/files/", files={"file": (name, io.BytesIO(data), ctype)})
    file_id = upload.json()["file_id"]

    response = await client.get(f"/files/{file_id}")
    assert "content-disposition" in response.headers
    assert name in response.headers["content-disposition"]


@pytest.mark.anyio
async def test_download_unknown_id_returns_404(client):
    """Requesting a non-existent file_id must return HTTP 404."""
    response = await client.get("/files/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "file_not_found"


@pytest.mark.anyio
async def test_download_invalid_uuid_returns_422(client):
    """Malformed file identifiers should fail FastAPI validation."""
    response = await client.get("/files/not-a-uuid")
    assert response.status_code == 422


# ── Summary ───────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_summary_text_file_returns_extractive(client):
    """Without an HF token the summary must fall back to extractive and flag it."""
    content = "Machine learning is transforming healthcare. " * 20
    name, data, ctype = make_text_file(content)
    upload = await client.post("/files/", files={"file": (name, io.BytesIO(data), ctype)})
    file_id = upload.json()["file_id"]

    response = await client.get(f"/files/{file_id}/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == file_id
    assert isinstance(body["summary"], str)
    assert len(body["summary"]) > 0
    assert body["summary_source"] in {"llm", "extractive", "metadata"}
    assert body["summary"].startswith("[Extractive summary")


@pytest.mark.anyio
async def test_summary_binary_file_returns_metadata_source(client):
    """Binary files that cannot be decoded must return summary_source='metadata'."""
    binary_data = bytes(range(256)) * 100  # non-UTF-8 binary
    upload = await client.post(
        "/files/",
        files={"file": ("data.bin", io.BytesIO(binary_data), "application/octet-stream")},
    )
    file_id = upload.json()["file_id"]

    response = await client.get(f"/files/{file_id}/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["summary_source"] == "metadata"
    assert "data.bin" in body["summary"]


@pytest.mark.anyio
async def test_summary_unknown_id_returns_404(client):
    """Summary endpoint with a non-existent file_id must return HTTP 404."""
    response = await client.get("/files/00000000-0000-0000-0000-000000000000/summary")
    assert response.status_code == 404
    assert response.json()["error"] == "file_not_found"


@pytest.mark.anyio
async def test_summary_invalid_uuid_returns_422(client):
    """Summary route should validate file identifiers before hitting the service."""
    response = await client.get("/files/not-a-uuid/summary")
    assert response.status_code == 422


# ── Metadata integrity ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_upload_metadata_matches_list(client):
    """Metadata returned on upload must exactly match what appears in the list."""
    name, data, ctype = make_text_file("Integrity check content.")
    upload = await client.post("/files/", files={"file": (name, io.BytesIO(data), ctype)})
    assert upload.status_code == 201
    uploaded = upload.json()

    list_resp = await client.get("/files/")
    files = list_resp.json()["files"]
    assert len(files) == 1

    record = files[0]
    assert record["file_id"] == uploaded["file_id"]
    assert record["file_name"] == uploaded["file_name"]
    assert record["size_bytes"] == uploaded["size_bytes"]
