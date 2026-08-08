import base64
import hashlib
import hmac
import json
import time

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.dashboard import PushSubscription, User
from app.models.event import Event


def response_token(user_id: int, event_id: int) -> str:
    payload = {"user_id": user_id, "event_id": event_id, "exp": int(time.time()) + 86_400}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(
        b"="
    )
    signature = hmac.new(settings.auth_secret.encode(), body, hashlib.sha256).digest()
    return f"{body.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def decode_response_token(token: str) -> tuple[int, int]:
    try:
        body_text, signature_text = token.split(".", 1)
        body = body_text.encode()
        signature = base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
        expected = hmac.new(settings.auth_secret.encode(), body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body_text + "=" * (-len(body_text) % 4)))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError
        return int(payload["user_id"]), int(payload["event_id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid response token") from exc


def send_event_pushes(event_id: int) -> None:
    if not settings.vapid_private_key or not settings.vapid_public_key:
        return
    from app.database.session import engine

    with Session(engine) as db:
        event = db.get(Event, event_id)
        if event is None:
            return
        subscriptions = list(db.scalars(select(PushSubscription)).all())
        stale: list[int] = []
        for subscription in subscriptions:
            user = db.get(User, subscription.user_id)
            if user is None or not user.active:
                stale.append(subscription.id)
                continue
            payload = json.dumps(
                {
                    "title": f"Lärmereignis: {event.label_de or event.label}",
                    "body": f"{event.device} · {event.db_level:.1f} dB",
                    "event_id": event.id,
                    "response_token": response_token(user.id, event.id),
                }
            )
            try:
                webpush(
                    subscription_info={
                        "endpoint": subscription.endpoint,
                        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                    },
                    data=payload,
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject},
                    timeout=10,
                )
            except WebPushException as exc:
                if exc.response is not None and exc.response.status_code in (404, 410):
                    stale.append(subscription.id)
        if stale:
            db.execute(delete(PushSubscription).where(PushSubscription.id.in_(stale)))
            db.commit()
