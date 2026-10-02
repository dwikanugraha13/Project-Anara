"use client";

import React from "react";
import type { ToolProgressPayload } from "@/hooks/useWebSocket";

export interface DockStatusStackProps {
  liveToolProgress?: ToolProgressPayload | null;
  onInterrupt: () => void;
}

/**
 * DockStatusStack — Live tool execution activity banner (Anara Engineering Standard).
 * Displays real-time tool state, summary, and quick interrupt controls.
 */
export function DockStatusStack({
  liveToolProgress,
  onInterrupt,
}: DockStatusStackProps) {
  if (!liveToolProgress) return null;

  return (
    <div className="w-full flex items-center justify-between px-3 py-1.5 rounded-xl border border-cyan-400/25 bg-[#030712]/95 backdrop-blur-2xl font-mono text-xs text-cyan-200 select-none animate-fade-in shadow-[0_4px_20px_rgba(0,0,0,0.6)]">
      <div className="flex items-center gap-2 min-w-0">
        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping shrink-0" />
        <span className="font-bold text-slate-100 text-[11px] shrink-0">&gt; executing</span>
        <span className="text-cyan-300 font-semibold truncate text-[11.5px]">
          {liveToolProgress.toolName}
        </span>
        {liveToolProgress.summary && (
          <span className="text-slate-400 truncate text-[11px]">
            {liveToolProgress.summary}
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={onInterrupt}
        className="px-2 py-0.5 rounded-md text-[10.5px] font-mono text-rose-300 hover:text-white bg-rose-500/15 hover:bg-rose-500/30 border border-rose-400/30 transition-all cursor-pointer shrink-0 ml-2 active:scale-95"
        title="Interrupt tool execution"
      >
        Stop
      </button>
    </div>
  );
}
