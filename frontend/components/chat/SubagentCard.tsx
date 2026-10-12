"use client";

"use client";

import React, { useState, useEffect, useRef, useMemo, ReactNode } from "react";
import type { SubagentProgressItem, SubagentTaskData, SubagentStatus } from "../hud/types";
import { SCAFFOLD_GLYPH_CLASS } from "./ScaffoldRow";
import { DisclosureCaret } from "./DisclosureCaret";
import {
  type DelegateRow,
  type DelegateRowStatus,
  isDelegateRowLive,
  formatElapsed,
  formatDurationSeconds,
  delegateRowsFromCall,
  mergeDelegateRows,
  normalizeDelegateStatus,
} from "./delegateModel";

// Re-export model types and utilities for seamless consumer imports
export type { DelegateRow, DelegateRowStatus };
export {
  isDelegateRowLive,
  formatElapsed,
  formatDurationSeconds,
  delegateRowsFromCall,
  mergeDelegateRows,
  normalizeDelegateStatus,
};

// Depth of relayed activity items kept mounted behind the visible one (Anara Standard)
const TICKER_DEPTH = 6;

// Module-level registry so elapsed timers survive component unmount/remount
const startedAtByKey = new Map<string, number>();

function getTimerOrigin(key?: string, since?: number): number {
  if (since !== undefined && since > 0) return since;
  if (!key) return Date.now();
  const existing = startedAtByKey.get(key);
  if (existing !== undefined) return existing;
  const now = Date.now();
  startedAtByKey.set(key, now);
  return now;
}

/**
 * useElapsedSeconds — Live seconds stopwatch hook matching desktop activity timer.
 * Origin order: explicit timestamp -> registry entry -> mount time.
 */
export function useElapsedSeconds(active = true, timerKey?: string, since?: number): number {
  const startRef = useRef(getTimerOrigin(timerKey, since));
  const [elapsed, setElapsed] = useState(() => Math.max(0, Math.floor((Date.now() - startRef.current) / 1000)));

  useEffect(() => {
    if (since !== undefined && since > 0) {
      startRef.current = since;
    } else if (timerKey) {
      startRef.current = getTimerOrigin(timerKey);
    }

    if (!active) return;
    setElapsed(Math.max(0, Math.floor((Date.now() - startRef.current) / 1000)));

    const interval = setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - startRef.current) / 1000)));
    }, 1000);

    return () => clearInterval(interval);
  }, [active, since, timerKey]);

  return elapsed;
}

// ── STATUS GLYPH ─────────────────────────────────────────────────────────────

export function statusGlyph(status: DelegateRowStatus, label?: string): ReactNode {
  const norm = normalizeDelegateStatus(status);

  if (isDelegateRowLive(norm)) {
    return (
      <span
        aria-label={label || "Running"}
        className="relative flex h-3.5 w-3.5 shrink-0 items-center justify-center"
      >
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
      </span>
    );
  }

  if (norm === "error" || norm === "failed" || norm === "timed_out") {
    return (
      <svg
        aria-label={label || "Error"}
        className="w-3.5 h-3.5 text-rose-400 shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <circle cx="12" cy="12" r="10" strokeWidth={2} />
        <line x1="12" y1="8" x2="12" y2="12" strokeWidth={2} strokeLinecap="round" />
        <line x1="12" y1="16" x2="12.01" y2="16" strokeWidth={2} strokeLinecap="round" />
      </svg>
    );
  }

  if (norm === "stopped" || norm === "interrupted") {
    return (
      <svg
        aria-label={label || "Stopped"}
        className="w-3.5 h-3.5 text-amber-400/90 shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <circle cx="12" cy="12" r="10" strokeWidth={2} />
        <rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor" stroke="none" />
      </svg>
    );
  }

  if (norm === "dispatched") {
    // Parked background delegation that outlived turn, not streaming progress
    return <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-slate-500 shrink-0" />;
  }

  return (
    <svg
      aria-label={label || "Completed"}
      className="w-3.5 h-3.5 text-emerald-400/90 shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <circle cx="12" cy="12" r="10" strokeWidth={2} />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m9 12 2 2 4-4" />
    </svg>
  );
}

