"""CSV output helpers shared by pipelines."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


def format_value(value: Any) -> str:
    """Render a value the way JavaScript's String() does for the numbers this model emits."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer() and abs(value) < 1e21:
            return str(int(value))
        return repr(value)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([format_value(row.get(c)) for c in columns])
