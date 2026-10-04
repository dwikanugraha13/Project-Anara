"use client";

import React, { useState, useMemo } from "react";
import { AgentActionData } from "../hud/types";
import { FILE_EDIT_TOOLS, SHELL_TOOLS, SEARCH_TOOLS, READ_TOOLS, clampForDisplay } from "./toolCardUtils";
import { TerminalTranscript } from "./TerminalTranscript";
import { ReadFileView } from "./ReadFileView";
import { GrepResultView } from "./GrepResultView";
import { GlobResultView } from "./GlobResultView";
import { AgentActionCard } from "./AgentActionCard";

// ── TOOL RUN GROUP CARD (Anara Desktop Standard) ────────────────────────
export function ToolRunGroupCard({
  items,
  isRunning = false,
  onOpenFile,
}: {
  items: AgentActionData[];
  isRunning?: boolean;
  onOpenFile?: (filePath: string, fileName?: string) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedRowIdx, setExpandedRowIdx] = useState<number | null>(null);
  const [dismissedIndices, setDismissedIndices] = useState<Set<number>>(new Set());

  if (!items || items.length === 0) return null;

  const activeItems = useMemo(
    () => items.filter((_, idx) => !dismissedIndices.has(idx)),
    [items, dismissedIndices]
  );

  if (activeItems.length === 0) return null;

  const summary = useMemo(() => {
    let readCount = 0;
    let searchCount = 0;
    let commandCount = 0;
    let editCount = 0;
    const fileSet = new Set<string>();

    for (const item of activeItems) {
      const tool = (item.toolName || "").toLowerCase();
      const isShell = SHELL_TOOLS.has(tool) || tool.includes("cli") || tool.includes("terminal") || tool.includes("exec");
      const isEdit = FILE_EDIT_TOOLS.has(tool) || tool.includes("write") || tool.includes("edit") || tool.includes("patch");
      const isRead = READ_TOOLS.has(tool) || tool.includes("read") || tool.includes("scan");
      const isSearch = SEARCH_TOOLS.has(tool) || tool.includes("grep") || tool.includes("glob") || tool.includes("search");

      if (isShell) {
        commandCount++;
      } else if (isEdit) {
        editCount++;
        const target = item.filename || item.filePath || item.detail || "";
        if (target) fileSet.add(target);
      } else if (isRead) {
        readCount++;
        const target = item.filename || item.filePath || item.detail || "";
        const cleaned = target.replace(/^(read|scan)\s+/i, "").trim();
        if (cleaned) fileSet.add(cleaned);
      } else if (isSearch) {
        searchCount++;
      }
    }

    // High polish single-tool clauses
    if (activeItems.length === 1) {
      const single = activeItems[0];
      const tool = (single.toolName || "").toLowerCase();
      if (SHELL_TOOLS.has(tool)) {
        return `${isRunning ? "Running" : "Ran"} ${single.command || single.detail || "command"}`;
      }
      if (tool.includes("read")) {
        const file = single.filename || single.filePath?.split(/[/\\]/).pop() || single.detail || "file";
        return `${isRunning ? "Reading" : "Read"} ${file}`;
      }
      if (tool.includes("grep") || tool.includes("search")) {
        const pat = single.detail?.replace(/^(Regex|pattern)[=:]\s*/i, "").trim() || "codebase";
        return `${isRunning ? "Searching" : "Searched"} ${pat}`;
      }
      if (tool.includes("glob") || tool.includes("list")) {
        return `${isRunning ? "Listing" : "Listed"} files`;
      }
      if (tool.includes("write") || tool.includes("edit")) {
        const file = single.filename || single.filePath?.split(/[/\\]/).pop() || "file";
        return `${isRunning ? "Editing" : "Edited"} ${file}`;
      }
    }

    const uniqueFiles = fileSet.size;
    const clauses: string[] = [];

    if (editCount > 0) {
      clauses.push(`${isRunning ? "Editing" : "Edited"} ${editCount} file${editCount > 1 ? "s" : ""}`);
    }

    if (uniqueFiles > 0) {
      clauses.push(`${isRunning ? "Exploring" : "Explored"} ${uniqueFiles} file${uniqueFiles > 1 ? "s" : ""}`);
    } else if (readCount > 0 || searchCount > 0) {
      const totalOps = readCount + searchCount;
      clauses.push(`${isRunning ? "Exploring" : "Explored"} ${totalOps} file${totalOps > 1 ? "s" : ""}`);
    }

    if (commandCount > 0) {
      clauses.push(`${isRunning ? "running" : "ran"} ${commandCount} command${commandCount > 1 ? "s" : ""}`);
    }

    if (clauses.length === 0) {
      clauses.push(`${isRunning ? "Running" : "Executed"} ${activeItems.length} tool${activeItems.length > 1 ? "s" : ""}`);
    }

    return clauses.join(", ");
  }, [activeItems, isRunning]);

  return (
    <div className="my-1.5 font-mono text-xs select-none">
      {/* Group Header Button */}
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        className="flex items-center gap-2 text-left text-slate-400 hover:text-slate-200 transition-colors cursor-pointer py-1 group"
      >
        <span className="relative flex h-2 w-2 shrink-0">
          {isRunning ? (
            <>
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
            </>
          ) : (
            <span className="inline-flex rounded-full h-1.5 w-1.5 bg-slate-500 group-hover:bg-cyan-400 transition-colors" />
          )}
        </span>
        <span className={`text-[12px] font-medium tracking-tight ${isRunning ? "text-cyan-300 animate-pulse" : "text-slate-400 group-hover:text-slate-200"}`}>
          {summary}
        </span>
        <svg
          className={`w-3.5 h-3.5 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ml-0.5 ${
            isExpanded ? "rotate-90" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>

      {/* Expanded List of Tool Rows */}
      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${
          isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div className="pl-3.5 py-1 space-y-1.5 border-l border-white/[0.08] my-1 font-mono text-[11px]">
            {activeItems.map((sub, sIdx) => {
              const tool = (sub.toolName || "").toLowerCase();
              const isShell = SHELL_TOOLS.has(tool) || tool.includes("cli") || tool.includes("terminal") || tool.includes("exec");
              const isRead = READ_TOOLS.has(tool) || tool.includes("read") || tool.includes("scan");
              const isGrep = tool.includes("grep");
              const isGlob = tool.includes("glob");
              const isWrite = FILE_EDIT_TOOLS.has(tool) || tool.includes("write") || tool.includes("edit") || tool.includes("patch");

              const rawTarget = sub.command || sub.filePath || sub.detail || sub.actionTitle || "";
              const cmdText = sub.command || sub.detail || sub.actionTitle || "command";
              const exitCode = sub.exitCode;
              const duration = sub.durationText;

              const isRowExpanded = expandedRowIdx === sIdx;

              // Shell tool row
              if (isShell) {
                return (
                  <div key={sIdx} className="flex flex-col group/row">
                    <div className="flex items-center gap-2 py-0.5 px-1.5 rounded hover:bg-white/[0.04] transition-colors cursor-pointer">
                      <svg className="w-3.5 h-3.5 text-slate-500 group-hover/row:text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      
                      <button
                        type="button"
                        onClick={() => setExpandedRowIdx(isRowExpanded ? null : sIdx)}
                        className="flex-1 min-w-0 text-left truncate text-slate-300 group-hover/row:text-white font-mono text-[11px]"
                      >
                        {cmdText}
                      </button>

                      {duration && (
                        <span className="text-[10px] text-slate-500 font-mono tabular-nums shrink-0 ml-auto">
                          {duration}
                        </span>
                      )}

                      <button
                        type="button"
                        onClick={() => setExpandedRowIdx(isRowExpanded ? null : sIdx)}
                        className="text-slate-500 hover:text-slate-300 p-0.5 shrink-0"
                      >
                        <svg
                          className={`w-3 h-3 transition-transform duration-150 ${isRowExpanded ? "rotate-90" : ""}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDismissedIndices((prev) => new Set([...prev, sIdx]));
                        }}
                        className="text-slate-600 hover:text-slate-300 p-0.5 rounded opacity-0 group-hover/row:opacity-100 transition-opacity shrink-0"
                        title="Dismiss"
                      >
                        ✕
                      </button>
                    </div>

                    {isRowExpanded && (
                      <div className="pl-5 pr-1 py-1">
                        <TerminalTranscript
                          command={cmdText}
                          exitCode={exitCode ?? 0}
                          rawResult={sub.rawResult || sub.summary}
                          durationText={duration}
                        />
                      </div>
                    )}
                  </div>
                );
              }

              // File exploration item (Read, Grep, Glob, Edit)
              const cleanTarget = rawTarget.replace(/^(read|scan|grep|glob|list)\s+/i, "").trim();
              const lastSlash = Math.max(cleanTarget.lastIndexOf("/"), cleanTarget.lastIndexOf("\\"));
              const dir = lastSlash !== -1 ? cleanTarget.slice(0, lastSlash + 1) : "";
              const file = sub.filename || (lastSlash !== -1 ? cleanTarget.slice(lastSlash + 1) : cleanTarget);
              const opBadge = isRead ? "READ" : isGrep ? "GREP" : isGlob ? "GLOB" : isWrite ? "EDIT" : "EXPLORE";

              return (
                <div key={sIdx} className="flex flex-col group/row">
                  <div
                    onClick={() => setExpandedRowIdx(isRowExpanded ? null : sIdx)}
                    className="flex items-center gap-2 py-0.5 px-1.5 rounded transition-colors cursor-pointer hover:bg-white/[0.04] text-slate-300"
                  >
                    <span
                      className={`px-1.5 py-px rounded text-[9.5px] font-bold shrink-0 tracking-wider border ${
                        isRead
                          ? "bg-cyan-500/10 text-cyan-300 border-cyan-400/20"
                          : isGrep
                          ? "bg-purple-500/10 text-purple-300 border-purple-400/20"
                          : isGlob
                          ? "bg-amber-500/10 text-amber-300 border-amber-400/20"
                          : "bg-emerald-500/10 text-emerald-300 border-emerald-400/20"
                      }`}
                    >
                      {opBadge}
                    </span>
                    <div className="truncate flex items-baseline gap-0.5 min-w-0 flex-1">
                      {dir && <span className="text-slate-500 truncate text-[10px]">{dir}</span>}
                      <span className="text-slate-200 font-medium group-hover/row:text-cyan-300 transition-colors truncate">
                        {file}
                      </span>
                    </div>

                    <span className="text-slate-500 hover:text-slate-300 p-0.5 shrink-0 ml-auto">
                      <svg
                        className={`w-3 h-3 transition-transform duration-150 ${isRowExpanded ? "rotate-90" : ""}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </span>

                    {onOpenFile && isRead && (
                      <span
                        onClick={(e) => {
                          e.stopPropagation();
                          cleanTarget && onOpenFile(cleanTarget, file);
                        }}
                        className="text-slate-600 hover:text-cyan-300 text-[10px] shrink-0 opacity-0 group-hover/row:opacity-100 transition-opacity ml-1"
                        title="Open in Code Editor"
                      >
                        ↗
                      </span>
                    )}

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDismissedIndices((prev) => new Set([...prev, sIdx]));
                      }}
                      className="text-slate-600 hover:text-slate-300 p-0.5 rounded opacity-0 group-hover/row:opacity-100 transition-opacity shrink-0 ml-1"
                      title="Dismiss"
                    >
                      ✕
                    </button>
                  </div>

                  {/* Inline Dedicated Rich Viewers */}
                  {isRowExpanded && (
                    <div className="pl-4 pr-1 py-1">
                      {isRead ? (
                        <ReadFileView
                          filePath={sub.filePath || cleanTarget || file}
                          content={sub.content || sub.rawResult || sub.summary || ""}
                          onOpenFile={onOpenFile}
                        />
                      ) : isGrep ? (
                        <GrepResultView
                          pattern={sub.detail?.replace(/^(Regex|pattern)[=:]\s*/i, "").trim() || ""}
                          rawResult={sub.rawResult || sub.summary}
                          onOpenFile={onOpenFile}
                        />
                      ) : isGlob ? (
                        <GlobResultView
                          pattern={sub.detail?.replace(/^pattern[=:]\s*/i, "").trim() || "*"}
                          rawResult={sub.rawResult || sub.summary}
                          onOpenFile={onOpenFile}
                        />
                      ) : isWrite ? (
                        <AgentActionCard
                          action={sub}
                          onOpenFile={onOpenFile}
                        />
                      ) : (
                        <pre className="p-2.5 rounded border border-white/[0.06] bg-black/50 text-slate-300 text-[10.5px] leading-relaxed max-h-[220px] overflow-x-auto overflow-y-auto custom-scrollbar whitespace-pre font-mono shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
                          {clampForDisplay(sub.rawResult || sub.content || sub.summary || "")}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// Backward-compatibility export
export const ExplorationGroupCard = ToolRunGroupCard;
