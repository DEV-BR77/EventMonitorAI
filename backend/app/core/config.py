from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NoiseMonitorAI"
    app_version: str = "0.1.0-alpha1"

    database_url: str = "sqlite:///./data/noisemonitorai.db"

    udp_port: int = 12345
    audio_sample_rate: int = 16000

    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()