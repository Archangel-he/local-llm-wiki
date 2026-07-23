from __future__ import annotations

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
    session_secret: str = "change-me-in-production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
