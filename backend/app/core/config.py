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

    udp_port: int = 12345
    audio_sample_rate: int = 16000

    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
