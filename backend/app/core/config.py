from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EventMonitorAI"
    app_version: str = "0.1.0-alpha1"

    database_url: str = "sqlite:///./data/eventmonitorai.db"
    auth_secret: str = "development-only-change-me"
    access_token_minutes: int = 480
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = ""
    ingest_api_key: str = ""
    home_assistant_webhook_url: str = ""
    home_assistant_token: str = ""

    udp_port: int = 12345
    audio_sample_rate: int = 16000

    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
