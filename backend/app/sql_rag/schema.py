"""Describe the live SQLite schema for the SQL-generation prompt (never invented)."""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

ALLOWED_TABLES: tuple[str, ...] = ("claims", "maintenance_tickets")
_MAX_ENUM_VALUES = 12  # list distinct values for low-cardinality text columns
_ENUM_SKIP = {"patient_name", "raised_by", "resolution_note"}


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """Open the database read-only (URI mode=ro) with query_only as a second guard."""
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON")
    return conn


def _describe(db_path: Path) -> str:
    lines: list[str] = []
    with connect_readonly(db_path) as conn:
        for table in ALLOWED_TABLES:
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            lines.append(f"TABLE {table} ({count} rows)")
            for _cid, name, ctype, _nn, _default, pk in cols:
                desc = f"  - {name} {ctype}{' PRIMARY KEY' if pk else ''}"
                if ctype.upper() == "TEXT" and name not in _ENUM_SKIP:
                    distinct = conn.execute(
                        f"SELECT COUNT(DISTINCT {name}) FROM {table}"
                    ).fetchone()[0]
                    if distinct <= _MAX_ENUM_VALUES:
                        values = [
                            r[0]
                            for r in conn.execute(
                                f"SELECT DISTINCT {name} FROM {table} "
                                f"WHERE {name} IS NOT NULL ORDER BY {name}"
                            )
                        ]
                        desc += f"; values: {', '.join(values)}"
                        if conn.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE {name} IS NULL"
                        ).fetchone()[0]:
                            desc += " (or NULL)"
                    elif name.endswith("_date"):
                        lo, hi = conn.execute(
                            f"SELECT MIN({name}), MAX({name}) FROM {table}"
                        ).fetchone()
                        desc += f"; ISO date text, range {lo} .. {hi} (NULL if not set)"
                    else:
                        sample = conn.execute(
                            f"SELECT {name} FROM {table} WHERE {name} IS NOT NULL LIMIT 1"
                        ).fetchone()
                        if sample:
                            desc += f"; e.g. {sample[0]!r}"
                lines.append(desc)
    return "\n".join(lines)


@lru_cache(maxsize=4)
def describe_schema(db_path: Path | None = None) -> str:
    return _describe(db_path or get_settings().sqlite_path)


@lru_cache(maxsize=4)
def latest_date(db_path: Path | None = None) -> str:
    """Latest date present in the data - the default anchor for relative time expressions."""
    path = db_path or get_settings().sqlite_path
    with connect_readonly(path) as conn:
        row = conn.execute(
            "SELECT MAX(d) FROM ("
            " SELECT MAX(submitted_date) d FROM claims UNION ALL"
            " SELECT MAX(resolved_date) FROM claims UNION ALL"
            " SELECT MAX(raised_date) FROM maintenance_tickets UNION ALL"
            " SELECT MAX(resolved_date) FROM maintenance_tickets)"
        ).fetchone()
    return str(row[0])


def as_of_date() -> str:
    configured = get_settings().sql_as_of_date.strip()
    return configured or latest_date()
