from __future__ import annotations

import json
from pathlib import Path

from core.database import Database


class JsonStorageBackend:
    @staticmethod
    def save(database: Database, path: str | Path) -> None:
        file_path = Path(path)
        payload = database.to_dict()
        file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def load(path: str | Path) -> Database:
        file_path = Path(path)
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return Database.from_dict(payload)


__all__ = ["JsonStorageBackend"]

