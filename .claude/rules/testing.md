# Testing Rules

- Never declare a phase complete without running its tests.
- **Unit tests** for pure logic: RBAC matrix, filter builder, SQL extraction/validation,
  router heuristics, chunk-type classification, JWT.
- **Integration tests** against real components: real Qdrant (local/embedded engine or server)
  with real embeddings; real `mediassist.db` (read-only); real FastAPI app via `TestClient`.
- **Adversarial security tests** assert at the *retrieval result* level that no chunk outside the
  role's collections is returned — not just that the LLM answer "looks" safe.
- **Regression tests**: when a bug is fixed, add a test that would have caught it.
- LLM-dependent tests are marked `@pytest.mark.llm` and skip when no API key is configured.
  Do not replace the LLM with canned answers to make an end-to-end test "pass".
- Test doubles are allowed only for isolating a unit (e.g. a stub LLM that returns SQL text to test
  the extraction/validation/execution steps), and must be clearly named as stubs.
- Never delete, skip or weaken a test to make the implementation pass.
