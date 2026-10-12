"use client";

import React, { useState, useRef, useEffect } from "react";
import { ScaffoldRow, SCAFFOLD_LABEL_CLASS, SCAFFOLD_META_CLASS, SCAFFOLD_GLYPH_CLASS } from "./ScaffoldRow";

// ── THINKING CARD (Hermes Desktop Parity Scaffolding Disclosure) ──────────────
export function ThinkingCard({
  text,
  durationSec,
  isLive = false,
}: {
  text?: string | null;
  durationSec?: number;
  isLive?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [userToggled, setUserToggled] = useState(false);
  const [liveElapsed, setLiveElapsed] = useState<number>(0);
  const liveStartTimeRef = useRef<number>(Date.now());
  const scrollRef = useRef<HTMLDivElement>(null);
  const followingRef = useRef<boolean>(true);
  const prevIsLiveRef = useRef<boolean>(isLive);

  // When live, start timer
  useEffect(() => {
    if (!isLive) return;
    liveStartTimeRef.current = Date.now();
    const interval = setInterval(() => {
      setLiveElapsed(Math.round((Date.now() - liveStartTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [isLive]);

  // When isLive transitions from true -> false (thinking finishes & reply starts):
  // Collapse disclosure automatically so user focus transitions directly to the streaming reply!
  useEffect(() => {
    if (prevIsLiveRef.current && !isLive) {
      if (!userToggled) {
        setIsExpanded(false);
      }
    }
    prevIsLiveRef.current = isLive;
  }, [isLive, userToggled]);

  // Auto-scroll reasoning preview on incoming tokens while live (disengages when user scrolls up)
  useEffect(() => {
    if (!isLive || !isExpanded || !scrollRef.current) return;
    const el = scrollRef.current;
    if (followingRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [text, isLive, isExpanded]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    followingRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
  };

  const hasContent = Boolean(text && text.trim().length > 0);
  if (!hasContent && !isLive) return null;

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

  const handleToggle = hasContent
    ? () => {
        setUserToggled(true);
        setIsExpanded(!isExpanded);
      }
    : undefined;

  return (
    <div
      className="group/scaffold relative flex flex-col w-full my-1 select-none font-mono text-[11px] text-slate-400"
      data-conversation-scaffold=""
      data-slot="aui_thinking-disclosure"
    >
      <ScaffoldRow
        open={isExpanded}
        onToggle={handleToggle}
        trailing={
          isLive && liveElapsed > 0 ? (
            <span className={SCAFFOLD_META_CLASS}>{liveElapsed}s</span>
          ) : undefined
        }
      >
        <span className={SCAFFOLD_GLYPH_CLASS}>
          {isLive ? (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
            </span>
          ) : (
            <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
          )}
        </span>
        <span className={`${SCAFFOLD_LABEL_CLASS} ${isLive ? "shimmer font-medium" : ""}`}>
          {thoughtLabel}
        </span>
      </ScaffoldRow>

      {/* Flush reasoning body without left border or indent */}
      {isExpanded && hasContent && (
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="mt-0.5 w-full min-w-0 max-w-full overflow-y-auto max-h-48 pt-0.5 pb-1 text-slate-300 font-sans text-xs leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere] break-words select-text custom-scrollbar animate-fade-in"
          data-slot="aui_thinking-body"
        >
          {text}
        </div>
      )}
    </div>
  );
}
