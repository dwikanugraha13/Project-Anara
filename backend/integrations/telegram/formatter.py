"""
formatter.py — Telegram HTML & ASCII Markdown Table Formatter for Project Anara.
Converts Markdown, GFM tables, task lists, and spoilers into valid Telegram Bot API HTML entities.
"""

import html
import re
from typing import List


def _render_markdown_table_to_ascii(t_block: str) -> str:
    """Renders a GFM Markdown table into an aligned Unicode box-drawing grid table for Telegram."""
    lines = [ln.strip() for ln in t_block.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return t_block
    rows: List[List[str]] = []
    for line in lines:
        if re.match(r"^\|?\s*:?-+:?\s*(\|?\s*:?-+:?\s*)+\|?$", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return t_block
    num_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < num_cols:
            r.append("")
    col_widths = [max(len(r[c]) for r in rows) for c in range(num_cols)]
    col_widths = [max(w, 3) for w in col_widths]

    top = "┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐"
    sep = "├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤"
    bot = "└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘"

    out = [top]
    for idx, r in enumerate(rows):
        row_str = "│ " + " │ ".join(r[c].ljust(col_widths[c]) for c in range(num_cols)) + " │"
        out.append(row_str)
        if idx == 0 and len(rows) > 1:
            out.append(sep)
    out.append(bot)
    return "```\n" + "\n".join(out) + "\n```"


def format_telegram_html(text: str) -> str:
    """
    Converts markdown, GFM extensions, and rich HTML into Telegram Bot API valid HTML entities:
    - Native Collapsible: <details><summary>Title</summary>Content</details> -> <blockquote expandable>
    - Native Grid Tables: Markdown tables -> Unicode Box-Drawing grids in <pre><code>
    - Task Lists: - [x] -> ✅, - [ ] -> ⬜
    - Spoilers: ||text|| -> <tg-spoiler>text</tg-spoiler>
    - Supported tags: <b>, <i>, <code>, <s>, <u>, <pre>, <blockquote>, <blockquote expandable>, <tg-spoiler>, <a href="...">
    - Converts Markdown **bold** -> <b>bold</b>, *italic* -> <i>italic</i>, ```code``` -> <pre><code>code</code></pre>
    - Safely escapes stray &, <, > that are not part of valid Telegram HTML tags.
    """
    if not text:
        return ""

    def _cb_details(m):
        summary = m.group(1).strip()
        body = m.group(2).strip()
        return f"<blockquote expandable><b>{summary}</b>\n\n{body}</blockquote>"

    text = re.sub(
        r"<details(?:\s+[^>]*)?>\s*<summary>(.*?)</summary>([\s\S]*?)</details>",
        _cb_details,
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r"<details(?:\s+[^>]*)?>([\s\S]*?)</details>",
        r"<blockquote expandable>\1</blockquote>",
        text,
        flags=re.IGNORECASE
    )

    # Transform GFM Markdown tables to ASCII Box Grid tables
    table_pattern = r"((?:^[ \t]*\|[^\n]+\|[ \t]*\r?\n)+^[ \t]*\|[^\n]+\|[ \t]*)"
    text = re.sub(table_pattern, lambda m: _render_markdown_table_to_ascii(m.group(0)), text, flags=re.MULTILINE)

    # Task Lists / Checkboxes
    text = re.sub(r"(?m)^(\s*)[-*]\s*\[[xX]\]\s*", r"\1✅ ", text)
    text = re.sub(r"(?m)^(\s*)[-*]\s*\[\s*\]\s*", r"\1⬜ ", text)

    # Telegram Spoilers
    text = re.sub(r"\|\|(.+?)\|\|", r"<tg-spoiler>\1</tg-spoiler>", text)

    # Protect code blocks
    code_blocks = []
    def _cb_block(m):
        code_blocks.append(m.group(1))
        return f"___CODE_BLOCK_{len(code_blocks)-1}___"

    s = re.sub(r"```(?:[a-zA-Z0-9_\-\+\.]+)?\n?([\s\S]*?)```", _cb_block, text)

    # Protect inline code
    inline_codes = []
    def _cb_inline(m):
        inline_codes.append(m.group(1))
        return f"___INLINE_CODE_{len(inline_codes)-1}___"

    s = re.sub(r"`([^`\n]+)`", _cb_inline, s)

    # Protect existing valid Telegram HTML tags (including attributes like class, href, expandable)
    valid_tags = []
    def _cb_tag(m):
        valid_tags.append(m.group(0))
        return f"___VALID_TAG_{len(valid_tags)-1}___"

    tag_pat = r"</?(?:b|i|u|s|code|pre|blockquote|a|tg-spoiler)(?:\s+[^>]*)?>"
    s = re.sub(tag_pat, _cb_tag, s, flags=re.IGNORECASE)

    # Escape remaining HTML entities (&, <, >)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Restore valid tags
    for i, t in enumerate(valid_tags):
        s = s.replace(f"___VALID_TAG_{i}___", t)

    # Convert Markdown formatting
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s, flags=re.DOTALL)
    s = re.sub(r"(?m)^#{1,6}\s*(.+)$", r"<b>\1</b>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", r'<a href="\2">\1</a>', s)

    # Restore code blocks & inline code
    for i, code in enumerate(code_blocks):
        clean = html.escape(code.strip())
        s = s.replace(f"___CODE_BLOCK_{i}___", f"<pre><code>{clean}</code></pre>")

    for i, code in enumerate(inline_codes):
        clean = html.escape(code.strip())
        s = s.replace(f"___INLINE_CODE_{i}___", f"<code>{clean}</code>")

    return s


_RICH_PROTECTED_REGION_RE = re.compile(
    r'(?:```[^\n]*\n[\s\S]*?```)'
    r'|(?:^[^\n]*\|[^\n]*\n'
    r'[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*'
    r'(?:\n[^\n]*\|[^\n]*)*)',
    re.MULTILINE
)


def _rich_normalize_linebreaks(text: str) -> str:
    """Convert lone \\n to hard breaks for sendRichMessage."""
    if not text or "\n" not in text:
        return text
    out: List[str] = []
    pos = 0
    for m in _RICH_PROTECTED_REGION_RE.finditer(text):
        out.append(re.sub(r"(?<!\n)\n(?!\n)", "  \n", text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(re.sub(r"(?<!\n)\n(?!\n)", "  \n", text[pos:]))
    return "".join(out)


def has_rich_telegram_constructs(text: str) -> bool:
    """Detects if content contains native Bot API 10.1 rich constructs."""
    if not text:
        return False
    if re.search(r"^[ \t]*\|[^\n]+\|[ \t]*\r?\n[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*", text, re.MULTILINE):
        return True
    if re.search(r"(?m)^\s*[-*]\s*\[[ xX]\]\s+", text):
        return True
    if re.search(r"(?m)<details\b|</details>|<summary\b|</summary>", text, re.IGNORECASE):
        return True
    if "$$" in text:
        return True
    return False


def split_message_chunks(text: str, max_chars: int = 2200, add_part_headers: bool = True) -> List[str]:
    """
    Semantic code-block-aware message chunker for Telegram (Anara Standard).
    Splits long messages along paragraph and newline boundaries without breaking markdown code blocks.
    Guarantees unlimited parts and adds header badges [Bagian X/N] when message exceeds threshold.
    """
    if not text or len(text) <= max_chars:
        return [text] if text else []

    raw_chunks: List[str] = []
    current_text = text
    effective_limit = max_chars - 40 if add_part_headers else max_chars

    while len(current_text) > effective_limit:
        candidate = current_text[:effective_limit]
        code_fence_count = candidate.count("```")
        ends_inside_code = (code_fence_count % 2 == 1)

        split_idx = -1
        p_idx = candidate.rfind("\n\n")
        if p_idx > effective_limit // 3:
            split_idx = p_idx + 2
        else:
            l_idx = candidate.rfind("\n")
            if l_idx > effective_limit // 3:
                split_idx = l_idx + 1
            else:
                s_idx = candidate.rfind(" ")
                if s_idx > effective_limit // 3:
                    split_idx = s_idx + 1
                else:
                    split_idx = effective_limit

        chunk_part = current_text[:split_idx]
        current_text = current_text[split_idx:]

        if ends_inside_code:
            m_lang = re.search(r"```([a-zA-Z0-9_-]*)\n", chunk_part)
            last_lang = m_lang.group(1) if m_lang else ""
            chunk_part = chunk_part + "\n```"
            current_text = f"```{last_lang}\n" + current_text

        raw_chunks.append(chunk_part)

    if current_text:
        raw_chunks.append(current_text)

    total_parts = len(raw_chunks)
    if total_parts <= 1 or not add_part_headers:
        return raw_chunks

    final_chunks: List[str] = []
    for idx, chunk in enumerate(raw_chunks, start=1):
        header = f"📄 <b>[Bagian {idx}/{total_parts}]</b>\n\n"
        final_chunks.append(header + chunk)

    return final_chunks


def split_html_chunks(html_text: str, max_chars: int = 3800) -> List[str]:
    """
    Splits an already-formatted Telegram HTML string into safe sub-chunks without breaking HTML entities.
    Accurately closes any open HTML tags at chunk boundaries and re-opens them with identical attributes
    at the start of subsequent chunks to prevent Telegram 'unclosed entity' 400 errors.
    """
    if not html_text or len(html_text) <= max_chars:
        return [html_text] if html_text else []

    chunks: List[str] = []
    current = html_text
    tag_re = re.compile(r'<(/)?([a-zA-Z0-9_-]+)(\s+[^>]*)?>')

    while len(current) > max_chars:
        # Reserve headroom for closing tags (e.g. 100 chars)
        candidate = current[:max_chars - 100]

        # Prevent splitting inside an HTML tag: <tag ...>
        last_open_angle = candidate.rfind('<')
        last_close_angle = candidate.rfind('>')
        if last_open_angle > last_close_angle:
            candidate = candidate[:last_open_angle]

        # Prefer splitting at semantic block closures or newlines
        split_idx = -1
        for sep in ['</blockquote>', '</pre>', '</code>', '</b>', '</i>', '\n\n', '\n', ' ']:
            p = candidate.rfind(sep)
            if p > len(candidate) // 3:
                split_idx = p + len(sep)
                break

        if split_idx <= 0:
            split_idx = len(candidate)

        raw_chunk = current[:split_idx]
        current = current[split_idx:]

        # Find open unclosed tags in raw_chunk
        open_tags: List[tuple] = []
        for m in tag_re.finditer(raw_chunk):
            is_close, tag_name, attrs = m.group(1), m.group(2).lower(), m.group(3)
            full_tag = m.group(0)
            if is_close:
                if open_tags and open_tags[-1][0] == tag_name:
                    open_tags.pop()
            else:
                open_tags.append((tag_name, full_tag))

        closing_str = "".join(f"</{t[0]}>" for t in reversed(open_tags))
        reopening_str = "".join(t[1] for t in open_tags)

        chunks.append(raw_chunk + closing_str)
        current = reopening_str + current

    if current:
        chunks.append(current)

    return chunks


