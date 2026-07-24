"""Container entry point for the shared worker implementation."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.worker.runner import main


def run() -> int:
    """Start the application worker and return its process exit code."""

    return main()


if __name__ == "__main__":
    raise SystemExit(run())
