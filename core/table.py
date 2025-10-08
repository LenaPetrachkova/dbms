from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from .types import FieldType, ValidationError, build_field_type


class SchemaValidationError(ValueError):
    """Raised when a schema definition is invalid."""


def _normalize_schema(schema: Mapping[str, Any]) -> Dict[str, FieldType]:
    normalized: Dict[str, FieldType] = {}
    for field_name, descriptor in schema.items():
        if not field_name or not isinstance(field_name, str):
            raise SchemaValidationError("Field names must be non-empty strings")
        normalized[field_name] = build_field_type(descriptor)
    return normalized


@dataclass
class Table:
    name: str
    schema: Dict[str, FieldType]
    rows: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(cls, name: str, schema: Mapping[str, Any]) -> "Table":
        normalized_schema = _normalize_schema(schema)
        return cls(name=name, schema=normalized_schema)

    def insert(self, row: Mapping[str, Any]) -> Dict[str, Any]:
        prepared = self._validate_row(row)
        self.rows.append(prepared)
        return prepared

    def update(self, row_id: str, new_values: Mapping[str, Any]) -> Dict[str, Any]:
        row = self._find_row(row_id)
        updated_row = {**row, **new_values}
        validated = self._validate_row(updated_row, allow_missing=True)
        row.update(validated)
        return row

    def delete(self, row_id: str) -> None:
        index = self._find_row_index(row_id)
        del self.rows[index]

    def get(self, row_id: str) -> Dict[str, Any]:
        return self._find_row(row_id).copy()

    def list_rows(self) -> List[Dict[str, Any]]:
        return [row.copy() for row in self.rows]

    def sort_by(self, column: str, reverse: bool = False) -> None:
        if column not in self.schema:
            raise KeyError(f"Unknown column '{column}'")
        self.rows.sort(key=lambda row: row[column], reverse=reverse)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "schema": {key: field_type.to_dict() for key, field_type in self.schema.items()},
            "rows": self.rows,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Table":
        schema_payload = payload["schema"]
        schema = {name: build_field_type(config) for name, config in schema_payload.items()}
        rows = list(payload.get("rows", []))
        table = cls(name=payload["name"], schema=schema, rows=[])
        for row in rows:
            prepared_row = {key: row[key] for key in schema.keys() if key in row}
            if "_id" in row:
                prepared_row["_id"] = row["_id"]
            table.insert(prepared_row)
        return table

    def _validate_row(self, row: Mapping[str, Any], allow_missing: bool = False) -> Dict[str, Any]:
        validated: Dict[str, Any] = {}
        for field_name, field_type in self.schema.items():
            if field_name not in row:
                if allow_missing:
                    continue
                raise ValidationError(f"Missing field '{field_name}'")
            value = field_type.validate(row[field_name])
            validated[field_name] = value
        _id = row.get("_id") or uuid.uuid4().hex
        validated["_id"] = _id
        return validated

    def _find_row(self, row_id: str) -> Dict[str, Any]:
        for row in self.rows:
            if row.get("_id") == row_id:
                return row
        raise KeyError(f"Row with _id={row_id!r} not found")

    def _find_row_index(self, row_id: str) -> int:
        for idx, row in enumerate(self.rows):
            if row.get("_id") == row_id:
                return idx
        raise KeyError(f"Row with _id={row_id!r} not found")


__all__ = ["Table", "SchemaValidationError"]

