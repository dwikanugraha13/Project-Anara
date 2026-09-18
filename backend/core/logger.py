"""
logger.py — Rotating File & Console Logger for Project Anara.
Anara Standard Logging Engine.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from constants import get_anara_logs_dir


def setup_anara_logging(log_level: int = logging.INFO):
    """Sets up root and Anara loggers with rotating file sink in ANARA_HOME/logs."""
    log_dir = get_anara_logs_dir()
    log_file = log_dir / "anara.log"

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(log_level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)

    # Rotating file handler (max 10MB, keep 5 backups)
    try:
        fh = RotatingFileHandler(
            str(log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
            errors="replace",
        )
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        root_logger.addHandler(fh)
        root_logger.info(f"[Logger] Enterprise rotating logger active. File sink: {log_file}")
    except Exception as e:
        root_logger.warning(f"[Logger] Failed to initialize file log sink: {e}")

    # Reduce noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
