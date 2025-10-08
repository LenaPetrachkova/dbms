from __future__ import annotations

import json
from pathlib import Path

from core.database import Database
from storage.json_backend import JsonStorageBackend


def test_save_and_load(tmp_path: Path) -> None:
    db = Database(name="testdb")
    table = db.create_table("items", {"name": "string", "price": "real"})
    table.insert({"name": "Item1", "price": 10.5})

    file_path = tmp_path / "db.json"
    JsonStorageBackend.save(db, file_path)

    assert json.loads(file_path.read_text(encoding="utf-8"))["name"] == "testdb"

    loaded = JsonStorageBackend.load(file_path)
    assert loaded.name == "testdb"
    assert "items" in loaded.tables
    rows = loaded.get_table("items").list_rows()
    assert rows[0]["name"] == "Item1"

