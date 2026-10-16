"""Unit tests for API key auth and the in-process rate limiter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api import security


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeRequest:
    def __init__(self, path: str = "/api/channels", host: str = "10.0.0.1") -> None:
        self.url = SimpleNamespace(path=path)
        self.client = _FakeClient(host)


def test_require_api_key_accepts_expected_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "get_settings", lambda: SimpleNamespace(api_key="secret"))
    assert security.require_api_key("secret") == "secret"


def test_require_api_key_rejects_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "get_settings", lambda: SimpleNamespace(api_key="secret"))
    with pytest.raises(HTTPException) as exc:
        security.require_api_key("wrong")
    assert exc.value.status_code == 401


def test_require_api_key_fails_closed_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "get_settings", lambda: SimpleNamespace(api_key=""))
    with pytest.raises(HTTPException) as exc:
        security.require_api_key("anything")
    assert exc.value.status_code == 500


def test_rate_limiter_blocks_after_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        security, "get_settings", lambda: SimpleNamespace(api_rate_limit_per_minute=2)
    )
    limiter = security.RateLimiter()
    request = _FakeRequest()

    limiter.check(request)
    limiter.check(request)
    with pytest.raises(HTTPException) as exc:
        limiter.check(request)
    assert exc.value.status_code == 429


def test_rate_limiter_exempts_public_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        security, "get_settings", lambda: SimpleNamespace(api_rate_limit_per_minute=1)
    )
    limiter = security.RateLimiter()
    for _ in range(5):
        limiter.check(_FakeRequest(path="/health"))
