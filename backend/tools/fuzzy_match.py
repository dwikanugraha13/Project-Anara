"""
fuzzy_match.py — Multi-Strategy Fuzzy Matcher & Path Resolver for Project Anara.
Provides robust text patch matching across line endings (CRLF/LF) and trailing whitespaces,
as well as fuzzy directory path discovery across user environment roots.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple


def _perform_fuzzy_replace(
    content: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Multi-strategy fuzzy replacement (Anara Enterprise Standard):
    1. Exact substring match
    2. Universal newline (CRLF <-> LF) normalization
    3. Trailing-whitespace normalized block match
    Returns (new_content, matched_old, error_message).
    """
    # Strategy 1: Exact match
    if old_string in content:
        count = content.count(old_string)
        if not replace_all and count > 1:
            return None, None, f"Found {count} matches for old_string. Provide more surrounding context lines or use replace_all=True."
        new_content = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)
        return new_content, old_string, None

    # Strategy 2: Line-ending normalization (CRLF / LF mismatch)
    crlf = chr(13) + chr(10)
    norm_content = content.replace(crlf, "\n")
    norm_old = old_string.replace(crlf, "\n")
    norm_new = new_string.replace(crlf, "\n")
    if norm_old in norm_content:
        count = norm_content.count(norm_old)
        if not replace_all and count > 1:
            return None, None, f"Found {count} matches for old_string under newline normalization. Provide more surrounding context lines."
        res = norm_content.replace(norm_old, norm_new) if replace_all else norm_content.replace(norm_old, norm_new, 1)
        if crlf in content:
            res = res.replace("\n", crlf)
        return res, old_string, None

    # Strategy 3: Trailing whitespace tolerance per line
    c_lines = content.splitlines(keepends=True)
    o_lines = [l.rstrip() for l in old_string.splitlines()]
    if o_lines and len(o_lines) <= len(c_lines):
        window_size = len(o_lines)
        matches = []
        for i in range(len(c_lines) - window_size + 1):
            window = [c_lines[i + j].rstrip() for j in range(window_size)]
            if window == o_lines:
                matches.append(i)
        if matches:
            if not replace_all and len(matches) > 1:
                return None, None, f"Found {len(matches)} whitespace-normalized matches. Provide more context lines."
            new_lines = new_string.splitlines(keepends=True)
            res_lines = list(c_lines)
            for m_idx in reversed(matches if replace_all else [matches[0]]):
                sub_new_lines = list(new_lines)
                if sub_new_lines and (m_idx + window_size - 1) < len(c_lines):
                    target_last_line = c_lines[m_idx + window_size - 1]
                    ends_with_nl = target_last_line.endswith(chr(10)) or target_last_line.endswith(chr(13))
                    last_has_nl = sub_new_lines[-1].endswith(chr(10)) or sub_new_lines[-1].endswith(chr(13))
                    if ends_with_nl and not last_has_nl:
                        sub_new_lines[-1] += chr(10)
                res_lines[m_idx:m_idx + window_size] = sub_new_lines
            return "".join(res_lines), old_string, None

    return None, None, f"Target block old_string not found in file."


def resolve_fuzzy_folder_path(folder_path: str) -> Optional[str]:
    """Resolves fuzzy path strings (e.g. 'Downloads', 'C: download', '~/Documents') to valid directories."""
    raw = (folder_path or "").strip().strip('"\'')
    if not raw:
        return None

    candidates = [
        os.path.abspath(os.path.expanduser(raw)),
        os.path.abspath(os.path.expanduser(raw.replace(":", ":/").replace("//", "/"))),
    ]

    lower_raw = raw.lower().replace("\\", "/").strip()
    user_home = os.path.expanduser("~")

    if "download" in lower_raw:
        candidates.extend([
            os.path.join(user_home, "Downloads"),
            "C:\\Downloads",
            "D:\\Downloads",
        ])
    elif "document" in lower_raw:
        candidates.extend([
            os.path.join(user_home, "Documents"),
            "C:\\Documents",
        ])
    elif "desktop" in lower_raw:
        candidates.extend([
            os.path.join(user_home, "Desktop"),
        ])
    elif "project" in lower_raw or "anara" in lower_raw:
        candidates.extend([
            os.path.join(user_home, "Documents", "Project Anara"),
            os.path.abspath("."),
        ])

    for cand in candidates:
        if cand and os.path.exists(cand) and os.path.isdir(cand):
            return os.path.normpath(cand)
    return None
