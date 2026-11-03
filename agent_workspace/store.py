from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import uuid

import aiosqlite

from .evidence import extract_pdf, source_id_for_invoice


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection
        self.connection.row_factory = aiosqlite.Row

    async def initialize(self):
        await self.connection.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, filename TEXT NOT NULL, data BLOB NOT NULL,
                pages TEXT NOT NULL, source_id TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, case_id TEXT, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                stage INTEGER NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
                data TEXT NOT NULL, created_at TEXT NOT NULL
            );
        """)
        await self.connection.execute(
            "UPDATE runs SET status='stopped', error='Execution stopped before completion. Retry resumes the persisted checkpoint.' WHERE status='running'"
        )
        await self.connection.commit()

    async def document(self, data: bytes, filename: str) -> dict:
        pages = extract_pdf(data)
        identifier = uuid.uuid4().hex
        filename = Path(filename).name[:120] or "document.pdf"
        source_id = source_id_for_invoice(data)
        await self.connection.execute(
            "INSERT INTO documents VALUES(?,?,?,?,?,?)",
            (identifier, filename, data, json.dumps(pages), source_id, now()),
        )
        await self.connection.commit()
        return {
            "id": identifier,
            "filename": filename,
            "pages": pages,
            "source_id": source_id,
        }

    async def get_document(self, identifier: str, *, include_data=False):
        async with self.connection.execute(
            "SELECT * FROM documents WHERE id=?", (identifier,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        result = {
            "id": row["id"],
            "filename": row["filename"],
            "pages": json.loads(row["pages"]),
            "source_id": row["source_id"],
        }
        if include_data:
            result["data"] = row["data"]
        return result

    async def new_run(self, case_id: str | None) -> str:
        identifier = uuid.uuid4().hex
        await self.connection.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,NULL)",
            (identifier, case_id, "running", now(), now()),
        )
        await self.connection.commit()
        return identifier

    async def set_status(self, identifier: str, status: str, error: str | None = None):
        await self.connection.execute(
            "UPDATE runs SET status=?,error=?,updated_at=? WHERE id=?",
            (status, error, now(), identifier),
        )
        await self.connection.commit()

    async def get_run(self, identifier: str):
        async with self.connection.execute(
            "SELECT * FROM runs WHERE id=?", (identifier,)
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def runs(self):
        async with self.connection.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT 100"
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def emit(self, run_id: str, stage: int, kind: str, title: str, data=None):
        await self.connection.execute(
            "INSERT INTO events(run_id,stage,kind,title,data,created_at) VALUES(?,?,?,?,?,?)",
            (run_id, stage, kind, title, json.dumps(data or {}), now()),
        )
        await self.connection.commit()

    async def events(self, run_id: str, after=0):
        async with self.connection.execute(
            "SELECT * FROM events WHERE run_id=? AND seq>? ORDER BY seq",
            (run_id, after),
        ) as cursor:
            return [
                {**dict(row), "data": json.loads(row["data"])}
                for row in await cursor.fetchall()
            ]
