"""Step 2b - validate that the extracted SQL is a single, read-only query on allowed tables."""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from app.sql_rag.schema import ALLOWED_TABLES

BLOCKED_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "REPLACE",
    "VACUUM",
    "REINDEX",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "UPSERT",
    "ANALYZE",
)
_BLOCKED_RE = re.compile(r"\b(" + "|".join(BLOCKED_KEYWORDS) + r")\b", re.IGNORECASE)
_BLOCKED_FUNCTIONS = {"load_extension", "readfile", "writefile", "fts3_tokenizer", "edit"}
_STRING_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")
_WRITE_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Command,
    exp.Merge,
    exp.TruncateTable,
)


class SQLValidationError(ValueError):
    pass


def validate_sql(sql: str) -> str:
    """Return the statement if it is safe to execute; raise ``SQLValidationError`` otherwise."""
    statement = sql.strip().rstrip(";").strip()
    if not statement:
        raise SQLValidationError("Empty SQL statement")
    if ";" in _STRING_LITERAL_RE.sub("''", statement):
        raise SQLValidationError("Multiple SQL statements are not allowed")
    if "--" in statement or "/*" in statement:
        raise SQLValidationError("SQL comments are not allowed")

    keyword_scan = _STRING_LITERAL_RE.sub("''", statement)
    blocked = _BLOCKED_RE.search(keyword_scan)
    if blocked:
        raise SQLValidationError(f"Blocked keyword in SQL: {blocked.group(1).upper()}")

    try:
        parsed = sqlglot.parse(statement, read="sqlite")
    except sqlglot.errors.ParseError as exc:
        raise SQLValidationError(f"SQL does not parse: {exc}") from exc
    if len(parsed) != 1 or parsed[0] is None:
        raise SQLValidationError("Exactly one SQL statement is required")
    tree = parsed[0]

    if not isinstance(tree, exp.Select | exp.Union | exp.Intersect | exp.Except):
        raise SQLValidationError(f"Only SELECT queries are allowed (got {tree.key.upper()})")
    if any(isinstance(node, _WRITE_NODES) for node in tree.walk()):
        raise SQLValidationError("Data-modifying statements are not allowed")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name and name not in ALLOWED_TABLES and name not in cte_names:
            raise SQLValidationError(f"Table not allowed: {table.name}")
    for func in tree.find_all(exp.Anonymous):
        if str(func.name).lower() in _BLOCKED_FUNCTIONS:
            raise SQLValidationError(f"Function not allowed: {func.name}")
    return statement
