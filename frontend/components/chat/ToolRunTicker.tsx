"use client";

import React, { Children, type ReactNode } from "react";

export interface ToolRunTickerProps {
  children?: ReactNode;
  activeItemText?: string;
  totalCount?: number;
  isRunning?: boolean;
  durationText?: string;
  inline?: boolean;
}

/**
 * ToolRunTicker.tsx — Anara Hairline Dynamic Reel Activity Ticker
 *
 * Provides a sleek single-line viewport over a sequence of tool actions.
 * Employs CSS translateY reel transitions (240ms cubic-bezier) so new tool operations
 * smoothly slide up into view in place, preventing multi-tool runs from flooding the chat.
 */
export function ToolRunTicker({
  children,
  activeItemText,
  totalCount = 0,
  isRunning = false,
  durationText,
  inline = false,
}: ToolRunTickerProps) {
  const rows = Children.toArray(children);
  const displayCount = totalCount || rows.length;
  const activeIdx = Math.max(0, rows.length - 1);

  if (inline) {
    return (
      <div className="h-[20px] overflow-hidden select-none font-mono text-[11px] [isolation:isolate] [overflow:clip]">
        <div
          className="transition-transform duration-[240ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{
            transform: `translateY(calc(${activeIdx} * 20px * -1))`,
          }}
        >
          {rows.map((row, idx) => (
            <div key={idx} className="h-[20px] flex items-center min-w-0 overflow-hidden">
              <span className={`truncate ${isRunning && idx === activeIdx ? "text-slate-200 font-medium" : "text-slate-400"}`}>
                {row}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }

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

          <div className="relative min-h-[22px] h-[22px] overflow-hidden min-w-0 flex-1 [isolation:isolate] [overflow:clip]">
            <div
              className="transition-transform duration-[240ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
              style={{
                transform: `translateY(calc(${activeIdx} * 22px * -1))`,
              }}
            >
              {rows.length > 0 ? (
                rows.map((row, idx) => (
                  <div key={idx} className="h-[22px] flex items-center min-w-0 overflow-hidden">
                    <span className={`truncate text-[11.5px] font-medium tracking-tight ${
                      isRunning && idx === activeIdx ? "text-slate-100" : "text-slate-300"
                    }`}>
                      {row}
                    </span>
                  </div>
                ))
              ) : (
                <div className="h-[22px] flex items-center min-w-0 overflow-hidden">
                  <span className="truncate text-[11.5px] font-medium tracking-tight text-slate-400">
                    {activeItemText || "Executing tool actions..."}
                  </span>
                </div>
              )}
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
