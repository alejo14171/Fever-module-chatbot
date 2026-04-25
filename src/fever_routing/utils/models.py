"""
Centralized model initialization factory.

Provider is configurable via settings (LLM_PROVIDER, LLM_MODEL, GOOGLE_API_KEY,
OPENAI_API_KEY, ANTHROPIC_API_KEY). Default is Gemini Flash, intentionally a
"not-too-smart" model so the deterministic Python orchestration carries the
clinical-flow weight while the LLM only reformulates and extracts.
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model

try:
    from config.settings import settings
except Exception:
    settings = None


def _provider() -> str:
    if settings is not None and getattr(settings, "llm_provider", None):
        return settings.llm_provider
    return os.getenv("LLM_PROVIDER", "google")


def _model_name() -> str:
    if settings is not None and getattr(settings, "llm_model", None):
        return settings.llm_model
    return os.getenv("LLM_MODEL", "gemini-2.5-flash")


def _api_key_for(provider: str) -> str:
    env_map = {
        "google": "GOOGLE_API_KEY",
        "google_genai": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    env_name = env_map.get(provider, "GOOGLE_API_KEY")

    if settings is not None:
        secret = None
        if provider.startswith("google"):
            secret = getattr(settings, "google_api_key", None)
        elif provider == "openai":
            secret = getattr(settings, "openai_api_key", None)
        elif provider == "anthropic":
            secret = getattr(settings, "anthropic_api_key", None)
        if secret is not None:
            try:
                value = secret.get_secret_value()
            except Exception:
                value = str(secret)
            if value:
                return value

    return os.getenv(env_name, "dummy-key-for-tests")


def _model_id(provider: str, model: str) -> str:
    if ":" in model:
        return model
    if provider in ("google", "google_genai"):
        return f"google_genai:{model}"
    if provider == "openai":
        return f"openai:{model}"
    if provider == "anthropic":
        return f"anthropic:{model}"
    return model


def _build(temperature: float):
    provider = _provider()
    model = _model_name()
    model_id = _model_id(provider, model)
    api_key = _api_key_for(provider)
    return init_chat_model(model_id, temperature=temperature, api_key=api_key)


class ModelFactory:
    """Provider-agnostic LLM factory. Defaults to Gemini Flash."""

    @staticmethod
    def get_receptor_model():
        return _build(temperature=0.0)

    @staticmethod
    def get_inquiry_model():
        return _build(temperature=0.5)

    @staticmethod
    def get_recommendation_model():
        return _build(temperature=0.3)

    @staticmethod
    def get_urgency_recommendation_model():
        return _build(temperature=0.1)

    @staticmethod
    def get_test_agent_model(temperature: float = 0.7):
        """For patient simulators / judges in test suite."""
        return _build(temperature=temperature)
