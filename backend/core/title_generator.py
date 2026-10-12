"""
Automatic session title generation from the user's opening message (Anara Standard).

Two stages, both off the critical path:
1. Instant deterministic title derived inline from user message (cannot fail, zero latency).
2. Asynchronous model upgrade via fast auxiliary LLM (cheap tier, thinking off, JSON constrained).

Enforces strict provenance authority: derived < llm < user.
A user title is never overwritten. Stage 2 upgrades stage 1.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Constants matching ground truth specifications
MAX_TITLE_INPUT_CHARS = 1000
MAX_DERIVED_TITLE_CHARS = 48
MAX_TITLE_WORDS = 12
TITLE_MAX_TOKENS = 128

PROMPT_GOOD_EXAMPLES = (
    "Fix login button on mobile",
    "Postgres connection pool exhaustion",
    "Friendly greeting",
)
PROMPT_VAGUE_EXAMPLE = "Code changes"

EXAMPLE_ECHO_REJECT = frozenset(
    t.lower() for t in PROMPT_GOOD_EXAMPLES if t != "Friendly greeting"
) | {PROMPT_VAGUE_EXAMPLE.lower()}

PROVISIONAL_GREETING_TITLE = "friendly greeting"

CONTROL_WRAPPERS = (
    ("<command-message>", "</command-message>"),
    ("<command-name>", "</command-name>"),
    ("<command-args>", "</command-args>"),
    ("<local-command-caveat>", "</local-command-caveat>"),
    ("<local-command-stderr>", "</local-command-stderr>"),
    ("<local-command-stdout>", "</local-command-stdout>"),
    ("<task-notification>", "</task-notification>"),
    ("<system-reminder>", "</system-reminder>"),
    ("<ide_opened_file>", "</ide_opened_file>"),
    ("<ide_selection>", "</ide_selection>"),
)

MACHINE_PREFIXES = (
    "[SYSTEM]",
    "[RUNTIME NOTE:",
    "[System note:",
    "[CONTEXT COMPACTION",
    "[System:",
    "[Runtime note:",
)

TITLE_PROMPT_TEMPLATE = (
    "You name chat sessions. Given the user's opening message, write a title "
    "that lets them find this conversation again in a list.\n\n"
    "Rules:\n"
    "- 3 to 7 words, sentence case (capitalize only the first word and proper nouns).\n"
    "- Name what the user wants DONE, not that they asked a question.\n"
    "- Keep technical terms, filenames, numbers, and error codes exact.\n"
    "- Drop filler words: the, this, my, a, an.\n"
    "- No trailing punctuation, no quotes, no tool names, no 'Title:' prefix.\n"
    "- Never answer the message. Name it.\n"
    "- Write the title in the same language as the user's message.\n"
    "- Always produce something, even for a bare greeting.\n"
    + "".join(f'Good: {{"title": "{t}"}}\n' for t in PROMPT_GOOD_EXAMPLES)
    + f'Too vague: {{"title": "{PROMPT_VAGUE_EXAMPLE}"}}\n'
    'Too long: {"title": "Investigate and fix the issue where the login button does not respond on mobile devices"}\n\n'
    'Reply with JSON only: {"title": "..."}'
)


def _strip_one_wrapper(text: str) -> str:
    lowered = text.lower()
    for open_tag, close_tag in CONTROL_WRAPPERS:
        if not lowered.startswith(open_tag):
            continue
        end = lowered.find(close_tag)
        if end == -1:
            return text[len(open_tag):].strip()
        return (text[end + len(close_tag):].strip() or text[len(open_tag):end].strip()).strip()
    return text


def strip_control_wrappers(text: str) -> str:
    """Remove leading control wrappers (nested too) so machine scaffolding reduces to the prose user typed."""
    current = (text or "").strip()
    for _ in range(len(CONTROL_WRAPPERS) * 2):
        stripped = _strip_one_wrapper(current)
        if stripped == current:
            break
        current = stripped
    return current


def is_titleable_user_message(user_message: str) -> bool:
    """False for machine-authored openers and empty turns."""
    if not isinstance(user_message, str) or not user_message.strip():
        return False
    stripped = user_message.lstrip()
    if any(stripped.startswith(prefix) for prefix in MACHINE_PREFIXES):
        return False
    return bool(strip_control_wrappers(user_message).strip())


def _first_line(text: str) -> str:
    return next((ln.strip() for ln in text.splitlines() if ln.strip()), "")


def _strip_title_prefix(text: str) -> str:
    t = text.strip()
    for prefix in ("title:", "topic:", "subject:"):
        if t.lower().startswith(prefix):
            return t[len(prefix):].strip()
    return t


def derive_title(user_message: str) -> Optional[str]:
    """
    Stage 1: Instant deterministic title from first line trimmed to a word boundary.
    Cannot fail, requires zero LLM calls.
    """
    if not is_titleable_user_message(user_message):
        return None
    cleaned = strip_control_wrappers(user_message)
    line = " ".join(_first_line(cleaned).split())
    if not line:
        return None
    if len(line) > MAX_DERIVED_TITLE_CHARS:
        cut = line[:MAX_DERIVED_TITLE_CHARS]
        space = cut.rfind(" ")
        line = (cut[:space] if space > MAX_DERIVED_TITLE_CHARS // 2 else cut).rstrip(" ,.;:—-") + "…"
    return line or None


def is_provisional_greeting_title(title: str) -> bool:
    """True if title is a bare greeting placeholder (so subsequent turn upgrades it)."""
    norm = re.sub(r"^[\W_]+|[\W_]+$", "", title.strip(), flags=re.UNICODE).lower()
    return norm in (
        PROVISIONAL_GREETING_TITLE,
        f"{PROVISIONAL_GREETING_TITLE} in chat",
        "greeting",
        "friendly greeting",
        "sapaan",
        "sapaan santai",
        "sapaan ramah",
        "halo",
        "hi",
    )


def is_prompt_example_echo(title: str) -> bool:
    """True when title echoes one of the prompt's example titles verbatim."""
    norm = re.sub(r"^[\W_]+|[\W_]+$", "", title.strip(), flags=re.UNICODE).lower()
    return norm in EXAMPLE_ECHO_REJECT


