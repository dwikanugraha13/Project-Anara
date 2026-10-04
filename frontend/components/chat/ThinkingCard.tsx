"use client";

import React, { useState, useRef, useEffect } from "react";

// ── THINKING CARD (Liquid Glass Reasoning Stream) ────────────────────────
export function ThinkingCard({
  text,
  durationSec,
  isLive = false,
}: {
  text: string;
  durationSec?: number;
  isLive?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(isLive);
  const [liveElapsed, setLiveElapsed] = useState<number>(0);
  const liveStartTimeRef = useRef<number>(Date.now());

  useEffect(() => {
    if (isLive) {
      setIsExpanded(true);
    }
  }, [isLive]);

  useEffect(() => {
    if (!isLive) return;
    liveStartTimeRef.current = Date.now();
    const interval = setInterval(() => {
      setLiveElapsed(Math.round((Date.now() - liveStartTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [isLive]);

  if (!text || text.trim().length === 0) return null;

  let thoughtLabel = "Thinking";
  if (!isLive) {
    if (durationSec === undefined || durationSec === null || durationSec <= 0) {
      thoughtLabel = "Thought";
    } else if (durationSec < 1) {
      thoughtLabel = "Thought briefly";
    } else {
      thoughtLabel = `Thought for ${durationSec.toFixed(1)}s`;
    }
  }

  return (
    <div className="group/scaffold relative flex flex-col w-full my-1 select-none font-mono opacity-[0.67] hover:opacity-100 transition-opacity duration-150">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-1.5 text-slate-400 hover:text-slate-200 focus-visible:outline-none transition-colors cursor-pointer group/btn py-0.5 max-w-fit"
          aria-expanded={isExpanded}
        >
          <span className="grid size-3.5 shrink-0 place-items-center">
            {isLive ? (
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
              </span>
            ) : (
              <span className="h-1.5 w-1.5 rounded-full bg-slate-500 group-hover/btn:bg-slate-300 transition-colors" />
            )}
          </span>

          <span className={`text-[11.5px] tracking-tight ${isLive ? "text-slate-200 animate-pulse font-medium" : "text-slate-400 group-hover/btn:text-slate-200"}`}>
            {thoughtLabel}
          </span>

          <svg
            className={`w-3 h-3 text-slate-500 opacity-0 group-hover/scaffold:opacity-80 transition-all duration-150 shrink-0 ml-0.5 ${
              isExpanded ? "rotate-90 opacity-80" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {isLive && liveElapsed > 0 && (
          <span className="text-[10px] font-mono tabular-nums text-slate-500 ml-auto">
            {liveElapsed.toFixed(1)}s
          </span>
        )}
      </div>

      {isExpanded && (
        <div className="mt-1 w-full min-w-0 max-w-full overflow-y-auto max-h-56 border-l border-white/[0.08] pl-3.5 py-1 text-slate-400 font-sans text-xs leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere] break-words select-text custom-scrollbar animate-fade-in">
          {text}
        </div>
      )}
    </div>
  );
}
