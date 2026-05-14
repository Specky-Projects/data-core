from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "data-core"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    log_level: str = "INFO"
    log_json: bool = False

    database_url: str = Field(
        default="postgresql+psycopg://data_core:data_core@localhost:5432/data_core"
    )
    auto_create_tables: bool = False

    scheduler_enabled: bool = True
    scheduler_collectors_enabled: bool = True
    scheduler_pipeline_enabled: bool = True
    scheduler_domain_jobs_enabled: bool = True
    scheduler_timezone: str = "America/Sao_Paulo"
    worker_concurrency: int = 2
    worker_pipeline_interval_seconds: int = 300

    collector_default_max_retries: int = 3
    collector_default_retry_delay_seconds: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
