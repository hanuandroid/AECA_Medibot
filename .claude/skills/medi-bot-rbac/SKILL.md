---
name: medi-bot-rbac
description: How MediBot enforces role-based access control at the Qdrant retrieval layer and in SQL RAG. Use whenever touching auth, roles, retrieval filters, /chat or /collections.
---

# MediBot RBAC

## The only correct flow

```text
JWT (verified, server-side)
  ↓
role  ∈ {doctor, nurse, billing_executive, technician, admin}
  ↓
allowed collections        (app/rbac.py ROLE_COLLECTIONS)
  ↓
Qdrant metadata filter     Filter(must=[FieldCondition(key="access_roles", match=MatchValue(value=role))])
  ↓
retrieval (inside Qdrant; filter on every Prefetch AND the outer query)
  ↓
reranking (only sees authorised candidates)
  ↓
LLM (only sees authorised top-3)
```

## ⚠️ Forbidden anti-pattern

```text
retrieve everything
       ↓
filter in Python
```

This violates the assignment ("restricted chunks must never be returned to the application,
not filtered after the fact"). It also silently shrinks top-k and leaks restricted text into
process memory/logs. Never write `[c for c in results if role in c.payload["access_roles"]]`
as the enforcement mechanism. (A post-retrieval *assertion* that raises if a restricted chunk
ever appears is fine as a tripwire.)

## Access matrix

| role | collections |
|---|---|
| doctor | clinical, nursing, general |
| nurse | nursing, general |
| billing_executive | billing, general |
| technician | equipment, general |
| admin | clinical, nursing, billing, equipment, general |

`access_roles` on each chunk is derived from this matrix at ingestion
(`roles_for_collection(collection)`), so the chunk says who may read it.

## Other rules
- `/chat` never reads a role from the request body; `ChatRequest` has no `role` field
  (extra fields are rejected).
- SQL RAG: `billing_executive`, `admin` only (`can_use_sql`).
- UX denial (router says the question targets only restricted collections, or SQL for a
  non-analytical role) returns `access_denied=true` with a message naming the role and its
  collections. The Qdrant filter is still the real boundary — the denial is UX, not security.

## Tests to keep green
`tests/test_rbac.py`, `tests/test_rbac_adversarial.py`, `tests/test_api.py`.
