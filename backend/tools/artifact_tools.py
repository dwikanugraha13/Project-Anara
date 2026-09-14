import logging
import os
import re
import tempfile
import urllib.parse
import zipfile
from typing import Any, Dict, List, Optional

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


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
            _generate_binary_pdf(raw_title, content, file_target_path)
        elif ext in [".docx", ".doc"]:
            _generate_binary_docx(raw_title, content, file_target_path)
        else:
            with open(file_target_path, "w", encoding="utf-8") as f:
                f.write(content)

        file_size_kb = round(os.path.getsize(file_target_path) / 1024, 1) or 0.1
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

        packed_files = []
        with zipfile.ZipFile(zip_artifact_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            if files and len(files) > 0:
                for fn in files:
                    clean_fn = fn.strip().strip('"\'')
                    full_p = os.path.join(active_f, clean_fn) if not os.path.isabs(clean_fn) else clean_fn
                    if os.path.exists(full_p) and os.path.isfile(full_p):
                        arcname = os.path.relpath(full_p, active_f) if not os.path.isabs(clean_fn) else os.path.basename(clean_fn)
                        zipf.write(full_p, arcname=arcname)
                        packed_files.append(arcname)
            else:
                for root, dirs, fnames in os.walk(active_f):
                    dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "venv", "__pycache__", ".next"]]
                    for f in fnames:
                        if f.lower().endswith(".zip"):
                            continue
                        f_full = os.path.join(root, f)
                        rel_arc = os.path.relpath(f_full, active_f)
                        zipf.write(f_full, arcname=rel_arc)
                        packed_files.append(rel_arc)

        try:
            import shutil
            shutil.copy2(zip_artifact_path, zip_workspace_path)
        except Exception:
            pass

        file_size_bytes = os.path.getsize(zip_artifact_path)
        file_size_kb = round(file_size_bytes / 1024, 1) or 0.1
        download_url = f"http://localhost:8000/api/agent/artifacts/download/{urllib.parse.quote(safe_filename)}"

        summary_msg = f"Berhasil mengompresi {len(packed_files)} berkas ({file_size_kb} KB). Tersedia untuk diunduh."

        _emit_agent_event("agent_action_complete", {
            "tool_name": "create_zip_archive",
            "action_title": f"Arsip ZIP Siap: {safe_filename}",
            "summary": summary_msg,
            "raw_result": "\n".join([f"- {f}" for f in packed_files]),
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
