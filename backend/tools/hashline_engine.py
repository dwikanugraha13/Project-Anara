"""
hashline_engine.py — High-Precision Line-Anchored Hashline Editing Engine for Project Anara.

Provides deterministic line-anchored patch application with 4-hex snapshot verification,
preventing whitespace mismatches, reducing token overhead, and ensuring atomic mutations.
Supports canonical operations:
- PUT N.=M: (replace inclusive lines N..M with body rows prefixed with '+')
- PUT <N: (insert body rows before line N)
- PUT >N: (insert body rows after line N)
- PUT >$: (append body rows at file tail)
- CUT N.=M (delete inclusive lines N..M, with optional @register capture)
- Named registers: CUT N.=M @name, PUT <N @name, PUT N.=M @name
"""

from __future__ import annotations

import re
import zlib
from typing import Any, Dict, List, Optional, Tuple


# Global session register store for cross-operation cut/paste
_SESSION_REGISTERS: Dict[str, List[str]] = {}


def compute_file_tag(content: str) -> str:
    """
    Computes a deterministic 4-uppercase-hex snapshot tag for normalized content.
    Normalizes CRLF -> LF and trims trailing whitespace per line for robust hashing.
    """
    normalized_lines = [line.rstrip() for line in content.replace("\r\n", "\n").splitlines()]
    normalized_text = "\n".join(normalized_lines)
    crc = zlib.crc32(normalized_text.encode("utf-8")) & 0xFFFF
    return f"{crc:04X}"


def format_hashline_content(
    rel_path: str,
    content: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None
) -> Tuple[str, str, int]:
    """
    Formats file content with hashline snapshot header [path#TAG] and line numbers.
    Returns (formatted_display_string, snapshot_tag, total_lines).
    """
    tag = compute_file_tag(content)
    lines = content.splitlines(keepends=True)
    total_lines = len(lines)

    start_line = max(1, int(offset)) if offset and int(offset) > 0 else 1
    max_lines = min(2000, int(limit)) if limit and int(limit) > 0 else (250 if offset is None and total_lines > 250 else total_lines)
    start_idx = start_line - 1
    end_idx = min(total_lines, start_idx + max_lines)

    slice_lines = lines[start_idx:end_idx]
    clean_path = rel_path.replace("\\", "/").lstrip("./")

    header = f"[{clean_path}#{tag}]\n"
    numbered_lines = [f"{start_line + i}:{line}" for i, line in enumerate(slice_lines)]
    body = "".join(numbered_lines)

    if offset is None and total_lines > 250:
        footer = f"\n[... truncated {total_lines - 250} more lines. Use offset=251 to read further ...]"
    else:
        footer = ""

    return header + body + footer, tag, total_lines


def is_hashline_syntax(text: str) -> bool:
    """
    Detects whether an input string represents a hashline patch payload.
    """
    if not text or not isinstance(text, str):
        return False

    raw = text.strip()
    if re.search(r"\[[^\]#\s]+#[0-9A-Fa-f]{4}\]", raw):
        return True
    if re.search(r"^(?:PUT|SWAP|CUT|DEL|INS\.(?:PRE|POST|HEAD|TAIL))\s+", raw, re.MULTILINE):
        return True
    if "*** Begin Patch" in raw or "*** End Patch" in raw:
        return True
    return False


