"use client";

import React, { useState, useEffect, useRef } from "react";
import { SubagentProgressItem, SubagentTaskData, SubagentStatus } from "../hud/types";
import { SCAFFOLD_GLYPH_CLASS } from "./ScaffoldRow";
import { DisclosureCaret } from "./DisclosureCaret";

// ── FORMAT STOPWATCH TIME ───────────────────────────────────────────────────
function formatElapsed(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
}

// ── STATUS GLYPH ─────────────────────────────────────────────────────────────
function StatusGlyph({ status }: { status: SubagentStatus }) {
  if (status === "running") {
    return (
      <span className="relative flex h-3.5 w-3.5 shrink-0 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
      </span>
    );
  }

  if (status === "failed" || status === "timed_out") {
    return (
      <svg className="w-3.5 h-3.5 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" strokeWidth={2} />
        <line x1="12" y1="8" x2="12" y2="12" strokeWidth={2} strokeLinecap="round" />
        <line x1="12" y1="16" x2="12.01" y2="16" strokeWidth={2} strokeLinecap="round" />
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

// ── AGENT ICON GLYPH (Codicon Agent Standard, Zero Emojis) ───────────────────
function AgentIconGlyph({ className = "w-3 h-3 text-slate-500" }: { className?: string }) {
  return (
    <svg className={`shrink-0 ${className}`} fill="currentColor" viewBox="0 0 16 16">
      <path d="M8 1a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM6 6a2 2 0 0 0-2 2v3h1V8a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3h1V8a2 2 0 0 0-2-2H6z" />
      <path d="M2.5 13a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5z" />
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
                isLive && idx === activeIdx ? "text-slate-200 font-medium" : "text-slate-500"
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

// ── SUBAGENT ROW VIEW (Compact 2-Line Footprint + In-Place Accordion) ───────
function SubagentRowView({
  task,
  onOpenFile,
}: {
  task: SubagentProgressItem;
  onOpenFile?: (filePath: string, fileName?: string) => void;
}) {
  const isLive = task.status === "running";
  const [open, setOpen] = useState(false);
  const [elapsed, setElapsed] = useState<number>(0);
  const startRef = useRef<number>(task.startedAt || Date.now());

  useEffect(() => {
    if (!isLive) return;
    const timer = setInterval(() => {
      setElapsed(Math.max(0, Math.round((Date.now() - startRef.current) / 1000)));
    }, 1000);
    return () => clearInterval(timer);
  }, [isLive]);

  const durationText = isLive
    ? formatElapsed(elapsed)
    : task.durationSec !== undefined
    ? formatElapsed(task.durationSec)
    : "";

  return (
    <div className="grid min-w-0 max-w-full gap-0.5 rounded-xl border border-white/[0.08] bg-white/[0.02] p-2.5 transition-all">
      {/* Line 1: Goal line (Scaffolded header) */}
      <div className="flex min-w-0 max-w-full items-center gap-1.5 font-mono text-xs select-none" data-conversation-scaffold="">
        <span className={SCAFFOLD_GLYPH_CLASS}>
          <StatusGlyph status={task.status} />
        </span>

        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="min-w-0 flex-1 truncate text-left font-medium text-slate-200 hover:text-white transition-colors cursor-pointer text-[11.5px]"
          title={task.goal}
        >
          {task.goal}
        </button>

        {task.model && (
          <span className="hidden sm:inline-flex px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.06] text-[10px] text-slate-300 font-mono shrink-0">
            {task.model}
          </span>
        )}

        {/* Live Elapsed Stopwatch / Settled Duration */}
        {durationText && (
          <span className="text-[10px] font-mono tabular-nums text-slate-400 shrink-0 ml-1">
            {durationText}
          </span>
        )}

        {/* Clean Agent Icon (Zero Emojis) */}
        <AgentIconGlyph className="w-3 h-3 text-slate-500 shrink-0 ml-1" />

        {/* In-place Accordion Caret */}
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="p-1 rounded text-slate-500 hover:text-slate-200 transition-colors cursor-pointer shrink-0"
          title={open ? "Collapse steps" : "Expand steps"}
        >
          <DisclosureCaret open={open} size={11} />
        </button>
      </div>

      {/* Line 2: Relayed Activity Ticker Reel (shown when closed or running) */}
      {task.activity.length > 0 && !open && (
        <div className="min-w-0 max-w-full pl-5">
          <SubagentActivityTicker activity={task.activity} isLive={isLive} />
        </div>
      )}

      {/* Expanded In-Place Drawer (Matching Reference Specification) */}
      {open && (
        <div className="mt-2 pl-5 pt-2 border-t border-white/[0.06] flex flex-col gap-2 font-mono text-xs">
          {/* Key Findings List if completed */}
          {task.keyFindings && task.keyFindings.length > 0 && (
            <div className="flex flex-col gap-1 p-2 rounded-lg bg-white/[0.02] border border-white/[0.06]">
              <span className="text-[10px] uppercase tracking-wider text-emerald-400 font-semibold">
                Key Findings
              </span>
              <ul className="space-y-0.5 font-sans text-[11px] text-slate-300 list-disc list-inside">
                {task.keyFindings.map((finding, idx) => (
                  <li key={idx} className="leading-snug">{finding}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Referenced Files with Link */}
          {task.referencedFiles && task.referencedFiles.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="text-[9.5px] uppercase tracking-wider text-slate-400 font-semibold">
                Referenced Files ({task.referencedFiles.length})
              </span>
              <div className="flex flex-wrap gap-1">
                {task.referencedFiles.map((file, idx) => {
                  const fname = file.split(/[\/\\]/).pop() || file;
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => onOpenFile?.(file, fname)}
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] text-slate-200 hover:text-white transition-colors cursor-pointer text-[10px]"
                    >
                      <span>{fname}</span>
                      <span className="text-slate-500 text-[9px]">↗</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Detailed In-Place Steps / Tool Calls */}
          <div className="flex flex-col gap-1">
            <span className="text-[9.5px] uppercase tracking-wider text-slate-400 font-semibold">
              Execution Trace ({task.activity.length} actions)
            </span>
            <div className="max-h-48 overflow-y-auto rounded-lg border border-white/[0.06] bg-black/40 p-2 space-y-1">
              {task.activity.map((step, idx) => (
                <div key={idx} className="flex items-start gap-1.5 text-[10.5px] leading-relaxed text-slate-300">
                  <span className="text-slate-600 select-none tabular-nums shrink-0">{idx + 1}.</span>
                  <span className="font-mono whitespace-pre-wrap break-all text-slate-300">{step}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Error notice if failed */}
          {task.error && (
            <div className="p-2 rounded-lg bg-rose-950/20 border border-rose-500/20 text-rose-300 text-[10.5px]">
              <span className="font-semibold block mb-0.5">Error:</span>
              {task.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── MAIN EXPORT: SUBAGENT DELEGATION CARD ────────────────────────────────────
export interface SubagentCardProps {
  data: SubagentTaskData;
  onOpenFile?: (filePath: string, fileName?: string) => void;
}

export function SubagentCard({ data, onOpenFile }: SubagentCardProps) {
  const [isOpen, setIsOpen] = useState(true);

  if (!data || !data.tasks || data.tasks.length === 0) return null;

  const total = data.tasks.length;
  const running = data.tasks.filter((t) => t.status === "running").length;
  const completed = data.tasks.filter((t) => t.status === "completed").length;
  const failed = data.tasks.filter((t) => t.status === "failed" || t.status === "timed_out").length;

  return (
    <div className="my-2 w-full max-w-full font-mono select-none" data-delegate-card="">
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
            ({completed}/{total} finished{running > 0 ? `, ${running} active` : ""}{failed > 0 ? `, ${failed} failed` : ""})
          </span>
        </button>

        {running > 0 && (
          <span className="flex items-center gap-1.5 text-[10px] text-slate-400 font-mono">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping" />
            <span>Executing...</span>
          </span>
        )}
      </div>

      {/* Subagent Rows (Compact Footprint: 2 lines per child) */}
      {isOpen && (
        <div className="flex flex-col gap-1.5">
          {data.tasks.map((task) => (
            <SubagentRowView
              key={task.taskId || task.id}
              task={task}
              onOpenFile={onOpenFile}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default SubagentCard;
