from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass
class LLMStatus:
    configured: bool
    provider: str
    model: str


class LLMGateway:
    """Provider-neutral placeholder. Core product behavior never depends on it."""

    def status(self) -> LLMStatus:
        settings = get_settings()
        configured = bool(
            settings.llm_enabled
            and settings.llm_base_url
            and settings.llm_api_key
            and settings.llm_model
        )
        return LLMStatus(configured=configured, provider="openai-compatible", model=settings.llm_model)

    def generate(self, _messages: list[dict]) -> str | None:
        # Deliberately left as a controlled integration point. Enabling an external
        # provider must include enterprise data-boundary and prompt-injection review.
        return None


llm_gateway = LLMGateway()

