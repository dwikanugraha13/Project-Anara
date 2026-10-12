import asyncio
import difflib
import fnmatch
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


from tools.document_extractors import (
    _extract_text_from_docx,
    _extract_text_from_pdf,
)
from tools.fuzzy_match import (
    _perform_fuzzy_replace,
    resolve_fuzzy_folder_path,
)


def _resolve_local_file_path(path: str) -> Optional[str]:
    """Resolves relative or fuzzy file paths to an absolute path within workspace or project."""
    clean_p = (path or "").strip().strip('"\'')
    if not clean_p:
        return None
    from core import anara_agent
    active_f = anara_agent.get_session_dir()
    expanded = os.path.expanduser(clean_p)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    candidates = [
        os.path.join(active_f, clean_p.lstrip("/\\")),
        expanded,
        os.path.join(active_f, clean_p),
        os.path.join(base_dir, clean_p),
        os.path.join(base_dir, "frontend", clean_p),
        os.path.join(base_dir, "backend", clean_p),
        os.path.join(os.path.expanduser("~"), "Desktop", clean_p),
        os.path.join(os.path.expanduser("~"), "Documents", clean_p),
    ]
    for c in candidates:
        if c and os.path.exists(c) and os.path.isfile(c):
            return os.path.abspath(c)

    if active_f and os.path.exists(active_f):
        target_name = os.path.basename(clean_p).lower()
        matches = []
        for r, _, files in os.walk(active_f):
            if any(ig in r for ig in [".git", "node_modules", "venv", "__pycache__", ".next"]):
                continue
            for f in files:
                if f.lower() == target_name:
                    matches.append(os.path.abspath(os.path.join(r, f)))
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            norm_clean = clean_p.replace("\\", "/").lower().lstrip("/")
            for m in matches:
                if m.replace("\\", "/").lower().endswith(norm_clean):
                    return m
            return matches[0]
    return None


# ==============================================================================
# Session Read / Write Tracking (Parity with Hermes tools/file_tools_read_tracking.py)
# Prevents blind file overwriting before reading and guards existing code logic
# ==============================================================================
_SESSION_READ_FILES: Set[str] = set()
_SESSION_WRITTEN_FILES: Set[str] = set()


def mark_file_read(path: str) -> None:
    try:
        _SESSION_READ_FILES.add(os.path.normcase(os.path.abspath(path)))
    except Exception:
        pass


def mark_file_written(path: str) -> None:
    try:
        norm = os.path.normcase(os.path.abspath(path))
        _SESSION_WRITTEN_FILES.add(norm)
        _SESSION_READ_FILES.add(norm)
    except Exception:
        pass


def has_file_been_read(path: str) -> bool:
    try:
        norm = os.path.normcase(os.path.abspath(path))
        return norm in _SESSION_READ_FILES or norm in _SESSION_WRITTEN_FILES
    except Exception:
        return True


def reset_session_file_tracking() -> None:
    """Helper for testing or session reset."""
    _SESSION_READ_FILES.clear()
    _SESSION_WRITTEN_FILES.clear()


def get_session_tracked_files() -> Dict[str, List[str]]:
    """Pi CompactionDetails parity: Returns lists of all files inspected and modified in the current session."""
    return {
        "read_files": sorted(list(_SESSION_READ_FILES)),
        "modified_files": sorted(list(_SESSION_WRITTEN_FILES)),
    }


