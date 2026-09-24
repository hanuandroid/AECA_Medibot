# SQL RAG Rules

1. **Inspect the schema first** — see `docs/DATABASE_SCHEMA.md`. The schema description given
   to the LLM is read from the live database (`sqlite_master` + distinct categorical values),
   never invented.
2. **LLM generates SQL** (SQLite dialect) from the question + schema + as-of date.
3. **Extract SQL safely** — handle ```sql fences, bare fences, "Here is the SQL:" prefixes,
   trailing explanations and trailing semicolons. Only the statement reaches the executor.
4. **Validate** — exactly one statement; must parse (sqlglot, sqlite dialect) as `SELECT`
   (optionally `WITH … SELECT`); reject `INSERT UPDATE DELETE DROP ALTER CREATE ATTACH DETACH
   PRAGMA REPLACE VACUUM REINDEX` and any table other than `claims` / `maintenance_tickets`.
5. **Execute against SQLite read-only** (`file:…?mode=ro` URI + `PRAGMA query_only=ON`),
   with a row cap.
6. **Return the result to the LLM** to write the natural-language answer (it must not invent
   numbers beyond the result).
7. Never execute destructive statements, never string-concatenate user input into SQL.
8. `sql_rag_chain(question: str) -> str` is a plain Python function and is the public entry point.
