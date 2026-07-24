from __future__ import annotations

import os

import pytest
from redis import Redis
from rq import Queue, SimpleWorker

from app.worker.health import WorkerHealthStatus, check_worker_health
from app.worker.jobs import probe_job

pytestmark = pytest.mark.integration


@pytest.fixture
def redis_connection() -> Redis:
    url = os.environ.get("REDIS_TEST_URL")
    if not url:
        pytest.skip("Set REDIS_TEST_URL to an isolated, disposable Redis database")
    connection = Redis.from_url(url)
    connection.ping()
    connection.flushdb()
    yield connection
    connection.flushdb()
    connection.close()


def test_probe_job_executes_through_rq(redis_connection: Redis) -> None:
    queue = Queue("default", connection=redis_connection)
    job = queue.enqueue(probe_job, "integration-probe")
    worker = SimpleWorker([queue], connection=redis_connection)

    assert worker.work(burst=True, logging_level="WARNING") is True
    job.refresh()
    assert job.result == {"status": "ok", "probe_id": "integration-probe"}


def test_worker_registration_drives_health(redis_connection: Redis) -> None:
    queue = Queue("default", connection=redis_connection)
    worker = SimpleWorker([queue], connection=redis_connection)

    worker.register_birth()
    try:
        healthy = check_worker_health(redis_connection)
        assert healthy.status is WorkerHealthStatus.OK
        assert healthy.active_workers == 1
    finally:
        worker.register_death()

    stopped = check_worker_health(redis_connection)
    assert stopped.status is WorkerHealthStatus.UNAVAILABLE
