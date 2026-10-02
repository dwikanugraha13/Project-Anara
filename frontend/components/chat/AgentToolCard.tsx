"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import { AgentActionData, TodoData } from "../hud/types";
import { anaraApi } from "@/lib/apiClient";

export interface AgentToolCardProps {
  action?: AgentActionData;
  todoData?: TodoData;
  sessionId?: number;
  onOpenFile?: (filePath: string, fileName?: string) => void;
  onDismiss?: () => void;
}

// ── CANONICAL TOOL TAXONOMY ─────────────────────────────────────────────────
export const FILE_EDIT_TOOLS = new Set([
  "patch",
  "write_file",
  "edit_file",
  "write",
  "edit",
  "artifact",
]);
export const SHELL_TOOLS = new Set([
  "terminal",
  "execute_code",
  "bash",
  "shell",
  "command",
  "cli",
]);
export const SEARCH_TOOLS = new Set([
  "search_files",
  "grep",
  "glob",
  "web_search",
  "search",
]);
export const READ_TOOLS = new Set([
  "read_file",
  "read",
  "scan",
  "list",
]);

// ── 1. THINKING CARD ────────────────────────────────────────────────────────
export function ThinkingCard({
  text,
  durationSec,
  isLive = false,
}: {
  text: string;
  durationSec?: number;
  isLive?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [liveElapsed, setLiveElapsed] = useState<number>(0);
  const liveStartTimeRef = useRef<number>(Date.now());

  useEffect(() => {
    if (!isLive) return;
    liveStartTimeRef.current = Date.now();
    const interval = setInterval(() => {
      setLiveElapsed((Date.now() - liveStartTimeRef.current) / 1000);
    }, 100);
    return () => clearInterval(interval);
  }, [isLive]);

  if (!text || text.trim().length === 0) return null;

  let thoughtLabel = "Thinking";
  if (!isLive) {
    if (durationSec === undefined || durationSec === null || durationSec <= 0) {
      thoughtLabel = "Thought";
    } else if (durationSec < 1) {
      thoughtLabel = "Thought briefly";
    } else {
      thoughtLabel = `Thought for ${durationSec.toFixed(1)}s`;
    }
  } else {
    thoughtLabel = "Thinking";
  }

  return (
    <div className="group/scaffold relative flex flex-col w-full my-1.5 select-none font-mono">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 text-slate-400 hover:text-slate-200 focus-visible:outline-none transition-colors cursor-pointer group py-0.5"
          aria-expanded={isExpanded}
        >
          <span className="relative flex h-1.5 w-1.5 shrink-0">
            {isLive ? (
              <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
              </>
            ) : (
              <span className="h-1.5 w-1.5 rounded-full bg-slate-500 group-hover:bg-cyan-400 transition-colors" />
            )}
          </span>

          <span className={`text-[11.5px] tracking-tight ${isLive ? "text-cyan-300 animate-pulse font-medium" : "text-slate-400 group-hover:text-slate-200"}`}>
            {thoughtLabel}
          </span>

          <svg
            className={`w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ${
              isExpanded ? "rotate-90" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {isLive && liveElapsed > 0 && (
          <span className="text-[10.5px] font-mono tabular-nums text-slate-500">
            {liveElapsed.toFixed(1)}s
          </span>
        )}
      </div>

      {isExpanded && (
        <div className="mt-1.5 w-full min-w-0 max-w-full overflow-y-auto max-h-56 border-l border-white/10 pl-3 py-1 text-slate-400 font-sans text-xs leading-relaxed whitespace-pre-wrap select-text custom-scrollbar animate-fade-in">
          {text}
        </div>
      )}
    </div>
  );
}

// ── 2. TERMINAL TRANSCRIPT (Anara Standard) ──────────────────────────────────
export function TerminalTranscript({
  command,
  exitCode,
  rawResult,
}: {
  command?: string;
  exitCode?: number;
  rawResult?: string;
}) {
  if (!command && exitCode === undefined && !rawResult) return null;

  return (
    <div className="flex flex-col gap-1.5 w-full my-1 font-mono text-[11px] select-text">
      {(command || exitCode !== undefined) && (
        <div className="flex min-w-0 items-center justify-between gap-2 rounded border border-white/[0.08] bg-black/60 px-2.5 py-1.5 leading-relaxed">
          {command && (
            <code className="min-w-0 flex-1 whitespace-pre-wrap break-all text-slate-300">
              <span className="text-cyan-400 select-none font-bold">$ </span>
              {command}
            </code>
          )}
          {exitCode !== undefined && (
            <span
              className={`shrink-0 rounded px-1.5 py-px text-[10px] font-bold tabular-nums border ${
                exitCode === 0
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/20"
              }`}
            >
              exit {exitCode}
            </span>
          )}
        </div>
      )}
      {rawResult && (
        <pre className="p-2.5 rounded border border-white/[0.06] bg-black/50 text-slate-300 text-[10.5px] leading-relaxed max-h-[220px] overflow-auto custom-scrollbar whitespace-pre-wrap break-all shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
          {rawResult}
        </pre>
      )}
    </div>
  );
}

// ── 3. TOOL RUN GROUP CARD (Anara Standard: "Explored X files, ran Y commands") ──
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
    const fileSet = new Set<string>();

    for (const item of activeItems) {
      const tool = (item.toolName || "").toLowerCase();
      const isShell = SHELL_TOOLS.has(tool) || tool.includes("cli") || tool.includes("terminal") || tool.includes("exec");
      const isRead = READ_TOOLS.has(tool) || tool.includes("read") || tool.includes("scan");
      const isSearch = SEARCH_TOOLS.has(tool) || tool.includes("grep") || tool.includes("glob") || tool.includes("search") || tool.includes("list");

      if (isShell) {
        commandCount++;
      } else if (isRead) {
        readCount++;
      } else if (isSearch) {
        searchCount++;
      }

      if (!isShell) {
        const target = item.filePath || item.detail || item.actionTitle || "";
        const cleaned = target.replace(/^(read|scan|grep|glob|list|search)\s+/i, "").trim();
        if (cleaned) {
          fileSet.add(cleaned);
        }
      }
    }

    const uniqueFiles = fileSet.size;
    const clauses: string[] = [];

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

              const rawTarget = sub.command || sub.filePath || sub.detail || sub.actionTitle || "";
              const cmdText = sub.command || sub.detail || sub.actionTitle || "command";
              const exitCode = sub.exitCode;
              const duration = sub.durationText;

              const isRowExpanded = expandedRowIdx === sIdx;

              if (isShell) {
                return (
                  <div key={sIdx} className="flex flex-col group/row">
                    <div className="flex items-center gap-2 py-0.5 px-1.5 rounded hover:bg-white/[0.04] transition-colors cursor-pointer">
                      {/* Terminal Icon */}
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

                      {/* Duration Tag */}
                      {duration && (
                        <span className="text-[10px] text-slate-500 font-mono tabular-nums shrink-0 ml-auto">
                          {duration}
                        </span>
                      )}

                      {/* Expand Chevron */}
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

                      {/* Dismiss X button */}
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

                    {/* Inline Terminal Transcript */}
                    {isRowExpanded && (
                      <div className="pl-5 pr-1 py-1">
                        <TerminalTranscript
                          command={cmdText}
                          exitCode={exitCode ?? 0}
                          rawResult={sub.rawResult || sub.summary}
                        />
                      </div>
                    )}
                  </div>
                );
              }

              // File exploration item
              const cleanTarget = rawTarget.replace(/^(read|scan|grep|glob|list)\s+/i, "").trim();
              const lastSlash = Math.max(cleanTarget.lastIndexOf("/"), cleanTarget.lastIndexOf("\\"));
              const dir = lastSlash !== -1 ? cleanTarget.slice(0, lastSlash + 1) : "";
              const file = lastSlash !== -1 ? cleanTarget.slice(lastSlash + 1) : cleanTarget;
              const opBadge = isRead ? "READ" : isGrep ? "GREP" : isGlob ? "GLOB" : "EXPLORE";

              return (
                <div
                  key={sIdx}
                  onClick={() => onOpenFile && cleanTarget && onOpenFile(cleanTarget, file)}
                  className={`flex items-center gap-2 py-0.5 px-1.5 rounded transition-colors group/row ${
                    onOpenFile ? "hover:bg-white/[0.04] cursor-pointer" : "text-slate-300"
                  }`}
                >
                  <span
                    className={`px-1.5 py-px rounded text-[9.5px] font-bold shrink-0 tracking-wider border ${
                      isRead
                        ? "bg-cyan-500/10 text-cyan-300 border-cyan-400/20"
                        : isGrep
                        ? "bg-purple-500/10 text-purple-300 border-purple-400/20"
                        : "bg-amber-500/10 text-amber-300 border-amber-400/20"
                    }`}
                  >
                    {opBadge}
                  </span>
                  <div className="truncate flex items-baseline gap-0.5 min-w-0">
                    {dir && <span className="text-slate-500 truncate text-[10px]">{dir}</span>}
                    <span className="text-slate-200 font-medium group-hover/row:text-cyan-300 transition-colors truncate">
                      {file}
                    </span>
                  </div>
                  {onOpenFile && (
                    <span className="text-slate-600 group-hover/row:text-slate-400 text-[10px] ml-auto shrink-0 opacity-0 group-hover/row:opacity-100 transition-opacity">
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

// ── 3. TODO CHECKLIST CARD ──────────────────────────────────────────────────
export function TodoChecklistCard({
  todoData,
  onDismiss,
}: {
  todoData?: TodoData | null;
  onDismiss?: () => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!todoData || !todoData.items || todoData.items.length === 0) return null;
  const total = todoData.items.length;
  const completed = todoData.items.filter((t) => t.is_completed).length;

  return (
    <div className="my-1.5 font-mono text-xs select-none">
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        className="flex items-center gap-2 text-left text-slate-300 hover:text-white transition-colors cursor-pointer py-1 group"
      >
        <span className="relative flex h-2 w-2 shrink-0">
          <span className={`inline-flex rounded-full h-1.5 w-1.5 ${completed === total ? "bg-emerald-400" : "bg-cyan-400"}`} />
        </span>
        <span className="font-semibold text-slate-200 tracking-tight text-[11.5px]">Tasks</span>
        <span className="text-slate-400 text-[11px]">({completed} of {total} completed)</span>
        <svg
          className={`w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ${
            isExpanded ? "rotate-90" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${
          isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div className="pl-4 py-1.5 space-y-1.5 border-l border-white/[0.08] my-1 font-mono text-[11px]">
            {todoData.items.map((item: any, idx: number) => (
              <div
                key={idx}
                className={`flex items-start gap-2 p-1 rounded transition-colors ${
                  item.is_completed ? "text-slate-500 line-through" : "text-slate-200 hover:bg-white/[0.02]"
                }`}
              >
                <span
                  className={`w-3.5 h-3.5 rounded mt-0.5 flex items-center justify-center text-[9px] shrink-0 font-bold ${
                    item.is_completed
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                      : "border border-white/20 text-transparent"
                  }`}
                >
                  {item.is_completed && (
                    <svg className="w-2.5 h-2.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </span>
                <div className="flex-1 min-w-0 font-sans">
                  <p className="leading-snug">{item.title}</p>
                  {item.content && (
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5">{item.content}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 4. AGENT ACTION CARD (Diffs & Terminal Runs) ─────────────────────────────
export interface DiffLineItem {
  type: "add" | "del" | "ctx" | "hunk";
  text: string;
  oldLine?: number;
  newLine?: number;
}

export function AgentActionCard({
  action,
  sessionId,
  onOpenFile,
  onDismiss,
}: {
  action?: AgentActionData;
  sessionId?: number;
  onOpenFile?: (filePath: string, fileName?: string) => void;
  onDismiss?: () => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isReverting, setIsReverting] = useState(false);
  const [isReverted, setIsReverted] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);
  const [confirmRollback, setConfirmRollback] = useState(false);
  const confirmTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current);
    };
  }, []);

  const rawDiff = action?.rawResult || action?.summary || "";
  const parsedDiff = useMemo(() => {
    if (!rawDiff) return { added: 0, deleted: 0, lines: [] as DiffLineItem[] };
    const rawLines = rawDiff.split("\n");
    let added = 0;
    let deleted = 0;
    let currentOldLine = 1;
    let currentNewLine = 1;

    const formatted: DiffLineItem[] = [];

    for (const l of rawLines) {
      if (
        l.startsWith("diff --git") ||
        l.startsWith("index ") ||
        l.startsWith("new file mode") ||
        l.startsWith("deleted file mode") ||
        l.startsWith("similarity ") ||
        l.startsWith("rename ") ||
        l.startsWith("\\")
      ) {
        continue;
      }
      if (l.startsWith("@@")) {
        const match = l.match(/@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@(.*)/);
        if (match) {
          currentOldLine = parseInt(match[1], 10);
          currentNewLine = parseInt(match[2], 10);
          const contextSuffix = (match[3] || "").trim();
          formatted.push({
            type: "hunk",
            text: contextSuffix ? `@@ ${contextSuffix}` : l,
          });
        } else {
          formatted.push({ type: "hunk", text: l });
        }
      } else if (l.startsWith("+") && !l.startsWith("+++")) {
        added++;
        formatted.push({
          type: "add",
          text: l.substring(1),
          newLine: currentNewLine++,
        });
      } else if (l.startsWith("-") && !l.startsWith("---")) {
        deleted++;
        formatted.push({
          type: "del",
          text: l.substring(1),
          oldLine: currentOldLine++,
        });
      } else if (l.startsWith("---") || l.startsWith("+++")) {
        continue;
      } else {
        formatted.push({
          type: "ctx",
          text: l.startsWith(" ") ? l.substring(1) : l,
          oldLine: currentOldLine++,
          newLine: currentNewLine++,
        });
      }
    }
    return { added, deleted, lines: formatted };
  }, [rawDiff]);

  if (!action) return null;

  const handleRollback = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!action?.checkpointId || isReverting || isReverted) return;

    if (!confirmRollback) {
      setConfirmRollback(true);
      if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current);
      confirmTimeoutRef.current = setTimeout(() => {
        setConfirmRollback(false);
      }, 3500);
      return;
    }

    if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current);
    setConfirmRollback(false);
    setIsReverting(true);

    try {
      await anaraApi.checkpoint.revert(action.checkpointId, sessionId);
      setIsReverted(true);
      setRollbackError(null);
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "workspace_updated" } }));
      }
    } catch (err: any) {
      console.warn("[Rollback Error]:", err);
      setRollbackError(err?.message || "Revert failed");
    } finally {
      setIsReverting(false);
    }
  };

  const tool = (action.toolName || "").toLowerCase();
  const isStart = action.eventType === "agent_action_start";
  const isWrite = FILE_EDIT_TOOLS.has(tool) || tool.includes("write") || tool.includes("edit") || tool.includes("patch") || tool.includes("artifact");
  const isShell = SHELL_TOOLS.has(tool) || tool.includes("bash") || tool.includes("shell") || tool.includes("terminal") || tool.includes("command") || tool.includes("cli");
  const isSearch = SEARCH_TOOLS.has(tool) || tool.includes("glob") || tool.includes("grep") || tool.includes("search");
  const isRead = READ_TOOLS.has(tool) || tool.includes("read") || tool.includes("scan") || tool.includes("list");

  const rawTarget = action.detail || action.actionTitle || "";
  const filename = action.filename || action.filePath?.split(/[/\\]/).pop() || rawTarget.split(" ")[0]?.split(/[/\\]/).pop() || "file";
  const lastSlash = action.filePath ? Math.max(action.filePath.lastIndexOf("/"), action.filePath.lastIndexOf("\\")) : -1;
  const dirPath = lastSlash !== -1 && action.filePath ? action.filePath.slice(0, lastSlash) : "";

  // ── Render File Modification Diff Card ──
  if (isWrite) {
    const addCount = action.added ?? parsedDiff.added ?? 1;
    const delCount = action.deleted ?? parsedDiff.deleted ?? 0;

    return (
      <div className="my-1.5 font-mono text-xs select-none">
        {/* Header Action Row */}
        <div className="w-full flex items-center justify-between py-1 transition-colors text-left">
          <button
            type="button"
            onClick={() => setIsExpanded((v) => !v)}
            className="flex items-center gap-2 min-w-0 flex-1 text-left cursor-pointer font-mono group py-0.5"
          >
            <span className="relative flex h-2 w-2 shrink-0">
              {isStart ? (
                <>
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
                </>
              ) : (
                <span className="inline-flex rounded-full h-1.5 w-1.5 bg-slate-500 group-hover:bg-cyan-400 transition-colors" />
              )}
            </span>
            <span className="text-cyan-400 font-bold text-[11px] tracking-tight">Edit</span>
            <span className="text-slate-200 font-semibold truncate text-[11.5px] group-hover:text-white transition-colors">
              {filename}
            </span>
            {dirPath && <span className="text-slate-500 truncate text-[10.5px]">{dirPath}</span>}
            <div className="flex items-center gap-1.5 text-[10px] shrink-0 ml-1 font-bold">
              <span className="text-emerald-400">+{addCount}</span>
              <span className="text-rose-400">-{delCount}</span>
            </div>
            <svg
              className={`w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ml-1 ${
                isExpanded ? "rotate-90" : ""
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>

          <div className="flex items-center gap-2 shrink-0">
            {action.checkpointId && (
              <button
                type="button"
                onClick={handleRollback}
                disabled={isReverting || isReverted}
                className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer border ${
                  isReverted
                    ? "bg-emerald-500/15 text-emerald-300 border-emerald-400/30"
                    : confirmRollback
                    ? "bg-amber-500/20 text-amber-200 border-amber-400/40"
                    : rollbackError
                    ? "bg-rose-500/20 text-rose-300 border-rose-400/40"
                    : "bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-white border-white/[0.08]"
                }`}
                title={confirmRollback ? "Click again to confirm revert" : rollbackError || "Revert this edit"}
              >
                {isReverted ? "Reverted" : confirmRollback ? "Confirm?" : rollbackError ? "Error" : "Revert"}
              </button>
            )}

            {onOpenFile && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenFile(action.filePath || filename, filename);
                }}
                className="px-2 py-0.5 rounded text-[10px] font-mono text-cyan-300 hover:text-white bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/25 transition-all cursor-pointer"
              >
                View
              </button>
            )}
          </div>
        </div>

        {/* Dual Line Number Gutter Diff Table */}
        <div
          className={`grid transition-[grid-template-rows] duration-200 ease-out ${
            isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
          }`}
        >
          <div className="overflow-hidden">
            <div className="mt-1.5 rounded-lg border border-white/[0.08] bg-black/50 font-mono text-[11px] max-h-[320px] overflow-auto overscroll-x-contain overscroll-y-auto custom-scrollbar select-text tabular-nums shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
              {parsedDiff.lines.length > 0 ? (
                <table className="w-full border-collapse">
                  <tbody>
                    {parsedDiff.lines.map((line: DiffLineItem, idx: number) => {
                      if (line.type === "hunk") {
                        return (
                          <tr key={idx} className="bg-cyan-950/20 text-cyan-300/80 font-mono text-[10px]">
                            <td colSpan={4} className="px-3 py-1 select-none font-medium">
                              {line.text}
                            </td>
                          </tr>
                        );
                      }
                      return (
                        <tr
                          key={idx}
                          className={`${
                            line.type === "add"
                              ? "bg-emerald-500/[0.08] text-emerald-200"
                              : line.type === "del"
                              ? "bg-rose-500/[0.08] text-rose-200"
                              : "text-slate-400 hover:bg-white/[0.015]"
                          }`}
                        >
                          <td className="w-8 pr-1.5 text-right select-none text-slate-600 font-mono text-[9.5px] py-0.5">
                            {line.type === "del" || line.type === "ctx" ? line.oldLine || "" : ""}
                          </td>
                          <td className="w-8 pr-2 text-right select-none text-slate-600 font-mono text-[9.5px] py-0.5">
                            {line.type === "add" || line.type === "ctx" ? line.newLine || "" : ""}
                          </td>
                          <td className="w-4 text-center select-none font-bold py-0.5 text-[10px]">
                            {line.type === "add" ? (
                              <span className="text-emerald-400">+</span>
                            ) : line.type === "del" ? (
                              <span className="text-rose-400">-</span>
                            ) : (
                              " "
                            )}
                          </td>
                          <td className="pl-1.5 pr-3 py-0.5 whitespace-pre font-mono leading-relaxed text-[11px]">
                            {line.text}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <pre className="text-slate-300 p-3 leading-relaxed whitespace-pre-wrap font-mono text-[11px]">
                  {rawDiff || "Modifications applied."}
                </pre>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Render Shell Execution Card (Anara Standard) ──
  if (isShell) {
    const cmd = action.command || action.detail || action.actionTitle || "command";
    const duration = action.durationText;

    return (
      <div className="my-1.5 font-mono text-xs select-none">
        <div className="flex items-center justify-between py-1 group/cmd">
          <button
            onClick={() => setIsExpanded((v) => !v)}
            className="flex items-center gap-2 text-left text-slate-300 hover:text-white transition-colors cursor-pointer flex-1 min-w-0"
          >
            <span className="relative flex h-2 w-2 shrink-0">
              {isStart ? (
                <>
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
                </>
              ) : (
                <span className="inline-flex rounded-full h-1.5 w-1.5 bg-slate-500 group-hover:bg-cyan-400 transition-colors" />
              )}
            </span>
            <span className="text-emerald-400 font-bold text-[11px] tracking-tight">Run</span>
            <span className="text-slate-300 group-hover:text-white truncate font-mono text-[11px] font-medium transition-colors">
              {cmd}
            </span>
            <svg
              className={`w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ml-1 ${
                isExpanded ? "rotate-90" : ""
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>

          {duration && (
            <span className="text-[10px] text-slate-500 font-mono tabular-nums shrink-0 ml-2">
              {duration}
            </span>
          )}
        </div>

        {action.summary || action.rawResult ? (
          <div
            className={`grid transition-[grid-template-rows] duration-200 ease-out ${
              isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
            }`}
          >
            <div className="overflow-hidden mt-1">
              <TerminalTranscript
                command={cmd}
                exitCode={action.exitCode ?? 0}
                rawResult={action.rawResult || action.summary}
              />
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  // ── Standalone Exploration Item ──
  const toolPrefix = isRead ? "Read" : isSearch ? (tool.includes("glob") ? "Glob" : tool.includes("search") ? "Search" : "Grep") : "Action";

  return (
    <div className="my-1.5 font-mono text-xs select-none">
      <div className="flex items-baseline gap-2 py-0.5 text-slate-300">
        <span className="font-semibold text-slate-200 shrink-0">{toolPrefix}</span>
        <span className="truncate text-slate-300 font-mono">{action.detail || action.actionTitle}</span>
        {isStart && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping ml-1" />}
      </div>
    </div>
  );
}

export default function AgentToolCard({
  action,
  todoData,
  sessionId,
  onOpenFile,
  onDismiss,
}: AgentToolCardProps) {
  if (todoData && todoData.items && todoData.items.length > 0) {
    return <TodoChecklistCard todoData={todoData} onDismiss={onDismiss} />;
  }
  return (
    <AgentActionCard
      action={action}
      sessionId={sessionId}
      onOpenFile={onOpenFile}
      onDismiss={onDismiss}
    />
  );
}