// ── STATUS BADGE ─────────────────────────────────────────────────────────────

export function StatusBadge({ status }: { status: DelegateRowStatus }) {
  const norm = normalizeDelegateStatus(status);

  switch (norm) {
    case "running":
    case "queued":
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9.5px] font-mono bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 shrink-0">
          <span className="h-1 w-1 rounded-full bg-cyan-400 animate-pulse" />
          <span>{norm === "queued" ? "queued" : "running"}</span>
        </span>
      );
    case "completed":
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9.5px] font-mono bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 shrink-0">
          <span>completed</span>
        </span>
      );
    case "error":
    case "failed":
    case "timed_out":
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9.5px] font-mono bg-rose-500/10 border border-rose-500/20 text-rose-400 shrink-0">
          <span>{norm === "timed_out" ? "timed out" : "error"}</span>
        </span>
      );
    case "stopped":
    case "interrupted":
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9.5px] font-mono bg-amber-500/10 border border-amber-500/20 text-amber-300 shrink-0">
          <span>stopped</span>
        </span>
      );
    case "dispatched":
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9.5px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-400 shrink-0">
          <span>dispatched</span>
        </span>
      );
    default:
      return null;
  }
}

// ── AGENT ICON GLYPH (Vector Standard, Zero Emojis) ─────────────────────────

export function AgentIconGlyph({ className = "w-3 h-3 text-slate-500" }: { className?: string }) {
  return (
    <svg className={`shrink-0 ${className}`} fill="currentColor" viewBox="0 0 16 16">
      <path d="M8 1a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM6 6a2 2 0 0 0-2 2v3h1V8a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3h1V8a2 2 0 0 0-2-2H6z" />
      <path d="M2.5 13a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5z" />
    </svg>
  );
}

// ── ANIMATED ACTIVITY TICKER REEL (Smooth 240ms translateY reel) ─────────────

