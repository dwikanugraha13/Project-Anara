"use client";

import React, { useState, useEffect, useRef } from "react";
import { SubagentProgressItem, SubagentTaskData, SubagentStatus } from "../hud/types";

// ── STATUS GLYPH ─────────────────────────────────────────────────────────────
function StatusGlyph({ status }: { status: SubagentStatus }) {
  if (status === "running") {
    return (
      <span className="relative flex h-3 w-3 shrink-0 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
      </span>
    );
  }

  if (status === "failed" || status === "timed_out") {
    return (
      <svg className="w-3.5 h-3.5 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" strokeWidth="2" />
        <line x1="12" y1="8" x2="12" y2="12" strokeWidth="2" strokeLinecap="round" />
        <line x1="12" y1="16" x2="12.01" y2="16" strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }

  if (status === "dispatched") {
    return <span className="h-1.5 w-1.5 rounded-full bg-slate-500 shrink-0" />;
  }

  return (
    <svg className="w-3.5 h-3.5 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M5 13l4 4L19 7" />
    </svg>
  );
}

// ── SUBAGENT REEL TICKER (Smooth 240ms translateY reel) ─────────────────────
function SubagentActivityTicker({
  activity,
  isLive,
}: {
  activity: string[];
  isLive: boolean;
}) {
  if (!activity || activity.length === 0) return null;
  // Keep last 6 lines in reel
  const recent = activity.slice(-6);
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
                isLive && idx === activeIdx ? "text-cyan-300 font-medium" : "text-slate-500"
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

// ── SUBAGENT ROW VIEW (2-line compact footprint) ─────────────────────────────
function SubagentRowView({
  task,
  onInspect,
}: {
  task: SubagentProgressItem;
  onInspect: (task: SubagentProgressItem) => void;
}) {
  const isLive = task.status === "running";
  const [elapsed, setElapsed] = useState<number>(0);
  const startRef = useRef<number>(task.startedAt || Date.now());

  useEffect(() => {
    if (!isLive) return;
    const timer = setInterval(() => {
      setElapsed(Math.max(0, Math.round((Date.now() - startRef.current) / 1000)));
    }, 1000);
    return () => clearInterval(timer);
  }, [isLive]);

  return (
    <div className="relative flex flex-col gap-1 rounded-xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] p-2.5 transition-all">
      {/* Top Hairline Accent */}
      <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-cyan-400/20 to-transparent pointer-events-none rounded-t-xl" />

      {/* Row Header: Status Glyph | Goal Text | Model Badge | Live Timer | Inspect */}
      <div className="flex items-center gap-2 min-w-0 font-mono text-xs select-none">
        <StatusGlyph status={task.status} />

        <button
          type="button"
          onClick={() => onInspect(task)}
          className="min-w-0 truncate text-left font-medium text-slate-200 hover:text-white transition-colors cursor-pointer text-[11.5px]"
          title={task.goal}
        >
          {task.goal}
        </button>

        {task.model && (
          <span className="hidden sm:inline-flex px-1.5 py-px rounded bg-white/[0.04] border border-white/[0.06] text-[9.5px] text-slate-400 font-mono">
            {task.model}
          </span>
        )}

        {/* Live Elapsed Stopwatch / Settled Duration */}
        <div className="ml-auto flex items-center gap-2 shrink-0">
          {isLive ? (
            <span className="text-[10px] font-mono tabular-nums text-cyan-400 animate-pulse">
              {elapsed}s
            </span>
          ) : task.durationSec !== undefined ? (
            <span className="text-[10px] font-mono tabular-nums text-slate-500">
              {task.durationSec.toFixed(1)}s
            </span>
          ) : null}

          {/* Agent Icon */}
          <span className="text-slate-500 text-[10px] select-none">⚡</span>

          {/* Inspect Button */}
          <button
            type="button"
            onClick={() => onInspect(task)}
            className="p-1 rounded text-slate-500 hover:text-slate-200 hover:bg-white/[0.06] transition-colors cursor-pointer"
            title="Inspect subagent execution details"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </button>
        </div>
      </div>

      {/* Line 2: Relayed Activity Ticker Reel */}
      {task.activity.length > 0 && (
        <div className="pl-5 min-w-0 max-w-full">
          <SubagentActivityTicker activity={task.activity} isLive={isLive} />
        </div>
      )}
    </div>
  );
}

// ── SUBAGENT DETAIL INSPECTION MODAL ─────────────────────────────────────────
function SubagentDetailModal({
  task,
  onClose,
  onOpenFile,
}: {
  task: SubagentProgressItem;
  onClose: () => void;
  onOpenFile?: (filePath: string, fileName?: string) => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl max-h-[85vh] rounded-2xl border border-white/[0.12] bg-[#060913] p-5 shadow-2xl overflow-y-auto custom-scrollbar flex flex-col gap-4 font-mono text-xs select-text"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Specular hairline */}
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent pointer-events-none" />

        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
          <div className="flex items-center gap-2.5 min-w-0">
            <StatusGlyph status={task.status} />
            <div className="min-w-0">
              <h3 className="font-semibold text-slate-100 text-sm truncate">{task.goal}</h3>
              <p className="text-[10.5px] text-slate-400">Subagent Mission #{task.taskId}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-white/[0.08] text-slate-400 hover:text-white transition-colors cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Mission Metadata */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
          <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
            <span className="text-slate-500 block text-[9.5px]">STATUS</span>
            <span className="font-medium text-slate-200 capitalize">{task.status}</span>
          </div>
          <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
            <span className="text-slate-500 block text-[9.5px]">MODEL</span>
            <span className="font-medium text-slate-200">{task.model || "Active Model"}</span>
          </div>
          <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
            <span className="text-slate-500 block text-[9.5px]">DURATION</span>
            <span className="font-medium text-slate-200 tabular-nums">
              {task.durationSec ? `${task.durationSec.toFixed(1)}s` : "Running"}
            </span>
          </div>
          <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
            <span className="text-slate-500 block text-[9.5px]">DEPTH</span>
            <span className="font-medium text-slate-200">{task.depth || 1}</span>
          </div>
        </div>

        {/* Executive Summary / Findings */}
        {(task.findings || task.summary) && (
          <div className="flex flex-col gap-1.5 p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
            <span className="text-[10px] uppercase tracking-wider text-cyan-400 font-bold">
              Executive Findings
            </span>
            <p className="font-sans text-[12px] leading-relaxed text-slate-200 whitespace-pre-wrap">
              {task.findings || task.summary}
            </p>
          </div>
        )}

        {/* Key Findings List */}
        {task.keyFindings && task.keyFindings.length > 0 && (
          <div className="flex flex-col gap-1.5 p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
            <span className="text-[10px] uppercase tracking-wider text-emerald-400 font-bold">
              Key Discoveries
            </span>
            <ul className="space-y-1 font-sans text-[11.5px] text-slate-300 list-disc list-inside">
              {task.keyFindings.map((finding, idx) => (
                <li key={idx} className="leading-snug">{finding}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Referenced Files */}
        {task.referencedFiles && task.referencedFiles.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">
              Referenced Files ({task.referencedFiles.length})
            </span>
            <div className="flex flex-wrap gap-1.5">
              {task.referencedFiles.map((file, idx) => {
                const fname = file.split(/[\/\\]/).pop() || file;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => onOpenFile?.(file, fname)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] text-cyan-300 hover:text-white transition-colors cursor-pointer text-[10.5px]"
                  >
                    <span>{fname}</span>
                    <span className="text-slate-500 text-[9px]">↗</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Complete Activity Steps Reel */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">
            Execution Log ({task.activity.length} steps)
          </span>
          <div className="max-h-48 overflow-y-auto custom-scrollbar rounded-lg border border-white/[0.06] bg-black/60 p-2.5 space-y-1">
            {task.activity.map((step, idx) => (
              <div key={idx} className="flex items-start gap-2 text-[10.5px] leading-relaxed text-slate-300">
                <span className="text-slate-600 select-none tabular-nums shrink-0">{idx + 1}.</span>
                <span className="font-mono whitespace-pre-wrap break-all">{step}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Error payload if any */}
        {task.error && (
          <div className="p-3 rounded-xl bg-rose-950/20 border border-rose-500/20 text-rose-300 text-[11px] leading-relaxed">
            <span className="font-bold block mb-0.5">Execution Error:</span>
            {task.error}
          </div>
        )}
      </div>
    </div>
  );
}

// ── MAIN EXPORT: SUBAGENT DELEGATION CARD ────────────────────────────────────
export interface SubagentCardProps {
  data: SubagentTaskData;
  onOpenFile?: (filePath: string, fileName?: string) => void;
}

export function SubagentCard({ data, onOpenFile }: SubagentCardProps) {
  const [selectedTask, setSelectedTask] = useState<SubagentProgressItem | null>(null);

  if (!data || !data.tasks || data.tasks.length === 0) return null;

  const total = data.tasks.length;
  const running = data.tasks.filter((t) => t.status === "running").length;
  const completed = data.tasks.filter((t) => t.status === "completed").length;
  const failed = data.tasks.filter((t) => t.status === "failed" || t.status === "timed_out").length;
  const isAllDone = running === 0;

  return (
    <div className="my-2 w-full max-w-full rounded-2xl border border-white/[0.08] bg-[#060913]/90 p-3 shadow-2xl backdrop-blur-2xl font-mono select-none">
      {/* Group Title Bar */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/[0.06] text-xs">
        <div className="flex items-center gap-2">
          <span className="p-1 rounded-md bg-cyan-500/10 border border-cyan-400/25 text-cyan-300">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </span>
          <span className="font-semibold text-slate-100 text-[12px] tracking-tight">
            Delegated Swarm
          </span>
          <span className="text-[10.5px] text-slate-500">
            ({completed}/{total} finished{running > 0 ? `, ${running} active` : ""}{failed > 0 ? `, ${failed} failed` : ""})
          </span>
        </div>

        {running > 0 && (
          <span className="flex items-center gap-1.5 text-[10.5px] text-cyan-400 font-mono">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping" />
            <span>Executing...</span>
          </span>
        )}
      </div>

      {/* Subagent Rows Grid (Compact Footprint: 2 lines per child) */}
      <div className="flex flex-col gap-2">
        {data.tasks.map((task) => (
          <SubagentRowView
            key={task.taskId || task.id}
            task={task}
            onInspect={(t) => setSelectedTask(t)}
          />
        ))}
      </div>

      {/* Modal Inspector when a task is clicked */}
      {selectedTask && (
        <SubagentDetailModal
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
          onOpenFile={onOpenFile}
        />
      )}
    </div>
  );
}

export default SubagentCard;
