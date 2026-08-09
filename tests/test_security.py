import time
from types import SimpleNamespace

import pytest
from app.api.auth import login, update_user
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.database.base import Base
from app.models.dashboard import User
from app.schemas.dashboard import LoginRequest, UserUpdate
from app.services.login_guard import MAX_FAILURES, record_failure, reset_for_tests, retry_after
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


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


def test_admin_can_update_another_user_but_not_demote_self() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        admin = User(username="admin", password_hash=hash_password("admin-password"), role="admin")
        viewer = User(
            username="viewer", password_hash=hash_password("viewer-password"), role="viewer"
        )
        db.add_all([admin, viewer])
        db.commit()

        for _ in range(MAX_FAILURES):
            record_failure(viewer.username)
        assert retry_after(viewer.username) > 0

        updated = update_user(
            viewer.id,
            UserUpdate(role="operator", active=False, password="changed-password"),
            db,
            admin,
        )
        assert updated.role == "operator"
        assert updated.active is False
        assert verify_password("changed-password", updated.password_hash)
        assert retry_after(viewer.username) == 0

        with pytest.raises(HTTPException) as error:
            update_user(
                admin.id,
                UserUpdate(role="viewer", active=True),
                db,
                admin,
            )
        assert error.value.status_code == 409


def test_repeated_failed_logins_are_temporarily_rate_limited() -> None:
    reset_for_tests()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for _ in range(MAX_FAILURES):
            with pytest.raises(HTTPException) as error:
                login(LoginRequest(username="missing", password="not-the-password"), db)
            assert error.value.status_code == 401

        with pytest.raises(HTTPException) as error:
            login(LoginRequest(username="missing", password="not-the-password"), db)

        assert error.value.status_code == 429
        assert int(error.value.headers["Retry-After"]) > 0
    reset_for_tests()


def test_login_username_is_case_insensitive_and_trimmed() -> None:
    reset_for_tests()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            User(
                username="friend@example.com",
                password_hash=hash_password("correct-password"),
                role="viewer",
            )
        )
        db.commit()

        token = login(
            LoginRequest(username="  FRIEND@EXAMPLE.COM ", password="correct-password"), db
        )

        assert token.username == "friend@example.com"
    reset_for_tests()
