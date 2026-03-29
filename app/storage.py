"""
Storage layer.

Implements a local-disk + SQLite metadata store behind a protocol so
we can swap to S3/Postgres later without changing the service layer.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Protocol

import aiofiles
import aiosqlite
from fastapi import UploadFile

from app.config import settings
from app.exceptions import FileStorageError, FileTooLargeError
from app.models import FileMetadata

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS files (
    file_id      TEXT PRIMARY KEY,
    file_name    TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL,
    uploaded_at  TEXT NOT NULL,
    content_type TEXT NOT NULL
);
"""


class StorageProtocol(Protocol):
    async def init_db(self) -> None:
        ...

    async def save_upload_file(
        self,
        upload: UploadFile,
        max_size_bytes: int,
        chunk_size_bytes: int,
    ) -> FileMetadata:
        ...

    async def get_metadata(self, file_id: str) -> FileMetadata:
        ...

    async def list_files(self) -> list[FileMetadata]:
        ...

    async def stream_file(self, file_id: str, chunk_size_bytes: int) -> AsyncIterator[bytes]:
        ...

    async def read_file_bytes(self, file_id: str, max_bytes: int | None) -> bytes:
        ...


class LocalDiskStorage:
    """Local disk + SQLite implementation of the storage protocol."""

    def __init__(self, upload_dir: Path, db_path: Path) -> None:
        self._upload_dir = upload_dir
        self._db_path = db_path

    async def init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(CREATE_TABLE_SQL)
            await db.commit()
        logger.info("Database initialised at %s", self._db_path)

    async def save_upload_file(
        self,
        upload: UploadFile,
        max_size_bytes: int,
        chunk_size_bytes: int,
    ) -> FileMetadata:
        file_id = str(uuid.uuid4())
        uploaded_at = datetime.now(timezone.utc)
        file_name = upload.filename or "unnamed"
        content_type = upload.content_type or "application/octet-stream"

        self._upload_dir.mkdir(parents=True, exist_ok=True)
        dest_path = self._upload_dir / file_id

        size_bytes = 0
        try:
            async with aiofiles.open(dest_path, "wb") as fh:
                while True:
                    chunk = await upload.read(chunk_size_bytes)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > max_size_bytes:
                        raise FileTooLargeError(
                            received_bytes=size_bytes,
                            max_bytes=max_size_bytes,
                        )
                    await fh.write(chunk)
        except FileTooLargeError:
            dest_path.unlink(missing_ok=True)
            raise
        except OSError as exc:
            dest_path.unlink(missing_ok=True)
            raise FileStorageError(f"Could not write file to disk: {exc}") from exc

        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO files (file_id, file_name, size_bytes, uploaded_at, content_type)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (file_id, file_name, size_bytes, uploaded_at.isoformat(), content_type),
                )
                await db.commit()
        except aiosqlite.Error as exc:
            dest_path.unlink(missing_ok=True)
            raise FileStorageError(f"Could not persist metadata: {exc}") from exc

        logger.info("Stored file %s (%s, %d bytes)", file_id, file_name, size_bytes)

        return FileMetadata(
            file_id=file_id,
            file_name=file_name,
            size_bytes=size_bytes,
            uploaded_at=uploaded_at,
            content_type=content_type,
        )

    async def get_metadata(self, file_id: str) -> FileMetadata:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM files WHERE file_id = ?", (file_id,)) as cursor:
                row = await cursor.fetchone()

        if row is None:
            from app.exceptions import FileNotFoundError

            raise FileNotFoundError(file_id)

        return _row_to_metadata(row)

    async def list_files(self) -> list[FileMetadata]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM files ORDER BY uploaded_at DESC") as cursor:
                rows = await cursor.fetchall()

        return [_row_to_metadata(row) for row in rows]

    async def stream_file(self, file_id: str, chunk_size_bytes: int) -> AsyncIterator[bytes]:
        path = self._upload_dir / file_id
        if not path.exists():
            raise FileStorageError(
                f"File {file_id} is registered but missing from disk – possible data inconsistency"
            )

        async with aiofiles.open(path, "rb") as fh:
            while True:
                chunk = await fh.read(chunk_size_bytes)
                if not chunk:
                    break
                yield chunk

    async def read_file_bytes(self, file_id: str, max_bytes: int | None) -> bytes:
        path = self._upload_dir / file_id
        if not path.exists():
            raise FileStorageError(
                f"File {file_id} is registered but missing from disk – possible data inconsistency"
            )

        try:
            async with aiofiles.open(path, "rb") as fh:
                if max_bytes is None:
                    return await fh.read()
                return await fh.read(max_bytes)
        except OSError as exc:
            raise FileStorageError(f"Could not read file from disk: {exc}") from exc


def _row_to_metadata(row: aiosqlite.Row) -> FileMetadata:
    return FileMetadata(
        file_id=row["file_id"],
        file_name=row["file_name"],
        size_bytes=row["size_bytes"],
        uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
        content_type=row["content_type"],
    )


def build_storage() -> LocalDiskStorage:
    return LocalDiskStorage(upload_dir=settings.upload_dir, db_path=settings.db_path)
