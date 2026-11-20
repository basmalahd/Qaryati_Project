from datetime import timedelta

import pytest

from app.core import security
from app.core.errors import UnauthorizedError


def test_password_hash_roundtrip():
    h = security.hash_password("Password123")
    assert h != "Password123"
    assert security.verify_password("Password123", h)
    assert not security.verify_password("wrong", h)


def test_access_token_roundtrip():
    token = security.create_access_token("42")
    assert security.decode_token(token, security.ACCESS)["sub"] == "42"


def test_access_token_rejected_as_refresh():
    token = security.create_access_token("42")
    with pytest.raises(UnauthorizedError):
        security.decode_token(token, security.REFRESH)


def test_expired_token_rejected():
    token = security.create_token("42", security.ACCESS, timedelta(seconds=-5))
    with pytest.raises(UnauthorizedError):
        security.decode_token(token, security.ACCESS)


def test_garbage_token_rejected():
    with pytest.raises(UnauthorizedError):
        security.decode_token("not.a.jwt", security.ACCESS)
