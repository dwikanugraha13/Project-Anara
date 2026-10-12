"""
dedup.py — In-Memory Sliding Window Message Deduplication for Anara Integrations.
Hermes Agent gateway/platforms/helpers.py parity.
"""

import hashlib
import threading
import time
from collections import OrderedDict
from typing import Optional


class MessageDeduplicator:
    """Thread-safe sliding window deduplicator based on LRU OrderedDict with TTL (Hermes Parity)."""

    def __init__(self, max_size: int = 500, ttl_seconds: float = 300.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def is_duplicate(self, message_id: Optional[str]) -> bool:
        """Returns True if message_id has been seen recently, otherwise records it and returns False."""
        if not message_id:
            return False
        clean_id = str(message_id).strip()
        if not clean_id:
            return False

        now = time.time()
        with self._lock:
            self._prune(now)
            if clean_id in self._seen:
                # Refresh entry position
                self._seen.move_to_end(clean_id)
                return True

            self._seen[clean_id] = now
            if len(self._seen) > self.max_size:
                self._seen.popitem(last=False)
            return False

    def is_content_duplicate(self, sender_id: str, content: str, window_seconds: float = 5.0) -> bool:
        """
        Secondary fingerprint check: prevents duplicate processing when upstream
        retries identical text under different or absent message IDs (replay storm guard).
        """
        if not content or not content.strip():
            return False
        digest = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()[:16]
        key = f"content:{sender_id}:{digest}"
        now = time.time()
        with self._lock:
            self._prune(now)
            if key in self._seen:
                if now - self._seen[key] < window_seconds:
                    return True
                del self._seen[key]
            self._seen[key] = now
            return False

    def contains(self, message_id: str) -> bool:
        """Checks membership without adding or refreshing."""
        if not message_id:
            return False
        now = time.time()
        with self._lock:
            self._prune(now)
            return message_id in self._seen

    def discard(self, message_id: Optional[str]) -> None:
        """Releases a claimed message ID after cancelled or failed handoff."""
        if not message_id:
            return
        with self._lock:
            self._seen.pop(str(message_id).strip(), None)

    def clear(self) -> None:
        """Clears all tracked message IDs."""
        with self._lock:
            self._seen.clear()

    def _prune(self, now: float):
        """Removes expired entries from head of LRU queue."""
        cutoff = now - self.ttl_seconds
        while self._seen:
            oldest_id, oldest_time = next(iter(self._seen.items()))
            if oldest_time < cutoff:
                self._seen.pop(oldest_id)
            else:
                break


inbound_deduplicator = MessageDeduplicator(max_size=2000, ttl_seconds=300.0)

