"use client";

import React, { useMemo } from "react";

export interface ContextUsageData {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  contextLimit?: number;
  contextRemaining?: number;
  modelId?: string;
  source?: "actual" | "estimated";
}

export interface ContextUsagePopoverProps {
  isOpen: boolean;
  onClose: () => void;
  usage?: ContextUsageData | null;
}

function formatTokens(n: number): string {
  if (!n || isNaN(n)) return "0";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${n}`;
}

export default function ContextUsagePopover({
  isOpen,
  onClose,
  usage,
}: ContextUsagePopoverProps) {
  if (!isOpen) return null;

  const total = usage?.totalTokens || (usage?.promptTokens || 0) + (usage?.completionTokens || 0);
  const max = usage?.contextLimit || 1_000_000;
  const percent = Math.min(100, Math.max(0, Math.round((total / max) * 100)));

  // Segmented breakdown categories
  const categories = useMemo(() => {
    const prompt = usage?.promptTokens || 0;
    const completion = usage?.completionTokens || 0;
    
    // Estimates based on prompt composition
    const sysPrompt = Math.round(prompt * 0.35);
    const tools = Math.round(prompt * 0.25);
    const history = Math.max(0, prompt - sysPrompt - tools);

    return [
      { id: "sys", label: "Agent Core & System", tokens: sysPrompt, color: "#22d3ee" }, // Cyan
      { id: "tools", label: "Active Tools Schema", tokens: tools, color: "#818cf8" },  // Indigo
      { id: "history", label: "Conversation History", tokens: history, color: "#34d399" }, // Emerald
      { id: "gen", label: "Generation Output", tokens: completion, color: "#fbbf24" },  // Amber
    ];
  }, [usage]);

  const segmentTotal = categories.reduce((sum, c) => sum + c.tokens, 0) || total || 1;

  return (
    <div className="fixed inset-0 z-50 pointer-events-auto" onClick={onClose}>
      <div
        className="absolute bottom-8 right-6 w-80 p-3.5 rounded-xl bg-[#060913]/95 backdrop-blur-2xl border border-white/15 shadow-[0_20px_50px_rgba(0,0,0,0.85)] text-xs font-mono text-slate-200 select-none animate-in fade-in zoom-in-95 duration-100"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-2 border-b border-white/[0.08]">
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                percent >= 90
                  ? "bg-rose-500 shadow-[0_0_8px_#f43f5e]"
                  : percent >= 80
                  ? "bg-amber-400 shadow-[0_0_8px_#fbbf24]"
                  : "bg-cyan-400 shadow-[0_0_8px_#22d3ee]"
              }`}
            />
            <span className="font-semibold text-white">Context Window</span>
          </div>
          <span className={`text-[11px] ${percent >= 90 ? "text-rose-400 font-bold" : percent >= 80 ? "text-amber-300" : "text-slate-400"}`}>
            {formatTokens(total)} / {formatTokens(max)} ({percent}%)
          </span>
        </div>

        {/* Model ID & Source */}
        <div className="flex items-center justify-between py-2 text-[10.5px] text-slate-400">
          <span className="truncate max-w-[180px]">{usage?.modelId || "Current Model"}</span>
          <span className="px-1.5 py-0.5 rounded bg-white/[0.04] text-[9.5px] uppercase tracking-wider text-slate-400">
            {usage?.source === "actual" ? "Actual (API)" : "Estimated"}
          </span>
        </div>

        {/* Segmented Progress Meter */}
        <div className="h-1.5 w-full bg-white/[0.05] rounded-full overflow-hidden flex my-1">
          {categories.map((c) => {
            const widthPct = Math.max(1, (c.tokens / segmentTotal) * 100);
            return (
              <span
                key={c.id}
                style={{ width: `${widthPct}%`, backgroundColor: c.color }}
                className="h-full transition-all duration-300"
                title={`${c.label}: ${formatTokens(c.tokens)}`}
              />
            );
          })}
        </div>

        {/* Detailed Category Rows */}
        <div className="mt-2.5 space-y-1.5 text-[11px]">
          {categories.map((c) => (
            <div key={c.id} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: c.color }} />
                <span className="text-slate-300">{c.label}</span>
              </div>
              <span className="text-slate-400 font-mono">~{formatTokens(c.tokens)}</span>
            </div>
          ))}
        </div>

        {/* High Context Threshold Warning Banner */}
        {percent >= 85 && (
          <div className="mt-2.5 p-2 rounded-lg bg-rose-500/10 border border-rose-500/25 text-[10px] text-rose-300 flex items-center gap-1.5 animate-fade-in">
            <svg className="w-3.5 h-3.5 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span><strong>Context Near Limit:</strong> Next turns will automatically compact conversation history to preserve memory.</span>
          </div>
        )}

        {/* Footer Hint */}
        <div className="mt-3 pt-2 border-t border-white/[0.08] text-[9.5px] text-slate-500 text-center">
          Auto-compacts when context exceeds 85% budget
        </div>
      </div>
    </div>
  );
}
