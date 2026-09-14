import fnmatch
import logging
import os
import re
from typing import Any, Dict, List, Optional

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


def _extract_text_from_docx(file_path: str) -> str:
    """Extracts text from Microsoft Word .docx files including paragraphs and tables."""
    try:
        import docx
        doc = docx.Document(file_path)
        paragraphs = []
        for p in doc.paragraphs:
            if p.text.strip():
                paragraphs.append(p.text.strip())
        for table in doc.tables:
            for row in table.rows:
                row_txt = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                if row_txt:
                    paragraphs.append(f"| {row_txt} |")
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.warning(f"[AgentTools] Docx extract error: {e}")
        return ""


def _extract_text_from_pdf(file_path: str) -> str:
    """Extracts raw text from PDF file with multiple fallback strategies."""
    text_content = ""
    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        pages_text = []
        for idx, page in enumerate(reader.pages[:30]):
            t = page.extract_text() or ""
            if t.strip():
                pages_text.append(f"[Halaman {idx+1}]\n{t}")
        text_content = "\n\n".join(pages_text)
    except Exception:
        pass

    if not text_content:
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
                matches = re.findall(rb"[(](.*?)[)]\s*Tj", raw)
                if matches:
                    text_content = " ".join([m.decode("latin1", errors="ignore") for m in matches])
        except Exception:
            pass

    return text_content.strip() or "[PDF Terdeteksi: Berisi dokumen digital visual]"


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
        for r, _, files in os.walk(active_f):
            if any(ig in r for ig in [".git", "node_modules", "venv", "__pycache__", ".next"]):
                continue
            for f in files:
                if f.lower() == target_name:
                    return os.path.abspath(os.path.join(r, f))
    return None


