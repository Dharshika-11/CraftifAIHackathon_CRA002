"""
CraftifAI PipeGen — Structured Logger
=======================================
Configures Python logging with optional JSON-formatted output for machine
consumption.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object.

    Fields: ``ts``, ``level``, ``logger``, ``message``, plus any extras
    attached via ``extra={...}`` on the log call.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge extra fields (skip internal attributes)
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord(
                "", 0, "", 0, "", (), None
            ).__dict__ and key not in ("message", "msg"):
                try:
                    json.dumps(val)  # only serialisable values
                    payload[key] = val
                except (TypeError, ValueError):
                    pass
        return json.dumps(payload, default=str)


def setup_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[str] = None,
) -> None:
    """Configure the root logger for the entire pipeline.

    Parameters
    ----------
    level : str
        Logging level name (``"DEBUG"``, ``"INFO"``, …).
    json_output : bool
        If ``True``, use :class:`JSONFormatter`.
    log_file : str or None
        If set, also write logs to this file.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any pre-existing handlers (avoid duplicates on re-init)
    root.handlers.clear()

    # Formatter
    if json_output:
        fmt = JSONFormatter()
    else:
        fmt = logging.Formatter(
            "%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
            datefmt="%H:%M:%S",
        )

    # Console handler
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        logging.info("Logging to file: %s", log_file)

    logging.info("Logging initialised — level=%s  json=%s", level, json_output)
