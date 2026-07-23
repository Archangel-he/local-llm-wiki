from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db

router = APIRouter(tags=["health"])


def _check_llm() -> str:
    """Check Ollama availability without importing heavy deps.

    In MVP 0 this always returns 'degraded' when LLM_BASE_URL is unreachable.
    """
    import urllib.request

    try:
        url = settings.llm_base_url.rstrip("/") + "/api/tags"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return "ok"
    except Exception:
        return "unavailable"


@router.get("/health")
def health(db: Session = Depends(get_db)):
    components: dict[str, str] = {
        "api": "ok",
        "postgres": "ok",
        "redis": "ok",
        "worker": "ok",
        "storage": "ok",
        "llm": "ok",
    }

    # Check PostgreSQL
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        components["postgres"] = "unavailable"

    # Check Redis
    import redis as redis_lib

    try:
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=3)
        r.ping()
    except Exception:
        components["redis"] = "unavailable"

    # Check Ollama (non-blocking)
    components["llm"] = _check_llm()

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
