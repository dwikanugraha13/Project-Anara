"""
context_pin.py — Context Pinning System for Project Anara.
Parity with Hermes Agent context_pin & conversation_compression pinning (Nous Research).

Allows users, system architects, and agents to PIN critical instructions, database schemas,
project rules, or active documents with immunity from rolling context compaction.
Pinned items are never pruned or summarized into lossy capsules.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger("anara.core.context_pin")


class ContextPinManager:
    """Thread-safe registry for session-scoped and workspace-scoped pinned context items."""

    _instance: Optional[ContextPinManager] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        # Map: session_id -> dict of label -> {label, content, created_at}
        self._pins: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._mutex = threading.Lock()

    @classmethod
    def get_instance(cls) -> ContextPinManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = ContextPinManager()
            return cls._instance

    def pin(self, session_id: str, label: str, content: str) -> None:
        """Pins a critical instruction or file content for a given session."""
        import time
        sid = str(session_id or "default")
        with self._mutex:
            if sid not in self._pins:
                self._pins[sid] = {}
            self._pins[sid][label] = {
                "label": label,
                "content": content.strip(),
                "timestamp": time.time(),
            }
        logger.info(f"[ContextPin] Pinned item '{label}' for session '{sid}' ({len(content)} chars).")

    def unpin(self, session_id: str, label: str) -> bool:
        """Removes a pin for a given session."""
        sid = str(session_id or "default")
        with self._mutex:
            if sid in self._pins and label in self._pins[sid]:
                del self._pins[sid][label]
                logger.info(f"[ContextPin] Unpinned item '{label}' for session '{sid}'.")
                return True
        return False

    def list_pins(self, session_id: str) -> List[Dict[str, Any]]:
        """Returns all pinned context items for a given session."""
        sid = str(session_id or "default")
        with self._mutex:
            return list(self._pins.get(sid, {}).values())

    def render_pinned_capsule(self, session_id: str) -> str:
        """Renders all pinned items into an immutable prompt capsule."""
        pins = self.list_pins(session_id)
        if not pins:
            return ""
        blocks = []
        for p in pins:
            blocks.append(f"### [PINNED] {p['label']}:\n{p['content']}")
        return "\n\n[IMMUTABLE PINNED CONTEXT (PRESERVED ACROSS COMPACTION)]:\n" + "\n\n".join(blocks) + "\n\n"

    def clear(self, session_id: str) -> None:
        """Clears all pins for a session."""
        sid = str(session_id or "default")
        with self._mutex:
            self._pins.pop(sid, None)


# Global singleton instance
context_pin_manager = ContextPinManager.get_instance()


def is_item_pinned(item: Any) -> bool:
    """Helper to detect if a message turn or content object carries pinned status."""
    if not isinstance(item, dict):
        return False
    return bool(item.get("pinned") or item.get("is_pinned") or item.get("_pinned"))
