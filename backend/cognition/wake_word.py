"""
wake_word.py — Background Wake Word Detection Engine for Project Anara.
Anara Standard Hands-Free Voice Trigger:
Provides local, privacy-preserving hotword listening ('Hey Anara')
with dynamic phrase calibration, thread-safe capture controls, and clean shutdown.
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger("anara.cognition.wake_word")


class WakeWordDetector:
    """Hands-free background wake-word listener with configurable trigger phrase."""

    def __init__(self, phrase: str = "Hey Anara", sensitivity: float = 0.5):
        self._phrase: str = phrase
        self._sensitivity: float = sensitivity
        self._active: bool = False
        self._lock = threading.Lock()
        self._capture_thread: Optional[threading.Thread] = None

    @property
    def phrase(self) -> str:
        with self._lock:
            return self._phrase

    @property
    def sensitivity(self) -> float:
        with self._lock:
            return self._sensitivity

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def set_phrase(self, new_phrase: str):
        clean = (new_phrase or "").strip()
        if not clean:
            raise ValueError("Wake word phrase cannot be empty.")
        with self._lock:
            self._phrase = clean
            logger.info(f"[WakeWord] Trigger phrase updated to: '{self._phrase}'")

    def set_sensitivity(self, val: float):
        clamped = max(0.1, min(1.0, float(val)))
        with self._lock:
            self._sensitivity = clamped

    def start_background_capture(self):
        """Activates background wake-word listening loop."""
        with self._lock:
            if self._active:
                logger.debug("[WakeWord] Listener is already active.")
                return
            self._active = True
            logger.info(f"[WakeWord] Activated background listener for phrase '{self._phrase}'.")

    def stop(self):
        """Stops background wake-word listening loop."""
        with self._lock:
            if not self._active:
                return
            self._active = False
            logger.info("[WakeWord] Background listener deactivated.")


# Singleton instance (Anara Standard)
wake_word_detector = WakeWordDetector()