async def _tool_read_local_file(file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Reads a local text/document/PDF/DOCX/code file safely.
    Supports optional windowed line-by-line reading with offset (1-indexed) and limit.
    """
    path = (file_path or "").strip().strip('"\'')
    if not path:
        return {"status": "error", "message": "Path file kosong"}

    action_detail = f"{os.path.basename(path)}" + (f" offset={offset} limit={limit}" if offset else "")
    _emit_agent_event("agent_action_start", {
        "tool_name": "read_local_file",
        "action_title": "Baca",
        "detail": action_detail,
        "filename": os.path.basename(path),
        "icon": "file"
    })

    try:
        target_file = _resolve_local_file_path(path)
        if not target_file:
            res_msg = f"File '{os.path.basename(path)}' tidak ditemukan di path komputer."
            return {"status": "error", "message": res_msg}

        ext = os.path.splitext(target_file)[1].lower()
        if ext == ".pdf":
            content = _extract_text_from_pdf(target_file)
        elif ext in [".docx", ".doc"]:
            content = _extract_text_from_docx(target_file) or "[Dokumen Word: Teks berhasil dipindai]"
        else:
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        if offset is not None or limit is not None:
            start_line = max(1, int(offset)) if offset and int(offset) > 0 else 1
            max_lines = min(2000, int(limit)) if limit and int(limit) > 0 else 500
            start_idx = start_line - 1
            end_idx = min(total_lines, start_idx + max_lines)
            slice_lines = lines[start_idx:end_idx]
            numbered_content = "".join([f"{start_line + i}: {line}" for i, line in enumerate(slice_lines)])
            display_content = numbered_content
            summary_msg = f"Membaca baris {start_line}-{end_idx} dari {total_lines} baris."
        else:
            if total_lines > 250:
                numbered_content = "".join([f"{i + 1}: {line}" for i, line in enumerate(lines[:250])])
                display_content = numbered_content + f"\n\n[... dipotong {total_lines - 250} baris lagi. Gunakan offset={251} untuk membaca lanjutan ...]"
                summary_msg = f"Membaca 250 baris pertama dari {total_lines} baris."
            else:
                numbered_content = "".join([f"{i + 1}: {line}" for i, line in enumerate(lines)])
                display_content = numbered_content
                summary_msg = f"Berhasil membaca {total_lines} baris."

        _emit_agent_event("agent_action_complete", {
            "tool_name": "read_local_file",
            "action_title": "Baca",
            "detail": action_detail,
            "filename": os.path.basename(path),
            "file_path": target_file,
            "summary": summary_msg,
            "raw_result": display_content[:800],
            "icon": "file"
        })

        return {
            "status": "success",
            "file_name": os.path.basename(target_file),
            "file_path": target_file,
            "extension": ext,
            "total_lines": total_lines,
            "content": display_content
        }
    except Exception as e:
        logger.warning(f"[AgentTools] Read file error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False
) -> Dict[str, Any]:
    """Selectively edits an existing code or document file in-place by exact string replacement."""
    path = (file_path or "").strip().strip('"\'')
    if not path:
        return {"status": "error", "message": "file_path tidak boleh kosong."}
    if not old_string:
        return {"status": "error", "message": "old_string tidak boleh kosong."}

    _emit_agent_event("agent_action_start", {
        "tool_name": "edit_file",
        "action_title": "Menyunting Berkas",
        "detail": f"File: {os.path.basename(path)}",
        "icon": "edit"
    })

    target_file = _resolve_local_file_path(path)
    if not target_file:
        return {"status": "error", "message": f"Berkas '{path}' tidak ditemukan. Pastikan berkas sudah ada sebelum disunting."}

    try:
        from core import anara_agent
        checkpoint_id = anara_agent.create_checkpoint(None)

        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if old_string not in content:
            return {
                "status": "error",
                "message": (
                    f"old_string tidak ditemukan di dalam berkas '{os.path.basename(target_file)}'. "
                    "Pastikan teks yang ingin diganti cocok persis dengan isi berkas saat dibaca."
                )
            }

        count = content.count(old_string)
        if not replace_all and count > 1:
            return {
                "status": "error",
                "message": (
                    f"Ditemukan {count} kecocokan untuk old_string. "
                    "Sertakan beberapa baris kode di sekitarnya agar unik, atau setel replace_all=True."
                )
            }

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        old_lines = old_string.splitlines()
        new_lines = new_string.splitlines()
        diff_lines = []
        for ol in old_lines:
            diff_lines.append(f"-{ol}")
        for nl in new_lines:
            diff_lines.append(f"+{nl}")
        diff_str = "\n".join(diff_lines)

        added = len(new_lines)
        deleted = len(old_lines)
        size_kb = round(len(new_content.encode("utf-8")) / 1024, 2)
        filename = os.path.basename(target_file)

        git_commit_sha = anara_agent.record_git_commit(
            file_path=target_file,
            message=f"edit {filename} (+{added} -{deleted} lines)"
        )

        rel_dir = os.path.dirname(target_file)
        _emit_agent_event("agent_action_complete", {
            "tool_name": "edit_file",
            "action_title": f"Sunting {filename} {rel_dir} +{added} -{deleted}",
            "detail": f"{filename} {rel_dir}",
            "summary": f"+{added} -{deleted}" + (f" [{git_commit_sha}]" if git_commit_sha else ""),
            "raw_result": diff_str[:3000],
            "file_path": target_file,
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
            "file_path": target_file,
            "filename": filename,
            "file_ext": os.path.splitext(target_file)[1],
            "content": new_content,
            "size_kb": size_kb,
        })

        return {
            "status": "success",
            "file_path": target_file,
            "filename": filename,
            "added_lines": added,
            "deleted_lines": deleted,
            "checkpoint_id": checkpoint_id,
            "git_commit": git_commit_sha,
            "message": f"Berkas '{filename}' berhasil diperbarui (+{added} -{deleted} baris)" + (f" [commit {git_commit_sha}]." if git_commit_sha else "."),
            "diff": diff_str[:1000]
        }
    except Exception as e:
        logger.warning(f"[AgentTools] Edit file error: {e}")
        return {"status": "error", "message": f"Gagal menyunting berkas: {e}"}


async def _tool_write_local_file(file_path: str, content: str) -> Dict[str, Any]:
    """Creates or updates a file locally on the computer (Desktop or workspace)."""
    raw_path = (file_path or "").strip().strip('"\'')
    if not raw_path:
        return {"status": "error", "message": "Path file kosong"}

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
        "action_title": "Menulis File",
        "detail": f"File: {os.path.basename(raw_path)}",
        "icon": "file"
    })

    try:
        from core import anara_agent
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
        anara_agent.ensure_git_repo(None)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        file_ext = os.path.splitext(target_path)[1]
        filename = os.path.basename(target_path)
        size_kb = round(len(content.encode('utf-8')) / 1024, 2)

        git_commit_sha = anara_agent.record_git_commit(
            file_path=target_path,
            message=f"write {filename} ({size_kb} KB)"
        )

        _emit_agent_event("agent_action_complete", {
            "tool_name": "write_local_file",
            "action_title": "File Disimpan",
            "summary": f"{filename} ({size_kb} KB)" + (f" [{git_commit_sha}]" if git_commit_sha else ""),
            "file_path": target_path,
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
            "file_path": target_path,
            "filename": filename,
            "file_ext": file_ext,
            "content": content,
            "size_kb": size_kb,
        })

        return {
            "status": "success",
            "message": f"File berhasil ditulis ke '{target_path}'" + (f" [commit {git_commit_sha}]." if git_commit_sha else "."),
            "file_path": target_path,
            "checkpoint_id": checkpoint_id,
            "git_commit": git_commit_sha,
            "size_bytes": len(content.encode('utf-8'))
        }
    except Exception as e:
        logger.warning(f"[AgentTools] Write file error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_list_directory(directory_path: Optional[str] = None) -> Dict[str, Any]:
    """Lists files and folders inside a local directory."""
    dir_path = (directory_path or "").strip().strip('"\'')
    if not dir_path:
        target_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    else:
        target_dir = os.path.expanduser(dir_path)

    _emit_agent_event("agent_action_start", {
        "tool_name": "list_directory",
        "action_title": "Menjelajah Direktori",
        "detail": f"Folder: {os.path.basename(target_dir) or target_dir}",
        "icon": "📂"
    })

    try:
        if not os.path.exists(target_dir):
            return {"status": "error", "message": f"Direktori '{target_dir}' tidak ditemukan"}

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
            "action_title": "Isi Direktori Terbaca",
            "summary": f"Ditemukan {len(entries)} file & folder.",
            "icon": "📂"
        })

        return {
            "status": "success",
            "directory": target_dir,
            "total_items": len(entries),
            "items": entries
        }
    except Exception as e:
        logger.warning(f"[AgentTools] List dir error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_scan_workspace_folder(folder_path: str) -> Dict[str, Any]:
    """Scans and builds a recursive file tree of an imported local folder project."""
    raw_path = (folder_path or "").strip().strip('"\'')
    target_dir = os.path.expanduser(raw_path) if raw_path else os.path.join(os.path.expanduser("~"), "Desktop")

    _emit_agent_event("agent_action_start", {
        "tool_name": "scan_workspace_folder",
        "action_title": "Memindai Pohon Proyek",
        "detail": f"Folder: {os.path.basename(target_dir)}",
        "icon": "📁"
    })

    IGNORED_DIRS = {".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build", ".vscode"}
    tree = []
    total_files = 0

    try:
        if not os.path.exists(target_dir):
            return {"status": "error", "message": f"Folder '{target_dir}' tidak ditemukan"}

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

        _emit_agent_event("agent_action_complete", {
            "tool_name": "scan_workspace_folder",
            "action_title": "Pohon Proyek Terindeks",
            "summary": f"Berhasil memindai {total_files} file dalam proyek.",
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


async def _tool_glob_find_files(pattern: str, path: Optional[str] = None) -> Dict[str, Any]:
    """Fast file pattern matching across the project workspace."""
    from core import anara_agent

    pat = (pattern or "").strip()
    if not pat:
        return {"status": "error", "message": "Pola glob pattern tidak boleh kosong."}

    active_f = anara_agent.get_session_dir()
    root_dir = os.path.abspath(os.path.expanduser(path)) if path else active_f
    if not os.path.exists(root_dir):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        root_dir = base_dir

    _emit_agent_event("agent_action_start", {
        "tool_name": "glob_find_files",
        "action_title": "Pencarian Berkas (Glob)",
        "detail": f"Pola: {pat}",
        "icon": "search"
    })

    IGNORED_DIRS = {".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build", ".venv", ".vscode"}
    matches = []

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
            if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(f, pat):
                matches.append(rel_path)
                if len(matches) >= 100:
                    break
        if len(matches) >= 100:
            break

    summary_msg = f"Ditemukan {len(matches)} berkas cocok dengan pola '{pat}'."
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
        return {"status": "error", "message": "Pola pencarian regex tidak boleh kosong."}

    active_f = anara_agent.get_session_dir()
    root_dir = os.path.abspath(os.path.expanduser(path)) if path else active_f
    if not os.path.exists(root_dir):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        root_dir = base_dir

    _emit_agent_event("agent_action_start", {
        "tool_name": "grep_search_code",
        "action_title": "Pencarian Kode (Grep)",
        "detail": f"Regex: {pat}",
        "icon": "search"
    })

    try:
        regex = re.compile(pat, re.IGNORECASE)
    except re.error as e:
        return {"status": "error", "message": f"Pola regex tidak valid: {e}"}

    IGNORED_DIRS = {".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build", ".venv", ".vscode"}
    BINARY_EXTS = {".png", ".jpg", ".jpeg", ".ico", ".pdf", ".zip", ".tar", ".exe", ".dll", ".woff", ".woff2", ".ttf", ".sqlite", ".db"}
    matches = []

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
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
                            matches.append({
                                "file": rel_path,
                                "line_number": line_num,
                                "line": line.rstrip("\r\n")[:250]
                            })
                            if len(matches) >= 60:
                                break
            except Exception:
                continue
        if len(matches) >= 60:
            break

    grep_detail = f"/ pattern={pat}" + (f" include={include}" if include else "")
    summary_str = "\n".join([f"{m['file']}:{m['line_number']}: {m['line']}" for m in matches[:20]])
    _emit_agent_event("agent_action_complete", {
        "tool_name": "grep_search_code",
        "action_title": "Grep",
        "detail": grep_detail,
        "summary": f"Ditemukan {len(matches)} baris cocok.",
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
