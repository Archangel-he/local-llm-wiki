from __future__ import annotations

from fastapi import APIRouter, Depends
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..llm import bootstrap_runtime_profile
from ..llm.health import probe_default_llm
from ..worker.health import check_worker_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: Session = Depends(get_db)):  # noqa: B008
    components: dict[str, str] = {
        "api": "ok",
        "postgres": "ok",
        "redis": "ok",
        "worker": "unavailable",
        "storage": "ok",
        "llm": "ok",
    }

    # Check PostgreSQL
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        components["postgres"] = "unavailable"

    # Check Redis and derive worker health from live RQ registrations.
    redis_connection: Redis | None = None
    try:
        redis_connection = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        redis_connection.ping()
        components["worker"] = check_worker_health(redis_connection).status.value
    except (RedisError, ValueError):
        components["redis"] = "unavailable"
        components["worker"] = "unavailable"
    finally:
        if redis_connection is not None:
            redis_connection.close()

    # Bootstrap settings are temporary; B can replace this with a DB loader.
    profile = bootstrap_runtime_profile(
        provider=settings.llm_provider,
        base_url=settings.llm_base_url,
        model_name=settings.llm_model,
    )
    components["llm"] = (await probe_default_llm(profile)).status.value

    # Determine overall status
    failed = [k for k, v in components.items() if v == "unavailable"]
    if "api" in failed or "postgres" in failed:
        overall = "unhealthy"
    elif failed:
        overall = "degraded"
    else:
        overall = "ok"

    return {
        "status": overall,
        "components": components,
    }
