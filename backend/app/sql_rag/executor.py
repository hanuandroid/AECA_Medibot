"""Step 3a - execute validated SQL against mediassist.db in read-only mode."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.sql_rag.schema import connect_readonly
from app.sql_rag.validate import validate_sql


class SQLExecutionError(RuntimeError):
    pass


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    truncated: bool

    def as_text(self) -> str:
        if not self.rows:
            return "(no rows)"
        header = " | ".join(self.columns)
        body = "\n".join(" | ".join("NULL" if v is None else str(v) for v in r) for r in self.rows)
        return f"{header}\n{body}"


def execute_readonly(
    sql: str, *, db_path: Path | None = None, max_rows: int | None = None
) -> QueryResult:
    """Validate (again - never trust the caller) and execute; returns at most ``max_rows`` rows."""
    statement = validate_sql(sql)
    s = get_settings()
    max_rows = max_rows or s.sql_max_rows
    conn = connect_readonly(db_path or s.sqlite_path)
    try:
        cur = conn.execute(statement)
        rows = cur.fetchmany(max_rows + 1)
        columns = [d[0] for d in cur.description or []]
    except sqlite3.Error as exc:
        raise SQLExecutionError(str(exc)) from exc
    finally:
        conn.close()
    return QueryResult(columns=columns, rows=rows[:max_rows], truncated=len(rows) > max_rows)