def _extract_json_title(raw: str) -> Optional[str]:
    """Extracts title from strict JSON or loose regex matching."""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("title"), str):
            return parsed["title"].strip()
    except (ValueError, TypeError):
        pass
    match = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
    if match:
        try:
            return json.loads(f'"{match.group(1)}"').strip()
        except Exception:
            return match.group(1).strip()
    return None


def clean_title(text: str) -> Optional[str]:
    """Normalizes model output into clean session title."""
    cleaned = _strip_title_prefix(" ".join((text or "").split()).strip("\"'").strip()).strip("\"'").strip().rstrip(".!,;:")
    if len(cleaned) > 80:
        cleaned = cleaned[:77].rstrip() + "..."
    return cleaned or None


def apply_instant_title(
    session_id: Any,
    user_message: str,
    title_callback: Optional[Callable[[str, str], None]] = None,
) -> Optional[str]:
    """
    Writes the derived title synchronously in turn prologue.
    Returns the title, or None if message is untitleable or session already has user/llm authority.
    """
    if not session_id or not user_message:
        return None
    try:
        from memory import memory_engine
        derived = derive_title(user_message)
        if not derived:
            return None
        ok = memory_engine.set_auto_title(session_id, derived, source="derived")
        if ok:
            logger.info(f"[TitleGenerator] Applied instant title for #{session_id}: '{derived}'")
            try:
                from shared_state import broadcast_agent_event
                broadcast_agent_event({
                    "type": "session_title_updated",
                    "sessionId": session_id,
                    "session_id": session_id,
                    "title": derived,
                    "source": "derived",
                })
            except Exception as e_bc:
                logger.debug(f"[TitleGenerator] Real-time instant title broadcast notice: {e_bc}")
            if title_callback:
                try:
                    title_callback(derived, "derived")
                except Exception:
                    pass
            return derived
    except Exception as e:
        logger.debug(f"[TitleGenerator] Instant title error: {e}")
    return None


