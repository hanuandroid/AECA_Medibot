# Security Rules

1. **RBAC is server-side.** The frontend only *displays* permissions; it is never the boundary.
2. **RBAC is enforced in Qdrant.** Every `query_points` / `search` / `scroll` call used for
   retrieval MUST carry `build_access_filter(role)` — on each `Prefetch` and on the top-level
   `query_filter`. There is no code path that queries Qdrant without it.
3. **Never retrieve-then-filter.** Post-hoc Python filtering of an unrestricted result set is
   forbidden (it still exposes chunks to the application and breaks top-k semantics).
   A defensive assertion *after* retrieval is allowed as a tripwire, never as the mechanism.
4. **Never trust a role from the client.** `/chat` ignores any `role` in the body. The role is
   read from the verified JWT (`sub` + `role` claims, HS256, expiry enforced).
5. **Role validity.** Only `doctor`, `nurse`, `billing_executive`, `technician`, `admin` exist.
   Unknown roles are rejected (401/403), never defaulted to a permissive role.
6. **Never expose unauthorized chunks** — not in `sources`, not in logs returned to clients,
   not in the LLM prompt.
7. **Prompt injection cannot change authorization.** Authorization is decided before the LLM is
   involved. The system prompt additionally instructs the model to ignore override attempts, but
   that is defence-in-depth only.
8. **SQL RAG is restricted** to `billing_executive` and `admin`. Checked in the API layer *and*
   inside the SQL service entry point.
9. **SQL is read-only.** Single `SELECT`/`WITH` statement only; the SQLite connection is opened
   in read-only URI mode (`mode=ro`); `PRAGMA query_only=ON`; row limit enforced.
10. **Secrets never committed.** `.env` is git-ignored; `.env.example` holds placeholders only.
    JWT secret and demo passwords come from environment variables.
