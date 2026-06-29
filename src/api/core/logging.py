"""
Structured JSON logging.

Configures the root logger to emit one JSON object per line with fields:
  timestamp, level, logger, message, request_id, and any extra fields passed
  via the `extra` kwarg.

Usage:
    from src.api.core.logging import setup_logging
    setup_logging()   # call once at startup

Log a request-correlated message anywhere in the codebase:
    import logging
    _logger = logging.getLogger(__name__)
    _logger.info("run completed", extra={"run_id": str(run.id), "duration_s": 4.2})
"""

import json
import logging
import sys
from datetime import datetime, timezone

from src.api.core.request_id import get_request_id


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id() or None,
        }
        # Merge any extra fields supplied via logger.xxx(..., extra={...})
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "taskiq"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