def apply_hashline_patch(
    content: str,
    patch_str: str,
    file_path: Optional[str] = None,
    registers: Optional[Dict[str, List[str]]] = None
) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Applies hashline operations onto file content.
    Returns (new_content, error_message, statistics_dict).
    """
    stats = {
        "added_lines": 0,
        "deleted_lines": 0,
        "operations": [],
        "tag_verified": False,
        "tag": None,
    }

    if registers is None:
        registers = _SESSION_REGISTERS

    current_tag = compute_file_tag(content)
    stats["tag"] = current_tag

    # Strip wrapper markers if present
    cleaned_patch = patch_str.replace("\r\n", "\n")
    cleaned_patch = re.sub(r"^\s*\*\*\*\s*Begin\s+Patch\s*", "", cleaned_patch, flags=re.MULTILINE)
    cleaned_patch = re.sub(r"^\s*\*\*\*\s*End\s+Patch\s*", "", cleaned_patch, flags=re.MULTILINE)

    patch_lines = cleaned_patch.splitlines()
    if not patch_lines:
        return None, "Empty hashline patch payload.", stats

    # Parse sections and verify tag if header exists
    lines = content.splitlines(keepends=True)
    if not lines and content:
        lines = [content]

    # Check for section header e.g. [path/to/file.py#1A2B]
    first_line_idx = 0
    while first_line_idx < len(patch_lines) and not patch_lines[first_line_idx].strip():
        first_line_idx += 1

    if first_line_idx < len(patch_lines):
        header_match = re.match(r"^\s*\[([^\]#]+)#([0-9A-Fa-f]{4})\]\s*$", patch_lines[first_line_idx])
        if header_match:
            declared_path, declared_tag = header_match.groups()
            declared_tag = declared_tag.upper()
            if declared_tag != current_tag:
                return (
                    None,
                    f"Stale snapshot tag mismatch: patch specifies #{declared_tag}, but current file is #{current_tag}. "
                    f"Please re-read '{file_path or declared_path}' before editing.",
                    stats
                )
            stats["tag_verified"] = True
            first_line_idx += 1

    # Operations parsing
    ops = []
    idx = first_line_idx

    while idx < len(patch_lines):
        line = patch_lines[idx].rstrip()
        if not line:
            idx += 1
            continue

        # Header match for another section (skip if same or break)
        if re.match(r"^\s*\[([^\]#]+)#[0-9A-Fa-f]{4}\]\s*$", line):
            idx += 1
            continue

        # 1. PUT N.=M: or SWAP N.=M: (Replace lines N..M)
        m_put_range = re.match(r"^\s*(?:PUT|SWAP)\s+(\d+)\.=(\d+)(?:\s+@(\w+))?:\s*$", line)
        if m_put_range:
            start_l, end_l, reg_name = int(m_put_range.group(1)), int(m_put_range.group(2)), m_put_range.group(3)
            idx += 1
            body_lines = []
            while idx < len(patch_lines) and patch_lines[idx].startswith("+"):
                raw_body = patch_lines[idx][1:]
                if raw_body.startswith("-") or raw_body.startswith("+"):
                    raw_body = raw_body[1:]
                body_lines.append(raw_body + "\n")
                idx += 1
            ops.append({
                "type": "replace_range",
                "start": start_l,
                "end": end_l,
                "body": body_lines,
                "reg": reg_name
            })
            continue

        # 2. PUT N.=M @name (Replace lines with register without body)
        m_put_reg = re.match(r"^\s*(?:PUT|SWAP)\s+(\d+)\.=(\d+)\s+@(\w+)\s*$", line)
        if m_put_reg:
            start_l, end_l, reg_name = int(m_put_reg.group(1)), int(m_put_reg.group(2)), m_put_reg.group(3)
            body_lines = list(registers.get(reg_name, []))
            ops.append({
                "type": "replace_range",
                "start": start_l,
                "end": end_l,
                "body": body_lines,
                "reg": reg_name
            })
            idx += 1
            continue

        # 3. PUT <N: (Insert before line N)
        m_put_before = re.match(r"^\s*(?:PUT\s+<(\d+)|INS\.PRE\s+(\d+)):\s*$", line)
        if m_put_before:
            target_l = int(m_put_before.group(1) or m_put_before.group(2))
            idx += 1
            body_lines = []
            while idx < len(patch_lines) and patch_lines[idx].startswith("+"):
                raw_body = patch_lines[idx][1:]
                if raw_body.startswith("-") or raw_body.startswith("+"):
                    raw_body = raw_body[1:]
                body_lines.append(raw_body + "\n")
                idx += 1
            ops.append({
                "type": "insert_before",
                "line": target_l,
                "body": body_lines
            })
            continue

        # 3b. PUT <N @name (Paste register before line N)
        m_put_before_reg = re.match(r"^\s*(?:PUT\s+<(\d+)|INS\.PRE\s+(\d+))(?:\s+@(\w+))\s*$", line)
        if m_put_before_reg:
            target_l = int(m_put_before_reg.group(1) or m_put_before_reg.group(2))
            reg_name = m_put_before_reg.group(3)
            ops.append({
                "type": "insert_before_reg",
                "line": target_l,
                "reg": reg_name
            })
            idx += 1
            continue

        # 4. PUT >N: (Insert after line N)
        m_put_after = re.match(r"^\s*(?:PUT\s+>(\d+)|INS\.POST\s+(\d+)):\s*$", line)
        if m_put_after:
            target_l = int(m_put_after.group(1) or m_put_after.group(2))
            idx += 1
            body_lines = []
            while idx < len(patch_lines) and patch_lines[idx].startswith("+"):
                raw_body = patch_lines[idx][1:]
                if raw_body.startswith("-") or raw_body.startswith("+"):
                    raw_body = raw_body[1:]
                body_lines.append(raw_body + "\n")
                idx += 1
            ops.append({
                "type": "insert_after",
                "line": target_l,
                "body": body_lines
            })
            continue

        # 4b. PUT >N @name (Paste register after line N)
        m_put_after_reg = re.match(r"^\s*(?:PUT\s+>(\d+)|INS\.POST\s+(\d+))(?:\s+@(\w+))\s*$", line)
        if m_put_after_reg:
            target_l = int(m_put_after_reg.group(1) or m_put_after_reg.group(2))
            reg_name = m_put_after_reg.group(3)
            ops.append({
                "type": "insert_after_reg",
                "line": target_l,
                "reg": reg_name
            })
            idx += 1
            continue

        # 5. PUT >$: (Append at tail)
        m_put_tail = re.match(r"^\s*(?:PUT\s+>\$|INS\.TAIL):\s*$", line)
        if m_put_tail:
            idx += 1
            body_lines = []
            while idx < len(patch_lines) and patch_lines[idx].startswith("+"):
                raw_body = patch_lines[idx][1:]
                if raw_body.startswith("-") or raw_body.startswith("+"):
                    raw_body = raw_body[1:]
                body_lines.append(raw_body + "\n")
                idx += 1
            ops.append({
                "type": "insert_tail",
                "body": body_lines
            })
            continue

        # 5b. PUT >$ @name (Paste register at tail)
        m_put_tail_reg = re.match(r"^\s*(?:PUT\s+>\$|INS\.TAIL)(?:\s+@(\w+))\s*$", line)
        if m_put_tail_reg:
            reg_name = m_put_tail_reg.group(1)
            ops.append({
                "type": "insert_tail_reg",
                "reg": reg_name
            })
            idx += 1
            continue

        # 6. CUT N.=M (Delete range, with optional register)
        m_cut = re.match(r"^\s*(?:CUT|DEL)\s+(\d+)\.=(\d+)(?:\s+@(\w+))?\s*$", line)
        if m_cut:
            start_l, end_l, reg_name = int(m_cut.group(1)), int(m_cut.group(2)), m_cut.group(3)
            ops.append({
                "type": "cut_range",
                "start": start_l,
                "end": end_l,
                "reg": reg_name
            })
            idx += 1
            continue

        # Unrecognized line
        return None, f"Unrecognized hashline instruction at line {idx + 1}: '{line}'.", stats

    if not ops:
        return None, "No valid hashline operations found in payload.", stats

    total_cur = len(lines)

    # Validate line numbers
    for op in ops:
        t = op["type"]
        if t in ("replace_range", "replace_range_reg", "cut_range"):
            s, e = op["start"], op["end"]
            if s < 1 or e > total_cur or s > e:
                return None, f"Line range {s}..{e} out of bounds for file with {total_cur} lines.", stats
        elif t in ("insert_before", "insert_before_reg", "insert_after", "insert_after_reg"):
            l = op["line"]
            if l < 1 or (t.startswith("insert_after") and l > total_cur) or (t.startswith("insert_before") and l > total_cur + 1):
                return None, f"Anchor line {l} out of bounds for file with {total_cur} lines.", stats

    # Multi-slot projection onto original snapshot lines
    pre_inserts: Dict[int, List[str]] = {k: [] for k in range(1, total_cur + 1)}
    post_inserts: Dict[int, List[str]] = {k: [] for k in range(1, total_cur + 1)}
    line_status: Dict[int, bool] = {k: True for k in range(1, total_cur + 1)}
    tail_inserts: List[str] = []

    # Execute operations in exact sequence top-to-bottom so earlier cuts populate registers
    for op in ops:
        t = op["type"]
        if t == "cut_range":
            s, e = op["start"], op["end"]
            captured = [lines[k - 1] for k in range(s, e + 1)]
            reg = op.get("reg")
            if reg:
                registers[reg] = captured
                registers[f"@{reg}"] = captured
            for k in range(s, e + 1):
                line_status[k] = False
            deleted_cnt = e - s + 1
            stats["deleted_lines"] += deleted_cnt
            stats["operations"].append(f"cut_range: {s}..{e} (-{deleted_cnt})")

        elif t == "replace_range":
            s, e = op["start"], op["end"]
            body = list(op["body"])
            for k in range(s, e + 1):
                line_status[k] = False
            pre_inserts[s].extend(body)
            deleted_cnt = e - s + 1
            added_cnt = len(body)
            stats["deleted_lines"] += deleted_cnt
            stats["added_lines"] += added_cnt
            stats["operations"].append(f"replace_range: {s}..{e} (-{deleted_cnt} +{added_cnt})")

        elif t == "replace_range_reg":
            s, e = op["start"], op["end"]
            reg = op.get("reg")
            body = list(registers.get(reg, registers.get(f"@{reg}", [])))
            for k in range(s, e + 1):
                line_status[k] = False
            pre_inserts[s].extend(body)
            deleted_cnt = e - s + 1
            added_cnt = len(body)
            stats["deleted_lines"] += deleted_cnt
            stats["added_lines"] += added_cnt
            stats["operations"].append(f"replace_range_reg: {s}..{e} @{reg} (-{deleted_cnt} +{added_cnt})")

        elif t == "insert_before":
            l = op["line"]
            body = list(op["body"])
            if l <= total_cur:
                pre_inserts[l].extend(body)
            else:
                tail_inserts.extend(body)
            stats["added_lines"] += len(body)
            stats["operations"].append(f"insert_before: line {l} (+{len(body)})")

        elif t == "insert_before_reg":
            l = op["line"]
            reg = op.get("reg")
            body = list(registers.get(reg, registers.get(f"@{reg}", [])))
            if l <= total_cur:
                pre_inserts[l].extend(body)
            else:
                tail_inserts.extend(body)
            stats["added_lines"] += len(body)
            stats["operations"].append(f"insert_before_reg: line {l} @{reg} (+{len(body)})")

        elif t == "insert_after":
            l = op["line"]
            body = list(op["body"])
            post_inserts[l].extend(body)
            stats["added_lines"] += len(body)
            stats["operations"].append(f"insert_after: line {l} (+{len(body)})")

        elif t == "insert_after_reg":
            l = op["line"]
            reg = op.get("reg")
            body = list(registers.get(reg, registers.get(f"@{reg}", [])))
            post_inserts[l].extend(body)
            stats["added_lines"] += len(body)
            stats["operations"].append(f"insert_after_reg: line {l} @{reg} (+{len(body)})")

        elif t == "insert_tail":
            body = list(op["body"])
            tail_inserts.extend(body)
            stats["added_lines"] += len(body)
            stats["operations"].append(f"insert_tail: (+{len(body)})")

        elif t == "insert_tail_reg":
            reg = op.get("reg")
            body = list(registers.get(reg, registers.get(f"@{reg}", [])))
            tail_inserts.extend(body)
            stats["added_lines"] += len(body)
            stats["operations"].append(f"insert_tail_reg: @{reg} (+{len(body)})")

    # Assemble projection
    assembled: List[str] = []
    for k in range(1, total_cur + 1):
        if pre_inserts.get(k):
            assembled.extend(pre_inserts[k])
        if line_status.get(k, True):
            assembled.append(lines[k - 1])
        if post_inserts.get(k):
            assembled.extend(post_inserts[k])

    if tail_inserts:
        if assembled and not assembled[-1].endswith("\n"):
            assembled[-1] += "\n"
        assembled.extend(tail_inserts)

    new_content = "".join(assembled)
    return new_content, None, stats
