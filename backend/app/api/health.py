from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..llm import bootstrap_runtime_profile
from ..llm.health import probe_default_llm
from ..models import ModelProfile, Workspace
from ..seed import DEFAULT_WORKSPACE_ID
from ..services.model_profiles import runtime_profile
from ..services.storage import get_storage
from ..worker.health import check_worker_health

router = APIRouter(tags=["health"])


def _selected_runtime_profile(db: Session):
    try:
        profile = db.scalar(
            select(ModelProfile)
            .join(Workspace, Workspace.default_model_profile_id == ModelProfile.id)
            .where(
                Workspace.id == DEFAULT_WORKSPACE_ID,
                Workspace.status == "active",
                ModelProfile.status == "active",
            )
        )
    except SQLAlchemyError:
        profile = None
    if isinstance(profile, ModelProfile):
        try:
            return runtime_profile(profile)
        except (RuntimeError, ValueError):
            return None
    return bootstrap_runtime_profile(
        provider=settings.llm_provider,
        base_url=settings.llm_base_url,
        model_name=settings.llm_model,
    )


@router.get("/health")
async def health(request: Request, db: Session = Depends(get_db)):  # noqa: B008
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

    try:
        if not get_storage().health():
            components["storage"] = "unavailable"
    except Exception:
        components["storage"] = "unavailable"

    profile = _selected_runtime_profile(db)
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
        "request_id": request.state.request_id,
    }
