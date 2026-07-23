from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import redis
from rq import Connection, Worker

from app.config import settings


def run() -> None:
    """Start an RQ worker listening on the default queue."""
    redis_conn = redis.from_url(settings.redis_url)
    with Connection(redis_conn):
        w = Worker(["default"])
        w.work()


if __name__ == "__main__":
    run()
