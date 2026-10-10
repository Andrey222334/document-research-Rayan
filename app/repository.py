"""SQLite stores complete documents; Elasticsearch stores only searchable fields."""

import json
from pathlib import Path

import aiosqlite

from app.models import Document


class DocumentRepository:
    def __init__(self, path: str):
        self.path = path

    async def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY,
                    rubrics TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_date TEXT NOT NULL
                )
            """)
            await db.commit()

    async def upsert(self, documents: list[Document]) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executemany(
                "INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?)",
                [(d.id, json.dumps(d.rubrics, ensure_ascii=False), d.text,
                  d.created_date.isoformat()) for d in documents],
            )
            await db.commit()

    async def newest(self, ids: list[int]) -> list[Document]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT * FROM documents WHERE id IN ({placeholders}) "
                "ORDER BY created_date DESC, id ASC LIMIT 20", ids,
            ) as cursor:
                rows = await cursor.fetchall()
        return [Document(**{**dict(row), "rubrics": json.loads(row["rubrics"])})
                for row in rows]

    async def delete(self, document_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            await db.commit()
            return cursor.rowcount > 0
