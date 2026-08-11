import json
from urllib.request import Request, urlopen

from app.core.config import settings


def email_configured() -> bool:
    return bool(settings.resend_api_key and settings.resend_from)


def send_verification_email(recipient: str, verification_url: str) -> None:
    if not email_configured():
        raise RuntimeError("E-Mail-Versand ist noch nicht konfiguriert")
    payload = json.dumps({
        "from": settings.resend_from,
        "to": [recipient],
        "subject": "EventMonitorAI – E-Mail-Adresse bestätigen",
        "text": (
            "Willkommen bei EventMonitorAI. Bestätigen Sie Ihre E-Mail-Adresse innerhalb von "
            f"24 Stunden über diesen Link:\n\n{verification_url}\n\n"
            "Falls Sie sich nicht registriert haben, ignorieren Sie diese Nachricht."
        ),
    }).encode()
    request = Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "EventMonitorAI/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        if response.status not in (200, 201):
            raise RuntimeError(f"Resend antwortete mit HTTP {response.status}")
