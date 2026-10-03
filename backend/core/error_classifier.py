"""
error_classifier.py — Upstream Model API Error Classification and Smart Recovery Ladder for Project Anara.

Maps raw provider exceptions (Google Gemini, OpenAI Codex, Anthropic, Custom HTTP endpoints)
into structured ClassifiedApiError instances with actionable recovery hints:
- Jittered exponential backoff for HTTP 429 rate limits
- API key rotation hints for HTTP 401/403 auth failures
- Immediate fallback model flags for HTTP 404 or permanent model blocks
- Context compression triggers for HTTP 413 or prompt context length overflows
"""

from __future__ import annotations

import enum
import math
import random
import re
from dataclasses import dataclass
from typing import Any, Optional


class AnaraFailoverReason(enum.Enum):
    """Why an upstream model API call failed — dictates intelligent recovery strategy."""
    auth = "auth"                           # 401/403: Invalid, expired, or missing key -> rotate credential
    billing = "billing"                     # 402: Quota or credit exhaustion -> rotate or alert
    rate_limit = "rate_limit"               # 429: Concurrency or RPM/TPM limit -> jittered backoff then retry
    overloaded = "overloaded"               # 503/529: Provider overloaded -> backoff and retry
    server_error = "server_error"           # 500/502: Internal server error -> retry
    timeout = "timeout"                     # Network/socket timeout -> retry with fresh client
    context_overflow = "context_overflow"   # 413 or context length exceeded -> trigger micro-compaction
    model_not_found = "model_not_found"     # 404 or unserved model slug -> fallback to secondary model
    format_error = "format_error"           # 400: Malformed tool schema or arguments -> strip and retry
    unknown = "unknown"                     # Unclassified failure -> exponential backoff retry


@dataclass
class ClassifiedApiError:
    """Actionable classification of an API error with execution recovery hints."""
    reason: AnaraFailoverReason
    status_code: Optional[int] = None
    message: str = ""
    provider: Optional[str] = None
    retryable: bool = False
    backoff_seconds: float = 0.0
    should_rotate_key: bool = False
    should_compress: bool = False
    should_fallback: bool = False
    raw_error: Optional[Exception] = None

    def __str__(self) -> str:
        return f"[ClassifiedApiError reason={self.reason.value} status={self.status_code} retryable={self.retryable} backoff={self.backoff_seconds:.1f}s]"


def calculate_jittered_backoff(
    attempt: int,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    jitter_factor: float = 0.5,
) -> float:
    """Calculates exponential backoff with decorrelated jitter to prevent thundering herd."""
    exp = min(attempt, 6)
    delay = min(base_delay * (2 ** exp), max_delay)
    jitter = delay * jitter_factor * (random.random() * 2 - 1)
    return max(0.5, delay + jitter)


