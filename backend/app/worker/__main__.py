"""Allow local execution with ``python -m app.worker``."""

from app.worker.runner import main

if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
