from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api import auth
from app.api.auth import login, register, verify_email
from app.database.base import Base
from app.models.dashboard import AdminNotification, Tenant, TenantMembership, User
from app.schemas.dashboard import LoginRequest, RegistrationRequest


def test_registration_requires_email_confirmation(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sent = {}
    monkeypatch.setattr(auth, "email_configured", lambda: True)
    monkeypatch.setattr(auth, "send_verification_email", lambda recipient, url: sent.update(recipient=recipient, url=url))
    with Session(engine) as db:
        db.add(Tenant(id=1, name="Platform", slug="platform"))
        db.commit()
        result = register(RegistrationRequest(email="New.User@example.eu", password="secure-password"), db)
        assert result["message"] == "Bestätigungs-E-Mail wurde versendet"
        user = db.scalar(select(User).where(User.username == "new.user@example.eu"))
        assert user.active is False
        assert db.scalar(select(TenantMembership).where(TenantMembership.user_id == user.id)).active is False
        assert db.scalar(select(AdminNotification)).kind == "registration"
        token = sent["url"].split("token=", 1)[1]
        verify_email(token, db)
        response = login(LoginRequest(username="new.user@example.eu", password="secure-password"), db)
        assert response.username == "new.user@example.eu"
        assert response.role == "admin"


def test_registration_ui_is_linked_from_public_site() -> None:
    assert "?register=1" in open("website/public/index.html", encoding="utf-8").read()
    dashboard = open("frontend/index.html", encoding="utf-8").read()
    assert 'id="register-form"' in dashboard
    assert 'id="admin-notification-center"' in dashboard