async def generate_title_llm(user_message: str, timeout: float = 6.0) -> Optional[str]:
    """Calls fast auxiliary model to generate a concise, topic-focused title."""
    snippet = strip_control_wrappers(user_message)[:MAX_TITLE_INPUT_CHARS].strip()
    if not snippet:
        return None

    try:
        from core.capabilities import get_fast_auxiliary_model
        from providers.caller import call_universal_chat_model
        aux_model = get_fast_auxiliary_model()

        res = await asyncio.wait_for(
            call_universal_chat_model(
                model_id=aux_model,
                user_prompt=snippet,
                system_instruction=TITLE_PROMPT_TEMPLATE,
                max_tokens=TITLE_MAX_TOKENS,
                temperature=0.3,
                read_only=True,
                reasoning_effort="off",
            ),
            timeout=timeout,
        )

        raw = str(res or "").strip()
        fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
        if fenced:
            raw = fenced.group(1).strip()

        extracted = _extract_json_title(raw)
        if not extracted:
            # Prose fallback
            extracted = _strip_title_prefix(_first_line(raw)).strip("\"'").strip()

        if not extracted:
            return None

        # Guard 1: Answer-shaped output rejection (> 12 words means model answered the user)
        if len(extracted.split()) > MAX_TITLE_WORDS:
            logger.debug(f"[TitleGenerator] Rejected answer-shaped output ({len(extracted.split())} words > {MAX_TITLE_WORDS}): {extracted!r}")
            return None

        title = clean_title(extracted)
        if not title:
            return None

        if len(title.split()) > MAX_TITLE_WORDS:
            logger.debug(f"[TitleGenerator] Rejected answer-shaped output ({len(title.split())} words > {MAX_TITLE_WORDS}): {title!r}")
            return None

        # Guard 2: Prompt-example echo rejection
        if is_prompt_example_echo(title):
            logger.debug(f"[TitleGenerator] Rejected prompt-example echo title: {title!r}")
            return None

        return title
    except Exception as e:
        logger.debug(f"[TitleGenerator] LLM title generation notice: {e}")
        return None


async def auto_title_session_async(
    session_id: Any,
    user_message: str,
    title_callback: Optional[Callable[[str, str], None]] = None,
) -> Optional[str]:
    """
    Stage 2: Background model upgrade.
    Skips if session already holds an 'llm' or 'user' title.
    """
    if not session_id or not user_message:
        return None
    try:
        from memory import memory_engine
        sid = memory_engine._resolve_session_id(session_id) or session_id
        current = memory_engine.get_session(sid)
        if not current:
            return None

        # Check if already upgraded to llm or user
        curr_source = current.get("title_source")
        if curr_source in ("llm", "user"):
            return None

        title = await generate_title_llm(user_message)
        source = "llm"

        # If model generated bare greeting, tag as derived so next turn can upgrade
        if title and is_provisional_greeting_title(title):
            source = "derived"

        # Fallback to derived title if model produced nothing
        if not title:
            title = derive_title(user_message)
            source = "derived"

        if not title:
            return None

        ok = memory_engine.set_auto_title(sid, title, source=source)
        if ok:
            logger.info(f"[TitleGenerator] Auto-titled session #{sid}: '{title}' (source={source})")
            try:
                from shared_state import broadcast_agent_event
                broadcast_agent_event({
                    "type": "session_title_updated",
                    "sessionId": sid,
                    "session_id": sid,
                    "title": title,
                    "source": source,
                })
            except Exception as e_bc:
                logger.debug(f"[TitleGenerator] Real-time auto-title broadcast notice: {e_bc}")
            if title_callback:
                try:
                    title_callback(title, source)
                except Exception:
                    pass
            return title
    except Exception as e:
        logger.debug(f"[TitleGenerator] Auto-title background error: {e}")
    return None


def maybe_auto_title(
    session_id: Any,
    user_message: str,
    conversation_history: Optional[list] = None,
    title_callback: Optional[Callable[[str, str], None]] = None,
) -> Optional[asyncio.Task]:
    """
    Public entry point called in Turn Prologue before model starts streaming.
    Applies instant derived title immediately (Stage 1), then spawns background task
    to upgrade via LLM (Stage 2).
    """
    if not session_id or not user_message:
        return None
    if not is_titleable_user_message(user_message):
        return None

    try:
        from memory import memory_engine
        sid = memory_engine._resolve_session_id(session_id) or session_id
        current = memory_engine.get_session(sid)
        if current:
            curr_source = current.get("title_source")
            curr_title = (current.get("title") or "").strip()
            is_placeholder = (
                not curr_title
                or curr_title.lower() in ("new chat", "new session", "new project", "session", "chat")
                or curr_title.lower().startswith(("session #", "chat #", "telegram chat (", "web chat (", "discord chat ("))
            )
            # If user already typed custom title or already upgraded by LLM, skip
            if not is_placeholder and curr_source in ("llm", "user"):
                return None

        # 1. Apply Instant Derived Title (Inline, cannot fail)
        apply_instant_title(sid, user_message, title_callback)

        # 2. Spawn Asynchronous Model Upgrade (Stage 2)
        task = asyncio.create_task(
            auto_title_session_async(sid, user_message, title_callback)
        )
        return task
    except Exception as e:
        logger.debug(f"[TitleGenerator] maybe_auto_title error: {e}")
        return None
