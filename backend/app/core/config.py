from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.version import __version__


class Settings(BaseSettings):
    app_name: str = "EventMonitorAI"
    app_version: str = __version__

    database_url: str = "sqlite:///./data/eventmonitorai.db"
    auth_secret: str = "development-only-change-me"
    access_token_minutes: int = 480
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = ""
    ingest_api_key: str = ""
    home_assistant_webhook_url: str = ""
    home_assistant_token: str = ""
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_subject: str = "mailto:admin@eventmonitor.eu"
    clip_directory: str = "/data/clips"
    person_media_directory: str = "/data/person-media"
    nightly_review_hour: int = 3
    support_url: str = ""
    support_target_eur: float = 1450
    support_collected_eur: float = 0
    public_base_url: str = "http://localhost:8000"
    resend_api_key: str = ""
    resend_from: str = "EventMonitorAI <noreply@eventmonitor.eu>"
    resend_reply_to: str = "kontakt@eventmonitor.eu"

    udp_port: int = 12345
    audio_sample_rate: int = 16000

    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.database_url.startswith("postgresql"):
            if self.auth_secret == "development-only-change-me" or len(self.auth_secret) < 32:
                raise ValueError(
                    "AUTH_SECRET muss im PostgreSQL-Betrieb mindestens 32 Zeichen haben"
                )
            if len(self.ingest_api_key) < 24:
                raise ValueError(
                    "INGEST_API_KEY muss im PostgreSQL-Betrieb mindestens 24 Zeichen haben"
                )
        if not 5 <= self.access_token_minutes <= 1440:
            raise ValueError("ACCESS_TOKEN_MINUTES muss zwischen 5 und 1440 liegen")
        return self


settings = Settings()
