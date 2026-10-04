"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import { AgentActionData } from "../hud/types";
import { anaraApi } from "@/lib/apiClient";
import { stripDiffFileHeaders, FILE_EDIT_TOOLS, SHELL_TOOLS, SEARCH_TOOLS, READ_TOOLS, clampForDisplay } from "./toolCardUtils";
import { TerminalTranscript } from "./TerminalTranscript";
import { ReadFileView } from "./ReadFileView";
import { GrepResultView } from "./GrepResultView";
import { GlobResultView } from "./GlobResultView";
import { SubagentCard } from "./SubagentCard";

// ── DIFF & CODE MODIFICATION CARD (Anara Desktop Standard) ──────────────
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
  const tool = (action?.toolName || "").toLowerCase();
  const isFileEdit = Boolean(
    action?.added !== undefined ||
    action?.deleted !== undefined ||
    action?.checkpointId ||
    tool.includes("patch") ||
    tool.includes("write") ||
    tool.includes("edit")
  );
  const [isExpanded, setIsExpanded] = useState(isFileEdit);
  const [isReverting, setIsReverting] = useState(false);
  const [isReverted, setIsReverted] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);
  const [confirmRollback, setConfirmRollback] = useState(false);
  const [copied, setCopied] = useState(false);
  const confirmTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    };
  }, []);

  const rawDiff = action?.rawResult || action?.summary || "";
  const cleanedDiff = useMemo(() => stripDiffFileHeaders(rawDiff), [rawDiff]);

  const parsedDiff = useMemo(() => {
    if (!cleanedDiff) return { isRealDiff: false, added: 0, deleted: 0, lines: [] as DiffLineItem[] };
    const rawLines = cleanedDiff.split("\n");
    let added = 0;
    let deleted = 0;
    let currentOldLine = 1;
    let currentNewLine = 1;
    let hasDiffSignals = false;

    const formatted: DiffLineItem[] = [];

    for (const l of rawLines) {
      if (l.startsWith("@@")) {
        hasDiffSignals = true;
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
        hasDiffSignals = true;
        added++;
        formatted.push({
          type: "add",
          text: l.substring(1),
          newLine: currentNewLine++,
        });
      } else if (l.startsWith("-") && !l.startsWith("---")) {
        hasDiffSignals = true;
        deleted++;
        formatted.push({
          type: "del",
          text: l.substring(1),
          oldLine: currentOldLine++,
        });
      } else {
        formatted.push({
          type: "ctx",
          text: l.startsWith(" ") ? l.substring(1) : l,
          oldLine: currentOldLine++,
          newLine: currentNewLine++,
        });
      }
    }

    return { isRealDiff: hasDiffSignals, added, deleted, lines: formatted };
  }, [cleanedDiff]);

  if (!action) return null;

  const handleCopyDiff = (e: React.MouseEvent) => {
    e.stopPropagation();
    const payload = rawDiff || action.content || "";
    navigator.clipboard.writeText(payload).then(() => {
      setCopied(true);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    });
  };

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

  const isStart = (action?.eventType || "") === "agent_action_start";
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

            <button
              type="button"
              onClick={handleCopyDiff}
              className="text-slate-500 hover:text-slate-300 p-1 rounded hover:bg-white/[0.05] transition-colors cursor-pointer text-[10px]"
              title="Copy diff"
            >
              {copied ? <span className="text-emerald-400 font-medium">Copied</span> : "Copy"}
            </button>
          </div>
        </div>

        {/* Dual Line Number Gutter Diff Table */}
        <div
          className={`grid transition-[grid-template-rows] duration-200 ease-out ${
            isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
          }`}
        >
          <div className="overflow-hidden">
            <div className="mt-1.5 rounded-lg border border-white/[0.08] bg-black/60 font-mono text-[11px] max-h-[340px] overflow-x-auto overflow-y-auto overscroll-x-contain overscroll-y-auto custom-scrollbar select-text tabular-nums shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
              {parsedDiff.isRealDiff ? (
                <table className="w-full border-collapse">
                  <tbody>
                    {parsedDiff.lines.map((line: DiffLineItem, idx: number) => {
                      if (line.type === "hunk") {
                        return (
                          <tr key={idx} className="bg-cyan-950/30 text-cyan-300 font-mono text-[10px] border-y border-cyan-800/20">
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
                              ? "bg-emerald-500/[0.09] text-emerald-200 border-l-2 border-emerald-400"
                              : line.type === "del"
                              ? "bg-rose-500/[0.09] text-rose-200 border-l-2 border-rose-400"
                              : "text-slate-400 hover:bg-white/[0.015] border-l-2 border-transparent"
                          }`}
                        >
                          <td className="w-9 pr-1.5 text-right select-none text-slate-600 font-mono text-[10px] py-0.5 tabular-nums">
                            {line.type === "del" || line.type === "ctx" ? line.oldLine || "" : ""}
                          </td>
                          <td className="w-9 pr-2 text-right select-none text-slate-600 font-mono text-[10px] py-0.5 tabular-nums border-r border-white/[0.06]">
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
                          <td className="pl-1.5 pr-3 py-0.5 whitespace-pre font-mono leading-relaxed text-[11px] min-h-[1.25rem]">
                            {line.text || " "}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : action.content ? (
                <table className="w-full border-collapse">
                  <tbody>
                    {action.content.split("\n").map((lineText: string, lIdx: number) => (
                      <tr key={lIdx} className="hover:bg-white/[0.02]">
                        <td className="w-10 pr-2 text-right select-none text-slate-600 font-mono text-[10px] py-0.5 border-r border-white/[0.06] tabular-nums">
                          {lIdx + 1}
                        </td>
                        <td className="pl-3 pr-3 py-0.5 whitespace-pre font-mono leading-relaxed text-[11px] text-slate-200 min-h-[1.25rem]">
                          {lineText || " "}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <pre className="text-slate-300 p-3 leading-relaxed whitespace-pre font-mono text-[11px]">
                  {rawDiff || "Modifications applied."}
                </pre>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Render Shell Execution Card ──
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

        {isExpanded && (
          <div className="mt-1">
            <TerminalTranscript
              command={cmd}
              exitCode={action.exitCode ?? 0}
              rawResult={action.rawResult || action.summary}
              durationText={duration}
            />
          </div>
        )}
      </div>
    );
  }

  // ── Render Read File Card ──
  if (isRead) {
    const target = action.filePath || action.detail || filename;
    return (
      <ReadFileView
        filePath={target}
        content={action.content || action.rawResult || action.summary || ""}
        onOpenFile={onOpenFile}
      />
    );
  }

  // ── Render Grep Card ──
  if (tool.includes("grep") || (isSearch && !tool.includes("glob"))) {
    const pat = action.detail?.replace(/^(Regex|pattern)[=:]\s*/i, "").trim() || action.actionTitle || "";
    return (
      <GrepResultView
        pattern={pat}
        rawResult={action.rawResult || action.summary}
        onOpenFile={onOpenFile}
      />
    );
  }

  // ── Render Glob Card ──
  if (tool.includes("glob") || tool.includes("list")) {
    const pat = action.detail?.replace(/^pattern[=:]\s*/i, "").trim() || "*";
    return (
      <GlobResultView
        pattern={pat}
        rawResult={action.rawResult || action.summary}
        onOpenFile={onOpenFile}
      />
    );
  }

  // ── Render Subagent Delegation Card ──
  if (action.subagentData || tool.includes("delegate") || tool.includes("subagent")) {
    const rawData = action.subagentData || {
      delegationId: action.checkpointId || `del_${Date.now()}`,
      goal: action.detail || action.actionTitle || "Delegated Mission",
      status: isStart ? "running" : "completed",
      tasks: [
        {
          id: "task_1",
          taskId: "1",
          goal: action.detail || action.actionTitle || "Delegated Mission",
          status: isStart ? "running" : "completed",
          activity: action.summary ? [action.summary] : ["Executing delegated mission in background..."],
          durationSec: action.durationMs ? action.durationMs / 1000 : undefined,
          findings: action.rawResult,
        },
      ],
    };
    return <SubagentCard data={rawData} onOpenFile={onOpenFile} />;
  }

  // ── Fallback Generic Action Item ──
  return (
    <div className="my-1.5 font-mono text-xs select-none">
      <div className="flex items-baseline gap-2 py-0.5 text-slate-300">
        <span className="font-semibold text-slate-200 shrink-0">Action</span>
        <span className="truncate text-slate-300 font-mono">{action.detail || action.actionTitle}</span>
        {isStart && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping ml-1" />}
      </div>
    </div>
  );
}
