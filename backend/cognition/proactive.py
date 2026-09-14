"""
proactive_service.py

Anara Proactive Engine — turns Anara from a passive assistant that only answers
when spoken to, into one that takes sensible initiative.

Three kinds of initiative:
1. due_reminder  — a to-do whose `due_date` has arrived (that column existed in
                   the schema but was never used before)
2. greeting      — a context-aware welcome the first time a speaker is recognised
                   in a session ("Selamat pagi Agnan! Ada 3 tugas hari ini...")
3. follow_up     — gentle check-in on an active project that has not been
                   mentioned for a while

Safety rules (so Anara never becomes annoying):
- at most one initiative per PROACTIVE_MIN_GAP seconds
- never while the user is speaking or Anara is talking
- never during dance mode / media playback
- each reminder fires only once per session
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

WIB = timezone(timedelta(hours=7))

# Minimum seconds between two proactive messages
PROACTIVE_MIN_GAP = 600.0
# How often the scheduler wakes up
TICK_SECONDS = 30.0
# A project untouched for this long triggers a follow-up
PROJECT_STALE_DAYS = 2
# Fire reminders when the due time is within this window
DUE_WINDOW_MINUTES = 5


def _parse_due(raw: Optional[str]) -> Optional[datetime]:
    """
    Parses the free-form `due_date` column into an aware datetime (WIB).
    Accepts: '2026-08-29 14:30', '2026-08-29T14:30', '2026-08-29', '14:30', '14.30'.
    Bare times are interpreted as the next occurrence of that clock time.
    """
    if not raw:
        return None
    txt = str(raw).strip()
    if not txt:
        return None

    now = datetime.now(WIB)

    # Full date (+ optional time)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{1,2})[:.](\d{2}))?", txt)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh = int(m.group(4) or 0)
        mm = int(m.group(5) or 0)
        try:
            return datetime(y, mo, d, hh, mm, tzinfo=WIB)
        except ValueError:
            return None

    # Bare clock time -> next occurrence
    m = re.match(r"^(\d{1,2})[:.](\d{2})$", txt)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target

    return None


def _parse_sqlite_ts(raw: Optional[str]) -> Optional[datetime]:
    """Parses SQLite CURRENT_TIMESTAMP values (UTC) into aware datetimes."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _time_greeting(now: datetime) -> str:
    h = now.hour
    if h < 4:
        return "Masih larut"
    if h < 11:
        return "Selamat pagi"
    if h < 15:
        return "Selamat siang"
    if h < 18:
        return "Selamat sore"
    return "Selamat malam"


