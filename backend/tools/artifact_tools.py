import logging
import os
import re
import tempfile
import urllib.parse
import zipfile
from typing import Any, Dict, List, Optional

from .events import _emit_agent_event

logger = logging.getLogger(__name__)

_TURN_ARTIFACTS: List[Dict[str, Any]] = []


def register_turn_artifact(file_path: str, filename: str, mime_type: str = ""):
    """Registers an artifact generated during the turn for multi-channel auto-dispatching."""
    if not file_path or not os.path.isfile(file_path):
        return
    for art in _TURN_ARTIFACTS:
        if art.get("path") == file_path:
            return
    _TURN_ARTIFACTS.append({
        "path": file_path,
        "filename": filename,
        "mime_type": mime_type or ("application/zip" if filename.endswith(".zip") else "application/pdf" if filename.endswith(".pdf") else "application/octet-stream")
    })


def get_turn_artifacts() -> List[Dict[str, Any]]:
    """Returns artifacts created during the turn."""
    return list(_TURN_ARTIFACTS)


def clear_turn_artifacts():
    """Clears artifacts created during the turn."""
    _TURN_ARTIFACTS.clear()




def _generate_binary_pdf(title: str, content: str, output_path: str, image_urls: Optional[List[str]] = None):
    """Generates a professional PDF document with optional photos using reportlab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0284c7'),
        spaceAfter=14
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=8
    )

    story = []
    story.append(Paragraph(title or "Dokumen Anara Agent", title_style))
    story.append(Spacer(1, 10))

    for line in content.split("\n"):
        clean_l = line.strip()
        if not clean_l:
            story.append(Spacer(1, 6))
            continue
        clean_l = clean_l.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        clean_l = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", clean_l)
        clean_l = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", clean_l)
        story.append(Paragraph(clean_l, body_style))

    doc.build(story)


def _generate_binary_docx(title: str, content: str, output_path: str):
    """Generates a professional Microsoft Word (.docx) document using python-docx."""
    import docx
    from docx.shared import Pt, RGBColor

    doc = docx.Document()

    title_text = (title or "Dokumen Resmi").strip()
    p_title = doc.add_paragraph()
    r_title = p_title.add_run(title_text)
    r_title.bold = True
    r_title.font.size = Pt(20)
    r_title.font.color.rgb = RGBColor(2, 132, 199)
    p_title.paragraph_format.space_after = Pt(14)

    def _add_styled_runs(paragraph, text: str):
        pattern = r"(\*\*[^*]+\*\*|\*[^*]+\*)"
        parts = re.split(pattern, text)
        for part in parts:
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                r = paragraph.add_run(part[2:-2])
                r.bold = True
            elif part.startswith("*") and part.endswith("*"):
                r = paragraph.add_run(part[1:-1])
                r.italic = True
            else:
                paragraph.add_run(part)

    for line in content.split("\n"):
        clean_l = line.strip()
        if not clean_l:
            continue
        
        if clean_l.startswith("### "):
            h = doc.add_paragraph()
            r = h.add_run(clean_l.replace("### ", "").strip())
            r.bold = True
            r.font.size = Pt(13)
            r.font.color.rgb = RGBColor(2, 132, 199)
            h.paragraph_format.space_before = Pt(10)
            h.paragraph_format.space_after = Pt(4)
        elif clean_l.startswith("## "):
            h = doc.add_paragraph()
            r = h.add_run(clean_l.replace("## ", "").strip())
            r.bold = True
            r.font.size = Pt(15)
            r.font.color.rgb = RGBColor(2, 132, 199)
            h.paragraph_format.space_before = Pt(12)
            h.paragraph_format.space_after = Pt(4)
        elif clean_l.startswith("# "):
            h = doc.add_paragraph()
            r = h.add_run(clean_l.replace("# ", "").strip())
            r.bold = True
            r.font.size = Pt(17)
            r.font.color.rgb = RGBColor(2, 132, 199)
            h.paragraph_format.space_before = Pt(14)
            h.paragraph_format.space_after = Pt(6)
        elif clean_l.startswith("- ") or clean_l.startswith("* ") or clean_l.startswith("• "):
            p = doc.add_paragraph(style='List Bullet')
            _add_styled_runs(p, clean_l[2:].strip())
            p.paragraph_format.space_after = Pt(3)
        elif re.match(r"^\d+\.\s+", clean_l):
            p = doc.add_paragraph(style='List Number')
            sub_txt = re.sub(r"^\d+\.\s+", "", clean_l).strip()
            _add_styled_runs(p, sub_txt)
            p.paragraph_format.space_after = Pt(3)
        else:
            p = doc.add_paragraph()
            _add_styled_runs(p, clean_l)
            p.paragraph_format.space_after = Pt(6)

    doc.save(output_path)


async def _tool_generate_file_artifact(
    filename: str,
    content: str,
    title: Optional[str] = None,
    destination_folder: Optional[str] = None
) -> Dict[str, Any]:
    """Universal Hermes/OpenClaw-Grade File Artifact Generator."""
    raw_name = (filename or "document.txt").strip().strip('"\'')
    raw_title = (title or os.path.splitext(raw_name)[0]).strip()
    ext = os.path.splitext(raw_name)[1].lower() or ".txt"
    base_name = os.path.splitext(raw_name)[0]
    safe_filename = f"{base_name}{ext}"

    artifacts_dir = os.path.join(tempfile.gettempdir(), "anara_agent_artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    icon = "📕" if ext == ".pdf" else "📘" if ext in [".docx", ".doc"] else "📦" if ext == ".zip" else "📄"

    _emit_agent_event("agent_action_start", {
        "tool_name": "generate_file_artifact",
        "action_title": f"Membuat Berkas: {safe_filename}",
        "detail": f"Format: {ext.upper()}",
        "icon": icon
    })

    try:
        if destination_folder and destination_folder.strip():
            dest_clean = os.path.expanduser(destination_folder.strip().strip('"\''))
            if os.path.isdir(dest_clean):
                file_target_path = os.path.join(dest_clean, safe_filename)
            else:
                file_target_path = dest_clean
        else:
            file_target_path = os.path.join(artifacts_dir, safe_filename)

        os.makedirs(os.path.dirname(file_target_path), exist_ok=True)

        if ext == ".pdf":
            await asyncio.to_thread(_generate_binary_pdf, raw_title, content, file_target_path)
        elif ext in [".docx", ".doc"]:
            await asyncio.to_thread(_generate_binary_docx, raw_title, content, file_target_path)
        else:
            def _write_plain():
                with open(file_target_path, "w", encoding="utf-8") as f:
                    f.write(content)
            await asyncio.to_thread(_write_plain)

        file_size_kb = round(os.path.getsize(file_target_path) / 1024, 1) or 0.1
        register_turn_artifact(file_target_path, safe_filename)
        download_url = f"http://localhost:8000/api/agent/artifacts/download/{urllib.parse.quote(safe_filename)}"

        _emit_agent_event("agent_action_complete", {
            "tool_name": "generate_file_artifact",
            "action_title": f"Berkas Siap: {safe_filename}",
            "summary": f"Format {ext.upper()} • {file_size_kb} KB • Tersedia untuk diunduh.",
            "raw_result": content[:300],
            "icon": icon
        })

        _emit_agent_event("agent_hud_project", {
            "visual_type": "document_viewer",
            "title": raw_title,
            "summary": f"Berkas '{safe_filename}' telah dibuat dan siap diunduh.",
            "documentViewerData": {
                "fileName": safe_filename,
                "fileExt": ext,
                "fileSizeKb": file_size_kb,
                "totalChars": len(content),
                "content": content[:8000],
                "isPdf": ext == ".pdf",
                "downloadUrl": download_url
            }
        })

        if destination_folder:
            msg = f"Berkas '{safe_filename}' ({file_size_kb} KB) berhasil dibuat dan disimpan langsung ke '{file_target_path}'."
        else:
            msg = f"Berkas '{safe_filename}' ({file_size_kb} KB) telah selesai dibuat dan tampil di layar HUD. Pengguna dapat mengunduhnya lewat tombol download."

        return {
            "status": "success",
            "message": msg,
            "filename": safe_filename,
            "file_path": file_target_path,
            "download_url": download_url,
            "size_kb": file_size_kb
        }

    except Exception as e:
        logger.error(f"[AgentTools] Generate artifact error: {e}", exc_info=True)
        return {"status": "error", "message": f"Gagal membuat berkas '{safe_filename}': {str(e)}"}


async def _tool_create_zip_archive(
    archive_name: Optional[str] = None,
    folder_path: Optional[str] = None,
    files: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Creates a real binary ZIP archive from project workspace files or specified files."""
    raw_name = (archive_name or "project.zip").strip().strip('"\'')
    if not raw_name.lower().endswith(".zip"):
        raw_name += ".zip"
    safe_filename = os.path.basename(raw_name)

    _emit_agent_event("agent_action_start", {
        "tool_name": "create_zip_archive",
        "action_title": f"Membuat Arsip ZIP: {safe_filename}",
        "detail": "Mengumpulkan & mengompresi berkas proyek...",
        "icon": "📦"
    })

    try:
        from core import anara_agent
        from memory import memory_engine

        active_f = None
        if folder_path and folder_path.strip():
            c_f = os.path.expanduser(folder_path.strip().strip('"\''))
            if os.path.isdir(c_f):
                active_f = c_f
        if not active_f:
            active_f = anara_agent.get_session_dir()

        os.makedirs(active_f, exist_ok=True)

        existing_files = [f for f in os.listdir(active_f) if not f.endswith(".zip") and os.path.isfile(os.path.join(active_f, f))]
        if len(existing_files) == 0:
            logger.info("[AgentTools] Workspace is empty — running Hermes Auto-Recovery from recent conversation code blocks...")
            recent_turns = memory_engine.get_recent_conversations(limit=6)
            recovered_count = 0
            for turn in reversed(recent_turns):
                ai_text = turn.get("ai_text") or ""
                code_matches = re.findall(r"```([a-zA-Z0-9_\-\.]+)?\s*\n([\s\S]*?)```", ai_text)
                for lang_hint, code_content in code_matches:
                    clean_code = code_content.strip()
                    if not clean_code or len(clean_code) < 10:
                        continue
                    
                    fname = None
                    fn_comment = re.search(r"(?://|/\*|#|<!--)\s*(?:filename|file|nama berkas|berkas)\s*[:=]\s*([a-zA-Z0-9_\-\.]+)", code_content, re.IGNORECASE)
                    if fn_comment:
                        fname = fn_comment.group(1).strip()
                    elif lang_hint:
                        lh = lang_hint.lower()
                        if lh in ["html", "htm"]:
                            fname = "index.html"
                        elif lh in ["css"]:
                            fname = "styles.css" if not os.path.exists(os.path.join(active_f, "styles.css")) else f"style_{recovered_count}.css"
                        elif lh in ["js", "javascript"]:
                            fname = "app.js" if not os.path.exists(os.path.join(active_f, "app.js")) else f"script_{recovered_count}.js"
                        elif lh in ["py", "python"]:
                            fname = "main.py" if not os.path.exists(os.path.join(active_f, "main.py")) else f"script_{recovered_count}.py"
                        elif lh in ["json"]:
                            fname = "data.json"
                    
                    if not fname:
                        if "<!doctype html" in clean_code.lower() or "<html" in clean_code.lower():
                            fname = "index.html"
                        elif "body {" in clean_code or "@tailwind" in clean_code:
                            fname = "styles.css"
                        elif "function" in clean_code or "const " in clean_code or "document.get" in clean_code:
                            fname = "app.js"
                        else:
                            recovered_count += 1
                            fname = f"file_{recovered_count}.txt"

                    target_rec_path = os.path.join(active_f, fname)
                    with open(target_rec_path, "w", encoding="utf-8") as f_rec:
                        f_rec.write(code_content)
                    logger.info(f"[AgentTools] Hermes Recovered '{fname}' ({len(code_content)} chars) into workspace")

        artifacts_dir = os.path.join(tempfile.gettempdir(), "anara_agent_artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        zip_artifact_path = os.path.join(artifacts_dir, safe_filename)
        zip_workspace_path = os.path.join(active_f, safe_filename)

        def _zip_worker():
            packed = []
            with zipfile.ZipFile(zip_artifact_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                if files and len(files) > 0:
                    for fn in files:
                        clean_fn = fn.strip().strip('"\'')
                        full_p = os.path.join(active_f, clean_fn) if not os.path.isabs(clean_fn) else clean_fn
                        if os.path.exists(full_p) and os.path.isfile(full_p):
                            arcname = os.path.relpath(full_p, active_f) if not os.path.isabs(clean_fn) else os.path.basename(clean_fn)
                            zipf.write(full_p, arcname=arcname)
                            packed.append(arcname)
                else:
                    for root, dirs, fnames in os.walk(active_f):
                        dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build"]]
                        for f in fnames:
                            if f.lower().endswith(".zip"):
                                continue
                            f_full = os.path.join(root, f)
                            rel_arc = os.path.relpath(f_full, active_f)
                            zipf.write(f_full, arcname=rel_arc)
                            packed.append(rel_arc)

            try:
                import shutil
                shutil.copy2(zip_artifact_path, zip_workspace_path)
            except Exception:
                pass
            return packed

        packed_files = await asyncio.to_thread(_zip_worker)

        file_size_bytes = os.path.getsize(zip_artifact_path)
        file_size_kb = round(file_size_bytes / 1024, 1) or 0.1
        register_turn_artifact(zip_workspace_path, safe_filename, 'application/zip')
        download_url = f"http://localhost:8000/api/agent/artifacts/download/{urllib.parse.quote(safe_filename)}"

        summary_msg = f"Berhasil mengompresi {len(packed_files)} berkas ({file_size_kb} KB). Tersedia untuk diunduh."

        _emit_agent_event("agent_action_complete", {
            "tool_name": "create_zip_archive",
            "action_title": f"Arsip ZIP Siap: {safe_filename}",
            "summary": summary_msg,
            "raw_result": "\n".join([f"- {f}" for f in packed_files]),
            "file_path": zip_workspace_path,
            "filename": safe_filename,
            "icon": "zip"
        })

        _emit_agent_event("agent_hud_project", {
            "visual_type": "document_viewer",
            "title": f"Arsip Proyek: {safe_filename}",
            "summary": f"Berkas ZIP proyek ({file_size_kb} KB) berisi {len(packed_files)} file siap diunduh.",
            "documentViewerData": {
                "fileName": safe_filename,
                "fileExt": ".zip",
                "fileSizeKb": file_size_kb,
                "totalChars": len(packed_files),
                "content": f"Daftar Berkas dalam {safe_filename}:\n" + "\n".join([f"• {f}" for f in packed_files]) + f"\n\nLokasi berkas: {zip_workspace_path}",
                "isPdf": False,
                "isZip": True,
                "archiveFiles": packed_files,
                "archiveTotal": len(packed_files),
                "downloadUrl": download_url
            }
        })

        return {
            "status": "success",
            "message": f"Arsip ZIP '{safe_filename}' ({file_size_kb} KB) telah berhasil dibuat! Berisi {len(packed_files)} berkas: {', '.join(packed_files)}. Kartu unduhan interaktif telah tampil di layar HUD.",
            "filename": safe_filename,
            "download_url": download_url,
            "file_path": zip_workspace_path,
            "size_kb": file_size_kb,
            "files_count": len(packed_files),
            "files": packed_files
        }

    except Exception as e:
        logger.error(f"[AgentTools] Create zip archive error: {e}", exc_info=True)
        return {"status": "error", "message": f"Gagal membuat arsip ZIP '{safe_filename}': {str(e)}"}


async def _tool_extract_zip_archive(
    zip_path: str,
    destination_folder: Optional[str] = None
) -> Dict[str, Any]:
    """Fast native extraction of a ZIP archive with path traversal protection (Unzip in milliseconds)."""
    raw_zip = (zip_path or "").strip().strip('"\'')
    if not raw_zip:
        return {"status": "error", "message": "Path berkas ZIP tidak boleh kosong."}

    from core import anara_agent
    active_f = anara_agent.get_session_dir()

    resolved_zip = os.path.abspath(raw_zip) if os.path.isabs(raw_zip) else os.path.join(active_f, raw_zip)
    if not os.path.exists(resolved_zip) or not os.path.isfile(resolved_zip):
        alt = os.path.join(tempfile.gettempdir(), "anara_agent_artifacts", os.path.basename(raw_zip))
        if os.path.exists(alt):
            resolved_zip = alt
        else:
            return {"status": "error", "message": f"Berkas ZIP tidak ditemukan: '{raw_zip}'"}

    dest_dir = os.path.abspath(destination_folder.strip().strip('"\'')) if destination_folder else active_f
    os.makedirs(dest_dir, exist_ok=True)

    _emit_agent_event("agent_action_start", {
        "tool_name": "extract_zip_archive",
        "action_title": f"Mengekstrak ZIP: {os.path.basename(resolved_zip)}",
        "detail": f"Tujuan: {dest_dir}",
        "icon": "📦"
    })

    def _extract_worker():
        extracted = []
        with zipfile.ZipFile(resolved_zip, "r") as zipf:
            for member in zipf.infolist():
                target_path = os.path.abspath(os.path.join(dest_dir, member.filename))
                if not (target_path == dest_dir or target_path.startswith(dest_dir + os.sep)):
                    logger.warning(f"[Unzip] Blocked path traversal attempt in zip: {member.filename}")
                    continue
                zipf.extract(member, dest_dir)
                extracted.append(member.filename)
        return extracted

    try:
        extracted_files = await asyncio.to_thread(_extract_worker)
        msg = f"Berhasil mengekstrak {len(extracted_files)} berkas dari '{os.path.basename(resolved_zip)}' ke '{dest_dir}'."
        _emit_agent_event("agent_action_complete", {
            "tool_name": "extract_zip_archive",
            "action_title": f"ZIP Terekstrak: {os.path.basename(resolved_zip)}",
            "summary": f"{len(extracted_files)} berkas terekstrak ke {dest_dir}",
            "raw_result": "\n".join([f"- {f}" for f in extracted_files[:30]]),
            "icon": "📦"
        })
        return {
            "status": "success",
            "message": msg,
            "zip_path": resolved_zip,
            "destination_folder": dest_dir,
            "extracted_count": len(extracted_files),
            "files": extracted_files[:100]
        }
    except Exception as e:
        logger.error(f"[AgentTools] Extract zip error: {e}")
        return {"status": "error", "message": f"Gagal mengekstrak berkas ZIP: {str(e)}"}


async def _tool_read_zip_contents(zip_path: str) -> Dict[str, Any]:
    """Fast inspection of ZIP archive contents without extracting to disk (Inspect ZIP in 1ms)."""
    raw_zip = (zip_path or "").strip().strip('"\'')
    if not raw_zip:
        return {"status": "error", "message": "Path berkas ZIP tidak boleh kosong."}

    from core import anara_agent
    active_f = anara_agent.get_session_dir()

    resolved_zip = os.path.abspath(raw_zip) if os.path.isabs(raw_zip) else os.path.join(active_f, raw_zip)
    if not os.path.exists(resolved_zip):
        alt = os.path.join(tempfile.gettempdir(), "anara_agent_artifacts", os.path.basename(raw_zip))
        if os.path.exists(alt):
            resolved_zip = alt
        else:
            return {"status": "error", "message": f"Berkas ZIP tidak ditemukan: '{raw_zip}'"}

    def _read_worker():
        items = []
        total_uncompressed = 0
        total_compressed = 0
        with zipfile.ZipFile(resolved_zip, "r") as zipf:
            for info in zipf.infolist():
                total_uncompressed += info.file_size
                total_compressed += info.compress_size
                items.append({
                    "filename": info.filename,
                    "size_kb": round(info.file_size / 1024, 2),
                    "compressed_kb": round(info.compress_size / 1024, 2),
                    "is_dir": info.is_dir(),
                    "date": f"{info.date_time[0]}-{info.date_time[1]:02d}-{info.date_time[2]:02d}"
                })
        return items, total_uncompressed, total_compressed

    try:
        items, total_uncomp, total_comp = await asyncio.to_thread(_read_worker)
        ratio = round((1 - (total_comp / total_uncomp)) * 100, 1) if total_uncomp > 0 else 0
        return {
            "status": "success",
            "zip_name": os.path.basename(resolved_zip),
            "file_path": resolved_zip,
            "total_files": len([i for i in items if not i["is_dir"]]),
            "uncompressed_size_kb": round(total_uncomp / 1024, 1),
            "compressed_size_kb": round(total_comp / 1024, 1),
            "compression_ratio": f"{ratio}%",
            "contents": items[:60]
        }
    except Exception as e:
        logger.error(f"[AgentTools] Read zip contents error: {e}")
        return {"status": "error", "message": f"Gagal membaca isi ZIP: {str(e)}"}


async def _tool_send_document_file(
    file_path: str,
    channel: Optional[str] = None,
    recipient: Optional[str] = None,
    caption: Optional[str] = None
) -> Dict[str, Any]:
    """Sends a local document file (.pdf, .docx, .zip, etc.) directly to Telegram or WhatsApp chat."""
    raw_path = (file_path or "").strip().strip('"\'')
    if not raw_path:
        return {"status": "error", "message": "Path berkas tidak boleh kosong."}

    from core import anara_agent
    active_f = anara_agent.get_session_dir()
    resolved_path = os.path.abspath(raw_path) if os.path.isabs(raw_path) else os.path.join(active_f, raw_path)
    if not os.path.isfile(resolved_path):
        alt = os.path.join(tempfile.gettempdir(), "anara_agent_artifacts", os.path.basename(raw_path))
        if os.path.isfile(alt):
            resolved_path = alt
        else:
            return {"status": "error", "message": f"Berkas tidak ditemukan: '{raw_path}'"}

    target_channel = (channel or "telegram").lower().strip()
    filename = os.path.basename(resolved_path)

    if target_channel == "whatsapp":
        from integrations.whatsapp import send_whatsapp_document
        res = await send_whatsapp_document(to=recipient or "", file_path=resolved_path, caption=caption or filename)
        return {"status": res.get("status", "success"), "channel": "whatsapp", "filename": filename, "result": res}
    else:
        from integrations.telegram import send_telegram_document
        res = await send_telegram_document(file_path=resolved_path, chat_id=recipient, caption=caption or filename)
        return {"status": res.get("status", "success"), "channel": "telegram", "filename": filename, "result": res}


async def _tool_rezip_archive(
    zip_path: str,
    files_to_add: List[str],
    files_to_remove: Optional[List[str]] = None,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fast native updating/re-zipping of an existing ZIP archive without fully unpacking it.
    Can add new files, overwrite existing files, or remove files in milliseconds.
    """
    raw_zip = (zip_path or "").strip().strip('"\'')
    if not raw_zip:
        return {"status": "error", "message": "Path berkas ZIP asal tidak boleh kosong."}

    from core import anara_agent
    active_f = anara_agent.get_session_dir()

    resolved_zip = os.path.abspath(raw_zip) if os.path.isabs(raw_zip) else os.path.join(active_f, raw_zip)
    if not os.path.exists(resolved_zip) or not os.path.isfile(resolved_zip):
        alt = os.path.join(tempfile.gettempdir(), "anara_agent_artifacts", os.path.basename(raw_zip))
        if os.path.isfile(alt):
            resolved_zip = alt
        else:
            return {"status": "error", "message": f"Berkas ZIP asal tidak ditemukan: '{raw_zip}'"}

    target_out = os.path.abspath(output_path.strip().strip('"\'')) if output_path else resolved_zip
    remove_set = {r.strip().lower() for r in (files_to_remove or [])}
    add_paths = [os.path.abspath(p.strip().strip('"\'')) if os.path.isabs(p.strip().strip('"\'')) else os.path.join(active_f, p.strip().strip('"\'')) for p in (files_to_add or [])]

    valid_adds = [p for p in add_paths if os.path.isfile(p)]
    if not valid_adds and not remove_set:
        return {"status": "error", "message": "Tidak ada berkas yang valid untuk ditambahkan atau dihapus."}

    _emit_agent_event("agent_action_start", {
        "tool_name": "rezip_archive",
        "action_title": f"Memperbarui ZIP: {os.path.basename(resolved_zip)}",
        "detail": f"Tambah: {len(valid_adds)} berkas, Hapus: {len(remove_set)} berkas",
        "icon": "??"
    })

    def _rezip_worker():
        temp_fd, temp_zip = tempfile.mkstemp(suffix=".zip", prefix="rezip_")
        os.close(temp_fd)

        added_names = {os.path.basename(p).lower(): p for p in valid_adds}
        final_entries = []

        with zipfile.ZipFile(resolved_zip, "r") as zip_in, zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zip_out:
            for item in zip_in.infolist():
                norm_name = item.filename.lower()
                base_norm = os.path.basename(item.filename).lower()

                if norm_name in remove_set or base_norm in remove_set:
                    logger.info(f"[Rezip] Removed from zip: {item.filename}")
                    continue

                if base_norm in added_names or norm_name in added_names:
                    continue

                zip_out.writestr(item, zip_in.read(item.filename))
                final_entries.append(item.filename)

            for file_p in valid_adds:
                arc_name = os.path.basename(file_p)
                zip_out.write(file_p, arcname=arc_name)
                final_entries.append(arc_name)

        import shutil
        os.makedirs(os.path.dirname(target_out), exist_ok=True)
        shutil.move(temp_zip, target_out)
        return final_entries

    try:
        final_contents = await asyncio.to_thread(_rezip_worker)
        file_size_bytes = os.path.getsize(target_out)
        file_size_kb = round(file_size_bytes / 1024, 1) or 0.1
        safe_name = os.path.basename(target_out)
        download_url = f"http://localhost:8000/api/agent/artifacts/download/{urllib.parse.quote(safe_name)}"

        register_turn_artifact(target_out, safe_name, "application/zip")

        _emit_agent_event("agent_action_complete", {
            "tool_name": "rezip_archive",
            "action_title": f"ZIP Diperbarui: {safe_name}",
            "summary": f"Kini berisi {len(final_contents)} berkas ({file_size_kb} KB).",
            "raw_result": "\n".join([f"- {f}" for f in final_contents]),
            "icon": "??"
        })

        return {
            "status": "success",
            "message": f"Arsip ZIP '{safe_name}' ({file_size_kb} KB) berhasil diperbarui! Kini berisi {len(final_contents)} berkas: {', '.join(final_contents)}.",
            "zip_path": target_out,
            "filename": safe_name,
            "download_url": download_url,
            "size_kb": file_size_kb,
            "total_files": len(final_contents),
            "files": final_contents
        }
    except Exception as e:
        logger.error(f"[AgentTools] Rezip archive error: {e}", exc_info=True)
        return {"status": "error", "message": f"Gagal memperbarui berkas ZIP: {str(e)}"}
