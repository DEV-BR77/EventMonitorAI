import time
from types import SimpleNamespace

import pytest
from app.core.security import create_token, decode_token, hash_password, verify_password
from fastapi import HTTPException


def test_password_hash_round_trip() -> None:
    encoded = hash_password("a sufficiently long password")

    assert encoded != "a sufficiently long password"
    assert verify_password("a sufficiently long password", encoded)
    assert not verify_password("wrong password", encoded)


def test_signed_token_round_trip() -> None:
    user = SimpleNamespace(username="alice", role="viewer")

    payload = decode_token(create_token(user))

    assert payload["sub"] == "alice"
    assert payload["role"] == "viewer"
    assert payload["exp"] > time.time()


def test_modified_token_is_rejected() -> None:
    user = SimpleNamespace(username="alice", role="viewer")
    token = create_token(user)

    with pytest.raises(HTTPException):
        decode_token(f"{token}changed")
