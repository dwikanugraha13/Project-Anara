"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";

export interface SegmentedStudioTabsProps {
  activeTab: "sessions" | "code" | "bots";
  activeSessionId?: number | null;
  onOpenBrain?: () => void;
  onSelectSessions?: () => void;
  className?: string;
}

/**
 * SegmentedStudioTabs — Unified connected segmented control for switching
 * between Chat Sessions, Code Studio, and Bot settings with a smooth sliding pill.
 */
export function SegmentedStudioTabs({
  activeTab: initialActiveTab,
  activeSessionId,
  onOpenBrain,
  onSelectSessions,
  className = "",
}: SegmentedStudioTabsProps) {
  const router = useRouter();
  const [currentTab, setCurrentTab] = useState<"sessions" | "code" | "bots">(initialActiveTab);

  // Exact pre-warmed geometry to prevent layout shift on frame 0
  const initialLeft = initialActiveTab === "sessions" ? 2 : initialActiveTab === "code" ? 82 : 148;
  const initialWidth = initialActiveTab === "sessions" ? 78 : initialActiveTab === "code" ? 64 : 52;
  const [indicatorStyle, setIndicatorStyle] = useState({ left: initialLeft, width: initialWidth, opacity: 1 });

  const sessionsRef = useRef<HTMLButtonElement | null>(null);
  const codeRef = useRef<HTMLButtonElement | null>(null);
  const botsRef = useRef<HTMLButtonElement | null>(null);

  const updateIndicator = useCallback((tab: "sessions" | "code" | "bots") => {
    let el: HTMLButtonElement | null = null;
    if (tab === "sessions") el = sessionsRef.current;
    else if (tab === "code") el = codeRef.current;
    else if (tab === "bots") el = botsRef.current;

    if (el) {
      setIndicatorStyle({
        left: el.offsetLeft,
        width: el.offsetWidth,
        opacity: 1,
      });
    }
  }, []);

  useEffect(() => {
    setCurrentTab(initialActiveTab);
    updateIndicator(initialActiveTab);
  }, [initialActiveTab, updateIndicator]);

  useEffect(() => {
    const timer = setTimeout(() => updateIndicator(currentTab), 40);
    const handleResize = () => updateIndicator(currentTab);
    window.addEventListener("resize", handleResize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", handleResize);
    };
  }, [currentTab, updateIndicator]);

  const handleTabClick = (tab: "sessions" | "code" | "bots") => {
    if (tab === currentTab && tab !== "bots") return;
    setCurrentTab(tab);
    updateIndicator(tab);

    if (tab === "sessions") {
      if (initialActiveTab === "sessions") {
        onSelectSessions?.();
      } else {
        const target = activeSessionId ? `/?session_id=${activeSessionId}` : "/";
        setTimeout(() => router.push(target), 140);
      }
    } else if (tab === "code") {
      if (initialActiveTab === "code") {
        // already on code studio
      } else {
        const target = activeSessionId ? `/code?session_id=${activeSessionId}` : "/code";
        setTimeout(() => router.push(target), 140);
      }
    } else if (tab === "bots") {
      onOpenBrain?.();
      setTimeout(() => {
        setCurrentTab(initialActiveTab);
        updateIndicator(initialActiveTab);
      }, 300);
    }
  };

  return (
    <div className={`relative flex items-center p-0.5 rounded-lg bg-white/[0.04] border border-white/[0.08] backdrop-blur-md font-mono text-xs select-none shrink-0 ${className}`}>
      {/* Sliding Pill Indicator */}
      <div
        className="absolute top-0.5 bottom-0.5 rounded-[6px] bg-gradient-to-r from-cyan-500/20 via-blue-500/15 to-cyan-500/20 border border-cyan-400/35 shadow-[0_0_12px_rgba(34,211,238,0.2)] transition-all duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] pointer-events-none"
        style={{
          left: `${indicatorStyle.left}px`,
          width: `${indicatorStyle.width}px`,
          opacity: indicatorStyle.opacity,
        }}
      />

      {/* SESSIONS */}
      <button
        ref={sessionsRef}
        type="button"
        onClick={() => handleTabClick("sessions")}
        className={`relative z-10 px-2.5 py-1 text-[11px] font-semibold tracking-wider transition-colors duration-200 cursor-pointer flex items-center gap-1.5 ${
          currentTab === "sessions" ? "text-white font-bold" : "text-slate-400 hover:text-slate-200"
        }`}
        title="Chat & 3D Companion Studio"
      >
        <span>SESSIONS</span>
      </button>

      {/* CODE */}
      <button
        ref={codeRef}
        type="button"
        onClick={() => handleTabClick("code")}
        className={`relative z-10 px-2.5 py-1 text-[11px] font-semibold tracking-wider transition-colors duration-200 cursor-pointer flex items-center gap-1.5 ${
          currentTab === "code" ? "text-cyan-300 font-bold" : "text-slate-400 hover:text-cyan-300"
        }`}
        title="Switch to Anara Code Studio"
      >
        <svg className="w-3 h-3 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>
        <span>CODE</span>
      </button>

      {/* BOTS */}
      <button
        ref={botsRef}
        type="button"
        onClick={() => handleTabClick("bots")}
        className={`relative z-10 px-2.5 py-1 text-[11px] font-semibold tracking-wider transition-colors duration-200 cursor-pointer flex items-center gap-1.5 ${
          currentTab === "bots" ? "text-white font-bold" : "text-slate-400 hover:text-slate-200"
        }`}
        title="Bot Profiles & Models"
      >
        <span>BOTS</span>
      </button>
    </div>
  );
}

export default SegmentedStudioTabs;
