"""RQ entry points. Business jobs accept identifiers only."""

from __future__ import annotations

from app.ingest.pipeline import run_ingest_job
from app.services.exports import run_export_job


def probe_job(probe_id: str) -> dict[str, str]:
    if not probe_id or len(probe_id) > 128:
        raise ValueError("probe_id must contain between 1 and 128 characters")
    return {"status": "ok", "probe_id": probe_id}


def ingest_job(job_id: str) -> None:
    """Execute one persisted ingest Job without accepting secrets or file data."""

    run_ingest_job(job_id)


def export_job(job_id: str) -> None:
    """Create one persisted Obsidian-compatible Vault export."""

    run_export_job(job_id)
