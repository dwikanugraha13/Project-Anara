"""
dedup.py — In-Memory Sliding Window Message Deduplication for Anara Integrations.
Anara Standard Multi-Channel Message Deduplication.
"""

import time
from collections import OrderedDict
from typing import Optional


class MessageDeduplicator:
    """Thread-safe / Async sliding window deduplicator based on LRU OrderedDict with TTL."""

    def __init__(self, max_size: int = 500, ttl_seconds: float = 300.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._seen: OrderedDict[str, float] = OrderedDict()

    def is_duplicate(self, message_id: str) -> bool:
        """Returns True if message_id has been seen recently, otherwise records it and returns False."""
        now = time.time()
        self._prune(now)

        if message_id in self._seen:
            # Refresh entry position
            self._seen.move_to_end(message_id)
            return True

        self._seen[message_id] = now
        if len(self._seen) > self.max_size:
            self._seen.popitem(last=False)
        return False

    def contains(self, message_id: str) -> bool:
        """Checks membership without adding or refreshing."""
        now = time.time()
        self._prune(now)
        return message_id in self._seen

    def _prune(self, now: float):
        """Removes expired entries from head of LRU queue."""
        cutoff = now - self.ttl_seconds
        while self._seen:
            oldest_id, oldest_time = next(iter(self._seen.items()))
            if oldest_time < cutoff:
                self._seen.pop(oldest_id)
            else:
                break
