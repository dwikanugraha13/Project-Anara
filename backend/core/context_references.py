"""
context_references.py — Pre-Flight Context Grounding & Reference Expansion for Project Anara.
Hermes Parity: Expands @file:, @folder:, @diff, and @staged directives inline in the turn prologue.

Provides immediate zero-turn context injection for files, folders, and git diffs,
bypassing the latency and token overhead of an initial tool-round discovery turn.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("anara.core.context_references")

_MAX_REFERENCES_PER_TURN = 16
_MAX_CHARS_PER_REFERENCE = 12000

_QUOTED_REFERENCE_VALUE = r'(?:`[^`\n]+`|"[^"\n]+"|\'[^\'\n]+\')'
_REFERENCE_PATTERN = re.compile(
    rf"(?<![\w/])@(?:(?P<simple>diff|staged)\b|(?P<kind>file|folder|git):(?P<value>{_QUOTED_REFERENCE_VALUE}(?::\d+(?:-\d+)?)?|\S+))"
)

_FILE_VALUE_PATTERN = re.compile(
    r'^(?:(?P<quote>`|"|\')(?P<qpath>.+?)(?P=quote)|(?P<path>.+?))(?::(?P<start>\d+)(?:-(?P<end>\d+))?)?$'
)

_EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "bash",
    ".bash": "bash",
    ".ps1": "powershell",
    ".sql": "sql",
}


@dataclass(frozen=True)
class ContextReference:
    raw: str
    kind: str
    target: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None


def parse_context_references(text: str) -> List[ContextReference]:
    """Parses @file:, @folder:, @diff, and @staged references from text."""
    if not isinstance(text, str) or "@" not in text:
        return []

    refs: List[ContextReference] = []
    seen = set()

    for m in _REFERENCE_PATTERN.finditer(text):
        if len(refs) >= _MAX_REFERENCES_PER_TURN:
            break

        simple = m.group("simple")
        if simple:
            raw = m.group(0)
            if raw not in seen:
                seen.add(raw)
                refs.append(ContextReference(raw=raw, kind=simple, target=simple))
            continue

        kind = m.group("kind")
        val = m.group("value") or ""
        raw = m.group(0)
        if not val or raw in seen:
            continue

        if kind == "file":
            fm = _FILE_VALUE_PATTERN.match(val)
            if fm:
                path = fm.group("qpath") or fm.group("path") or ""
                start = int(fm.group("start")) if fm.group("start") else None
                end = int(fm.group("end")) if fm.group("end") else start
                seen.add(raw)
                refs.append(ContextReference(
                    raw=raw,
                    kind="file",
                    target=path,
                    line_start=start,
                    line_end=end,
                ))
        elif kind in ("folder", "git"):
            clean_val = val.strip('`"\'')
            seen.add(raw)
            refs.append(ContextReference(raw=raw, kind=kind, target=clean_val))

    return refs


def _read_file_grounding(ref: ContextReference, base_dir: Path, max_chars: int) -> str:
    """Safely reads a file or line slice and returns a markdown fenced block."""
    try:
        from core.binary_guard import is_binary_filename
        if is_binary_filename(ref.target):
            return f"[Binary file skipped: {ref.target}]"
    except Exception:
        pass

    target_path = (base_dir / ref.target).resolve()
    if not target_path.exists() or not target_path.is_file():
        # Try relative to cwd
        target_path = Path(ref.target).resolve()
        if not target_path.exists() or not target_path.is_file():
            return f"[Grounding error: file '{ref.target}' not found]"

    ext = target_path.suffix.lower()
    lang = _EXT_TO_LANG.get(ext, "")

    try:
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if ref.line_start is not None:
            s_idx = max(0, ref.line_start - 1)
            e_idx = ref.line_end if ref.line_end is not None else len(lines)
            selected = lines[s_idx:e_idx]
            range_info = f":{ref.line_start}-{ref.line_end if ref.line_end else len(lines)}"
        else:
            selected = lines
            range_info = ""

        content = "".join(selected)
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n... [Truncated at {max_chars} chars]"

        return f"```{lang}\n# {ref.target}{range_info}\n{content}\n```"
    except Exception as e:
        return f"[Grounding error reading '{ref.target}': {e}]"


def _read_folder_grounding(ref: ContextReference, base_dir: Path) -> str:
    """Lists entries inside a directory."""
    folder_path = (base_dir / ref.target).resolve()
    if not folder_path.exists() or not folder_path.is_dir():
        folder_path = Path(ref.target).resolve()
        if not folder_path.exists() or not folder_path.is_dir():
            return f"[Grounding error: directory '{ref.target}' not found]"

    try:
        entries = []
        for root, dirs, files in os.walk(folder_path):
            rel_root = os.path.relpath(root, folder_path)
            for d in sorted(dirs[:20]):
                entries.append(f"📁 {os.path.join(rel_root, d) if rel_root != '.' else d}/")
            for f in sorted(files[:30]):
                entries.append(f"📄 {os.path.join(rel_root, f) if rel_root != '.' else f}")
            break  # Top-level only for compact grounding

        joined = "\n".join(entries[:50])
        return f"```\n# Directory: {ref.target}\n{joined}\n```"
    except Exception as e:
        return f"[Grounding error listing '{ref.target}': {e}]"


def _read_git_diff(staged: bool = False, max_chars: int = _MAX_CHARS_PER_REFERENCE) -> str:
    """Runs git diff or git diff --cached with bounded execution."""
    cmd = ["git", "diff", "--cached"] if staged else ["git", "diff"]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5.0,
            errors="replace",
        )
        out = (res.stdout or "").strip()
        if not out:
            return f"[No {'staged ' if staged else ''}git diff present]"
        if len(out) > max_chars:
            out = out[:max_chars] + f"\n... [Truncated at {max_chars} chars]"
        return f"```diff\n# {'git diff --cached' if staged else 'git diff'}\n{out}\n```"
    except Exception as e:
        return f"[Git diff error: {e}]"


def expand_context_references(
    text: str,
    cwd: Optional[str] = None,
    max_chars_per_ref: int = _MAX_CHARS_PER_REFERENCE,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Expands all @file, @folder, @diff, and @staged references in text.
    Returns (expanded_text, list_of_expanded_reference_metadata).
    """
    refs = parse_context_references(text)
    if not refs:
        return text, []

    base_dir = Path(cwd).resolve() if cwd else Path.cwd()
    expanded_blocks: List[str] = []
    metadata: List[Dict[str, Any]] = []

    for ref in refs:
        if ref.kind == "file":
            block = _read_file_grounding(ref, base_dir, max_chars_per_ref)
            expanded_blocks.append(f"📄 [Grounding Reference: {ref.raw}]\n{block}")
            metadata.append({"type": "file", "target": ref.target, "raw": ref.raw})
        elif ref.kind == "folder":
            block = _read_folder_grounding(ref, base_dir)
            expanded_blocks.append(f"📁 [Grounding Reference: {ref.raw}]\n{block}")
            metadata.append({"type": "folder", "target": ref.target, "raw": ref.raw})
        elif ref.kind == "diff":
            block = _read_git_diff(staged=False, max_chars=max_chars_per_ref)
            expanded_blocks.append(f"🔍 [Grounding Reference: @diff]\n{block}")
            metadata.append({"type": "diff", "target": "git diff", "raw": "@diff"})
        elif ref.kind == "staged":
            block = _read_git_diff(staged=True, max_chars=max_chars_per_ref)
            expanded_blocks.append(f"🔍 [Grounding Reference: @staged]\n{block}")
            metadata.append({"type": "staged", "target": "git diff --cached", "raw": "@staged"})

    if not expanded_blocks:
        return text, []

    combined_context = "\n\n".join(expanded_blocks)
    grounded_prompt = f"{text}\n\n[PRE-FLIGHT CONTEXT GROUNDING]\n{combined_context}"
    return grounded_prompt, metadata
