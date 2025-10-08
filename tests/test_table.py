from __future__ import annotations

import pytest

from core.table import Table
from core.types import StringIntervalType, ValidationError


def test_insert_valid_row():
    table = Table.create(
        "people",
        {
            "age": "integer",
            "name": "string",
        },
    )
    inserted = table.insert({"age": 30, "name": "Alice"})
    assert inserted["age"] == 30
    assert inserted["name"] == "Alice"
    assert "_id" in inserted


def test_sort_by_numeric_field():
    table = Table.create("numbers", {"value": "integer"})
    table.insert({"value": 5})
    table.insert({"value": 2})
    table.insert({"value": 8})

    table.sort_by("value")
    values = [row["value"] for row in table.list_rows()]
    assert values == [2, 5, 8]


def test_interval_type_validation():
    interval = StringIntervalType(min_value="a", max_value="m")
    table = Table.create("interval", {"value": interval})
    table.insert({"value": "hello"})

    with pytest.raises(ValidationError):
        table.insert({"value": "zeta"})

