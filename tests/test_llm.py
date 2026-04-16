import pytest

from app.config import Settings
from app.llm import LLMAdvisor, LLMUnavailableError


def test_llm_disabled_fails_fast() -> None:
    advisor = LLMAdvisor(Settings(llm_enabled=False))
    with pytest.raises(LLMUnavailableError):
        advisor.suggest({"service": "auth-prod"})


def test_openai_missing_key_fallback_error() -> None:
    advisor = LLMAdvisor(Settings(llm_enabled=True, llm_provider="openai", openai_api_key=""))
    with pytest.raises(LLMUnavailableError):
        advisor.suggest({"service": "auth-prod"})
