"use client";

import React from "react";

export interface IdeToolbarProps {
  filePath: string;
  cleanName: string;
  dirPath: string;
  fileExt: string;
  isDirty: boolean;
  originalContent?: string;
  activeCode: string;
  viewMode: "code" | "diff" | "preview";
  setViewMode: (mode: "code" | "diff" | "preview") => void;
  diffCounts: { added: number; deleted: number };
  saveSuccess: boolean;
  isSaving: boolean;
  handleSave: () => void;
  onSaveFile?: (filePath: string, newContent: string) => Promise<boolean>;
  onAskAnara?: (filePath: string, fileName: string) => void;
  isTerminalOpen?: boolean;
  onToggleTerminal?: () => void;
  isFindOpen: boolean;
  handleOpenSearch: (replace: boolean) => void;
  handleCopy: () => void;
  copied: boolean;
  embedded?: boolean;
  onClose: () => void;
  renderLanguageSvgIcon: () => React.ReactNode;
}

/**
 * IdeToolbar — Antigravity Obsidian Studio clean breadcrumbs & toolbar cluster.
 * Houses file path, view mode switches (Code/Diff/Preview), diff stats, and quick actions.
 */
export function IdeToolbar({
  filePath,
  cleanName,
  dirPath,
  fileExt,
  isDirty,
  originalContent,
  activeCode,
  viewMode,
  setViewMode,
  diffCounts,
  saveSuccess,
  isSaving,
  handleSave,
  onSaveFile,
  onAskAnara,
  isTerminalOpen,
  onToggleTerminal,
  isFindOpen,
  handleOpenSearch,
  handleCopy,
  copied,
  embedded,
  onClose,
  renderLanguageSvgIcon,
}: IdeToolbarProps) {
  return (
    <div className="flex items-center justify-between px-3 py-1 bg-[#060913]/90 backdrop-blur-2xl border-b border-white/[0.08] font-mono text-xs select-none shrink-0">
      {/* Left: Status Badge M/A + Language Icon + File Name & Path */}
      <div className="flex items-center gap-2 min-w-0 flex-1 pr-2">
        <span
          className={`px-1.5 py-0.2 rounded font-bold text-[9.5px] font-mono shrink-0 ${
            isDirty
              ? "bg-amber-500/20 text-amber-300 border border-amber-400/40"
              : originalContent
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-400/40"
              : "bg-emerald-500/20 text-emerald-300 border border-emerald-400/40"
          }`}
        >
          {isDirty ? "MODIFIED" : originalContent ? "DIFF" : "READY"}
        </span>

        {renderLanguageSvgIcon()}

        <div className="flex items-center gap-1 truncate font-mono text-xs">
          {dirPath ? (
            dirPath.split(/[\/\\]/).filter(Boolean).map((segment, idx) => (
              <React.Fragment key={idx}>
                <span className="text-[11px] text-slate-400 hover:text-slate-200 transition-colors cursor-default">
                  {segment}
                </span>
                <svg className="w-2.5 h-2.5 text-slate-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </React.Fragment>
            ))
          ) : null}
          <span className="font-semibold text-slate-100 text-xs truncate" title={cleanName}>
            {cleanName}
          </span>
        </div>

        {/* Rendered Preview Switch for Markdown */}
        {(fileExt === ".md" || fileExt === "md") && (
          <div className="flex items-center bg-white/[0.04] rounded-lg p-0.5 border border-white/[0.08] ml-2 shrink-0">
            <button
              type="button"
              onClick={() => setViewMode(viewMode === "preview" ? "code" : "preview")}
              className={`px-2 py-0.5 rounded-md text-[10.5px] font-mono font-medium transition-all ${
                viewMode === "preview"
                  ? "bg-cyan-500/25 text-cyan-300 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
              title="Toggle rendered markdown preview"
            >
              {viewMode === "preview" ? "Source" : "Preview"}
            </button>
          </div>
        )}

        {/* Code vs Diff Mode Toggle Switch */}
        {originalContent && originalContent !== activeCode && (
          <div className="flex items-center bg-white/[0.04] rounded-lg p-0.5 border border-white/[0.08] ml-2 shrink-0">
            <button
              type="button"
              onClick={() => setViewMode("code")}
              className={`px-2 py-0.5 rounded-md text-[10.5px] font-mono font-medium transition-all ${
                viewMode === "code"
                  ? "bg-cyan-500/25 text-cyan-300 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
              title="View active editable code"
            >
              Code
            </button>
            <button
              type="button"
              onClick={() => setViewMode("diff")}
              className={`px-2 py-0.5 rounded-md text-[10.5px] font-mono font-medium flex items-center gap-1 transition-all ${
                viewMode === "diff"
                  ? "bg-purple-500/25 text-purple-300 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
              title="View unified diff against original version"
            >
              <span>Diff</span>
              {(diffCounts.added > 0 || diffCounts.deleted > 0) && (
                <span className="flex items-center gap-0.5 text-[9.5px]">
                  {diffCounts.added > 0 && <span className="text-emerald-400 font-bold">+{diffCounts.added}</span>}
                  {diffCounts.deleted > 0 && <span className="text-rose-400 font-bold">-{diffCounts.deleted}</span>}
                </span>
              )}
            </button>
          </div>
        )}

        {/* Save Status Notification */}
        {saveSuccess ? (
          <span className="flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] font-mono font-bold text-emerald-300 bg-emerald-500/15 border border-emerald-400/30 shrink-0 ml-1">
            <svg className="w-2.5 h-2.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
            <span>Saved</span>
          </span>
        ) : isDirty ? (
          <span className="w-1.5 h-1.5 rounded-full bg-slate-300 shadow-sm shrink-0 ml-1" title="Unsaved changes (Ctrl+S to save)" />
        ) : null}
      </div>

      {/* Right: Activity Bar Actions */}
      <div className="flex items-center gap-1.5 shrink-0">
        {onAskAnara && (
          <button
            type="button"
            onClick={() => onAskAnara(filePath, cleanName)}
            className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-400/30 text-cyan-200 hover:text-cyan-100 text-xs font-medium font-mono cursor-pointer transition-all"
            title="Ask Anara to analyze or explain this file"
          >
            <svg className="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span className="text-[10px]">Ask Anara</span>
          </button>
        )}

        {onToggleTerminal && (
          <button
            type="button"
            onClick={onToggleTerminal}
            className={`flex items-center gap-1 px-2 py-0.5 rounded-lg border text-xs font-medium font-mono cursor-pointer transition-all ${
              isTerminalOpen
                ? "bg-white/15 border-white/30 text-white shadow-sm"
                : "bg-white/[0.04] hover:bg-white/10 border-white/10 text-slate-400 hover:text-white"
            }`}
            title={isTerminalOpen ? "Hide Terminal Shell" : "Show Terminal Shell"}
          >
            <svg className="w-3 h-3 text-current" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-[10px]">Terminal</span>
          </button>
        )}

        {isDirty && onSaveFile && (
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/40 text-emerald-200 text-xs font-medium font-mono cursor-pointer transition-all active:scale-95"
            title="Save changes (Ctrl + S)"
          >
            <svg className="w-3 h-3 text-emerald-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
            <span className="text-[10px]">{isSaving ? "Saving..." : "Save"}</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => handleOpenSearch(false)}
          className={`flex items-center gap-1 px-2 py-0.5 rounded-lg border text-xs font-medium font-mono cursor-pointer transition-all ${
            isFindOpen
              ? "bg-white/15 border-white/30 text-white shadow-[0_0_12px_rgba(255,255,255,0.1)]"
              : "bg-white/[0.04] hover:bg-white/10 border-white/10 text-slate-400 hover:text-white"
          }`}
          title="Find / Find & Replace (Ctrl + F)"
        >
          <svg className="w-3 h-3 text-current" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span className="text-[10px]">Find</span>
        </button>

        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-white/[0.04] hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white text-xs font-medium font-mono cursor-pointer transition-all"
          title="Copy file content"
        >
          {copied ? (
            <>
              <svg className="w-3 h-3 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
              <span>Copied</span>
            </>
          ) : (
            <span>Copy</span>
          )}
        </button>

        {!embedded && (
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-xl bg-white/10 hover:bg-rose-500/30 hover:text-rose-200 text-slate-400 border border-white/10 transition-all cursor-pointer ml-1"
            title="Close IDE Inspector"
          >
            <svg className="w-3.5 h-3.5 text-current" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
