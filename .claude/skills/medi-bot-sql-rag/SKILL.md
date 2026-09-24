---
name: medi-bot-sql-rag
description: How MediBot answers analytical questions with the three-stage sql_rag_chain over mediassist.db (LLM → SQL, extract + validate, execute read-only, LLM → answer). Use when changing backend/app/sql_rag.
---

# MediBot SQL RAG

```text
Question
   ↓
LLM generates SQL        (prompt: live schema + categorical values + as-of date, SQLite dialect)
   ↓
Extract SQL              (extract_sql: ```sql fences / bare fences / "Here is the SQL:" / trailing prose)
   ↓
Validate SQL             (validate_sql: single SELECT/WITH, sqlglot parse, allow-listed tables,
   ↓                      blocked keywords INSERT UPDATE DELETE DROP ALTER CREATE ATTACH PRAGMA …)
Execute SQLite           (file:…?mode=ro, PRAGMA query_only=ON, row cap)
   ↓
Result (columns + rows)
   ↓
LLM                      (answer strictly from the rows; state when the result is empty)
   ↓
Natural language answer
```

## Public API
```python
def sql_rag_chain(question: str) -> str: ...            # the plain function the assignment asks for
def run_sql_rag(question: str) -> SQLRagResult: ...     # same steps, returns sql + rows for the API/debug
```

## Schema facts (from the real DB — see docs/DATABASE_SCHEMA.md)
- `claims(status ∈ approved|escalated|pending|rejected|submitted, department, claim_type,
  insurer, claimed_amount, approved_amount, submitted_date, resolved_date …)`
- `maintenance_tickets(category, campus, issue_type, fault_code, status ∈ open|in_progress|
  escalated|resolved, raised_date, resolved_date …)`
- All dates are ISO `YYYY-MM-DD` text in 2024. Relative dates ("last month") resolve against
  `SQL_AS_OF_DATE` (default: latest date in the DB) — documented, not hidden.

## Rules
- Role gate: `billing_executive`, `admin` only.
- Never execute raw LLM output; never execute anything that fails validation.
- Tests use the real `mediassist.db` and compare against hand-written reference SQL.
