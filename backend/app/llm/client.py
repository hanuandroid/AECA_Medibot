"""Cloud LLM client. Provider chosen by ``LLM_PROVIDER``:

* ``openai``      - OpenAI (or any OpenAI-compatible endpoint via ``LLM_BASE_URL``)
* ``groq``        - Groq (OpenAI-compatible)
* ``gemini``      - Google Gemini (OpenAI-compatible endpoint)
* ``openrouter``  - OpenRouter (OpenAI-compatible)
* ``anthropic``   - Anthropic Messages API
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)

OPENAI_COMPATIBLE_BASE_URLS: dict[str, str | None] = {
    "openai": None,
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openrouter": "https://openrouter.ai/api/v1",
}


class LLMNotConfiguredError(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    provider: str
    model: str

    def complete(self, system: str, user: str, *, max_tokens: int = 800) -> str: ...


class OpenAICompatibleClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None,
        temperature: float,
        timeout: float,
    ) -> None:
        from openai import OpenAI

        self.provider = provider
        self.model = model
        self.temperature = temperature
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=2)

    def complete(self, system: str, user: str, *, max_tokens: int = 800) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=self.temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - normalise SDK errors
            raise LLMError(f"{self.provider} completion failed: {exc}") from exc
        return (resp.choices[0].message.content or "").strip()


class AnthropicClient:
    def __init__(self, model: str, api_key: str, temperature: float, timeout: float) -> None:
        from anthropic import Anthropic

        self.provider = "anthropic"
        self.model = model
        # Current Claude models use their default sampling; temperature is not sent.
        self.temperature = temperature
        self._client = Anthropic(api_key=api_key, timeout=timeout, max_retries=2)

    def complete(self, system: str, user: str, *, max_tokens: int = 800) -> str:
        try:
            resp = self._client.messages.create(
                model=self.model,
                system=system,
                messages=[{"role": "user", "content": user}],
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"anthropic completion failed: {exc}") from exc
        from anthropic.types import TextBlock

        return "".join(b.text for b in resp.content if isinstance(b, TextBlock)).strip()


@lru_cache(maxsize=1)
def get_llm() -> LLMClient:
    s = get_settings()
    key = s.resolved_llm_api_key
    if not key:
        raise LLMNotConfiguredError(
            "No LLM API key configured. Set LLM_API_KEY (or OPENAI_API_KEY / ANTHROPIC_API_KEY / "
            "GROQ_API_KEY) and LLM_PROVIDER / LLM_MODEL in backend/.env."
        )
    provider = s.llm_provider.lower()
    if provider == "anthropic":
        return AnthropicClient(s.llm_model, key, s.llm_temperature, s.llm_timeout_seconds)
    if provider not in OPENAI_COMPATIBLE_BASE_URLS:
        raise LLMNotConfiguredError(f"Unsupported LLM_PROVIDER {s.llm_provider!r}")
    base_url = s.llm_base_url or OPENAI_COMPATIBLE_BASE_URLS[provider]
    logger.info("LLM provider=%s model=%s", provider, s.llm_model)
    return OpenAICompatibleClient(
        provider, s.llm_model, key, base_url, s.llm_temperature, s.llm_timeout_seconds
    )
