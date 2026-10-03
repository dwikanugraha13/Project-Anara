"use client";

import React, { Children, type ReactNode } from "react";

export interface ToolRunTickerProps {
  children?: ReactNode;
  activeItemText?: string;
  totalCount?: number;
  isRunning?: boolean;
  durationText?: string;
}

/**
 * ToolRunTicker.tsx — Anara Flat Hairline Single-Line Activity Ticker
 *
 * Provides a sleek single-line viewport over a growing list of tool executions.
 * Each new action ticks smoothly in place with status pulses, preventing multiple tool runs
 * from taking excessive vertical space in the transcript while preserving full auditability.
 */
export function ToolRunTicker({
  children,
  activeItemText,
  totalCount = 0,
  isRunning = false,
  durationText,
}: ToolRunTickerProps) {
  const rows = Children.toArray(children);
  const displayCount = totalCount || rows.length;

  return (
    <div className="my-1 w-full max-w-full select-none font-mono text-xs">
      <div className="flex items-center justify-between rounded-lg border border-white/[0.08] bg-[#060913]/80 px-3 py-1.5 backdrop-blur-md transition-all hover:border-white/15 shadow-lg">
        <div className="flex min-w-0 items-center gap-2.5 flex-1">
          <span className="relative flex h-2 w-2 shrink-0">
            {isRunning ? (
              <>
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
              </>
            ) : (
              <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400/80" />
            )}
          </span>

          <div className="relative min-h-[22px] h-[22px] flex items-center overflow-hidden min-w-0 flex-1">
            <div className="flex items-center text-[11.5px] font-medium tracking-tight text-slate-300 transition-transform duration-200">
              <span className={`truncate ${isRunning ? "text-cyan-300" : "text-slate-300"}`}>
                {activeItemText || (rows.length > 0 ? rows[rows.length - 1] : "Executing tool actions...")}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 ml-2">
          {durationText && (
            <span className="text-[10px] text-slate-500 font-mono tabular-nums">
              {durationText}
            </span>
          )}
          {displayCount > 1 && (
            <span className="rounded bg-white/[0.06] border border-white/[0.06] px-1.5 py-0.5 text-[9.5px] font-mono text-slate-400">
              {displayCount} steps
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default ToolRunTicker;
