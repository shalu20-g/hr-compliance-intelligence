"""Pending-review store for company HR documents.

Uploaded company documents first enter ``pending`` (or ``rejected`` when
clearly personal/unrelated). Only explicitly approved documents are indexed
into the shared ChromaDB. Pending/rejected files live under
``<documents_directory>/.pending`` and are never scanned by the ingestion
pipeline, so they cannot affect RAG answers.

Persistence is a small JSON file inside the configured documents directory
(``.review_store.json``), which keeps tests isolated because each test uses
its own documents directory.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)

STORE_FILENAME = ".review_store.json"
PENDING_SUBDIR = ".pending"


def pending_dir_for(settings: Settings) -> Path:
    path = Path(settings.documents_directory) / PENDING_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_path_for(settings: Settings) -> Path:
    docs = Path(settings.documents_directory)
    docs.mkdir(parents=True, exist_ok=True)
    return docs / STORE_FILENAME


class ReviewStore:
    """File-backed CRUD for document review records."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = store_path_for(settings)
        self.pending_dir = pending_dir_for(settings)

    # -- persistence helpers -- #
    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError):
            logger.warning("Review store at %s unreadable; starting fresh.", self.path)
            return {}

    def _save(self, records: dict[str, dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # -- CRUD -- #
    def create(
        self,
        *,
        filename: str,
        status: str,
        reason: str,
        category: str,
        confidence: float,
        uploaded_by: str,
    ) -> dict[str, Any]:
        records = self._load()
        review_id = uuid.uuid4().hex[:12]
        record = {
            "review_id": review_id,
            "filename": filename,
            "status": status,
            "reason": reason,
            "category": category,
            "confidence": confidence,
            "uploaded_by": uploaded_by,
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        records[review_id] = record
        self._save(records)
        logger.info("Review %s created for '%s' status=%s.", review_id, filename, status)
        return record

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        records = self._load()
        items = list(records.values())
        if status:
            items = [r for r in items if r.get("status") == status]
        return sorted(items, key=lambda r: r.get("created_at", ""))

    def get(self, review_id: str) -> dict[str, Any] | None:
        return self._load().get(review_id)

    def set_status(
        self, review_id: str, status: str, reason: str | None = None
    ) -> dict[str, Any] | None:
        records = self._load()
        record = records.get(review_id)
        if record is None:
            return None
        record["status"] = status
        if reason:
            record["reason"] = reason
        record["updated_at"] = self._now()
        self._save(records)
        return record

    def save_pending_file(self, filename: str, content: bytes) -> Path:
        """Persist an uploaded file into the quarantine dir (never Chroma)."""
        safe = Path(filename).name
        target = self.pending_dir / safe
        # Avoid collisions: suffix a counter.
        counter = 1
        while target.exists():
            target = self.pending_dir / f"{Path(safe).stem}_{counter}{Path(safe).suffix}"
            counter += 1
        target.write_bytes(content)
        return target


__all__ = ["ReviewStore", "pending_dir_for", "store_path_for"]
