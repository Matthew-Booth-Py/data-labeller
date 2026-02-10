"""Helpers for building optional OpenAI request parameters."""

from uu_backend.config import get_settings


def reasoning_options_for_model(model: str | None) -> dict:
    """Return reasoning options for models that support reasoning effort."""
    settings = get_settings()
    effort = (settings.openai_reasoning_effort or "").strip().lower()
    if not model or effort not in {"low", "medium", "high"}:
        return {}
    if model.startswith("gpt-5"):
        return {"reasoning_effort": effort}
    return {}