def _generate_compact_symbols_outline(code_text: str, ext: str, max_symbols: int = 25) -> str:
    """Generates a compact symbol and line-number outline for large source code files."""
    ext = (ext or "").lower()
    symbols: List[str] = []

    if ext == ".py":
        import ast
        try:
            tree = ast.parse(code_text)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    methods = [sub.name for sub in node.body if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    m_str = f" ({len(methods)} methods)" if methods else ""
                    symbols.append(f"• class {node.name} (lines {node.lineno}-{getattr(node, 'end_lineno', node.lineno)}){m_str}")
                    for sub in node.body[:6]:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            symbols.append(f"    - def {sub.name}() -> line {sub.lineno}")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(f"• def {node.name}() -> line {node.lineno}")
        except Exception:
            pass

    if not symbols and ext in (".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".py"):
        lines = code_text.splitlines()
        for idx, line in enumerate(lines, 1):
            s = line.strip()
            m = re.match(r"^(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|fn|func|def)\s+([a-zA-Z0-9_]+)", s)
            if m:
                symbols.append(f"• {m.group(1)} -> line {idx}")
            if len(symbols) >= max_symbols:
                break

    if not symbols:
        return ""
    return "\n".join(symbols[:max_symbols])


_SPECULATIVE_PREFETCH_STORE: Dict[str, Tuple[float, float, str]] = {}


def speculative_prefetch_file(file_path: str) -> bool:
    """
    Speculatively pre-reads a local file into memory cache before model finishes JSON turn.
    Parity with Oh My Pi (speculation/host.ts).
    """
    try:
        norm = os.path.normcase(os.path.abspath(file_path))
        if os.path.isfile(norm):
            mtime = os.path.getmtime(norm)
            if norm in _SPECULATIVE_PREFETCH_STORE:
                c_mtime, c_time, _ = _SPECULATIVE_PREFETCH_STORE[norm]
                if c_mtime == mtime and time.time() - c_time < 15.0:
                    return True
            with open(norm, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            _SPECULATIVE_PREFETCH_STORE[norm] = (mtime, time.time(), content)
            return True
    except Exception:
        pass
    return False


async def _tool_read_local_file(file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Reads a local text/document/PDF/DOCX/code file safely.
    Supports optional windowed line-by-line reading with offset (1-indexed) and limit.
    """
    path = (file_path or "").strip().strip('"\'')
    if not path:
        return {"status": "error", "message": "file_path parameter cannot be empty."}

    action_detail = f"{os.path.basename(path)}" + (f" offset={offset} limit={limit}" if offset else "")
    _emit_agent_event("agent_action_start", {
        "tool_name": "read_local_file",
        "action_title": "Read File",
        "detail": action_detail,
        "filename": os.path.basename(path),
        "icon": "file"
    })

    try:
        target_file = _resolve_local_file_path(path)
        if not target_file:
            res_msg = f"File '{os.path.basename(path)}' not found in workspace. Verify the file path or use 'glob_find_files' / 'list_directory' to locate it."
            return {
                "status": "not_found",
                "is_error": False,
                "file_name": os.path.basename(path),
                "message": res_msg,
                "content": f"[Observation: {res_msg}]"
            }

        # WorkspaceSentinel Read Access Validation (Anara Enterprise Architecture)
        from core.workspace_sentinel import workspace_sentinel
        is_allowed, denial_reason = workspace_sentinel.validate_file_access(target_file, action="read")
        if not is_allowed:
            return {
                "status": "denied",
                "is_error": True,
                "file_name": os.path.basename(path),
                "message": denial_reason or f"Read access to '{os.path.basename(path)}' is restricted by security policy.",
                "content": f"[Security Denial: {denial_reason}]"
            }

        ext = os.path.splitext(target_file)[1].lower()
        from core.binary_guard import is_binary_file, get_binary_file_notice
        if ext == ".pdf":
            content = _extract_text_from_pdf(target_file)
        elif ext in [".docx", ".doc"]:
            content = _extract_text_from_docx(target_file) or "[Word Document: Text content extracted]"
        elif is_binary_file(target_file):
            size_b = os.path.getsize(target_file) if os.path.exists(target_file) else None
            notice = get_binary_file_notice(target_file, size_bytes=size_b)
            return {
                "status": "binary_file",
                "is_error": False,
                "file_name": os.path.basename(target_file),
                "message": notice,
                "content": notice,
            }
        else:
            norm_key = os.path.normcase(os.path.abspath(target_file))
            content = None
            if norm_key in _SPECULATIVE_PREFETCH_STORE:
                c_mtime, c_time, cached_c = _SPECULATIVE_PREFETCH_STORE[norm_key]
                try:
                    cur_mtime = os.path.getmtime(target_file)
                    if cur_mtime == c_mtime and time.time() - c_time < 15.0:
                        content = cached_c
                except Exception:
                    pass

            if content is None:
                with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                try:
                    _SPECULATIVE_PREFETCH_STORE[norm_key] = (os.path.getmtime(target_file), time.time(), content)
                except Exception:
                    pass

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        from tools.hashline_engine import compute_file_tag
        file_tag = compute_file_tag(content)
        try:
            rel_display = os.path.relpath(target_file, os.getcwd()).replace("\\", "/")
        except Exception:
            rel_display = os.path.basename(target_file)
        tag_header = f"[{rel_display}#{file_tag}]\n"

        if offset is not None or limit is not None:
            start_line = max(1, int(offset)) if offset and int(offset) > 0 else 1
            max_lines = min(2000, int(limit)) if limit and int(limit) > 0 else 500
            start_idx = start_line - 1
            end_idx = min(total_lines, start_idx + max_lines)
            slice_lines = lines[start_idx:end_idx]
            numbered_content = "".join([f"{start_line + i}: {line}" for i, line in enumerate(slice_lines)])
            display_content = tag_header + numbered_content
            summary_msg = f"Read lines {start_line}-{end_idx} of {total_lines} total lines [tag #{file_tag}]."
        else:
            if total_lines > 250:
                numbered_content = "".join([f"{i + 1}: {line}" for i, line in enumerate(lines[:250])])
                outline_str = _generate_compact_symbols_outline(content, ext)
                outline_footer = f"\n\n[OUTLINE DIRECTORY (Symbols & Lines)]:\n{outline_str}" if outline_str else ""
                display_content = tag_header + numbered_content + f"\n\n[... truncated {total_lines - 250} more lines. Use offset={251} to read further ...]{outline_footer}"
                summary_msg = f"Read first 250 lines of {total_lines} total lines [tag #{file_tag}]."
            else:
                numbered_content = "".join([f"{i + 1}: {line}" for i, line in enumerate(lines)])
                display_content = tag_header + numbered_content
                summary_msg = f"Read all {total_lines} lines [tag #{file_tag}]."

        norm_target_file = target_file.replace("\\", "/")
        _emit_agent_event("agent_action_complete", {
            "tool_name": "read_local_file",
            "action_title": "Read",
            "detail": action_detail,
            "filename": os.path.basename(path),
            "file_path": norm_target_file,
            "summary": summary_msg,
            "raw_result": display_content[:800],
            "icon": "file"
        })

        mark_file_read(target_file)

        return {
            "status": "success",
            "file_name": os.path.basename(target_file),
            "file_path": norm_target_file,
            "extension": ext,
            "total_lines": total_lines,
            "file_tag": file_tag,
            "content": display_content
        }
    except Exception as e:
        logger.warning(f"[AgentTools] Read file error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_edit_file(
    file_path: str,
    old_string: Optional[str] = None,
    new_string: Optional[str] = None,
    replace_all: bool = False,
    patch: Optional[str] = None
) -> Dict[str, Any]:
    """Selectively edits an existing code or document file in-place by exact or fuzzy string replacement or line-anchored hashline patches."""
    path = (file_path or "").strip().strip('"\'')
    if not path:
        return {"status": "error", "message": "file_path parameter cannot be empty."}

    from tools.hashline_engine import is_hashline_syntax, apply_hashline_patch

    hashline_payload = None
    if patch and is_hashline_syntax(patch):
        hashline_payload = patch
    elif old_string and is_hashline_syntax(old_string):
        hashline_payload = old_string
    elif new_string and is_hashline_syntax(new_string):
        hashline_payload = new_string

    if not hashline_payload and not old_string:
        return {"status": "error", "message": "Either old_string or a valid hashline patch parameter must be provided."}

    _emit_agent_event("agent_action_start", {
        "tool_name": "edit_file",
        "action_title": "Edit File",
        "detail": f"File: {os.path.basename(path)}" + (" [Hashline]" if hashline_payload else ""),
        "icon": "edit"
    })

    target_file = _resolve_local_file_path(path)
    if not target_file:
        return {"status": "error", "message": f"File '{path}' not found. Ensure the file exists before editing."}

    from core.workspace_sentinel import workspace_sentinel
    is_safe, denial_msg = workspace_sentinel.validate_file_access(target_file, action="edit")
    if not is_safe:
        return {"status": "error", "message": denial_msg or "File edit access restricted by Workspace Sentinel."}

    try:
        from core import anara_agent
        checkpoint_id = anara_agent.create_checkpoint(None)

        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if hashline_payload:
            new_content, err, h_stats = apply_hashline_patch(content, hashline_payload, file_path=target_file)
            if err or new_content is None:
                return {
                    "status": "error",
                    "message": f"{err or 'Hashline patch failed'} in file '{os.path.basename(target_file)}'."
                }
            added = h_stats["added_lines"]
            deleted = h_stats["deleted_lines"]
        else:
            if not old_string:
                return {"status": "error", "message": "old_string cannot be empty for string replacement."}
            target_new = new_string if new_string is not None else ""
            new_content, matched_old, err = _perform_fuzzy_replace(content, old_string, target_new, replace_all=replace_all)
            if err or new_content is None:
                return {
                    "status": "error",
                    "message": f"{err or 'Replacement failed'} in file '{os.path.basename(target_file)}'."
                }
            added = len(target_new.splitlines())
            deleted = len(old_string.splitlines())

        # Atomic replacement to eliminate risk of empty file on crash
        tmp_target = f"{target_file}.tmp_{os.getpid()}_{int(time.time() * 1000)}"
        with open(tmp_target, "w", encoding="utf-8", newline="") as f:
            f.write(new_content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_target, target_file)
        mark_file_written(target_file)

        # Ground-Truth Read-Back Verification (Anara Standard)
        expected_check = ""
        if not hashline_payload and new_string:
            expected_check = new_string[:80] if len(new_string) > 5 else new_string
        read_back = workspace_sentinel.verify_read_back(target_file, expected_snippet=expected_check)
        if not read_back.get("verified"):
            logger.warning(f"[WorkspaceSentinel] Post-edit read-back warning for '{target_file}': {read_back.get('error')}")

        diff_iter = difflib.unified_diff(
            content.splitlines(),
            new_content.splitlines(),
            fromfile=f"a/{os.path.basename(target_file)}",
            tofile=f"b/{os.path.basename(target_file)}",
            lineterm=""
        )
        diff_str = "\n".join(diff_iter)
        if not diff_str:
            diff_str = f"Modified {os.path.basename(target_file)}"

        size_kb = round(len(new_content.encode("utf-8")) / 1024, 2)
        filename = os.path.basename(target_file)

        git_commit_sha = anara_agent.record_git_commit(
            file_path=target_file,
            message=f"edit {filename} (+{added} -{deleted} lines)"
        )

        rel_dir = os.path.dirname(target_file).replace("\\", "/")
        norm_target_file = target_file.replace("\\", "/")
        _emit_agent_event("agent_action_complete", {
            "tool_name": "edit_file",
            "action_title": f"Edit {filename} (+{added} -{deleted})",
            "detail": f"{filename} {rel_dir}",
            "summary": f"+{added} -{deleted}" + (f" [{git_commit_sha}]" if git_commit_sha else ""),
            "raw_result": diff_str[:3000],
            "file_path": norm_target_file,
            "filename": filename,
            "file_ext": os.path.splitext(target_file)[1],
            "content": new_content,
            "size_kb": size_kb,
            "checkpoint_id": checkpoint_id,
            "git_commit": git_commit_sha,
            "added": added,
            "deleted": deleted,
            "icon": "edit"
        })

        _emit_agent_event("workspace_file_created", {
            "file_path": norm_target_file,
            "filename": filename,
            "file_ext": os.path.splitext(target_file)[1],
            "content": new_content,
            "size_kb": size_kb,
        })

        # Emit real-time telemetry event for Code Studio Live Split-Diff (Pilar 2)
        try:
            from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance
            loop = asyncio.get_running_loop()
            loop.create_task(
                telemetry_bus.emit(
                    event_type=EventType.FILE_MODIFIED,
                    provenance=ActivityProvenance.TOOL_RUNNER,
                    session_id=str(anara_agent.get_active_session_id() or "default"),
                    trace_id=f"tr_{filename}",
                    payload={
                        "action": "edit",
                        "file_path": norm_target_file,
                        "filename": filename,
                        "diff": diff_str[:5000],
                        "added_lines": added,
                        "deleted_lines": deleted,
                        "size_kb": size_kb,
                        "git_commit": git_commit_sha,
                    }
                )
            )
        except (RuntimeError, Exception):
            pass

        # Hermes-Parity: In-Process Post-Write Syntax Lint Gate with Differential Delta Filtering
        from tools.inproc_linter import lint_code_syntax
        lint_err = lint_code_syntax(target_file, new_content, pre_content=content)
        extra_notice = ""
        if lint_err:
            extra_notice = f"\n[LINT WARNING]: {lint_err['message']}. Please review and correct this syntax issue in your next step."

        return {
            "status": "success",
            "file_path": norm_target_file,
            "filename": filename,
            "added_lines": added,
            "deleted_lines": deleted,
            "checkpoint_id": checkpoint_id,
            "git_commit": git_commit_sha,
            "lint_warning": lint_err.get("message") if lint_err else None,
            "message": f"File '{filename}' updated successfully (+{added} -{deleted} lines)" + (f" [commit {git_commit_sha}]." if git_commit_sha else ".") + extra_notice,
            "diff": diff_str[:1000]
        }
    except Exception as e:
        logger.warning(f"[AgentTools] Edit file error: {e}")
        return {"status": "error", "message": f"Failed to edit file: {e}"}


async def _tool_write_local_file(file_path: str, content: str, overwrite: bool = False, **kwargs) -> Dict[str, Any]:
    """Creates or updates a file locally on the computer (Desktop or workspace)."""
    raw_path = (file_path or "").strip().strip('"\'')
    if not raw_path:
        return {"status": "error", "message": "file_path parameter cannot be empty."}

    if raw_path.lower().endswith(".pdf") or raw_path.lower().endswith(".docx"):
        from .artifact_tools import _tool_generate_file_artifact
        return await _tool_generate_file_artifact(
            filename=os.path.basename(raw_path),
            content=content,
            destination_folder=os.path.dirname(raw_path) or None
        )

    if raw_path.lower().endswith(".zip"):
        from .artifact_tools import _tool_create_zip_archive
        return await _tool_create_zip_archive(
            archive_name=os.path.basename(raw_path),
            folder_path=os.path.dirname(raw_path) or None
        )

    _emit_agent_event("agent_action_start", {
        "tool_name": "write_local_file",
        "action_title": "Write File",
        "detail": f"File: {os.path.basename(raw_path)}",
        "icon": "file-plus"
    })

    try:
        from core import anara_agent
        from core.workspace_sentinel import workspace_sentinel

        is_safe, denial_msg = workspace_sentinel.validate_file_access(raw_path, action="write")
        if not is_safe:
            return {"status": "error", "message": denial_msg or "File write access restricted by Workspace Sentinel."}

        active_f = anara_agent.get_session_dir()
        has_custom = anara_agent.has_active_custom_workspace()
        checkpoint_id = anara_agent.create_checkpoint(None)

        if has_custom:
            # Anara Code Mode: file writes are strictly confined within the attached project folder
            if os.path.isabs(raw_path):
                abs_candidate = os.path.abspath(os.path.expanduser(raw_path))
                abs_root = os.path.abspath(active_f)
                if abs_candidate.lower().startswith(abs_root.lower()):
                    target_path = abs_candidate
                else:
                    # Strip drive letter and keep inside project root
                    clean_sub = re.sub(r'^[a-zA-Z]:[/\\]+', '', raw_path).lstrip("/\\")
                    target_path = os.path.join(active_f, clean_sub)
            else:
                clean_sub = raw_path.lstrip("/\\")
                target_path = os.path.join(active_f, clean_sub)
        else:
            # Anara Chat Mode: strictly sandbox all writes in session temp directory — NEVER touch host C:\ !
            clean_sub = re.sub(r'^[a-zA-Z]:[/\\]+', '', raw_path).lstrip("/\\")
            target_path = os.path.join(active_f, clean_sub)

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        file_already_exists = os.path.exists(target_path)

        # 1. Hermes Parity: Binary Document & Asset Protection Guard
        from core.binary_guard import check_binary_write_prohibited
        is_prohib, reason = check_binary_write_prohibited(target_path, exists=file_already_exists)
        if is_prohib:
            return {"status": "error", "message": reason}

        # 2. Hermes Parity: Read-Before-Write Baseline (Blind Overwrite Guard)
        if file_already_exists and os.path.getsize(target_path) > 100:
            if not has_file_been_read(target_path) and not bool(overwrite):
                existing_size = os.path.getsize(target_path)
                return {
                    "status": "error",
                    "error_type": "UnreadExistingFileOverwriteWarning",
                    "message": (
                        f"Refusing to overwrite existing file '{os.path.basename(target_path)}' ({existing_size} bytes). "
                        "This file has not been read in this session. Blindly overwriting it may accidentally erase existing code. "
                        "Please read the file first using 'read_local_file' or use 'edit_file' for surgical edits. "
                        "To force a complete overwrite, pass overwrite=True."
                    ),
                }

        existing_pre_content = None
        if file_already_exists:
            try:
                with open(target_path, "r", encoding="utf-8", errors="replace") as f_prev:
                    existing_pre_content = f_prev.read()
            except Exception:
                pass

        anara_agent.ensure_git_repo(None)
        tmp_target = f"{target_path}.tmp_{os.getpid()}_{int(time.time() * 1000)}"
        with open(tmp_target, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_target, target_path)
        mark_file_written(target_path)

        # Ground-Truth Read-Back Verification (Anara Standard)
        read_back = workspace_sentinel.verify_read_back(target_path, expected_snippet=content[:80] if len(content) > 5 else content)
        if not read_back.get("verified"):
            logger.warning(f"[WorkspaceSentinel] Post-write read-back warning for '{target_path}': {read_back.get('error')}")

        file_ext = os.path.splitext(target_path)[1]
        filename = os.path.basename(target_path)
        size_kb = round(len(content.encode('utf-8')) / 1024, 2)

        git_commit_sha = anara_agent.record_git_commit(
            file_path=target_path,
            message=f"write {filename} ({size_kb} KB)"
        )

        norm_target_path = target_path.replace("\\", "/")
        _emit_agent_event("agent_action_complete", {
            "tool_name": "write_local_file",
            "action_title": "File Saved",
            "summary": f"{filename} ({size_kb} KB)" + (f" [{git_commit_sha}]" if git_commit_sha else ""),
            "file_path": norm_target_path,
            "filename": filename,
            "file_ext": file_ext,
            "content": content,
            "size_kb": size_kb,
            "checkpoint_id": checkpoint_id,
            "git_commit": git_commit_sha,
            "raw_result": content[:600],
            "icon": "file"
        })

        _emit_agent_event("workspace_file_created", {
            "file_path": norm_target_path,
            "filename": filename,
            "file_ext": file_ext,
            "content": content,
            "size_kb": size_kb,
        })

        # Emit real-time telemetry event for Code Studio Live Split-Diff (Pilar 2)
        try:
            from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance
            loop = asyncio.get_running_loop()
            loop.create_task(
                telemetry_bus.emit(
                    event_type=EventType.FILE_MODIFIED,
                    provenance=ActivityProvenance.TOOL_RUNNER,
                    session_id=str(anara_agent.get_active_session_id() or "default"),
                    trace_id=f"tr_{filename}",
                    payload={
                        "action": "write",
                        "file_path": norm_target_path,
                        "filename": filename,
                        "size_kb": size_kb,
                        "git_commit": git_commit_sha,
                    }
                )
            )
        except (RuntimeError, Exception):
            pass

        # Hermes-Parity: In-Process Post-Write Syntax Lint Gate with Differential Delta Filtering
        from tools.inproc_linter import lint_code_syntax
        lint_err = lint_code_syntax(target_path, content, pre_content=existing_pre_content)
        extra_notice = ""
        if lint_err:
            extra_notice = f"\n[LINT WARNING]: {lint_err['message']}. Please review and correct this syntax issue in your next step."

        return {
            "status": "success",
            "message": f"File written successfully to '{norm_target_path}'" + (f" [commit {git_commit_sha}]." if git_commit_sha else ".") + extra_notice,
            "lint_warning": lint_err.get("message") if lint_err else None,
            "file_path": norm_target_path,
            "checkpoint_id": checkpoint_id,
            "git_commit": git_commit_sha,
            "size_bytes": len(content.encode('utf-8'))
        }
    except Exception as e:
        logger.warning(f"[AgentTools] Write file error: {e}")
        return {"status": "error", "message": f"Failed to write file: {e}"}


async def _tool_delete_local_file(file_path: str) -> Dict[str, Any]:
    """
    Safely deletes a specific target file requested by the user.
    Strictly protects against wildcards (*), directory wipes, and vital system files (Anara Standard).
    """
    raw_path = (file_path or "").strip().strip('"\'')
    if not raw_path:
        return {"status": "error", "message": "file_path parameter cannot be empty."}

    # 1. Blind wildcard & path traversal guard
    if any(wc in raw_path for wc in ("*", "?", "..")):
        return {
            "status": "error",
            "message": f"Rejected: Wildcard characters or directory traversal ('{raw_path}') are forbidden for deletion."
        }

    try:
        from core import anara_agent
        from core.workspace_sentinel import workspace_sentinel

        resolved = _resolve_local_file_path(raw_path)
        if not resolved or not os.path.exists(resolved):
            return {"status": "error", "message": f"File '{raw_path}' not found."}

        # 2. Critical file immunity via WorkspaceSentinel on fully-resolved canonical target
        is_safe, denial_msg = workspace_sentinel.validate_file_access(resolved, action="delete")
        if not is_safe:
            return {"status": "error", "message": denial_msg or f"Access denied: Deletion of '{raw_path}' blocked by Workspace Sentinel."}

        if os.path.isdir(resolved):
            return {"status": "error", "message": f"'{raw_path}' is a directory, not a file. This tool only deletes individual files."}

        norm_path = resolved.replace("\\", "/").lower()
        target_base = os.path.basename(norm_path)

        _emit_agent_event("agent_action_start", {
            "tool_name": "delete_local_file",
            "action_title": "Delete File",
            "detail": f"File: {target_base}",
            "icon": "trash"
        })

        # Create checkpoint before deletion
        checkpoint_id = anara_agent.create_checkpoint(None)
        os.remove(resolved)

        git_commit_sha = anara_agent.record_git_commit(
            file_path=resolved,
            message=f"delete {target_base}"
        )

        _emit_agent_event("agent_action_complete", {
            "tool_name": "delete_local_file",
            "action_title": "File Deleted",
            "summary": f"File '{target_base}' deleted successfully.",
            "file_path": resolved,
            "filename": target_base,
            "checkpoint_id": checkpoint_id,
            "git_commit": git_commit_sha,
            "icon": "trash"
        })

        _emit_agent_event("workspace_file_deleted", {
            "file_path": resolved,
            "filename": target_base,
        })

        return {
            "status": "success",
            "message": f"File '{target_base}' deleted successfully." + (f" [commit {git_commit_sha}]." if git_commit_sha else "."),
            "file_path": resolved,
            "filename": target_base,
            "checkpoint_id": checkpoint_id,
            "git_commit": git_commit_sha
        }
    except Exception as e:
        logger.warning(f"[AgentTools] Delete file error: {e}")
        return {"status": "error", "message": f"Failed to delete file: {e}"}


async def _tool_list_directory(directory_path: Optional[str] = None) -> Dict[str, Any]:
    """Lists files and folders inside a local directory."""
    dir_path = (directory_path or "").strip().strip('"\'')
    if not dir_path:
        target_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    else:
        target_dir = os.path.expanduser(dir_path)

    _emit_agent_event("agent_action_start", {
        "tool_name": "list_directory",
        "action_title": "List Directory",
        "detail": f"Folder: {os.path.basename(target_dir) or target_dir}",
        "icon": "folder"
    })

    try:
        if not os.path.exists(target_dir):
            return {"status": "error", "message": f"Directory '{target_dir}' was not found."}

        entries = []
        for name in os.listdir(target_dir)[:40]:
            full = os.path.join(target_dir, name)
            is_dir = os.path.isdir(full)
            size = os.path.getsize(full) if not is_dir else 0
            entries.append({
                "name": name,
                "type": "directory" if is_dir else "file",
                "size_kb": round(size / 1024, 1) if not is_dir else 0,
            })

        _emit_agent_event("agent_action_complete", {
            "tool_name": "list_directory",
            "action_title": "Directory Listed",
            "summary": f"Found {len(entries)} files & folders.",
            "icon": "folder"
        })

        return {
            "status": "success",
            "directory": target_dir,
            "total_items": len(entries),
            "items": entries
        }
    except Exception as e:
        logger.warning(f"[AgentTools] List dir error: {e}")
        return {"status": "error", "message": f"Failed to list directory: {e}"}


async def _tool_scan_workspace_folder(folder_path: str) -> Dict[str, Any]:
    """Scans and builds a recursive file tree of an imported local folder project."""
    raw_path = (folder_path or "").strip().strip('"\'')
    target_dir = os.path.expanduser(raw_path) if raw_path else os.path.join(os.path.expanduser("~"), "Desktop")

    _emit_agent_event("agent_action_start", {
        "tool_name": "scan_workspace_folder",
        "action_title": "Scan Workspace Folder",
        "detail": f"Folder: {os.path.basename(target_dir)}",
        "icon": "folder"
    })

    IGNORED_DIRS = {".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build", ".vscode"}
    tree = []
    total_files = 0

    try:
        if not os.path.exists(target_dir):
            return {"status": "error", "message": f"Folder '{target_dir}' was not found."}

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            rel_root = os.path.relpath(root, target_dir)
            
            for f in files:
                if total_files >= 60:
                    break
                rel_file = os.path.normpath(os.path.join(rel_root, f)) if rel_root != "." else f
                full_file = os.path.join(root, f)
                ext = os.path.splitext(f)[1].lower()
                tree.append({
                    "path": rel_file.replace("\\", "/"),
                    "name": f,
                    "ext": ext,
                    "size_kb": round(os.path.getsize(full_file) / 1024, 1),
                })
                total_files += 1

            if total_files >= 60:
                break

        _emit_agent_event("agent_action_complete", {
            "tool_name": "scan_workspace_folder",
            "action_title": "Project Tree Indexed",
            "summary": f"Indexed {total_files} files in project.",
            "icon": "📁"
        })

        return {
            "status": "success",
            "project_name": os.path.basename(target_dir),
            "root_path": target_dir,
            "total_files": total_files,
            "file_tree": tree
        }
    except Exception as e:
        logger.warning(f"[AgentTools] Scan folder error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_switch_workspace(folder_path: str) -> Dict[str, Any]:
    """
    Switches and locks the agent's active project workspace to a specified local directory.
    Supports fuzzy paths (e.g. 'Downloads', 'Documents', 'C: download', '~/Projects').
    """
    from core.agent import anara_agent

    resolved_path = resolve_fuzzy_folder_path(folder_path)
    if not resolved_path:
        return {
            "status": "error",
            "message": f"Folder '{folder_path}' does not exist or is not a valid directory."
        }

    try:
        current_sid = anara_agent.get_active_session_id()
        tree = anara_agent.attach_local_folder(resolved_path, session_id=current_sid)
        ws_name = tree.get("workspace_name") or os.path.basename(resolved_path) or "Workspace"
        file_count = tree.get("total_files", 0)

        _emit_agent_event("agent_action_complete", {
            "tool_name": "switch_workspace",
            "action_title": "Workspace Switched",
            "summary": f"Switched active workspace to '{ws_name}' ({file_count} files).",
            "icon": "📁"
        })

        return {
            "status": "success",
            "workspace_name": ws_name,
            "root_path": resolved_path,
            "total_files": file_count,
            "message": f"Successfully switched workspace to '{ws_name}' at '{resolved_path}' ({file_count} files indexed)."
        }
    except Exception as e:
        logger.error(f"[AgentTools] Failed to switch workspace to '{resolved_path}': {e}")
        return {"status": "error", "message": f"Failed to switch workspace: {str(e)}"}


async def _tool_glob_find_files(pattern: str, path: Optional[str] = None) -> Dict[str, Any]:
    """Fast file pattern matching across the project workspace."""
    from core import anara_agent

    pat = (pattern or "").strip()
    if not pat:
        return {"status": "error", "message": "Pattern cannot be empty."}

    active_f = anara_agent.get_session_dir()
    root_dir = os.path.abspath(os.path.expanduser(path)) if path else active_f
    if not os.path.exists(root_dir):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        root_dir = base_dir

    _emit_agent_event("agent_action_start", {
        "tool_name": "glob_find_files",
        "action_title": "Find Files (Glob)",
        "detail": f"Pattern: {pat}",
        "icon": "search"
    })

    IGNORED_DIRS = {
        ".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build",
        ".venv", ".vscode", "appdata", ".cache", ".cargo", ".rustup", ".conda",
        ".npm", ".pnpm-store", ".gradle", "local settings", "application data"
    }

    def _sync_glob():
        res = []
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d.lower() not in IGNORED_DIRS and not d.startswith(".")]
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
                if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(f, pat):
                    res.append(rel_path)
                    if len(res) >= 100:
                        return res
        return res

    try:
        matches = await asyncio.wait_for(asyncio.to_thread(_sync_glob), timeout=8.0)
    except asyncio.TimeoutError:
        matches = []
        logger.debug(f"[fs_tools] glob search timed out for pattern '{pat}' in '{root_dir}'")

    # Speculative Tool Prefetching: Pre-warm memory cache for top matches
    for m_path in matches[:5]:
        full_m = os.path.join(root_dir, m_path) if not os.path.isabs(m_path) else m_path
        speculative_prefetch_file(full_m)

    summary_msg = f"Found {len(matches)} files matching pattern '{pat}'."
    _emit_agent_event("agent_action_complete", {
        "tool_name": "glob_find_files",
        "action_title": "Glob",
        "detail": f"pattern={pat}",
        "summary": summary_msg,
        "raw_result": "\n".join(matches[:25]),
        "icon": "search"
    })

    return {
        "status": "success",
        "pattern": pat,
        "root_directory": root_dir,
        "total_matches": len(matches),
        "files": matches
    }


async def _tool_grep_search_code(pattern: str, path: Optional[str] = None, include: Optional[str] = None) -> Dict[str, Any]:
    """Fast regex search inside codebase files."""
    from core import anara_agent

    pat = (pattern or "").strip()
    if not pat:
        return {"status": "error", "message": "Regex pattern cannot be empty."}

    active_f = anara_agent.get_session_dir()
    root_dir = os.path.abspath(os.path.expanduser(path)) if path else active_f
    if not os.path.exists(root_dir):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        root_dir = base_dir

    _emit_agent_event("agent_action_start", {
        "tool_name": "grep_search_code",
        "action_title": "Search Code (Grep)",
        "detail": f"Regex: {pat}",
        "icon": "search"
    })

    try:
        regex = re.compile(pat, re.IGNORECASE)
    except re.error as e:
        return {"status": "error", "message": f"Invalid regex pattern: {e}"}

    IGNORED_DIRS = {
        ".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build",
        ".venv", ".vscode", "appdata", ".cache", ".cargo", ".rustup", ".conda",
        ".npm", ".pnpm-store", ".gradle", "local settings", "application data"
    }
    BINARY_EXTS = {".png", ".jpg", ".jpeg", ".ico", ".pdf", ".zip", ".tar", ".exe", ".dll", ".woff", ".woff2", ".ttf", ".sqlite", ".db"}

    def _sync_grep():
        res = []
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d.lower() not in IGNORED_DIRS and not d.startswith(".")]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in BINARY_EXTS:
                    continue
                if include and not (fnmatch.fnmatch(f, include) or fnmatch.fnmatch(f, f"*.{include.lstrip('.*')}")):
                    continue

                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                        for line_num, line in enumerate(fp, 1):
                            if regex.search(line):
                                line_clean = line.rstrip()[:250]
                                res.append({
                                    "file": rel_path,
                                    "line_number": line_num,
                                    "line": line_clean
                                })
                                if len(res) >= 60:
                                    return res
                except Exception:
                    continue
            if len(res) >= 60:
                return res
        return res

    try:
        matches = await asyncio.wait_for(asyncio.to_thread(_sync_grep), timeout=10.0)
    except asyncio.TimeoutError:
        matches = []
        logger.debug(f"[fs_tools] grep search timed out for pattern '{pat}' in '{root_dir}'")

    grep_detail = f"/ pattern={pat}" + (f" include={include}" if include else "")
    summary_str = "\n".join([f"{m['file']}:{m['line_number']}: {m['line']}" for m in matches[:20]])
    _emit_agent_event("agent_action_complete", {
        "tool_name": "grep_search_code",
        "action_title": "Grep",
        "detail": grep_detail,
        "summary": f"Found {len(matches)} matching lines.",
        "raw_result": summary_str,
        "icon": "search"
    })

    return {
        "status": "success",
        "pattern": pat,
        "total_matches": len(matches),
        "matches": matches,
        "output": summary_str
    }


async def _tool_extract_code_outline(file_path: str) -> Dict[str, Any]:
    """
    Extracts structural outline of a source code file using AST and symbolic parsing (Anara Standard).
    Returns classes, functions, methods, line ranges, parameter signatures, and docstrings.
    Saves context tokens by eliminating the need to read entire large files.
    """
    clean_target = (file_path or "").strip().strip('"\'')
    if not clean_target:
        return {"status": "error", "message": "file_path cannot be empty."}

    norm_path = os.path.abspath(os.path.expanduser(clean_target))
    if not os.path.isfile(norm_path):
        return {"status": "error", "message": f"File not found: {clean_target}"}

    try:
        with open(norm_path, "r", encoding="utf-8", errors="replace") as f:
            code_text = f.read()
    except Exception as e:
        return {"status": "error", "message": f"Failed to read file: {e}"}

    total_lines = len(code_text.splitlines())
    ext = os.path.splitext(norm_path)[1].lower()
    symbols: List[Dict[str, Any]] = []

    # 1. Python AST parsing
    if ext == ".py":
        import ast
        try:
            tree = ast.parse(code_text, filename=norm_path)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    methods = []
                    class_doc = ast.get_docstring(node) or ""
                    first_doc_line = class_doc.splitlines()[0] if class_doc else ""
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            prefix = "async def " if isinstance(sub, ast.AsyncFunctionDef) else "def "
                            args_list = [a.arg for a in sub.args.args]
                            sub_doc = ast.get_docstring(sub) or ""
                            first_sub_doc = sub_doc.splitlines()[0] if sub_doc else ""
                            methods.append({
                                "name": sub.name,
                                "signature": f"{prefix}{sub.name}({', '.join(args_list)})",
                                "line_start": sub.lineno,
                                "line_end": getattr(sub, "end_lineno", sub.lineno),
                                "docstring": first_sub_doc,
                            })
                    symbols.append({
                        "type": "class",
                        "name": node.name,
                        "line_start": node.lineno,
                        "line_end": getattr(node, "end_lineno", node.lineno),
                        "docstring": first_doc_line,
                        "methods": methods,
                    })
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
                    args_list = [a.arg for a in node.args.args]
                    fn_doc = ast.get_docstring(node) or ""
                    first_fn_doc = fn_doc.splitlines()[0] if fn_doc else ""
                    symbols.append({
                        "type": "function",
                        "name": node.name,
                        "signature": f"{prefix}{node.name}({', '.join(args_list)})",
                        "line_start": node.lineno,
                        "line_end": getattr(node, "end_lineno", node.lineno),
                        "docstring": first_fn_doc,
                    })
        except Exception as e:
            logger.debug(f"[AST] Parsing note: {e}")

    # 2. General regex symbol parsing for JS, TS, Go, Rust, Markdown
    if not symbols:
        lines = code_text.splitlines()
        for idx, line in enumerate(lines, 1):
            s = line.strip()
            # JS/TS/Go/Rust functions & classes
            m = re.match(r"^(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|fn|func|def)\s+([a-zA-Z0-9_]+)", s)
            if m:
                symbols.append({
                    "type": "symbol",
                    "name": m.group(1),
                    "signature": s[:100],
                    "line_start": idx,
                    "line_end": idx,
                    "docstring": "",
                })
            elif s.startswith(("# ", "## ", "### ")):
                symbols.append({
                    "type": "heading",
                    "name": s,
                    "signature": s,
                    "line_start": idx,
                    "line_end": idx,
                    "docstring": "",
                })

    # Format human/LLM readable outline
    lines_out = [f"File: {clean_target} ({total_lines} lines)"]
    if not symbols:
        lines_out.append("(No top-level classes or functions found)")
    else:
        for sym in symbols:
            if sym.get("type") == "class":
                doc = f" — {sym['docstring']}" if sym.get("docstring") else ""
                lines_out.append(f"- class {sym['name']} (lines {sym['line_start']}-{sym['line_end']}){doc}")
                for m in sym.get("methods", []):
                    m_doc = f" — {m['docstring']}" if m.get("docstring") else ""
                    lines_out.append(f"    - {m['signature']} (lines {m['line_start']}-{m['line_end']}){m_doc}")
            else:
                sig = sym.get("signature") or sym.get("name")
                doc = f" — {sym['docstring']}" if sym.get("docstring") else ""
                lines_out.append(f"- {sig} (lines {sym['line_start']}-{sym['line_end']}){doc}")

    outline_str = "\n".join(lines_out)
    return {
        "status": "success",
        "file_path": clean_target,
        "total_lines": total_lines,
        "total_symbols": len(symbols),
        "outline": outline_str,
    }
