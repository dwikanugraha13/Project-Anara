"use client";

import React, { Children, type ReactNode } from "react";

export interface ToolRunTickerProps {
  children: ReactNode;
  activeItemText?: string;
  totalCount?: number;
  isRunning?: boolean;
}

/**
 * ToolRunTicker.tsx — Anara Flat Hairline Single-Line Activity Ticker
 *
 * Provides a sleek 26px single-line viewport over a growing list of tool executions.
 * Each new action ticks smoothly in place with status pulses, preventing multiple tool runs
 * from taking excessive vertical space in the transcript while preserving full auditability.
 */
export function ToolRunTicker({
  children,
  activeItemText,
  totalCount = 0,
  isRunning = false,
}: ToolRunTickerProps) {
  const rows = Children.toArray(children);
  const displayCount = totalCount || rows.length;

  return (
    <div className="my-1 w-full max-w-2xl select-none font-mono text-xs">
      <div className="flex items-center justify-between rounded-lg border border-white/[0.08] bg-black/40 px-3 py-1.5 backdrop-blur-md transition-all hover:border-white/15">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="relative flex h-2 w-2 shrink-0">
            {isRunning ? (
              <>
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
              </>
            ) : (
              <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400/80" />
            )}
          </span>

          <div className="relative h-4 overflow-hidden min-w-0">
            <div className="flex items-center text-[11px] font-medium tracking-tight text-slate-300 transition-transform duration-200">
              <span className="truncate">
                {activeItemText || (rows.length > 0 ? rows[rows.length - 1] : "Executing tool actions...")}
              </span>
            </div>
          </div>
        </div>

        {displayCount > 1 && (
          <span className="ml-2 shrink-0 rounded bg-white/[0.06] px-1.5 py-0.5 text-[9.5px] font-mono text-slate-400">
            {displayCount} steps
          </span>
        )}
      </div>
    </div>
  );
}

export default ToolRunTicker;
