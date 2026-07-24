"""RQ worker liveness for the API health aggregator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Worker


class WorkerHealthStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class WorkerHealth:
    status: WorkerHealthStatus
    active_workers: int
    safe_reason: str | None = None


def check_worker_health(
    connection: Redis,
    *,
    queue_name: str = "default",
) -> WorkerHealth:
    """Report workers currently registered for one queue.

    RQ registration keys have their own heartbeat TTL, so expired workers do
    not remain healthy merely because a stale application record exists.
    """

    try:
        queue = Queue(queue_name, connection=connection)
        workers = Worker.all(queue=queue)
    except (RedisError, ValueError):
        return WorkerHealth(
            WorkerHealthStatus.UNAVAILABLE,
            active_workers=0,
            safe_reason="redis_unavailable",
        )
    if not workers:
        return WorkerHealth(
            WorkerHealthStatus.UNAVAILABLE,
            active_workers=0,
            safe_reason="worker_not_registered",
        )
    return WorkerHealth(WorkerHealthStatus.OK, active_workers=len(workers))
