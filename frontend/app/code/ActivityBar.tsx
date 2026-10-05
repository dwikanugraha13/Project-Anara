"use client";

import React from "react";
import Link from "next/link";
import type { GitStatusData } from "@/components/sidebar/types";

export interface ActivityBarProps {
  isLeftOpen: boolean;
  setIsLeftOpen: React.Dispatch<React.SetStateAction<boolean>>;
  explorerMode: "tree" | "git" | "sessions";
  setExplorerMode: React.Dispatch<React.SetStateAction<"tree" | "git" | "sessions">>;
  isTerminalOpen: boolean;
  setIsTerminalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  isRightOpen: boolean;
  setIsRightOpen: React.Dispatch<React.SetStateAction<boolean>>;
  gitStatus: GitStatusData | null;
  setIsBrainDrawerOpen: (v: boolean) => void;
}

/**
 * ActivityBar — Anara Code Studio primary vertical icon rail.
 * Provides quick 1-click toggling for File Explorer, Git Review, Terminal, Agent Console, and Brain.
 */
export function ActivityBar({
  isLeftOpen,
  setIsLeftOpen,
  explorerMode,
  setExplorerMode,
  isTerminalOpen,
  setIsTerminalOpen,
  isRightOpen,
  setIsRightOpen,
  gitStatus,
  setIsBrainDrawerOpen,
}: ActivityBarProps) {
  return (
    <aside className="w-11 shrink-0 h-full bg-[#050811] border-r border-white/[0.08] flex flex-col items-center py-2 z-20 select-none">
      {/* Top Activity Actions */}
      <div className="flex flex-col items-center gap-1.5 w-full">
        {/* Explorer Toggle */}
        <button
          type="button"
          onClick={() => {
            if (isLeftOpen && explorerMode === "tree") {
              setIsLeftOpen(false);
            } else {
              setIsLeftOpen(true);
              setExplorerMode("tree");
            }
          }}
          className={`relative w-8 h-8 rounded-lg flex items-center justify-center transition-all cursor-pointer ${
            isLeftOpen && explorerMode === "tree"
              ? "bg-white/[0.08] text-cyan-300 shadow-sm"
              : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
          }`}
          title="File Explorer (Toggle Sidebar)"
        >
          {isLeftOpen && explorerMode === "tree" && (
            <div className="absolute left-0 inset-y-1.5 w-0.5 bg-cyan-400 rounded-r shadow-[0_0_6px_rgba(34,211,238,0.8)]" />
          )}
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
        </button>

        {/* Sessions & Chat History Toggle */}
        <button
          type="button"
          onClick={() => {
            if (isLeftOpen && explorerMode === "sessions") {
              setIsLeftOpen(false);
            } else {
              setIsLeftOpen(true);
              setExplorerMode("sessions");
            }
          }}
          className={`relative w-8 h-8 rounded-lg flex items-center justify-center transition-all cursor-pointer ${
            isLeftOpen && explorerMode === "sessions"
              ? "bg-white/[0.08] text-cyan-300 shadow-sm"
              : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
          }`}
          title="Chat & Workspace Sessions (Toggle)"
        >
          {isLeftOpen && explorerMode === "sessions" && (
            <div className="absolute left-0 inset-y-1.5 w-0.5 bg-cyan-400 rounded-r shadow-[0_0_6px_rgba(34,211,238,0.8)]" />
          )}
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>

        {/* Source Control (Git) Toggle */}
        <button
          type="button"
          onClick={() => {
            if (isLeftOpen && explorerMode === "git") {
              setIsLeftOpen(false);
            } else {
              setIsLeftOpen(true);
              setExplorerMode("git");
            }
          }}
          className={`relative w-8 h-8 rounded-lg flex items-center justify-center transition-all cursor-pointer ${
            isLeftOpen && explorerMode === "git"
              ? "bg-white/[0.08] text-cyan-300 shadow-sm"
              : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
          }`}
          title={`Source Control (Git Changes${gitStatus?.changed_count ? `: ${gitStatus.changed_count} files` : ""})`}
        >
          {isLeftOpen && explorerMode === "git" && (
            <div className="absolute left-0 inset-y-1.5 w-0.5 bg-cyan-400 rounded-r shadow-[0_0_6px_rgba(34,211,238,0.8)]" />
          )}
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7a3 3 0 100-6 3 3 0 000 6zm0 0v10m0 0a3 3 0 100 6 3 3 0 000-6zm8-4a3 3 0 100-6 3 3 0 000 6zm0 0v3a4 4 0 01-4 4h-4" />
          </svg>
          {gitStatus && gitStatus.changed_count > 0 && (
            <span className="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-cyan-400 text-black font-mono font-bold text-[8.5px] flex items-center justify-center shadow-sm">
              {gitStatus.changed_count > 9 ? "9+" : gitStatus.changed_count}
            </span>
          )}
        </button>

        {/* Integrated Terminal Toggle */}
        <button
          type="button"
          onClick={() => setIsTerminalOpen((v) => !v)}
          className={`relative w-8 h-8 rounded-lg flex items-center justify-center transition-all cursor-pointer ${
            isTerminalOpen
              ? "bg-white/[0.08] text-cyan-300 shadow-sm"
              : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
          }`}
          title="Integrated Terminal (Toggle)"
        >
          {isTerminalOpen && (
            <div className="absolute left-0 inset-y-1.5 w-0.5 bg-cyan-400 rounded-r shadow-[0_0_6px_rgba(34,211,238,0.8)]" />
          )}
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </button>

        {/* Agent Console Toggle */}
        <button
          type="button"
          onClick={() => setIsRightOpen((v) => !v)}
          className={`relative w-8 h-8 rounded-lg flex items-center justify-center transition-all cursor-pointer ${
            isRightOpen
              ? "bg-white/[0.08] text-cyan-300 shadow-sm"
              : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
          }`}
          title="Anara Autonomous Agent Console"
        >
          {isRightOpen && (
            <div className="absolute left-0 inset-y-1.5 w-0.5 bg-cyan-400 rounded-r shadow-[0_0_6px_rgba(34,211,238,0.8)]" />
          )}
          <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </button>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom Activity Actions: 3D Avatar & Brain */}
      <div className="flex flex-col items-center gap-1.5 w-full pt-2 border-t border-white/[0.06]">
        <Link
          href="/"
          className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-cyan-300 hover:bg-white/[0.04] transition-all cursor-pointer"
          title="Switch to 3D Avatar & Voice Studio"
        >
          <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </Link>

        <button
          type="button"
          onClick={() => setIsBrainDrawerOpen(true)}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-purple-300 hover:bg-white/[0.04] transition-all cursor-pointer"
          title="Anara Brain & Model Settings"
        >
          <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
