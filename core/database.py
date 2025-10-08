from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional

from .table import SchemaValidationError, Table


class TableExistsError(ValueError):
    pass


class TableNotFoundError(KeyError):
    pass


@dataclass
class Database:
    name: str
    tables: Dict[str, Table] = field(default_factory=dict)

    def create_table(self, name: str, schema: Mapping[str, object]) -> Table:
        if name in self.tables:
            raise TableExistsError(f"Table '{name}' already exists")
        table = Table.create(name, schema)
        self.tables[name] = table
        return table

    def drop_table(self, name: str) -> None:
        if name not in self.tables:
            raise TableNotFoundError(f"Table '{name}' does not exist")
        del self.tables[name]

    def get_table(self, name: str) -> Table:
        try:
            return self.tables[name]
        except KeyError as exc:
            raise TableNotFoundError(f"Table '{name}' does not exist") from exc

    def list_tables(self) -> Dict[str, Table]:
        return dict(self.tables)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "tables": {name: table.to_dict() for name, table in self.tables.items()},
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "Database":
        database = cls(name=payload["name"])
        for name, table_payload in payload.get("tables", {}).items():
            database.tables[name] = Table.from_dict(table_payload)
        return database


__all__ = ["Database", "TableExistsError", "TableNotFoundError", "SchemaValidationError"]

