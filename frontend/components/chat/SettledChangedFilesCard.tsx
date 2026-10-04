"use client";

import React, { useMemo } from "react";
import { TranscriptItem } from "../workbench/types";
import { FILE_EDIT_TOOLS } from "./toolCardUtils";

export interface ChangedFileEntry {
  path: string;
  filename: string;
  dirPath: string;
  added: number;
  deleted: number;
}

export interface SettledChangedFilesCardProps {
  transcript: TranscriptItem[];
  isStreaming?: boolean;
  onOpenFile?: (filePath: string, fileName?: string) => void;
  onOpenReviewTab?: () => void;
}

export function SettledChangedFilesCard({
  transcript,
  isStreaming = false,
  onOpenFile,
  onOpenReviewTab,
}: SettledChangedFilesCardProps) {
  // Only calculate for the last assistant turn when settled (!isStreaming)
  const changedFiles = useMemo<ChangedFileEntry[]>(() => {
    if (isStreaming || transcript.length === 0) return [];

    // Find the boundary of the last assistant turn (from the last user message to the end)
    let lastUserIdx = -1;
    for (let i = transcript.length - 1; i >= 0; i--) {
      if (transcript[i].speaker === "input") {
        lastUserIdx = i;
        break;
      }
    }

    const currentTurnItems =
      lastUserIdx !== -1 ? transcript.slice(lastUserIdx + 1) : transcript;

    const fileMap = new Map<string, ChangedFileEntry>();

    for (const item of currentTurnItems) {
      if (item.agentActionData) {
        const action = item.agentActionData;
        const tool = (action.toolName || action.tool || action.type || "").toLowerCase();
        const isFileEdit =
          FILE_EDIT_TOOLS.has(tool) ||
          action.type === "file_edit" ||
          Boolean(action.diff || action.patch || action.newContent);

        if (isFileEdit) {
          const rawPath = action.file || action.path || action.filename || "";
          if (!rawPath) continue;

          const normalizedPath = rawPath.replace(/\\/g, "/");
          const filename = normalizedPath.split("/").pop() || normalizedPath;
          const lastSlash = normalizedPath.lastIndexOf("/");
          const dirPath = lastSlash !== -1 ? normalizedPath.slice(0, lastSlash + 1) : "";

          const added = action.added || (action.contentLines ? action.contentLines : 1);
          const deleted = action.deleted || 0;

          const existing = fileMap.get(normalizedPath);
          if (existing) {
            existing.added += added;
            existing.deleted += deleted;
          } else {
            fileMap.set(normalizedPath, {
              path: normalizedPath,
              filename,
              dirPath,
              added,
              deleted,
            });
          }
        }
      }
    }

    return Array.from(fileMap.values());
  }, [transcript, isStreaming]);

  if (changedFiles.length === 0) return null;

  const totalAdded = changedFiles.reduce((acc, f) => acc + f.added, 0);
  const totalDeleted = changedFiles.reduce((acc, f) => acc + f.deleted, 0);

  return (
    <div className="w-full my-2 rounded-lg border border-white/[0.08] bg-black/40 backdrop-blur-md overflow-hidden select-none font-mono animate-fade-in">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.06] bg-white/[0.015]">
        <div className="flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span className="text-[11.5px] font-semibold text-slate-200">
            {changedFiles.length} file{changedFiles.length === 1 ? "" : "s"} modified
          </span>
          <div className="flex items-center gap-1 font-mono text-[10.5px] tabular-nums font-bold shrink-0 ml-1">
            {totalAdded > 0 && <span className="text-emerald-400">+{totalAdded}</span>}
            {totalDeleted > 0 && <span className="text-rose-400">−{totalDeleted}</span>}
          </div>
        </div>

        {onOpenReviewTab && (
          <button
            type="button"
            onClick={onOpenReviewTab}
            className="flex items-center gap-1 text-[11px] text-cyan-300 hover:text-white px-2 py-0.5 rounded bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/20 transition-all cursor-pointer font-sans"
            title="Inspect all changed files in Git Review"
          >
            <span>Review changes</span>
            <span className="text-[10px]">↗</span>
          </button>
        )}
      </div>

      {/* File list */}
      <div className="max-h-[140px] overflow-y-auto overscroll-y-auto custom-scrollbar p-1.5 space-y-0.5">
        {changedFiles.map((file, idx) => (
          <div
            key={idx}
            onClick={() => onOpenFile?.(file.path, file.filename)}
            className="flex items-center justify-between px-2 py-1 rounded hover:bg-white/[0.04] transition-colors cursor-pointer group text-xs"
          >
            <div className="flex items-baseline gap-1.5 min-w-0 truncate">
              <span className="text-slate-500 group-hover:text-slate-400 text-[10px]">»</span>
              <span className="text-slate-200 font-medium group-hover:text-cyan-300 transition-colors truncate text-[11px]">
                {file.filename}
              </span>
              {file.dirPath && (
                <span className="text-slate-500 text-[10px] truncate hidden sm:inline">
                  {file.dirPath}
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 shrink-0 ml-2">
              <div className="flex items-center gap-1 font-mono text-[10px] tabular-nums">
                {file.added > 0 && <span className="text-emerald-400/90">+{file.added}</span>}
                {file.deleted > 0 && <span className="text-rose-400/90">−{file.deleted}</span>}
              </div>
              <span className="text-slate-500 group-hover:text-cyan-300 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity">
                ↗
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
