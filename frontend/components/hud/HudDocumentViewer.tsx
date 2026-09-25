"use client";

import React, { useState } from "react";
import { DocumentViewerData, WorkspaceFolderData, HudDismissButton } from "./types";

interface HudDocumentViewerProps {
  documentViewerData?: DocumentViewerData;
  workspaceFolderData?: WorkspaceFolderData;
  onOpenFile?: (filePath: string) => void;
  onDismiss?: () => void;
}

export default function HudDocumentViewer({
  documentViewerData,
  workspaceFolderData,
  onOpenFile,
  onDismiss,
}: HudDocumentViewerProps) {
  const [copiedCode, setCopiedCode] = useState(false);

  const handleCopyCode = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  if (documentViewerData) {
    const isPdf = documentViewerData.isPdf || documentViewerData.fileExt === ".pdf";
    const isWord = documentViewerData.fileExt === ".docx" || documentViewerData.fileExt === ".doc";
    const isZip = documentViewerData.fileExt === ".zip";

    return (
      <div className="mt-2.5 rounded-2xl overflow-hidden border border-cyan-400/40 bg-slate-950/90 backdrop-blur-xl shadow-[0_0_35px_rgba(34,211,238,0.25)] text-white select-none">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-cyan-950/90 via-slate-900/90 to-indigo-950/90 border-b border-cyan-400/30 text-[11px] font-mono">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
            <span className="text-cyan-300 font-bold uppercase tracking-widest truncate">
               {isPdf ? "📄 PDF DOCUMENT VIEWER" : isWord ? "📘 WORD DOCX VIEWER" : isZip ? "📦 ZIP ARCHIVE VIEWER" : "📄 WORKSPACE DOCUMENT FILES"}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="px-2 py-0.5 rounded-md bg-white/10 text-slate-300 border border-white/10 text-[10px] font-mono">
              {documentViewerData.fileSizeKb} KB
            </span>
            <button
              onClick={() => handleCopyCode(documentViewerData.content)}
              className="px-2.5 py-1 rounded-lg bg-white/10 hover:bg-white/20 text-slate-200 border border-white/15 text-[10px] font-semibold cursor-pointer transition-all"
            >
              {copiedCode ? "✓ Disalin" : "Salin"}
            </button>
            {documentViewerData.downloadUrl && (
              <a
                href={documentViewerData.downloadUrl}
                download={documentViewerData.fileName}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1 rounded-lg bg-gradient-to-r from-cyan-500/30 to-indigo-500/30 hover:from-cyan-500/50 hover:to-indigo-500/50 text-cyan-100 border border-cyan-400/40 text-[10px] font-bold cursor-pointer transition-all flex items-center gap-1 shadow-[0_0_10px_rgba(34,211,238,0.2)]"
              >
                <span>📥 Unduh {isPdf ? "PDF" : isWord ? "DOCX" : isZip ? "ZIP" : documentViewerData.fileExt.toUpperCase()}</span>
              </a>
            )}
            <HudDismissButton onDismiss={onDismiss} />
          </div>
        </div>

        {/* Body */}
        <div className="p-4 sm:p-5 space-y-3 font-sans">
          <div className="flex items-center gap-2.5">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-lg shrink-0 border ${
              isPdf
                ? "bg-rose-500/20 border-rose-400/40 text-rose-300"
                : isWord
                ? "bg-blue-500/20 border-blue-400/40 text-blue-300"
                : isZip
                ? "bg-amber-500/20 border-amber-400/40 text-amber-300"
                : "bg-cyan-500/20 border-cyan-400/40 text-cyan-300"
            }`}>
              {isPdf ? "📕" : isWord ? "📘" : isZip ? "📦" : "📄"}
            </div>
            <div className="min-w-0">
              <h4 className="text-sm font-bold text-white truncate font-mono">{documentViewerData.fileName}</h4>
              <p className="text-[11px] text-slate-400">
                {isPdf
                  ? "Binary PDF document text intelligently extracted by Anara"
                  : isWord
                  ? "Dokumen resmi Microsoft Word (.docx) berhasil dibuat"
                  : isZip
                  ? "Compressed project file archive (.zip) ready for download"
                  : `Format ${documentViewerData.fileExt.toUpperCase()} • ${documentViewerData.totalChars || documentViewerData.content.length} karakter`}
              </p>
            </div>
          </div>

          {isZip && (documentViewerData as any).archiveFiles && (documentViewerData as any).archiveFiles.length > 0 ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                <span>Archive Contents ({(documentViewerData as any).archiveFiles.length} files):</span>
                <span className="text-[10px] text-emerald-300 font-bold">✓ Terkompresi Otomatis</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-[220px] overflow-y-auto custom-scrollbar p-1">
                {(documentViewerData as any).archiveFiles.map((fn: string, fIdx: number) => {
                  const ext = fn.split(".").pop()?.toLowerCase() || "";
                  const icon = ext === "html" || ext === "htm" ? "🌐" : ext === "css" ? "🎨" : ext === "js" || ext === "ts" ? "💻" : ext === "py" ? "🐍" : ext === "json" ? "📋" : "📄";
                  return (
                    <div
                      key={fIdx}
                      className="flex items-center justify-between p-2 rounded-xl bg-black/40 border border-white/10 text-xs font-mono text-slate-200"
                    >
                      <div className="flex items-center gap-2 truncate min-w-0 flex-1">
                        <span className="shrink-0">{icon}</span>
                        <span className="truncate">{fn}</span>
                      </div>
                      <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/5 shrink-0 ml-1">
                        {ext}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="p-3.5 rounded-xl bg-black/60 border border-white/10 text-xs text-slate-200 leading-relaxed max-h-[220px] overflow-y-auto custom-scrollbar font-mono whitespace-pre-wrap selection:bg-cyan-500/30">
              {documentViewerData.content}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (workspaceFolderData) {
    return (
      <div className="mt-2.5 rounded-2xl overflow-hidden border border-indigo-400/40 bg-slate-950/90 backdrop-blur-xl shadow-[0_0_35px_rgba(99,102,241,0.25)] text-white select-none">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-indigo-950/90 via-slate-900/90 to-purple-950/90 border-b border-indigo-400/30 text-[11px] font-mono">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-400 shadow-[0_0_8px_#818cf8]" />
            <span className="text-indigo-300 font-bold uppercase tracking-widest truncate">
               📁 PROJECT WORKSPACE &amp; FOLDER TREE
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="px-2 py-0.5 rounded-md bg-indigo-500/20 text-indigo-200 border border-indigo-400/35 text-[10px] font-mono font-bold">
              {workspaceFolderData.totalFiles} Files
            </span>
            <HudDismissButton onDismiss={onDismiss} />
          </div>
        </div>

        {/* Body */}
        <div className="p-4 sm:p-5 space-y-3 font-sans">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                <span>📁</span> {workspaceFolderData.folderName}
              </h4>
              {workspaceFolderData.rootPath && (
                <p className="text-[10px] text-slate-400 font-mono truncate max-w-sm">
                  {workspaceFolderData.rootPath}
                </p>
              )}
            </div>
          </div>

          {/* File Tree Explorer List */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-[220px] overflow-y-auto custom-scrollbar p-1">
            {workspaceFolderData.files.map((f, idx) => (
              <div
                key={idx}
                onClick={() => onOpenFile?.(f.path)}
                className="flex items-center justify-between p-2 rounded-xl bg-black/40 border border-white/5 hover:border-indigo-400/40 hover:bg-white/[0.04] text-xs transition-all cursor-pointer group"
                title={`Open & Analyze ${f.name}`}
              >
                <div className="flex items-center gap-2 truncate">
                  <span className="text-sm">
                    {f.is_pdf ? "📕" : f.is_image ? "🖼️" : f.is_code ? "💻" : "📄"}
                  </span>
                  <span className="font-mono text-slate-200 group-hover:text-cyan-300 truncate text-[11px]">
                    {f.path}
                  </span>
                </div>
                <span className="text-[9px] text-slate-500 font-mono shrink-0">
                  {f.size_kb} KB
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return null;
}