def classify_api_error(
    exc: Exception,
    attempt: int = 1,
    provider: Optional[str] = None,
) -> ClassifiedApiError:
    """
    Classifies raw HTTP/API client exceptions into structured recovery directives.
    Inspects HTTP status codes, error response text, and canonical exception attributes.
    """
    if not isinstance(exc, Exception):
        return ClassifiedApiError(
            reason=AnaraFailoverReason.unknown,
            message=str(exc),
            provider=provider,
            retryable=False,
        )

    # 1. Extract status code if available
    status_code: Optional[int] = None
    for attr in ("status_code", "status", "http_status", "code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int) and 100 <= val <= 599:
            status_code = val
            break
        elif isinstance(val, str) and val.isdigit() and 100 <= int(val) <= 599:
            status_code = int(val)
            break

    text = str(exc).lower()

    # If status_code not explicitly on exception, search for common HTTP error patterns
    if status_code is None:
        m_status = re.search(r"\b(400|401|402|403|404|413|429|500|502|503|504|529)\b", text)
        if m_status:
            status_code = int(m_status.group(1))

    # 2. Context Length Overflow Detection
    context_patterns = (
        "context_length_exceeded",
        "maximum context length",
        "context window",
        "prompt is too long",
        "too many tokens",
        "input length exceeds",
        "max_tokens is too large",
        "resourceexhausted",
    )
    if status_code == 413 or any(p in text for p in context_patterns):
        return ClassifiedApiError(
            reason=AnaraFailoverReason.context_overflow,
            status_code=status_code or 413,
            message="Context window exceeded prompt limit; compaction required.",
            provider=provider,
            retryable=True,
            backoff_seconds=0.5,
            should_compress=True,
            raw_error=exc,
        )

    # 3. Rate Limit / Throttling Detection (HTTP 429)
    rate_limit_patterns = (
        "rate_limit_exceeded",
        "rate limit",
        "too many requests",
        "quota exceeded",
        "requests per minute",
        "tokens per minute",
        "tpm",
        "rpm",
    )
    if status_code == 429 or any(p in text for p in rate_limit_patterns):
        backoff = calculate_jittered_backoff(attempt, base_delay=3.0, max_delay=45.0)
        # Parse retry-after if provided in exception message
        m_retry_after = re.search(r"retry[- ]after[:\s]+(\d+(?:\.\d+)?)", text)
        if m_retry_after:
            try:
                backoff = max(backoff, float(m_retry_after.group(1)))
            except Exception:
                pass

        return ClassifiedApiError(
            reason=AnaraFailoverReason.rate_limit,
            status_code=429,
            message="Upstream API rate limit throttled request.",
            provider=provider,
            retryable=True,
            backoff_seconds=backoff,
            should_rotate_key=(attempt >= 2),
            should_fallback=(attempt >= 4),
            raw_error=exc,
        )

    # 4. Authentication / Authorization Failure (HTTP 401 / 403)
    auth_patterns = (
        "unauthorized",
        "invalid_api_key",
        "incorrect api key",
        "authentication",
        "forbidden",
        "permission_denied",
        "access denied",
    )
    if status_code in (401, 403) or any(p in text for p in auth_patterns):
        return ClassifiedApiError(
            reason=AnaraFailoverReason.auth,
            status_code=status_code or 401,
            message="Authentication failure with active API key.",
            provider=provider,
            retryable=True,
            backoff_seconds=1.0,
            should_rotate_key=True,
            should_fallback=True,
            raw_error=exc,
        )

    # 5. Billing / Credit Depletion (HTTP 402)
    billing_patterns = (
        "insufficient_quota",
        "billing",
        "credit balance is too low",
        "quota depleted",
        "payment required",
    )
    if status_code == 402 or any(p in text for p in billing_patterns):
        return ClassifiedApiError(
            reason=AnaraFailoverReason.billing,
            status_code=402,
            message="Billing balance or quota depleted for active provider key.",
            provider=provider,
            retryable=True,
            backoff_seconds=0.5,
            should_rotate_key=True,
            should_fallback=True,
            raw_error=exc,
        )

    # 6. Model Not Found / Invalid Endpoint (HTTP 404)
    model_patterns = (
        "model_not_found",
        "does not exist",
        "not found",
        "invalid model",
        "model is not available",
    )
    if status_code == 404 or any(p in text for p in model_patterns):
        return ClassifiedApiError(
            reason=AnaraFailoverReason.model_not_found,
            status_code=404,
            message="Specified model slug not found on provider.",
            provider=provider,
            retryable=True,
            backoff_seconds=0.2,
            should_fallback=True,
            raw_error=exc,
        )

    # 7. Provider Overload & Server Downtime (HTTP 500, 502, 503, 529)
    if status_code in (500, 502, 503, 504, 529) or "overloaded" in text or "bad gateway" in text:
        backoff = calculate_jittered_backoff(attempt, base_delay=2.0, max_delay=30.0)
        is_overloaded = status_code in (503, 529) or "overloaded" in text
        return ClassifiedApiError(
            reason=AnaraFailoverReason.overloaded if is_overloaded else AnaraFailoverReason.server_error,
            status_code=status_code or 500,
            message="Provider server error or capacity overload.",
            provider=provider,
            retryable=True,
            backoff_seconds=backoff,
            should_fallback=(attempt >= 3),
            raw_error=exc,
        )

    # 8. Timeout Failures
    if "timeout" in text or "timed out" in text or "connection reset" in text:
        backoff = calculate_jittered_backoff(attempt, base_delay=1.5, max_delay=20.0)
        return ClassifiedApiError(
            reason=AnaraFailoverReason.timeout,
            status_code=408,
            message="Connection or socket read timed out.",
            provider=provider,
            retryable=True,
            backoff_seconds=backoff,
            should_fallback=(attempt >= 3),
            raw_error=exc,
        )

    # 9. Bad Request / Format Parameter Error (HTTP 400)
    if status_code == 400:
        return ClassifiedApiError(
            reason=AnaraFailoverReason.format_error,
            status_code=400,
            message="Provider rejected request formatting or schema.",
            provider=provider,
            retryable=False,
            should_fallback=True,
            raw_error=exc,
        )

    # 10. Default / Unclassified Fallback
    return ClassifiedApiError(
        reason=AnaraFailoverReason.unknown,
        status_code=status_code,
        message=str(exc)[:300],
        provider=provider,
        retryable=(attempt <= 2),
        backoff_seconds=calculate_jittered_backoff(attempt, base_delay=2.0),
        raw_error=exc,
    )
