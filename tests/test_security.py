import pytest
from fastapi import HTTPException

from app.security import verify_api_key


def test_verify_api_key_rejects_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.security.settings.auth_enabled", True)
    monkeypatch.setattr("app.security.settings.api_key", "secret")

    with pytest.raises(HTTPException) as exc:
        verify_api_key("wrong")

    assert exc.value.status_code == 401


def test_verify_api_key_accepts_correct_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.security.settings.auth_enabled", True)
    monkeypatch.setattr("app.security.settings.api_key", "secret")

    verify_api_key("secret")