class ProactiveEngine:
    """
    Per-session proactive scheduler. One instance lives for the lifetime of a
    WebSocket connection.
    """

    def __init__(
        self,
        memory_engine: Any,
        emit: Callable[[Dict[str, Any]], Any],
        can_speak: Callable[[], bool],
        get_speaker: Callable[[], Optional[str]],
    ):
        """
        emit         — async callback that delivers the proactive payload
        can_speak    — returns True when it is safe to interrupt (idle, no media)
        get_speaker  — returns the currently identified speaker name (or None)
        """
        self.memory = memory_engine
        self.emit = emit
        self.can_speak = can_speak
        self.get_speaker = get_speaker

        self._last_emit_ts: float = 0.0
        self._greeted: Set[str] = set()
        self._fired_reminders: Set[int] = set()
        self._followed_up: Set[int] = set()
        self._task: Optional[asyncio.Task] = None
        self._started_at = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0.0

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("[Proactive] Engine started")

    def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("[Proactive] Engine stopped")

    # ── scheduler ─────────────────────────────────────────────────────────
    async def _loop(self):
        # Small delay so the session can settle (biometrics, context injection)
        await asyncio.sleep(8.0)
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[Proactive] Tick error: {e}")
            await asyncio.sleep(TICK_SECONDS)

    async def _tick(self):
        loop_now = asyncio.get_event_loop().time()
        if loop_now - self._last_emit_ts < PROACTIVE_MIN_GAP and self._last_emit_ts > 0:
            return
        if not self.can_speak():
            return

        speaker = self.get_speaker()

        # Priority order: due reminders > greeting > project follow-up
        payload = (
            self._check_due_reminders(speaker)
            or self._check_greeting(speaker)
            or self._check_project_follow_up(speaker)
        )
        if not payload:
            return

        self._last_emit_ts = loop_now
        logger.info(f"[Proactive] Emitting '{payload['kind']}': {payload['text'][:70]!r}")
        await self.emit(payload)

    # ── checks ────────────────────────────────────────────────────────────
    def _check_due_reminders(self, speaker: Optional[str]) -> Optional[Dict[str, Any]]:
        try:
            todos = self.memory.get_notes_and_todos(speaker_name=speaker)
        except Exception:
            return None

        now = datetime.now(WIB)
        window = timedelta(minutes=DUE_WINDOW_MINUTES)

        for t in todos:
            tid = t.get("id")
            if tid in self._fired_reminders:
                continue
            if t.get("is_completed"):
                continue
            due = _parse_due(t.get("due_date"))
            if not due:
                continue
            # Fire when we are inside [due - window, due + window]
            if abs((due - now).total_seconds()) > window.total_seconds():
                # Also fire for overdue items discovered on first pass
                if not (now > due and (now - due) < timedelta(hours=12)):
                    continue

            self._fired_reminders.add(tid)
            title = (t.get("title") or "tugas").strip()
            name_part = f"{speaker}, " if speaker else ""
            overdue = now > due + window
            if overdue:
                text = f"{name_part}pengingat: '{title}' sudah lewat waktunya ({due.strftime('%H:%M')} WIB)."
            else:
                text = f"{name_part}waktunya '{title}' sekarang ({due.strftime('%H:%M')} WIB)."
            return {
                "kind": "due_reminder",
                "text": text,
                "todo": {
                    "id": tid,
                    "title": title,
                    "due": due.strftime("%H:%M"),
                    "content": t.get("content"),
                },
            }
        return None

    def _check_greeting(self, speaker: Optional[str]) -> Optional[Dict[str, Any]]:
        if not speaker or speaker in self._greeted:
            return None
        self._greeted.add(speaker)

        now = datetime.now(WIB)
        greeting = _time_greeting(now)

        pending: List[str] = []
        try:
            todos = self.memory.get_notes_and_todos(speaker_name=speaker)
            pending = [
                (t.get("title") or "").strip()
                for t in todos
                if not t.get("is_completed") and (t.get("title") or "").strip()
            ]
        except Exception:
            pass

        if pending:
            first = pending[0]
            if len(pending) == 1:
                text = f"{greeting} {speaker}! Ada satu tugas yang menunggu: {first}."
            else:
                text = (
                    f"{greeting} {speaker}! Kamu punya {len(pending)} tugas hari ini, "
                    f"yang pertama: {first}."
                )
        else:
            text = f"{greeting} {speaker}! Senang kamu kembali. Ada yang bisa Anara bantu?"

        return {
            "kind": "greeting",
            "text": text,
            "todos": pending[:5],
        }

    def _check_project_follow_up(self, speaker: Optional[str]) -> Optional[Dict[str, Any]]:
        if not speaker:
            return None
        try:
            projects = self.memory.get_projects_for_speaker(speaker)
        except Exception:
            return None

        now_utc = datetime.now(timezone.utc)
        stale_cut = now_utc - timedelta(days=PROJECT_STALE_DAYS)

        for p in projects:
            pid = p.get("id")
            if pid in self._followed_up:
                continue
            if (p.get("status") or "active").lower() != "active":
                continue
            updated = _parse_sqlite_ts(p.get("updated_at")) or _parse_sqlite_ts(p.get("created_at"))
            if not updated or updated > stale_cut:
                continue

            self._followed_up.add(pid)
            name = (p.get("name") or "proyekmu").strip()
            days = max(1, (now_utc - updated).days)
            return {
                "kind": "follow_up",
                "text": (
                    f"{speaker}, sudah {days} hari sejak terakhir kita bahas proyek "
                    f"'{name}'. Gimana progresnya?"
                ),
                "project": {"id": pid, "name": name, "days": days},
            }
        return None
