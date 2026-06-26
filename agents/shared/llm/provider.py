"""LLM provider protocol and factory."""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from agents.shared.llm.mock import MockProvider

_ENV_PROVIDER = "LLM_PROVIDER"
_DEFAULT_PROVIDER = "mock"


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal protocol for structured agent LLM completion."""

    def complete(self, messages: list[dict[str, str]], /) -> str | dict[str, Any]:
        """Return structured model output as a JSON string or parsed object."""


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider implementation.

    MVP supports ``mock`` only. Real OpenAI/Anthropic providers are deferred.
    """
    provider_name = os.environ.get(_ENV_PROVIDER, _DEFAULT_PROVIDER)
    normalized = provider_name.strip().lower() if provider_name else _DEFAULT_PROVIDER

    if normalized == "mock":
        return MockProvider()

    raise NotImplementedError(
        f"LLM provider {provider_name!r} is not implemented. "
        "Set LLM_PROVIDER=mock for local development and tests."
    )
