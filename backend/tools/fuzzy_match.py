"""
fuzzy_match.py — Multi-Strategy Fuzzy Matcher & Path Resolver for Project Anara.
Provides robust text patch matching across line endings (CRLF/LF) and trailing whitespaces,
as well as fuzzy directory path discovery across user environment roots.
"""

from __future__ import annotations

import os
import re
from typing import Optional, Tuple


_SKETCH_ELLIPSIS_PATTERN = re.compile(
    r"^[ \t]*(?:#|//|/\*|<!--|--|;)?\s*(?:\.\.\.|…|\.\.\.\s*\(.*?\)\s*\.\.\.)\s*"
    r"(?:existing|rest\s+of|remainder\s+of|other|omitted|earlier|previous|code|imports|content|functions|methods|statements|lines|logic)?.*?(?:\*/|-->)?[ \t]*$",
    re.IGNORECASE
)


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
    4. Apply-from-Sketch resolution (handling '// ... existing ...' placeholders)
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

    # Strategy 4: Apply-from-Sketch Mode (resolving '// ... existing code ...' placeholders)
    sketch_res = _resolve_sketch_ellipsis_replace(content, old_string, new_string)
    if sketch_res is not None:
        return sketch_res, old_string, None

    return None, None, f"Target block old_string not found in file."


def _resolve_sketch_ellipsis_replace(
    content: str,
    old_string: str,
    new_string: str
) -> Optional[str]:
    """
    Resolves sketch edits where the model omitted existing lines using ellipsis markers
    such as '// ... existing ...' or '# ... existing code ...'.
    """
    old_lines = old_string.splitlines()
    ellipsis_indices = [i for i, line in enumerate(old_lines) if _SKETCH_ELLIPSIS_PATTERN.match(line)]
    if not ellipsis_indices:
        return None

    # Take primary ellipsis
    e_idx = ellipsis_indices[0]
    prefix_lines = [l for l in old_lines[:e_idx] if l.strip()]
    suffix_lines = [l for l in old_lines[e_idx + 1:] if l.strip()]

    prefix_block = "\n".join(prefix_lines)
    suffix_block = "\n".join(suffix_lines)

    norm_c = content.replace("\r\n", "\n")

    # Case A: Both prefix anchor and suffix anchor exist
    if prefix_block and suffix_block:
        p_idx = norm_c.find(prefix_block)
        if p_idx == -1:
            # Try line-trimmed match for prefix
            for line in prefix_lines:
                if line in norm_c:
                    p_idx = norm_c.find(line)
                    break
        if p_idx == -1:
            return None

        s_search_start = p_idx + len(prefix_block)
        s_idx = norm_c.find(suffix_block, s_search_start)
        if s_idx == -1:
            for line in suffix_lines:
                found_s = norm_c.find(line, s_search_start)
                if found_s != -1:
                    s_idx = found_s
                    break
        if s_idx == -1 or s_idx < p_idx:
            return None

        enclosed_real = norm_c[p_idx + len(prefix_block):s_idx]

        # Resolve new_string
        new_lines = new_string.splitlines()
        new_ell_indices = [i for i, line in enumerate(new_lines) if _SKETCH_ELLIPSIS_PATTERN.match(line)]
        if new_ell_indices:
            n_idx = new_ell_indices[0]
            resolved_new_lines = new_lines[:n_idx] + [enclosed_real.rstrip("\n")] + new_lines[n_idx + 1:]
            resolved_new = "\n".join(resolved_new_lines)
        else:
            resolved_new = new_string

        target_span_end = s_idx + len(suffix_block)
        new_content = norm_c[:p_idx] + resolved_new + norm_c[target_span_end:]
        if "\r\n" in content:
            new_content = new_content.replace("\n", "\r\n")
        return new_content

    # Case B: Ellipsis at top (prefix empty, suffix anchor present)
    elif not prefix_block and suffix_block:
        s_idx = norm_c.find(suffix_block)
        if s_idx != -1:
            new_clean = "\n".join([l for l in new_string.splitlines() if not _SKETCH_ELLIPSIS_PATTERN.match(l)])
            new_content = norm_c[:s_idx] + new_clean + norm_c[s_idx + len(suffix_block):]
            if "\r\n" in content:
                new_content = new_content.replace("\n", "\r\n")
            return new_content

    # Case C: Ellipsis at bottom (prefix anchor present, suffix empty)
    elif prefix_block and not suffix_block:
        p_idx = norm_c.find(prefix_block)
        if p_idx != -1:
            new_clean = "\n".join([l for l in new_string.splitlines() if not _SKETCH_ELLIPSIS_PATTERN.match(l)])
            new_content = norm_c[:p_idx] + new_clean + norm_c[p_idx + len(prefix_block):]
            if "\r\n" in content:
                new_content = new_content.replace("\n", "\r\n")
            return new_content

    return None


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
