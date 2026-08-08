import json
import logging
from datetime import UTC, datetime
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.dashboard import NotificationRule
from app.models.event import Event

logger = logging.getLogger(__name__)


def _matches(rule: NotificationRule, event: Event) -> bool:
    return (
        rule.enabled
        and (rule.category == "*" or rule.category == event.category)
        and (rule.device == "*" or rule.device == event.device)
        and event.confidence >= rule.min_confidence
        and event.db_level >= rule.min_db_level
    )


def trigger_notifications(db: Session, event: Event) -> None:
    if not settings.home_assistant_webhook_url:
        return
    now = datetime.now(UTC)
    for rule in db.scalars(select(NotificationRule)).all():
        if not _matches(rule, event):
            continue
        if rule.last_triggered_at:
            last = datetime.fromisoformat(rule.last_triggered_at)
            if (now - last).total_seconds() < rule.cooldown_seconds:
                continue
        payload = json.dumps(
            {
                "event": "eventmonitorai_event",
                "rule": rule.name,
                "data": {
                    "id": event.id,
                    "timestamp": event.timestamp,
                    "category": event.category,
                    "label": event.label_de,
                    "confidence": event.confidence,
                    "db_level": event.db_level,
                    "device": event.device,
                },
            }
        ).encode()
        headers = {"Content-Type": "application/json"}
        if settings.home_assistant_token:
            headers["Authorization"] = f"Bearer {settings.home_assistant_token}"
        try:
            request = Request(settings.home_assistant_webhook_url, payload, headers, method="POST")
            with urlopen(request, timeout=5):  # noqa: S310
                pass
            rule.last_triggered_at = now.isoformat()
            db.commit()
        except OSError:
            logger.exception("Home Assistant notification failed for rule %s", rule.id)
