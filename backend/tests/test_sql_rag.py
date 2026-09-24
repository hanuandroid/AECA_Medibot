"""sql_rag_chain: the three explicit steps, safety, and >=4 analytical questions on the real DB."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from app.sql_rag import chain
from app.sql_rag.chain import SQLRagError, run_sql_rag, sql_rag_chain
from app.sql_rag.executor import execute_readonly
from app.sql_rag.schema import as_of_date, describe_schema, relative_date_windows

from .conftest import StubLLM


def test_sql_rag_chain_is_a_plain_function_with_the_required_signature() -> None:
    assert inspect.isfunction(sql_rag_chain)
    sig = inspect.signature(sql_rag_chain)
    assert list(sig.parameters) == ["question"]
    assert sig.parameters["question"].annotation in (str, "str")
    assert sig.return_annotation in (str, "str")


def test_schema_description_comes_from_the_live_database() -> None:
    schema = describe_schema()
    for col in (
        "claim_id",
        "status",
        "submitted_date",
        "approved_amount",
        "category",
        "issue_type",
        "fault_code",
        "raised_date",
    ):
        assert col in schema
    assert "escalated" in schema and "in_progress" in schema  # real categorical values
    assert as_of_date() == "2024-12-28"


def test_three_steps_with_fenced_llm_output() -> None:
    """Step 1 LLM -> fenced SQL + prose; step 2 cleans it; step 3 executes + LLM answers."""
    llm = StubLLM(
        "Here is the SQL:\n```sql\nSELECT COUNT(*) AS escalated FROM claims "
        "WHERE status = 'escalated';\n```\nThis counts escalated claims.",
        "8 claims are currently escalated.",
    )
    result = run_sql_rag("How many claims are escalated?", llm=llm)
    assert result.sql == "SELECT COUNT(*) AS escalated FROM claims WHERE status = 'escalated'"
    assert result.result.rows == [(8,)]
    assert result.answer == "8 claims are currently escalated."
    # The second LLM call received the executed SQL and the real result.
    _, answer_prompt = llm.calls[1]
    assert "escalated" in answer_prompt and "\n8" in answer_prompt
    assert "```" not in answer_prompt.split("SQL executed:")[1].split("Result")[0]


def test_destructive_sql_is_never_executed_and_is_repaired(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[str] = []
    real = chain.execute_readonly

    def spy(sql: str, **kw: Any) -> Any:
        executed.append(sql)
        return real(sql, **kw)

    monkeypatch.setattr(chain, "execute_readonly", spy)
    llm = StubLLM(
        "DELETE FROM claims WHERE status = 'escalated'",
        "SELECT COUNT(*) FROM claims WHERE status = 'escalated'",
        "There are 8 escalated claims.",
    )
    result = run_sql_rag("How many escalated claims?", llm=llm)
    assert executed == ["SELECT COUNT(*) FROM claims WHERE status = 'escalated'"]
    assert "rejected" in llm.calls[1][1]  # feedback about the rejected statement
    assert result.result.rows == [(8,)]


def test_chain_gives_up_after_repeated_invalid_sql() -> None:
    llm = StubLLM("DROP TABLE claims", "I refuse to write SQL")
    with pytest.raises(SQLRagError):
        run_sql_rag("drop everything", llm=llm)


def test_database_is_unchanged_after_attacks() -> None:
    assert execute_readonly("SELECT COUNT(*) FROM claims").rows == [(85,)]
    assert execute_readonly("SELECT COUNT(*) FROM maintenance_tickets").rows == [(78,)]


# --- analytical questions: reference SQL on the real database --------------------------------

REFERENCE = [
    (
        "How many claims are currently in escalated status?",
        "SELECT COUNT(*) FROM claims WHERE status = 'escalated'",
        8,
    ),
    (
        "Which equipment category has the most open maintenance tickets?",
        "SELECT category FROM maintenance_tickets WHERE status = 'open' GROUP BY category "
        "ORDER BY COUNT(*) DESC LIMIT 1",
        "radiology",
    ),
    (
        "Which department has the highest total claimed amount?",
        "SELECT department FROM claims GROUP BY department "
        "ORDER BY SUM(claimed_amount) DESC LIMIT 1",
        "orthopaedics",
    ),
    (
        "What is the average approved amount of approved claims?",
        "SELECT ROUND(AVG(approved_amount), 2) FROM claims WHERE status = 'approved'",
        55515.91,
    ),
    (
        "How many maintenance tickets have the issue type calibration due?",
        "SELECT COUNT(*) FROM maintenance_tickets WHERE issue_type = 'calibration_due'",
        13,
    ),
    (
        "How many billing claims were escalated last month?",
        "SELECT COUNT(*) FROM claims WHERE status = 'escalated' AND submitted_date >= "
        "date('2024-12-28', 'start of month', '-1 month') AND submitted_date < "
        "date('2024-12-28', 'start of month')",
        0,
    ),
    # Relative-date questions whose answers differ between November (last month) and December
    # (this month), so reading "last month" as the as-of month is caught (regression).
    (
        "How many claims were submitted last month?",
        "SELECT COUNT(*) FROM claims WHERE submitted_date >= '2024-11-01' "
        "AND submitted_date < '2024-12-01'",
        9,
    ),
    (
        "How many maintenance tickets were raised this month?",
        "SELECT COUNT(*) FROM maintenance_tickets WHERE raised_date >= '2024-12-01' "
        "AND raised_date < '2025-01-01'",
        7,
    ),
]


@pytest.mark.parametrize(
    ("as_of", "last_month", "this_month"),
    [
        ("2024-12-28", ("2024-11-01", "2024-12-01"), ("2024-12-01", "2025-01-01")),
        ("2024-01-15", ("2023-12-01", "2024-01-01"), ("2024-01-01", "2024-02-01")),
    ],
)
def test_relative_date_windows(
    as_of: str, last_month: tuple[str, str], this_month: tuple[str, str]
) -> None:
    windows = relative_date_windows(as_of)
    assert f"last month: date >= '{last_month[0]}' AND date < '{last_month[1]}'" in windows
    assert f"this month: date >= '{this_month[0]}' AND date < '{this_month[1]}'" in windows


def test_sql_prompt_contains_precomputed_date_windows() -> None:
    llm = StubLLM("SELECT 1 FROM claims", "ok")
    run_sql_rag("How many claims were submitted last month?", llm=llm)
    system_prompt, _ = llm.calls[0]
    assert "last month: date >= '2024-11-01' AND date < '2024-12-01'" in system_prompt


@pytest.mark.parametrize(("question", "sql", "expected"), REFERENCE)
def test_reference_answers_on_real_db(question: str, sql: str, expected: object) -> None:
    assert execute_readonly(sql).rows[0][0] == expected


def _flatten(rows: list[tuple[Any, ...]]) -> list[Any]:
    return [v for r in rows for v in r]


def _matches(value: Any, expected: object) -> bool:
    if isinstance(expected, float) and isinstance(value, int | float):
        return abs(float(value) - expected) < 0.01
    return value == expected


@pytest.mark.llm
@pytest.mark.parametrize(("question", "sql", "expected"), REFERENCE)
def test_sql_rag_live_llm(question: str, sql: str, expected: object) -> None:
    """End-to-end with the real cloud LLM: generated SQL must yield the reference value."""
    result = run_sql_rag(question)
    values = _flatten(result.result.rows[:1])
    assert any(_matches(v, expected) for v in values), (result.sql, result.result.rows[:5])
    assert result.answer.strip()
    expected_text = f"{expected:,.2f}" if isinstance(expected, float) else str(expected)
    normalised = result.answer.replace(",", "").lower()
    accepted = {expected_text.replace(",", "").lower(), str(expected).lower()}
    if expected == 0:
        accepted |= {"no ", "none", "zero"}  # "No claims were escalated" is a correct 0
    assert any(a in normalised for a in accepted), result.answer


@pytest.mark.llm
def test_sql_rag_chain_returns_string_live() -> None:
    answer = sql_rag_chain("How many claims were rejected?")
    assert isinstance(answer, str) and "12" in answer
