"use client";

import React, { useState, useMemo } from "react";
import { DocumentViewerData, WorkspaceFolderData, HudDismissButton } from "./types";

interface HudDocumentViewerProps {
  documentViewerData?: DocumentViewerData;
  workspaceFolderData?: WorkspaceFolderData;
  onOpenFile?: (filePath: string) => void;
  onDismiss?: () => void;
}

const CODE_LANGUAGES: Record<string, string> = {
  ts: "TypeScript",
  tsx: "React TypeScript",
  js: "JavaScript",
  jsx: "React JavaScript",
  mjs: "JavaScript",
  cjs: "JavaScript",
  py: "Python",
  pyw: "Python",
  rs: "Rust",
  go: "Go",
  java: "Java",
  c: "C",
  cpp: "C++",
  cc: "C++",
  h: "C Header",
  hpp: "C++ Header",
  cs: "C#",
  php: "PHP",
  rb: "Ruby",
  swift: "Swift",
  kt: "Kotlin",
  html: "HTML",
  htm: "HTML",
  css: "CSS",
  scss: "SCSS",
  sass: "Sass",
  less: "Less",
  json: "JSON",
  yaml: "YAML",
  yml: "YAML",
  toml: "TOML",
  xml: "XML",
  sql: "SQL",
  sh: "Shell Script",
  bash: "Bash",
  zsh: "Zsh",
  ps1: "PowerShell",
  md: "Markdown",
  markdown: "Markdown",
  txt: "Plain Text",
  env: "Environment Config",
  dockerfile: "Dockerfile",
  makefile: "Makefile",
};

