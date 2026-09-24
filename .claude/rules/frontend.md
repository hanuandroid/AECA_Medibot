# Frontend Rules

- Next.js (App Router) + TypeScript, strict mode. `npm run lint` and `npm run typecheck` pass.
- Components are small and presentational; API calls live in `lib/api.ts`; session state in
  `lib/session.ts`.
- **Role-aware UX**: header/sidebar shows username, role, accessible collections (✓) and
  restricted collections. Permissions shown come from the backend (`/collections/{role}`), not a
  frontend copy of the matrix.
- Every assistant message shows: answer, retrieval type label (`Hybrid RAG` / `SQL RAG`),
  and source citations (document + section + collection).
- RBAC denials render as a distinct, informative notice (not a generic error).
- Loading state while waiting for `/chat`; errors (network, 401 → back to login) displayed.
- Accessible: labelled inputs, keyboard submit, sufficient contrast, `aria-live` on the message list.
- The frontend never sends a role to `/chat`; it sends only the bearer token and the question.
