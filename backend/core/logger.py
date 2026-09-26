"""
logger.py — Rotating File & Console Logger for Project Anara.
Anara Enterprise Architecture: Secret redaction, ANSI stripping,
and Windows-safe file rollover.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
from typing import Optional

from constants import get_anara_logs_dir

# ---------------------------------------------------------------------------
# Sensitive Data Scrubbing Patterns (Anara Enterprise Architecture)
# ---------------------------------------------------------------------------
_SECRET_PATTERNS = [
    re.compile(r"AIzaSy[A-Za-z0-9_-]{33}"),                         # Google AI Studio Legacy
    re.compile(r"AQ\.[A-Za-z0-9_-]{30,}"),                         # Google AI Studio Modern
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),                          # OpenAI / General API Keys
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),                      # Anthropic API Keys
    re.compile(r"ghp_[A-Za-z0-9]{36}"),                            # GitHub PAT Classic
    re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),                   # GitHub PAT Fine-grained
    re.compile(r"hf_[A-Za-z0-9]{34,}"),                            # Hugging Face Token
    re.compile(r"(?i)(/bot|\bbot)\d{8,12}:[A-Za-z0-9_-]{20,50}"), # Telegram Bot Token in URL
    re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{20,50}\b"),              # Telegram Bot Token Bare
    re.compile(r"\b[A-Za-z0-9_-]{24,26}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,38}\b"),  # Discord Bot Token
    re.compile(r"(https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/)[A-Za-z0-9_-]+"),  # Discord Webhook
    re.compile(r"(?i)(authorization:\s*(?:Bearer\s+|Bot\s+|Basic\s+)?)[^\s,;]+"),  # Authorization Headers
    re.compile(r"(?i)(token=|api_key=|key=|password=|secret=|client_secret=|passwd=|access_token=|auth_token=|refresh_token=)[^&\s]+"),  # Sensitive Query/Form params
    re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9_-]+ )?PRIVATE KEY-----"),  # Private Keys
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),               # Slack Tokens
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                           # AWS Access Key ID
    re.compile(r"(?i)(aws_secret_access_key\s*[:=]\s*)[A-Za-z0-9/+=]{40}"),  # AWS Secret Access Key
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),  # JWT Tokens
    re.compile(r"(?i)((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^:]+:)[^@]+(@)"),  # Database URLs with password
]

_ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def redact_sensitive_text(text: str) -> str:
    """Masks credentials, API keys, and sensitive tokens (Anara Standard)."""
    if not isinstance(text, str) or not text:
        return text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups == 2:
            text = pattern.sub(r"\g<1>[REDACTED]\g<2>", text)
        elif pattern.groups == 1:
            text = pattern.sub(r"\g<1>[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED_SECRET]", text)
    return text


def strip_ansi(text: str) -> str:
    """Removes terminal escape color sequences from file sinks."""
    return _ANSI_ESCAPE_RE.sub("", text)


class AnaraRedactingFormatter(logging.Formatter):
    """Formatter that strips ANSI sequences for files and redacts secrets."""

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, is_file: bool = False):
        super().__init__(fmt, datefmt)
        self.is_file = is_file

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        if self.is_file:
            formatted = strip_ansi(formatted)
        return redact_sensitive_text(formatted)


class WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that catches Windows permission errors on file rollover gracefully."""

    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError):
            # On Windows, open handles from other threads or virus scanners can trigger WinError 32
            pass


def setup_anara_logging(log_level: int = logging.INFO):
    """Sets up root and Anara loggers with rotating file sink and sensitive data redaction."""
    log_dir = get_anara_logs_dir()
    log_file = log_dir / "anara.log"

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(log_level)

    console_formatter = AnaraRedactingFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        is_file=False,
    )
    file_formatter = AnaraRedactingFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        is_file=True,
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(console_formatter)
    root_logger.addHandler(ch)

    # Rotating file handler (max 10MB, keep 5 backups)
    try:
        fh = WindowsSafeRotatingFileHandler(
            str(log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
            errors="replace",
        )
        fh.setLevel(log_level)
        fh.setFormatter(file_formatter)
        root_logger.addHandler(fh)
        root_logger.info(f"[Logger] Enterprise rotating logger active. File sink: {log_file}")
    except Exception as e:
        root_logger.warning(f"[Logger] Failed to initialize file log sink: {e}")

    # Reduce noisy libraries
    noisy = [
        "uvicorn.access", "watchfiles", "httpcore", "httpx",
        "websockets", "websockets.client", "websockets.server",
        "google.genai", "google.auth", "urllib3"
    ]
    for n in noisy:
        logging.getLogger(n).setLevel(logging.WARNING)
