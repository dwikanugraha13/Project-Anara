"""
loopbreaker.py — Dynamic Execution Sentinel & Loop Breaker for Project Anara.
Anara Standard execution safety:
1. Dynamically fingerprints tool invocations via cryptographic hashing (Zero-hardcode).
2. Detects identical call stalls (A -> A -> A -> A) and alternating ping-pong cycles (A -> B -> A -> B -> A -> B).
3. Injects internal self-healing reflections to let the model self-correct without crashing.
4. 100% free of content filtering, censorship, or self-restricting locks.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AnaraLoopBreaker:
    """
    Dynamic execution loop breaker for Anara Autonomous Agent turns.
    Tracks mathematical execution patterns to prevent runaway token exhaustion.
    """

    def __init__(
        self,
        max_identical: int = 4,
        max_consecutive_errors: int = 5,
        window_size: int = 16,
    ):
        self.max_identical = max_identical
        self.max_consecutive_errors = max_consecutive_errors
        self.call_history: deque[str] = deque(maxlen=window_size)
        self.tool_names: deque[str] = deque(maxlen=window_size)
        self.consecutive_errors: int = 0

    def _hash_call(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Dynamically computes SHA-256 fingerprint of any tool name and arguments."""
        try:
            serialized_args = json.dumps(args, sort_keys=True, default=str, ensure_ascii=False)
        except Exception:
            serialized_args = str(sorted(args.items())) if isinstance(args, dict) else str(args)

        payload = f"{tool_name.strip().lower()}:{serialized_args}"
        return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:16]

    def record_and_check(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Records a tool invocation and checks for repetitive loops.
        Returns: (is_stalled, self_healing_message)
        """
        clean_name = (tool_name or "").strip()
        call_hash = self._hash_call(clean_name, args or {})
        self.call_history.append(call_hash)
        self.tool_names.append(clean_name)

        # 1. Check for trailing identical calls (A -> A -> A -> A)
        if len(self.call_history) >= self.max_identical:
            recent = list(self.call_history)[-self.max_identical:]
            if len(set(recent)) == 1:
                msg = (
                    f"[SYSTEM REFLECTION: PENCEGAH LOOP AKTIF]: Kamu memanggil alat '{clean_name}' "
                    f"sebanyak {self.max_identical} kali berturut-turut dengan parameter yang sama persis tanpa kemajuan. "
                    "Hentikan pemanggilan berulang ini sekarang! Evaluasi hasil yang sudah diperoleh sebelumnya, "
                    "gunakan strategi/alat lain yang relevan, atau berikan kesimpulan jawaban akhir kepada pengguna."
                )
                logger.warning(f"[LoopBreaker] Identical call stall detected for tool '{clean_name}' ({self.max_identical}x).")
                return True, msg

        # 2. Check for alternating ping-pong cycles (A -> B -> A -> B -> A -> B)
        if len(self.call_history) >= 6:
            recent_6 = list(self.call_history)[-6:]
            if recent_6[0] == recent_6[2] == recent_6[4] and recent_6[1] == recent_6[3] == recent_6[5] and recent_6[0] != recent_6[1]:
                t1, t2 = list(self.tool_names)[-2], list(self.tool_names)[-1]
                msg = (
                    f"[SYSTEM REFLECTION: PENCEGAH LOOP AKTIF]: Terdeteksi siklus bolak-balik (ping-pong loop) "
                    f"antara alat '{t1}' dan '{t2}'. Evaluasi data yang telah kamu kumpulkan, "
                    "hentikan pengulangan ini, dan selesaikan giliran tugasmu sekarang."
                )
                logger.warning(f"[LoopBreaker] Ping-pong cycle detected between '{t1}' and '{t2}'.")
                return True, msg

        return False, None

    def record_result(self, is_error: bool) -> Tuple[bool, Optional[str]]:
        """
        Tracks consecutive error cascades to guide the model when stuck.
        """
        if is_error:
            self.consecutive_errors += 1
            if self.consecutive_errors >= self.max_consecutive_errors:
                msg = (
                    f"[SYSTEM REFLECTION]: Terdeteksi {self.consecutive_errors} kegagalan alat berturut-turut. "
                    "Tinjau kembali akar masalah dari pesan error sebelumnya dan ubah pendekatanmu."
                )
                logger.warning(f"[LoopBreaker] Consecutive error threshold hit ({self.consecutive_errors}).")
                return True, msg
        else:
            self.consecutive_errors = 0
        return False, None

    def reset(self) -> None:
        """Resets the loop breaker history."""
        self.call_history.clear()
        self.tool_names.clear()
        self.consecutive_errors = 0