export default function HudDocumentViewer({
  documentViewerData,
  workspaceFolderData,
  onOpenFile,
  onDismiss,
}: HudDocumentViewerProps) {
  const [copiedCode, setCopiedCode] = useState(false);

  const handleCopyCode = (text: string) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text).catch(() => {});
    }
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const codeLines = useMemo(() => {
    if (!documentViewerData?.content) return [];
    return documentViewerData.content.split("\n");
  }, [documentViewerData?.content]);

  if (documentViewerData) {
    const rawExt = (documentViewerData.fileExt || "").toLowerCase().replace(/^\./, "");
    const inferredExt = (documentViewerData.fileName?.split(".").pop() || "").toLowerCase();
    const ext = rawExt || inferredExt;

    const isPdf = Boolean(documentViewerData.isPdf || ext === "pdf");
    const isWord = ext === "docx" || ext === "doc";
    const isZip = Boolean(
      documentViewerData.isZip ||
      ext === "zip" ||
      ext === "tar" ||
      ext === "gz" ||
      ext === "rar" ||
      (documentViewerData.archiveFiles && documentViewerData.archiveFiles.length > 0)
    );

    const isCode = !isPdf && !isWord && !isZip && (ext in CODE_LANGUAGES || ext === "txt");
    const languageLabel = CODE_LANGUAGES[ext] || (ext ? ext.toUpperCase() : "Document");
    const targetFilePath = documentViewerData.filePath || documentViewerData.fileName;

    const title = isPdf
      ? "PDF DOCUMENT VIEWER"
      : isWord
      ? "WORD DOCX VIEWER"
      : isZip
      ? "PROJECT ARCHIVE VIEWER"
      : isCode
      ? `${languageLabel.toUpperCase()} SOURCE`
      : "WORKSPACE DOCUMENT";

    const indicatorColor = isPdf
      ? "bg-rose-400"
      : isWord
      ? "bg-blue-400"
      : isZip
      ? "bg-amber-400"
      : isCode
      ? "bg-sky-400"
      : "bg-slate-400";

    const badgeStyle = isPdf
      ? "bg-rose-500/15 border-rose-400/25 text-rose-300"
      : isWord
      ? "bg-blue-500/15 border-blue-400/25 text-blue-300"
      : isZip
      ? "bg-amber-500/15 border-amber-400/25 text-amber-300"
      : isCode
      ? "bg-sky-500/15 border-sky-400/25 text-sky-300"
      : "bg-white/[0.06] border-white/[0.08] text-slate-300";

    const badgeLabel = isPdf
      ? "PDF"
      : isWord
      ? "DOCX"
      : isZip
      ? "ZIP"
      : isCode
      ? ext.slice(0, 4).toUpperCase()
      : "DOC";

    return (
      <div className="mt-2.5 rounded-2xl overflow-hidden border border-white/[0.08] bg-[#060913]/90 backdrop-blur-xl shadow-2xl shadow-black/80 text-white select-none">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-white/[0.03] border-b border-white/[0.08] text-[11px] font-mono">
          <div className="flex items-center gap-2 min-w-0">
            <span className={`w-2 h-2 rounded-full ${indicatorColor}`} />
            <span className="text-slate-200 font-semibold uppercase tracking-wider truncate">
              {title}
            </span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className="px-2 py-0.5 rounded-md bg-white/[0.05] text-slate-300 border border-white/[0.08] text-[10px] font-mono">
              {isCode && codeLines.length > 0 ? `${codeLines.length} lines • ` : ""}
              {documentViewerData.fileSizeKb} KB
            </span>

            {/* Open in IDE button */}
            {onOpenFile && targetFilePath && (
              <button
                type="button"
                onClick={() => onOpenFile(targetFilePath)}
                className="px-2.5 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-slate-200 hover:text-white border border-white/[0.08] text-[10px] font-mono font-medium transition-all flex items-center gap-1.5 cursor-pointer active:scale-95"
                title={`Open ${documentViewerData.fileName} in IDE`}
              >
                <svg className="w-3 h-3 text-sky-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                <span>Open in IDE</span>
              </button>
            )}

            {/* Copy button with feedback */}
            <button
              type="button"
              onClick={() => handleCopyCode(documentViewerData.content)}
              className={`px-2.5 py-1 rounded-lg border text-[10px] font-mono font-medium transition-all flex items-center gap-1.5 cursor-pointer active:scale-95 ${
                copiedCode
                  ? "bg-emerald-500/15 text-emerald-300 border-emerald-400/30"
                  : "bg-white/[0.05] hover:bg-white/[0.1] text-slate-200 border-white/[0.08]"
              }`}
              title="Copy content to clipboard"
            >
              {copiedCode ? (
                <>
                  <svg className="w-3 h-3 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <svg className="w-3 h-3 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  <span>Copy</span>
                </>
              )}
            </button>

            {/* Download button */}
            {documentViewerData.downloadUrl && (
              <a
                href={documentViewerData.downloadUrl}
                download={documentViewerData.fileName}
                target="_blank"
                rel="noreferrer"
                className="px-2.5 py-1 rounded-lg bg-white/[0.08] hover:bg-white/[0.14] text-slate-100 border border-white/[0.12] text-[10px] font-mono font-semibold transition-all flex items-center gap-1.5 cursor-pointer active:scale-95 shadow-sm"
                title={`Download ${documentViewerData.fileName}`}
              >
                <svg className="w-3 h-3 text-slate-300" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                <span>Download {isPdf ? "PDF" : isWord ? "DOCX" : isZip ? "ZIP" : (ext || "FILE").toUpperCase()}</span>
              </a>
            )}

            <HudDismissButton onDismiss={onDismiss} />
          </div>
        </div>

        {/* Body */}
        <div className="p-4 sm:p-5 space-y-3 font-sans">
          <div className="flex items-center gap-2.5">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-xs font-mono font-bold shrink-0 border ${badgeStyle}`}>
              {badgeLabel}
            </div>
            <div className="min-w-0">
              <h4 className="text-sm font-bold text-white truncate font-mono">{documentViewerData.fileName}</h4>
              <p className="text-[11px] text-slate-400">
                {isPdf
                  ? "Binary PDF document extracted for review"
                  : isWord
                  ? "Word document generated and ready for review"
                  : isZip
                  ? "Compressed project file archive ready for download"
                  : isCode
                  ? `${languageLabel} source • ${codeLines.length} lines • ${documentViewerData.totalChars || documentViewerData.content.length} chars`
                  : `Format ${ext ? ext.toUpperCase() : "DOCUMENT"} • ${documentViewerData.totalChars || documentViewerData.content.length} characters`}
              </p>
            </div>
          </div>

          {/* Content presentation */}
          {isZip && documentViewerData.archiveFiles && documentViewerData.archiveFiles.length > 0 ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                <span>Archive Contents ({documentViewerData.archiveFiles.length} files):</span>
                <span className="text-[10px] text-emerald-400 font-medium">Auto-Compressed Archive</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-[220px] overflow-y-auto custom-scrollbar p-1">
                {documentViewerData.archiveFiles.map((fn: string, fIdx: number) => {
                  const itemExt = fn.split(".").pop()?.toLowerCase() || "";
                  const icon =
                    itemExt === "html" || itemExt === "htm"
                      ? "🌐"
                      : itemExt === "css"
                      ? "🎨"
                      : itemExt === "js" || itemExt === "ts" || itemExt === "tsx" || itemExt === "jsx"
                      ? "💻"
                      : itemExt === "py"
                      ? "🐍"
                      : itemExt === "json"
                      ? "📋"
                      : "📄";
                  return (
                    <div
                      key={fIdx}
                      className="flex items-center justify-between p-2 rounded-xl bg-white/[0.02] border border-white/[0.06] text-xs font-mono text-slate-200"
                    >
                      <div className="flex items-center gap-2 truncate min-w-0 flex-1">
                        <span className="shrink-0">{icon}</span>
                        <span className="truncate">{fn}</span>
                      </div>
                      <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-white/[0.05] text-slate-400 border border-white/[0.06] shrink-0 ml-1">
                        {itemExt}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : isCode ? (
            <div className="rounded-xl bg-[#030712]/90 border border-white/[0.08] overflow-hidden">
              <div className="max-h-[260px] overflow-y-auto overflow-x-auto custom-scrollbar font-mono text-xs leading-relaxed">
                <div className="grid grid-cols-[auto_1fr] min-w-full">
                  {/* Gutter with line numbers */}
                  <div className="select-none py-2.5 pl-3 pr-2.5 text-right font-mono text-[11px] text-slate-500/70 border-r border-white/[0.06] bg-white/[0.01]">
                    {codeLines.map((_, idx) => (
                      <div key={idx} className="h-5 leading-5 tabular-nums">
                        {idx + 1}
                      </div>
                    ))}
                  </div>
                  {/* Code lines */}
                  <div className="py-2.5 px-3 overflow-x-auto text-slate-200 select-text">
                    {codeLines.map((line, idx) => (
                      <div key={idx} className="h-5 leading-5 whitespace-pre">
                        {line || "\u00A0"}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-3.5 rounded-xl bg-[#030712]/90 border border-white/[0.08] text-xs text-slate-200 leading-relaxed max-h-[220px] overflow-y-auto custom-scrollbar font-mono whitespace-pre-wrap select-text">
              {documentViewerData.content}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (workspaceFolderData) {
    return (
      <div className="mt-2.5 rounded-2xl overflow-hidden border border-white/[0.08] bg-[#060913]/90 backdrop-blur-xl shadow-2xl shadow-black/80 text-white select-none">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-white/[0.03] border-b border-white/[0.08] text-[11px] font-mono">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-2 h-2 rounded-full bg-indigo-400" />
            <span className="text-slate-200 font-semibold uppercase tracking-wider truncate">
              WORKSPACE FOLDER TREE
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="px-2 py-0.5 rounded-md bg-white/[0.05] text-slate-300 border border-white/[0.08] text-[10px] font-mono font-medium">
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
                <span className="w-2 h-2 rounded-full bg-indigo-400/80" />
                <span>{workspaceFolderData.folderName}</span>
              </h4>
              {workspaceFolderData.rootPath && (
                <p className="text-[10px] text-slate-400 font-mono truncate max-w-sm mt-0.5">
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
                className="flex items-center justify-between p-2 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-white/[0.15] hover:bg-white/[0.05] text-xs transition-all cursor-pointer group"
                title={`Open & Analyze ${f.name}`}
              >
                <div className="flex items-center gap-2 truncate">
                  <span className="text-[9px] uppercase font-mono font-bold px-1.5 py-0.5 rounded bg-white/10 text-slate-300">
                    {f.ext.replace(".", "") || "FILE"}
                  </span>
                  <span className="font-mono text-slate-200 group-hover:text-white truncate text-[11px] transition-colors">
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