export function SubagentActivityTicker({
  activity,
  isLive,
}: {
  activity: string[];
  isLive: boolean;
}) {
  if (!activity || activity.length === 0) return null;
  const recent = activity.slice(-TICKER_DEPTH);
  const activeIdx = Math.max(0, recent.length - 1);

  return (
    <div className="h-[20px] overflow-hidden select-none font-mono text-[11px] [isolation:isolate] [overflow:clip]">
      <div
        className="transition-transform duration-[240ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
        style={{
          transform: `translateY(calc(${activeIdx} * 20px * -1))`,
        }}
      >
        {recent.map((line, idx) => (
          <div key={idx} className="h-[20px] flex items-center min-w-0 overflow-hidden">
            <span
              className={`truncate transition-colors ${
                isLive && idx === activeIdx ? "shimmer text-slate-100 font-medium" : "text-slate-400"
              }`}
            >
              {line}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── DELEGATE ROW VIEW ────────────────────────────────────────────────────────

export interface DelegateRowViewProps {
  row: DelegateRow;
  onOpenFile?: (filePath: string, fileName?: string) => void;
  onOpenSession?: (sessionId: string) => void;
}

/**
 * DelegateRowView — Visual scaffolding for one delegated child:
 * - Line 1: Leading glyph, goal label preview, status badge, model, live elapsed timer, agent icon, caret
 * - Line 2: Animated ticker for active step (240ms translateY reel)
 * - Line 3: Collapsible findings drawer with neutral obsidian Liquid Glass styling
 */
export function DelegateRowView({ row, onOpenFile, onOpenSession }: DelegateRowViewProps) {
  const isLive = isDelegateRowLive(row.status);
  const [open, setOpen] = useState(false);
  const elapsed = useElapsedSeconds(isLive, `delegate:${row.id}`, row.startedAt);

  const durationText = isLive
    ? formatElapsed(elapsed)
    : row.durationSeconds !== undefined
    ? formatDurationSeconds(row.durationSeconds)
    : "";

  const recentActivity = row.activity.slice(-TICKER_DEPTH);
  const hasFindings = Boolean(
    (row.keyFindings && row.keyFindings.length > 0) || row.findings
  );

  return (
    <div className="grid min-w-0 max-w-full gap-0.5 rounded-xl border border-white/[0.08] bg-[#070b14]/75 backdrop-blur-md px-3 py-2.5 transition-all hover:border-white/15 shadow-sm">
      {/* Line 1: Header row with visual scaffolding (data-conversation-scaffold on inner row only) */}
      <div
        className="flex min-w-0 max-w-full items-center gap-1.5 font-mono text-xs select-none"
        data-conversation-scaffold=""
      >
        {/* Leading glyph */}
        <span className={SCAFFOLD_GLYPH_CLASS}>{statusGlyph(row.status)}</span>

        {/* Goal label preview */}
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="min-w-0 flex-1 truncate text-left font-medium text-slate-200 hover:text-white transition-colors cursor-pointer text-[11.5px]"
          title={row.goal}
        >
          {row.goal}
        </button>

        {/* Status badge */}
        <StatusBadge status={row.status} />

        {/* Model badge */}
        {row.model && (
          <span className="hidden sm:inline-flex px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.08] text-[10px] text-slate-300 font-mono shrink-0">
            {row.model}
          </span>
        )}

        {/* Live elapsed stopwatch or settled duration */}
        {durationText && (
          <span className="text-[10px] font-mono tabular-nums text-slate-400 shrink-0 ml-1">
            {durationText}
          </span>
        )}

        {/* Codicon Agent Icon */}
        <AgentIconGlyph className="w-3 h-3 text-slate-500 shrink-0 ml-1" />

        {/* In-place Accordion Caret */}
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="p-1 rounded text-slate-500 hover:text-slate-200 transition-colors cursor-pointer shrink-0"
          title={open ? "Collapse details" : "Expand details"}
        >
          <DisclosureCaret open={open} size={11} />
        </button>
      </div>

      {/* Line 2: Animated ticker for active step (shown when closed or running) */}
      {recentActivity.length > 0 && !open && (
        <div className="min-w-0 max-w-full pl-5">
          <SubagentActivityTicker activity={recentActivity} isLive={isLive} />
        </div>
      )}

      {/* Line 3: Clean collapsible findings drawer with neutral obsidian Liquid Glass styling */}
      {open && (
        <div className="mt-2.5 pl-5 pt-2.5 border-t border-white/[0.06] flex flex-col gap-2.5 font-mono text-xs animate-fade-in">
          {/* Key Findings Block */}
          {hasFindings && (
            <div className="flex flex-col gap-1.5 p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.08] backdrop-blur-sm">
              <span className="text-[10px] uppercase tracking-wider text-emerald-400/90 font-semibold font-mono">
                Key Findings
              </span>
              {row.keyFindings && row.keyFindings.length > 0 ? (
                <ul className="space-y-1 font-sans text-xs text-slate-200 list-disc list-inside">
                  {row.keyFindings.map((finding, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {finding}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="font-sans text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
                  {row.findings}
                </p>
              )}
            </div>
          )}

          {/* Referenced Files with Link */}
          {row.referencedFiles && row.referencedFiles.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-[9.5px] uppercase tracking-wider text-slate-400 font-semibold font-mono">
                Referenced Files ({row.referencedFiles.length})
              </span>
              <div className="flex flex-wrap gap-1.5">
                {row.referencedFiles.map((file, idx) => {
                  const fname = file.split(/[\/\\]/).pop() || file;
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => onOpenFile?.(file, fname)}
                      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] text-slate-200 hover:text-white transition-colors cursor-pointer text-[10.5px] font-mono"
                    >
                      <span>{fname}</span>
                      <span className="text-slate-400 text-[10px]">↗</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Execution Trace / Tool calls */}
          {row.activity.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-[9.5px] uppercase tracking-wider text-slate-400 font-semibold font-mono">
                Execution Trace ({row.activity.length} action{row.activity.length === 1 ? "" : "s"})
              </span>
              <div className="max-h-48 overflow-y-auto rounded-lg border border-white/[0.06] bg-black/50 p-2.5 space-y-1 custom-scrollbar">
                {row.activity.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-[11px] leading-relaxed text-slate-300">
                    <span className="text-slate-500 select-none tabular-nums shrink-0 font-mono text-[10px] mt-0.5">
                      {idx + 1}.
                    </span>
                    <span className="font-mono whitespace-pre-wrap break-all text-slate-300">
                      {step}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error Notice */}
          {row.error && (
            <div className="p-2.5 rounded-lg bg-rose-950/25 border border-rose-500/25 text-rose-300 text-[11px]">
              <span className="font-semibold block mb-0.5 font-mono">Error:</span>
              <span className="font-sans leading-relaxed">{row.error}</span>
            </div>
          )}

          {/* Child session link if available */}
          {row.sessionId && onOpenSession && (
            <div className="flex items-center justify-end pt-1">
              <button
                type="button"
                onClick={() => onOpenSession(row.sessionId!)}
                className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 font-mono transition-colors cursor-pointer"
              >
                <span>Open child session</span>
                <span className="text-[10px]">↗</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── MAIN EXPORT: SUBAGENT CARD ───────────────────────────────────────────────

export interface SubagentCardProps {
  data?: SubagentTaskData;
  rows?: DelegateRow[];
  args?: unknown;
  result?: unknown;
  toolCallId?: string;
  onOpenFile?: (filePath: string, fileName?: string) => void;
  onOpenSession?: (sessionId: string) => void;
}

export function SubagentCard({
  data,
  rows: explicitRows,
  args,
  result,
  toolCallId,
  onOpenFile,
  onOpenSession,
}: SubagentCardProps) {
  const [isOpen, setIsOpen] = useState(true);

  // Derive consolidated rows from explicit rows, incoming data payload, or tool args/result
  const resolvedRows: DelegateRow[] = useMemo(() => {
    if (explicitRows && explicitRows.length > 0) {
      return explicitRows;
    }

    const liveTasks = data?.tasks || [];

    if (args !== undefined || result !== undefined) {
      const callRows = delegateRowsFromCall(args, result, toolCallId);
      return mergeDelegateRows(callRows, liveTasks, toolCallId);
    }

    if (liveTasks.length > 0) {
      return liveTasks.map((t, idx) => ({
        id: t.taskId || t.id || `task_${idx + 1}`,
        goal: t.goal || t.title || "Delegated mission",
        status: normalizeDelegateStatus(t.status),
        activity: t.activity || [],
        durationSeconds: t.durationSeconds ?? t.durationSec,
        model: t.model,
        sessionId: t.sessionId || t.childSessionId,
        keyFindings: t.keyFindings,
        referencedFiles: t.referencedFiles,
        findings: t.findings,
        error: t.error,
        depth: t.depth,
        startedAt: t.startedAt,
      }));
    }

    return [];
  }, [explicitRows, data?.tasks, args, result, toolCallId]);

  if (resolvedRows.length === 0) return null;

  const total = resolvedRows.length;
  const running = resolvedRows.filter((r) => isDelegateRowLive(r.status)).length;
  const completed = resolvedRows.filter((r) => r.status === "completed").length;
  const failed = resolvedRows.filter(
    (r) => r.status === "error" || r.status === "failed" || r.status === "timed_out"
  ).length;

  return (
    <div className="my-2 w-full max-w-full font-mono select-none" data-delegate-card="" data-slot="tool-block">
      {/* Collapsible Header Row: Caret | N Subagents | Progress Stats */}
      <div className="mb-1.5 flex items-center justify-between text-xs" data-conversation-scaffold="">
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-white transition-colors"
        >
          <DisclosureCaret open={isOpen} size={11} />
          <span className="font-semibold text-slate-100 text-[12px] tracking-tight">
            {total} Subagent{total === 1 ? "" : "s"}
          </span>
          <span className="text-[10px] text-slate-500 font-mono ml-1">
            ({completed}/{total} finished
            {running > 0 ? `, ${running} active` : ""}
            {failed > 0 ? `, ${failed} failed` : ""})
          </span>
        </button>

        {running > 0 && (
          <span className="flex items-center gap-1.5 text-[10px] text-slate-400 font-mono">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping" />
            <span>Executing...</span>
          </span>
        )}
      </div>

      {/* Subagent Rows */}
      {isOpen && (
        <div className="flex flex-col gap-1.5">
          {resolvedRows.map((row) => (
            <DelegateRowView
              key={row.id}
              row={row}
              onOpenFile={onOpenFile}
              onOpenSession={onOpenSession}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default SubagentCard;
