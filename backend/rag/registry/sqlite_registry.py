import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.rag.registry.interface import DocumentRegistry
from backend.rag.registry.models import DocumentRecord


class SqliteRegistry(DocumentRegistry):
    def __init__(self, db_path: str):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                source_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'processing',
                chunk_count INTEGER NOT NULL DEFAULT 0,
                total_pages INTEGER NOT NULL DEFAULT 0,
                strategy TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def create_document(self, record: DocumentRecord) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO documents (id, filename, source_path, file_type, status,
                                   chunk_count, total_pages, strategy, tags, error,
                                   created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (record.id, record.filename, record.source_path, record.file_type,
             record.status, record.chunk_count, record.total_pages, record.strategy,
             _serialise_tags(record.tags), record.error,
             now, now),
        )
        self._conn.commit()

    def get_document(self, document_id: str) -> DocumentRecord | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def list_documents(self) -> list[DocumentRecord]:
        rows = self._conn.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def update_document(self, document_id: str, **fields: Any) -> None:
        allowed = {"status", "chunk_count", "total_pages", "strategy", "tags", "error"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now
        if "tags" in updates:
            updates["tags"] = _serialise_tags(updates["tags"])
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [document_id]
        self._conn.execute(
            f"UPDATE documents SET {set_clause} WHERE id = ?", values
        )
        self._conn.commit()

    def delete_document(self, document_id: str) -> None:
        self._conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        self._conn.commit()

    def close(self):
        self._conn.close()


def _serialise_tags(tags: list[str]) -> str:
    return ",".join(tags)


def _deserialise_tags(raw: str) -> list[str]:
    return [t for t in raw.split(",") if t]


def _row_to_record(row: sqlite3.Row) -> DocumentRecord:
    return DocumentRecord(
        id=row["id"],
        filename=row["filename"],
        source_path=row["source_path"],
        file_type=row["file_type"],
        status=row["status"],
        chunk_count=row["chunk_count"],
        total_pages=row["total_pages"],
        strategy=row["strategy"],
        tags=_deserialise_tags(row["tags"]),
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
