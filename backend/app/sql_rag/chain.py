"""SQL RAG over mediassist.db.

``sql_rag_chain(question) -> str`` is the plain Python function required by the assignment.
It runs three explicit steps:

1. **Generate** - the LLM translates the question into SQLite SQL (schema-grounded prompt).
2. **Clean**    - ``extract_sql`` pulls out only the SQL statement; ``validate_sql`` checks it
                  is a single read-only SELECT on the allowed tables.
3. **Execute & answer** - run it read-only against SQLite, then the LLM turns the result
                  rows into a natural-language answer.

If step 2 or 3a fails, the error is fed back to the LLM once to repair the query.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.llm.client import LLMClient, get_llm
from app.llm.prompts import (
    SQL_ANSWER_SYSTEM_PROMPT,
    SQL_ANSWER_USER_TEMPLATE,
    SQL_GENERATION_SYSTEM_PROMPT,
    SQL_GENERATION_USER_TEMPLATE,
)
from app.sql_rag.executor import QueryResult, SQLExecutionError, execute_readonly
from app.sql_rag.extract import SQLExtractionError, extract_sql
from app.sql_rag.schema import as_of_date, describe_schema, relative_date_windows
from app.sql_rag.validate import SQLValidationError, validate_sql

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2


class SQLRagError(RuntimeError):
    pass


@dataclass
class SQLRagResult:
    question: str
    answer: str
    sql: str
    result: QueryResult
    raw_llm_sql: str
    attempts: list[str] = field(default_factory=list)


def generate_sql(question: str, llm: LLMClient, feedback: str = "") -> str:
    """Step 1: natural language -> raw LLM output (expected to contain SQL)."""
    as_of = as_of_date()
    system = SQL_GENERATION_SYSTEM_PROMPT.format(
        schema=describe_schema(), as_of=as_of, date_windows=relative_date_windows(as_of)
    )
    user = SQL_GENERATION_USER_TEMPLATE.format(question=question, feedback=feedback)
    return llm.complete(system, user, max_tokens=500)


def answer_from_result(question: str, sql: str, result: QueryResult, llm: LLMClient) -> str:
    """Step 3b: query result -> natural-language answer."""
    user = SQL_ANSWER_USER_TEMPLATE.format(
        question=question,
        sql=sql,
        row_count=len(result.rows),
        truncated=", truncated" if result.truncated else "",
        result=result.as_text(),
    )
    return llm.complete(SQL_ANSWER_SYSTEM_PROMPT, user, max_tokens=400)


def run_sql_rag(question: str, llm: LLMClient | None = None) -> SQLRagResult:
    """Full pipeline, returning the SQL and rows too (used by the API and tests)."""
    llm = llm or get_llm()
    feedback = ""
    attempts: list[str] = []
    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        raw = generate_sql(question, llm, feedback)  # step 1
        attempts.append(raw)
        try:
            sql = validate_sql(extract_sql(raw))  # step 2
            result = execute_readonly(sql)  # step 3a
        except (SQLExtractionError, SQLValidationError, SQLExecutionError) as exc:
            last_error = exc
            logger.warning("SQL attempt rejected (%s): %r", exc, raw[:300])
            feedback = (
                f"\n\nYour previous answer was rejected: {exc}\n"
                "Return one valid SQLite SELECT statement only."
            )
            continue
        logger.info("sql_rag q=%r sql=%s rows=%d", question[:80], sql, len(result.rows))
        answer = answer_from_result(question, sql, result, llm)  # step 3b
        return SQLRagResult(question, answer, sql, result, raw, attempts)
    raise SQLRagError(f"Could not produce a valid SQL query: {last_error}")


def sql_rag_chain(question: str) -> str:
    """Answer an analytical question from mediassist.db (LLM -> SQL -> execute -> LLM)."""
    return run_sql_rag(question).answer
