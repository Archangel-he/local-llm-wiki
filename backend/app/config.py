from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "local"
    public_base_url: str = "http://localhost:8000"
    database_url: str = "postgresql+psycopg://wiki:wiki@postgres:5432/wiki"
    redis_url: str = "redis://redis:6379/0"
    storage_backend: str = "local"
    local_storage_path: str = "/app/storage"
    llm_provider: str = "ollama"
    llm_base_url: str = "http://host.docker.internal:11434"
    llm_model: str = ""
    max_upload_mb: int = 10
    job_max_attempts: int = 3
    parser_version: str = "mvp1-text-v1"
    rq_queue_name: str = "default"
    ingest_job_timeout_seconds: int = 900
    model_credential_key: SecretStr | None = None
    model_credential_key_version: int = 1
    session_secret: str = "change-me-in-production"
    default_user_email: str = "default-user@local.invalid"
    default_user_display_name: str = "Default User"
    default_workspace_name: str = "Default Workspace"
    default_workspace_slug: str = "default"
    default_llm_profile_key: str = "mock-default"
    mac_qwen36_enabled: bool = False
    mac_qwen36_base_url: str = "http://host.docker.internal:30000/v1"
    mac_qwen36_model: str = "qwen36-aggressive-q4km"
    spark_qwen36_enabled: bool = False
    spark_qwen36_base_url: str = "http://spark-tunnel:30000/v1"
    spark_qwen36_model: str = "qwen36-aggressive-q4km"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
