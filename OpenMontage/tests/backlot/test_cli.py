from __future__ import annotations

from backlot import __main__ as cli


def test_loopback_bind_does_not_require_auth(monkeypatch):
    monkeypatch.delenv("BACKLOT_AUTH_PASSWORD", raising=False)
    assert cli._public_bind_requires_auth("127.0.0.1") is False
    assert cli._public_bind_requires_auth("localhost") is False


def test_public_bind_requires_password(monkeypatch):
    monkeypatch.delenv("BACKLOT_AUTH_PASSWORD", raising=False)
    assert cli._public_bind_requires_auth("0.0.0.0") is True

    monkeypatch.setenv("BACKLOT_AUTH_PASSWORD", "configured")
    assert cli._public_bind_requires_auth("0.0.0.0") is False


def test_railway_port_is_used_when_backlot_port_is_unset(monkeypatch):
    monkeypatch.delenv("BACKLOT_PORT", raising=False)
    monkeypatch.setenv("PORT", "8642")
    assert cli._port() == 8642
