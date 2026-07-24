"""Shared RQ worker runner used by the container and local entry points."""

from __future__ import annotations

import logging
import os

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Worker

from app.worker.config import queue_name, redis_url

LOGGER = logging.getLogger("wiki.worker")


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        resolved_queue = queue_name(os.environ)
        connection = Redis.from_url(
            redis_url(os.environ),
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        connection.ping()
    except (RedisError, ValueError):
        # Do not log the Redis URL: it may contain credentials.
        LOGGER.error("worker_startup_failed reason=redis_unavailable_or_invalid_config")
        return 2

    queue = Queue(resolved_queue, connection=connection)
    worker = Worker([queue], connection=connection)
    LOGGER.info("worker_starting queue=%s", resolved_queue)
    try:
        completed_normally = worker.work(with_scheduler=False)
    except RedisError:
        LOGGER.error("worker_stopped reason=redis_unavailable")
        return 3
    return 0 if completed_normally else 1


if __name__ == "__main__":  # pragma: no cover - exercised by process smoke tests
    raise SystemExit(main())
