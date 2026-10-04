"use client";

import React, { useState, useEffect, useCallback } from "react";
import ReviewShipBar from "./ReviewShipBar";
import { getBackendUrl } from "@/lib/apiClient";

export interface GitFileItem {
  path: string;
  status: string; // "M", "A", "D", "??", "MM", etc.
  insertions?: number;
  deletions?: number;
}

export interface ReviewGitPaneProps {
  gitStatus: {
    is_git: boolean;
    branch?: string;
    changed_count: number;
    insertions?: number;
    deletions?: number;
    files: GitFileItem[];
  } | null;
  onRefreshGit: () => Promise<void>;
  onSelectDiffFile?: (filePath: string) => void;
  onAgentShip?: () => void;
  sessionId?: number | null;
  activeFilePath?: string;
}

export default function ReviewGitPane({
  gitStatus,
  onRefreshGit,
  onSelectDiffFile,
  onAgentShip,
  sessionId,
  activeFilePath,
}: ReviewGitPaneProps) {
  const [isBusy, setIsBusy] = useState(false);
  const [confirmRevertPath, setConfirmRevertPath] = useState<string | null>(null);
  const [isRevertingAll, setIsRevertingAll] = useState(false);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [diffText, setDiffText] = useState<string | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  const backendUrl = typeof window !== "undefined" ? getBackendUrl() : "http://localhost:8000";

  const fetchDiffForFile = useCallback(
    async (filePath: string) => {
      if (selectedFilePath === filePath && diffText !== null) {
        setSelectedFilePath(null);
        setDiffText(null);
        return;
      }
      setSelectedFilePath(filePath);
      setDiffLoading(true);
      try {
        const res = await fetch(
          `${backendUrl}/api/agent/git/file-diff?path=${encodeURIComponent(filePath)}&session_id=${sessionId || ""}`
        );
        if (res.ok) {
          const data = await res.json();
          setDiffText(data.diff || "");
        } else {
          setDiffText("Failed to load diff.");
        }
      } catch {
        setDiffText("Error loading diff.");
      } finally {
        setDiffLoading(false);
      }
    },
    [backendUrl, sessionId, selectedFilePath, diffText]
  );

  // Stage single or all files
  const handleStage = async (path?: string) => {
    setIsBusy(true);
    try {
      await fetch(`${backendUrl}/api/agent/git/stage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, session_id: sessionId }),
      });
      await onRefreshGit();
    } finally {
      setIsBusy(false);
    }
  };

  // Unstage single or all files
  const handleUnstage = async (path?: string) => {
    setIsBusy(true);
    try {
      await fetch(`${backendUrl}/api/agent/git/unstage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, session_id: sessionId }),
      });
      await onRefreshGit();
    } finally {
      setIsBusy(false);
    }
  };

  // Revert / Discard single file
  const handleRevert = async (path?: string) => {
    setIsBusy(true);
    try {
      await fetch(`${backendUrl}/api/agent/git/revert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, session_id: sessionId }),
      });
      setConfirmRevertPath(null);
      setIsRevertingAll(false);
      await onRefreshGit();
    } finally {
      setIsBusy(false);
    }
  };

  // Commit changes
  const handleCommit = async (message: string, push: boolean) => {
    setIsBusy(true);
    try {
      // Auto-stage all before commit if nothing is staged
      const res = await fetch(`${backendUrl}/api/agent/git/commit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, push, session_id: sessionId }),
      });
      if (res.ok) {
        await onRefreshGit();
      }
    } finally {
      setIsBusy(false);
    }
  };

  const files = gitStatus?.files || [];
  const hasChanges = files.length > 0;

  return (
    <div className="flex-1 min-h-0 flex flex-col h-full bg-[#060913] text-slate-200 select-none font-mono">
      {/* ── Header: Branch, Diff Metrics, Stage All, Discard All ── */}
      <div className="h-9 px-3 border-b border-white/[0.08] flex items-center justify-between shrink-0 bg-[#060913]/90 text-xs">
        <div className="flex items-center gap-2 min-w-0">
          <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7a3 3 0 100-6 3 3 0 000 6zm0 0v10m0 0a3 3 0 100 6 3 3 0 000-6zm8-4a3 3 0 100-6 3 3 0 000 6zm0 0v3a4 4 0 01-4 4h-4" />
          </svg>
          <span className="font-semibold text-white truncate">{gitStatus?.branch || "main"}</span>
          <span className="text-[10px] text-slate-500 font-normal">({files.length} changed)</span>
          {(gitStatus?.insertions !== undefined || gitStatus?.deletions !== undefined) && (
            <span className="text-[10px] flex items-center gap-1 font-mono">
              {gitStatus.insertions ? <span className="text-emerald-400">+{gitStatus.insertions}</span> : null}
              {gitStatus.deletions ? <span className="text-rose-400">-{gitStatus.deletions}</span> : null}
            </span>
          )}
        </div>

        {/* Global Toolbar Actions */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => handleStage()}
            disabled={!hasChanges || isBusy}
            className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer disabled:opacity-40"
            title="Stage All Changes"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => handleUnstage()}
            disabled={!hasChanges || isBusy}
            className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer disabled:opacity-40"
            title="Unstage All Changes"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => setIsRevertingAll(true)}
            disabled={!hasChanges || isBusy}
            className="p-1 rounded hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 transition-colors cursor-pointer disabled:opacity-40"
            title="Discard All Changes (Revert All)"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => onRefreshGit()}
            disabled={isBusy}
            className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer"
            title="Refresh Git Status"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* ── Revert Confirmation Dialog (Safety Guard) ── */}
      {(confirmRevertPath || isRevertingAll) && (
        <div className="p-3 bg-rose-950/90 border-b border-rose-500/40 text-rose-200 text-xs flex flex-col gap-2 animate-fade-in">
          <span className="font-semibold">
            {isRevertingAll
              ? "Discard all uncommitted changes across the entire workspace?"
              : `Discard working tree changes in '${confirmRevertPath}'?`}
          </span>
          <div className="flex items-center justify-end gap-2 font-mono">
            <button
              type="button"
              onClick={() => {
                setConfirmRevertPath(null);
                setIsRevertingAll(false);
              }}
              className="px-2.5 py-1 rounded bg-white/10 hover:bg-white/20 text-white text-[11px] transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => handleRevert(confirmRevertPath || undefined)}
              className="px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white font-semibold text-[11px] transition-colors cursor-pointer shadow-sm"
            >
              Discard Changes
            </button>
          </div>
        </div>
      )}

      {/* ── Changed Files List ── */}
      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-1.5 space-y-0.5">
        {!hasChanges ? (
          <div className="h-40 flex flex-col items-center justify-center text-slate-500 text-xs text-center p-4">
            <svg className="w-8 h-8 mb-2 text-slate-600 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 13l4 4L19 7" />
            </svg>
            <span>No uncommitted changes</span>
            <span className="text-[10px] text-slate-600 mt-1">Working tree clean</span>
          </div>
        ) : (
          files.map((file) => {
            const isSelected = selectedFilePath === file.path || activeFilePath === file.path;
            const isUntracked = file.status === "??" || file.status === "U";
            const isModified = file.status.includes("M");
            const isDeleted = file.status.includes("D");
            const isAdded = file.status.includes("A");

            return (
              <div
                key={file.path}
                className={`group flex items-center justify-between px-2 py-1.5 rounded-lg transition-colors cursor-pointer ${
                  isSelected ? "bg-white/10 text-white" : "hover:bg-white/[0.04] text-slate-300"
                }`}
                onClick={() => {
                  fetchDiffForFile(file.path);
                  onSelectDiffFile?.(file.path);
                }}
              >
                <div className="flex items-center gap-2 min-w-0">
                  {/* Status Badge */}
                  <span
                    className={`w-4 h-4 rounded text-[9.5px] font-bold font-mono flex items-center justify-center shrink-0 ${
                      isUntracked
                        ? "bg-amber-500/20 text-amber-300 border border-amber-400/30"
                        : isAdded
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-400/30"
                        : isDeleted
                        ? "bg-rose-500/20 text-rose-300 border border-rose-400/30"
                        : "bg-cyan-500/20 text-cyan-300 border border-cyan-400/30"
                    }`}
                    title={`Status: ${file.status}`}
                  >
                    {isUntracked ? "U" : isAdded ? "A" : isDeleted ? "D" : "M"}
                  </span>

                  <span className="text-xs truncate" title={file.path}>
                    {file.path.split("/").pop()}
                    <span className="text-[10px] text-slate-500 ml-1.5 font-normal">
                      {file.path.split("/").slice(0, -1).join("/")}
                    </span>
                  </span>
                </div>

                {/* Per-file Actions on Hover */}
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleStage(file.path);
                    }}
                    className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-cyan-300 transition-colors"
                    title="Stage File"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmRevertPath(file.path);
                    }}
                    className="p-1 rounded hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 transition-colors"
                    title="Discard Changes"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── Inline Diff Viewer (Desktop Reference Standard) ── */}
      {selectedFilePath && (
        <div className="border-t border-white/[0.08] bg-black/60 flex flex-col max-h-[220px] shrink-0 animate-fade-in select-text">
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/[0.06] bg-white/[0.02] text-xs select-none">
            <span className="font-semibold text-white truncate text-[11px]">
              Diff: {selectedFilePath.split("/").pop()}
            </span>
            <button
              type="button"
              onClick={() => {
                setSelectedFilePath(null);
                setDiffText(null);
              }}
              className="text-slate-500 hover:text-white p-0.5 rounded hover:bg-white/10 transition-colors cursor-pointer"
              title="Close diff view"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-x-auto overflow-y-auto overscroll-x-contain overscroll-y-auto p-2 font-mono text-[10.5px] leading-relaxed custom-scrollbar">
            {diffLoading ? (
              <div className="text-slate-500 italic py-2">Loading git diff...</div>
            ) : diffText ? (
              <pre className="whitespace-pre">
                {diffText.split("\n").map((line, idx) => {
                  const isAdd = line.startsWith("+") && !line.startsWith("+++");
                  const isDel = line.startsWith("-") && !line.startsWith("---");
                  const isHunk = line.startsWith("@@");
                  return (
                    <div
                      key={idx}
                      className={`px-1 rounded-xs ${
                        isAdd
                          ? "bg-emerald-500/10 text-emerald-300 border-l-2 border-emerald-400"
                          : isDel
                          ? "bg-rose-500/10 text-rose-300 border-l-2 border-rose-400"
                          : isHunk
                          ? "text-cyan-400/80 bg-cyan-950/20 py-0.5"
                          : "text-slate-400"
                      }`}
                    >
                      {line || " "}
                    </div>
                  );
                })}
              </pre>
            ) : (
              <div className="text-slate-500 italic py-2">No differences against HEAD.</div>
            )}
          </div>
        </div>
      )}

      {/* ── Review Ship Bar: Commit / Push / PR Actions ── */}
      <ReviewShipBar
        hasChanges={hasChanges}
        onCommit={handleCommit}
        onAgentShip={onAgentShip}
        isBusy={isBusy}
      />
    </div>
  );
}
