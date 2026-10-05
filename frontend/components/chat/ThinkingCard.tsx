"use client";

import React, { useState, useRef, useEffect } from "react";
import { ScaffoldRow, SCAFFOLD_LABEL_CLASS, SCAFFOLD_META_CLASS } from "./ScaffoldRow";

// ── THINKING CARD (Quiet Scaffolding Disclosure Standard) ────────────────────
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
  const scrollRef = useRef<HTMLDivElement>(null);

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

  // Auto-scroll reasoning preview on incoming tokens while live
  useEffect(() => {
    if (!isLive || !isExpanded || !scrollRef.current) return;
    const el = scrollRef.current;
    el.scrollTop = el.scrollHeight;
  }, [text, isLive, isExpanded]);

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
    <div
      className="group/scaffold relative flex flex-col w-full my-1 select-none font-mono text-[11px] text-slate-400"
      data-conversation-scaffold=""
      data-slot="aui_thinking-disclosure"
    >
      <ScaffoldRow
        open={isExpanded}
        onToggle={() => setIsExpanded(!isExpanded)}
        trailing={
          isLive && liveElapsed > 0 ? (
            <span className={SCAFFOLD_META_CLASS}>{liveElapsed}s</span>
          ) : undefined
        }
      >
        <span className={`${SCAFFOLD_LABEL_CLASS} ${isLive ? "text-slate-200 animate-pulse font-medium" : ""}`}>
          {thoughtLabel}
        </span>
      </ScaffoldRow>

      {/* Flush reasoning body without left border or indent */}
      {isExpanded && (
        <div
          ref={scrollRef}
          className="mt-0.5 w-full min-w-0 max-w-full overflow-y-auto max-h-48 pt-0.5 pb-1 text-slate-300 font-sans text-xs leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere] break-words select-text custom-scrollbar animate-fade-in"
          data-slot="aui_thinking-body"
        >
          {text}
        </div>
      )}
    </div>
  );
}
