# Python Rules

- Python 3.11–3.13, full type hints on public functions; `mypy app` must pass.
- Request/response and domain models are **Pydantic v2** models.
- Configuration via `pydantic-settings` (`app/config.py`), read from env / `backend/.env`.
- FastAPI endpoints: `async def` only when the body awaits; blocking work (embedding, Qdrant,
  LLM SDK calls) runs in sync endpoints (FastAPI runs them in a threadpool).
- Small modules with one responsibility; no god-objects.
- Raise specific exceptions (`AuthError`, `SQLValidationError`, `AccessDeniedError`, …) and map
  them to HTTP responses in the API layer. Never swallow exceptions silently.
- Use the `logging` module (`logger = logging.getLogger(__name__)`), never `print` in app code
  (scripts may print).
- `ruff check .` must pass.
