"""Infrastructure-only jobs.

Business handlers begin in MVP1 and must accept a ``job_id`` only.  This probe
exists solely to verify Redis/RQ wiring and is never exposed by the API.
"""

from __future__ import annotations


def probe_job(probe_id: str) -> dict[str, str]:
    if not probe_id or len(probe_id) > 128:
        raise ValueError("probe_id must contain between 1 and 128 characters")
    return {"status": "ok", "probe_id": probe_id}
