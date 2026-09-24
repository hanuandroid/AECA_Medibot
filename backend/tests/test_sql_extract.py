"""SQL extraction (step 2 of sql_rag_chain) and read-only validation."""

from __future__ import annotations

import pytest

from app.sql_rag.executor import execute_readonly
from app.sql_rag.extract import SQLExtractionError, extract_sql
from app.sql_rag.validate import SQLValidationError, validate_sql

Q = "SELECT COUNT(*) FROM claims WHERE status = 'escalated'"


@pytest.mark.parametrize(
    "raw",
    [
        f"```sql\n{Q};\n```",
        f"```sql\n{Q}\n```\nThis query counts escalated claims.",
        f"```\n{Q}\n```",
        f"```SQLite\n{Q};\n```",
        f"Here is the SQL:\n\n{Q}",
        f"Here is the SQL:\n\n{Q};\n\nThis counts the escalated claims.",
        f"SQL: {Q}",
        f"{Q};",
        f"  {Q}  ",
        f"Sure! The query you need is:\n```sql\n{Q}\n```\nLet me know if you need anything else.",
        f"```sql\n{Q}",  # unterminated fence
    ],
)
def test_extract_sql_variants(raw: str) -> None:
    assert extract_sql(raw) == Q


def test_extract_multiline_with_cte_and_blank_line_inside_parens() -> None:
    raw = """Here you go:

```sql
WITH monthly AS (
  SELECT strftime('%Y-%m', submitted_date) AS month, COUNT(*) AS n

  FROM claims
  GROUP BY month
)
SELECT month, n FROM monthly ORDER BY n DESC LIMIT 1;
```"""
    sql = extract_sql(raw)
    assert sql.startswith("WITH monthly AS (")
    assert sql.endswith("LIMIT 1")
    validate_sql(sql)


def test_extract_takes_only_first_statement() -> None:
    raw = f"{Q}; DROP TABLE claims;"
    assert extract_sql(raw) == Q


@pytest.mark.parametrize("raw", ["", "   ", "I cannot answer that.", "```\n```"])
def test_extract_rejects_non_sql(raw: str) -> None:
    with pytest.raises(SQLExtractionError):
        extract_sql(raw)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO claims (claim_id) VALUES ('x')",
        "UPDATE claims SET status = 'approved'",
        "DELETE FROM claims",
        "DROP TABLE claims",
        "ALTER TABLE claims ADD COLUMN x TEXT",
        "CREATE TABLE t (x INT)",
        "ATTACH DATABASE 'x.db' AS x",
        "PRAGMA table_info(claims)",
        "SELECT * FROM claims; DELETE FROM claims",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM claims -- comment",
        "SELECT load_extension('evil')",
        "REPLACE INTO claims (claim_id) VALUES ('x')",
        "WITH x AS (SELECT 1) DELETE FROM claims",
        "SELECT * FROM users",
    ],
)
def test_validate_rejects_unsafe_sql(sql: str) -> None:
    with pytest.raises(SQLValidationError):
        validate_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        Q,
        "SELECT category, COUNT(*) AS n FROM maintenance_tickets WHERE status = 'open' "
        "GROUP BY category ORDER BY n DESC",
        "WITH x AS (SELECT * FROM claims) SELECT COUNT(*) FROM x",
        "SELECT insurer, AVG(approved_amount) FROM claims GROUP BY insurer",
        # keywords inside string literals are data, not statements
        "SELECT COUNT(*) FROM maintenance_tickets "
        "WHERE resolution_note = 'Drop test; update later'",
    ],
)
def test_validate_accepts_read_only_selects(sql: str) -> None:
    assert validate_sql(sql)


def test_executor_is_read_only_even_if_validation_bypassed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second guard: the connection itself refuses writes."""
    import app.sql_rag.executor as ex

    monkeypatch.setattr(ex, "validate_sql", lambda s: s)
    with pytest.raises(ex.SQLExecutionError):
        execute_readonly("DELETE FROM claims")


def test_executor_runs_against_real_db() -> None:
    result = execute_readonly("SELECT COUNT(*) AS n FROM claims")
    assert result.columns == ["n"]
    assert result.rows[0][0] == 85


def test_executor_row_cap() -> None:
    result = execute_readonly("SELECT claim_id FROM claims", max_rows=10)
    assert len(result.rows) == 10 and result.truncated
