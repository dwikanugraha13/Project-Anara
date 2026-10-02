"use client";

import React, { useState, useEffect, useRef } from "react";
import ContextUsagePopover, { ContextUsageData } from "./ContextUsagePopover";

export interface AgentStatusBarProps {
  isConnected: boolean;
  activeSessionId?: number | string | null;
  gitStatus?: {
    is_git: boolean;
    branch?: string;
    changed_count: number;
    insertions?: number;
    deletions?: number;
  } | null;
  onOpenGitReview?: () => void;
  tokenUsage?: ContextUsageData | null;
  assistantStatus?: "idle" | "listening" | "thinking" | "speaking";
  activeModelId?: string;
  reasoningEffort?: string;
  onToggleTerminal?: () => void;
  isTerminalOpen?: boolean;
  subagentsCount?: number;
}

function formatTokens(n: number): string {
  if (!n || isNaN(n)) return "0";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${n}`;
}

export default function AgentStatusBar({
  isConnected,
  activeSessionId,
  gitStatus,
  onOpenGitReview,
  tokenUsage,
  assistantStatus = "idle",
  activeModelId = "anara-agent",
  reasoningEffort,
  onToggleTerminal,
  isTerminalOpen = false,
  subagentsCount = 0,
}: AgentStatusBarProps) {
  const [isContextPopoverOpen, setIsContextPopoverOpen] = useState(false);
  const [turnElapsedSec, setTurnElapsedSec] = useState<number | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const isGenerating = assistantStatus === "thinking" || assistantStatus === "speaking";

  // Live Turn Duration Timer
  useEffect(() => {
    if (isGenerating) {
      const startTime = Date.now();
      setTurnElapsedSec(0);
      timerRef.current = setInterval(() => {
        setTurnElapsedSec(Math.floor((Date.now() - startTime) / 1000));
      }, 500);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setTurnElapsedSec(null);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isGenerating]);

  const totalTokens = tokenUsage?.totalTokens || (tokenUsage?.promptTokens || 0) + (tokenUsage?.completionTokens || 0);
  const maxTokens = tokenUsage?.contextLimit || 1_000_000;
  const contextPct = Math.min(100, Math.max(0, Math.round((totalTokens / maxTokens) * 100)));

  const cleanModelName = (activeModelId || "anara").split("/").pop() || "anara";

  return (
    <>
      <footer className="h-[24px] shrink-0 px-3 bg-[#080A0F] border-t border-white/[0.08] flex items-center justify-between font-mono text-[10.5px] text-slate-400 select-none z-20">
        {/* ── Left Zone: Drawer, Gateway Status, Workspace Folder, Git, Subagents ── */}
        <div className="flex items-center gap-2.5 min-w-0">
          {/* Drawer / Pane Toggle Glyph */}
          <button
            type="button"
            className="hover:text-white transition-colors cursor-pointer text-slate-500 hover:text-slate-300"
            title="Toggle sidebar drawer"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 6h16M4 12h16M4 18h7" />
            </svg>
          </button>

          {/* Gateway Status Pill */}
          <div className="flex items-center gap-1.5" title={isConnected ? "Gateway Connected" : "Connecting to Gateway"}>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isConnected ? "bg-emerald-400 shadow-[0_0_6px_#34d399]" : "bg-rose-400 animate-pulse"
              }`}
            />
            <span className="text-slate-300 text-[10.5px]">
              {isConnected ? "Local Gateway" : "Gateway unavailable"}
            </span>
          </div>

          <span className="text-slate-700">|</span>

          {/* Workspace Root Directory Badge */}
          <div className="flex items-center gap-1 text-slate-300 text-[10.5px]">
            <svg className="w-3 h-3 text-amber-400/90 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <span className="font-semibold text-slate-200">Project Anara</span>
          </div>

          {/* Git Branch & Churn Badge */}
          {gitStatus?.is_git && (
            <>
              <span className="text-slate-700">|</span>
              <button
                type="button"
                onClick={onOpenGitReview}
                className="flex items-center gap-1 text-[10.5px] text-slate-300 hover:text-cyan-300 transition-colors cursor-pointer"
                title="Open Git Review Panel"
              >
                <svg className="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7a3 3 0 100-6 3 3 0 000 6zm0 0v10m0 0a3 3 0 100 6 3 3 0 000-6zm8-4a3 3 0 100-6 3 3 0 000 6zm0 0v3a4 4 0 01-4 4h-4" />
                </svg>
                <span className="font-semibold">{gitStatus.branch || "main"}</span>
                {gitStatus.changed_count > 0 && (
                  <span className="px-1 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 text-[9px]">
                    {gitStatus.changed_count}
                  </span>
                )}
                {(gitStatus.insertions !== undefined || gitStatus.deletions !== undefined) && (
                  <span className="text-[9px] flex items-center gap-0.5 ml-0.5 tabular-nums">
                    {gitStatus.insertions ? <span className="text-emerald-400">+{gitStatus.insertions}</span> : null}
                    {gitStatus.deletions ? <span className="text-rose-400">-{gitStatus.deletions}</span> : null}
                  </span>
                )}
              </button>
            </>
          )}

          {/* Subagents Swarm Badge */}
          {subagentsCount > 0 && (
            <>
              <span className="text-slate-700">|</span>
              <div className="flex items-center gap-1 text-[10.5px] text-violet-300">
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
                <span>{subagentsCount} subagents</span>
              </div>
            </>
          )}
        </div>

        {/* ── Right Zone: Context Gauge, Timer, Model Pill, Terminal ── */}
        <div className="flex items-center gap-2.5 shrink-0">
          {/* Live Turn Elapsed Timer */}
          {turnElapsedSec !== null && (
            <div className="flex items-center gap-1 text-[10.5px] text-amber-300 font-semibold px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-400/25 animate-pulse">
              <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>{turnElapsedSec}s</span>
            </div>
          )}

          {/* Context Token Usage Gauge */}
          <button
            type="button"
            onClick={() => setIsContextPopoverOpen((v) => !v)}
            className="flex items-center gap-1.5 px-2 py-0.5 rounded hover:bg-white/10 transition-colors text-[10.5px] text-slate-300 cursor-pointer"
            title="Click to view Context Window breakdown"
          >
            <span className="w-10 h-1.5 bg-white/10 rounded-full overflow-hidden flex">
              <span
                style={{ width: `${Math.max(4, contextPct)}%` }}
                className={`h-full ${
                  contextPct > 80 ? "bg-rose-400" : contextPct > 60 ? "bg-amber-400" : "bg-cyan-400"
                }`}
              />
            </span>
            <span className="text-[10px] tabular-nums">
              {formatTokens(totalTokens)} ({contextPct}%)
            </span>
          </button>

          <span className="text-slate-700">|</span>

          {/* Mode Indicator */}
          <div className="flex items-center gap-1 text-[10.5px] text-slate-300">
            <span className="text-amber-400">⚡</span>
            <span className="font-medium text-slate-200">Smart</span>
          </div>

          <span className="text-slate-700">|</span>

          {/* Active Model & Reasoning Effort */}
          <div className="flex items-center gap-1 text-[10.5px] text-slate-300">
            <span className="text-white font-medium capitalize">{cleanModelName}</span>
            {reasoningEffort && reasoningEffort !== "off" && (
              <span className="text-[9.5px] px-1 py-0.2 rounded bg-violet-500/20 text-violet-300 border border-violet-400/30 font-semibold uppercase">
                {reasoningEffort}
              </span>
            )}
          </div>

          <span className="text-slate-700">|</span>

          {/* Build Version String */}
          <span className="text-[10px] text-slate-500 font-mono">
            # v0.21.5+5778
          </span>

          {/* Terminal Toggle Button */}
          {onToggleTerminal && (
            <>
              <span className="text-slate-700">|</span>
              <button
                type="button"
                onClick={onToggleTerminal}
                className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] transition-colors cursor-pointer ${
                  isTerminalOpen
                    ? "bg-cyan-500/20 text-cyan-300 font-semibold"
                    : "text-slate-400 hover:text-white hover:bg-white/10"
                }`}
                title="Toggle Terminal Panel (Ctrl+`)"
              >
                <span>Terminal</span>
                <span className="text-[9px] text-slate-500 font-mono">Ctrl+`</span>
              </button>
            </>
          )}
        </div>
      </footer>

      {/* Context Breakdown Popover */}
      <ContextUsagePopover
        isOpen={isContextPopoverOpen}
        onClose={() => setIsContextPopoverOpen(false)}
        usage={tokenUsage}
      />
    </>
  );
}
