import smtplib
from email.message import EmailMessage

from app.core.config import settings


def email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def send_verification_email(recipient: str, verification_url: str) -> None:
    if not email_configured():
        raise RuntimeError("E-Mail-Versand ist noch nicht konfiguriert")
    message = EmailMessage()
    message["Subject"] = "EventMonitorAI – E-Mail-Adresse bestätigen"
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message.set_content(
        "Willkommen bei EventMonitorAI. Bestätigen Sie Ihre E-Mail-Adresse innerhalb von "
        f"24 Stunden über diesen Link:\n\n{verification_url}\n\n"
        "Falls Sie sich nicht registriert haben, ignorieren Sie diese Nachricht."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
