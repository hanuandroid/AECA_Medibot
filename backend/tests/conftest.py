"""Shared fixtures and skip conditions.

* ``index`` tests need the ingested Qdrant collection (run ``python -m app.ingestion``).
* ``llm`` tests need a real cloud LLM key. They are skipped - never faked - without one.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("WARMUP_MODELS", "false")
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ.setdefault("DEMO_PASSWORD", "test-password")

from app.config import get_settings  # noqa: E402
from app.retrieval.qdrant_store import index_status  # noqa: E402


def _index_ready() -> bool:
    status = index_status()
    return bool(status.get("reachable") and status.get("points"))


INDEX_READY = _index_ready()
LLM_READY = get_settings().llm_configured


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip_index = pytest.mark.skip(reason="Qdrant index not available - run python -m app.ingestion")
    skip_llm = pytest.mark.skip(reason="No LLM API key configured (LLM_API_KEY / OPENAI_API_KEY)")
    for item in items:
        if "index" in item.keywords and not INDEX_READY:
            item.add_marker(skip_index)
        if "llm" in item.keywords and not LLM_READY:
            item.add_marker(skip_llm)


class StubLLM:
    """Test double that returns scripted completions and records prompts (unit isolation only)."""

    provider = "stub"
    model = "stub"

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, *, max_tokens: int = 800) -> str:
        self.calls.append((system, user))
        if not self.responses:
            raise AssertionError("StubLLM ran out of scripted responses")
        return self.responses.pop(0)


@pytest.fixture
def stub_llm_factory() -> type[StubLLM]:
    return StubLLM
