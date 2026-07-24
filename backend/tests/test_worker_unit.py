from __future__ import annotations

import logging
from unittest.mock import Mock, patch

import pytest
from redis.exceptions import ConnectionError

from app.worker.config import DEFAULT_REDIS_URL, queue_name, redis_url
from app.worker.health import WorkerHealthStatus, check_worker_health
from app.worker.jobs import probe_job
from app.worker.runner import main


def test_worker_config_defaults_and_rejects_non_default_queue() -> None:
    assert redis_url({}) == DEFAULT_REDIS_URL
    assert queue_name({}) == "default"
    with pytest.raises(ValueError):
        queue_name({"RQ_QUEUE_NAME": "priority"})


def test_probe_job_is_deterministic_and_validated() -> None:
    assert probe_job("probe-1") == {"status": "ok", "probe_id": "probe-1"}
    with pytest.raises(ValueError):
        probe_job("")


def test_worker_health_uses_rq_registration() -> None:
    connection = Mock()
    with patch("app.worker.health.Worker.all", return_value=[Mock(), Mock()]):
        result = check_worker_health(connection)

    assert result.status is WorkerHealthStatus.OK
    assert result.active_workers == 2


def test_worker_health_reports_no_registration() -> None:
    connection = Mock()
    with patch("app.worker.health.Worker.all", return_value=[]):
        result = check_worker_health(connection)

    assert result.status is WorkerHealthStatus.UNAVAILABLE
    assert result.safe_reason == "worker_not_registered"


def test_worker_startup_failure_does_not_log_redis_credentials(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "redis-password-must-not-leak"
    monkeypatch.setenv("REDIS_URL", f"redis://user:{secret}@redis.invalid:6379/0")
    fake_connection = Mock()
    fake_connection.ping.side_effect = ConnectionError("unsafe upstream detail")

    with (
        patch("app.worker.runner.Redis.from_url", return_value=fake_connection),
        caplog.at_level(logging.ERROR),
    ):
        exit_code = main()

    assert exit_code == 2
    assert secret not in caplog.text
    assert "unsafe upstream detail" not in caplog.text
