from __future__ import annotations

from unittest.mock import Mock

from app.api import health as health_module
from app.llm import LLMHealth, LLMHealthStatus, RuntimeModelProfile
from app.llm.bootstrap import bootstrap_runtime_profile
from app.llm.providers import OllamaAdapter
from app.services.llm import get_llm
from app.worker.health import WorkerHealth, WorkerHealthStatus


def test_bootstrap_profile_is_optional_and_provider_neutral() -> None:
    assert (
        bootstrap_runtime_profile(
            provider="ollama",
            base_url="http://host.docker.internal:11434",
            model_name="",
        )
        is None
    )

    profile = bootstrap_runtime_profile(
        provider="ollama",
        base_url="http://host.docker.internal:11434",
        model_name="qwen",
    )

    assert profile is not None
    assert profile.profile_id == "bootstrap-default"
    assert isinstance(get_llm(profile), OllamaAdapter)


async def test_health_uses_real_worker_status_and_degrades_for_llm(
    monkeypatch,
) -> None:
    redis_connection = Mock()
    redis_connection.ping.return_value = True
    monkeypatch.setattr(
        health_module.Redis,
        "from_url",
        lambda *args, **kwargs: redis_connection,
    )
    monkeypatch.setattr(
        health_module,
        "check_worker_health",
        lambda connection: WorkerHealth(WorkerHealthStatus.OK, active_workers=1),
    )

    async def unavailable_llm(profile: RuntimeModelProfile | None) -> LLMHealth:
        return LLMHealth(
            LLMHealthStatus.UNAVAILABLE,
            safe_reason="offline",
        )

    monkeypatch.setattr(health_module, "probe_default_llm", unavailable_llm)
    database = Mock()

    result = await health_module.health(database)

    assert result["status"] == "degraded"
    assert result["components"]["redis"] == "ok"
    assert result["components"]["worker"] == "ok"
    assert result["components"]["llm"] == "unavailable"
    redis_connection.close.assert_called_once_with()
