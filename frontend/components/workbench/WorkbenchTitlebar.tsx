"use client";

import React from "react";
import type { GitStatusData } from "../sidebar/types";

export interface WorkbenchTitlebarProps {
  activeIdeFile?: {
    isOpen: boolean;
    fileName: string;
    filePath: string;
  } | null;
  transcript: any[];
  activeSessionId: number | null;
  handleNewSession: () => void;
  setIsBrainDrawerOpen: (v: boolean) => void;
  isContextPaneOpen: boolean;
  setIsContextPaneOpen: React.Dispatch<React.SetStateAction<boolean>>;
  contextTab: "editor" | "terminal" | "review";
  setContextTab: (tab: "editor" | "terminal" | "review") => void;
  fetchGitStatus: () => void;
  gitStatus: GitStatusData | null;
  setIsTerminalOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

/**
 * WorkbenchTitlebar — Unified 38px titlebar band for dual-pane companion workbench.
 * Houses active session badge, quick actions, context pane toggle, git status, and window glyphs.
 */
export function WorkbenchTitlebar({
  activeIdeFile,
  transcript,
  activeSessionId,
  handleNewSession,
  setIsBrainDrawerOpen,
  isContextPaneOpen,
  setIsContextPaneOpen,
  contextTab,
  setContextTab,
  fetchGitStatus,
  gitStatus,
  setIsTerminalOpen,
}: WorkbenchTitlebarProps) {
  return (
    <div className="h-[38px] shrink-0 px-3 border-b border-white/[0.08] bg-[#080B11] flex items-center justify-between text-xs font-mono select-none z-10">
      {/* Left: Active Tab Badge with Status Dot + Plus New Tab */}
      <div className="flex items-center gap-2 text-slate-400 min-w-0">
        <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-white/[0.05] border border-white/[0.08] text-white font-semibold text-[11px] tracking-wider uppercase">
          <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
          <span className="truncate max-w-[260px]">
            {activeIdeFile && activeIdeFile.isOpen
              ? activeIdeFile.fileName
              : transcript.length > 0
              ? (transcript[0]?.text?.slice(0, 32) || `SESSION #${activeSessionId || "LIVE"}`)
              : `SESSION #${activeSessionId || "LIVE"}`}
          </span>
        </div>

        <button
          type="button"
          onClick={handleNewSession}
          className="p-1 rounded-md hover:bg-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer"
          title="New session"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {/* Right: Window & Tool Controls Cluster */}
      <div className="flex items-center gap-1.5 text-slate-400">
        {/* Settings & Brain */}
        <button
          type="button"
          onClick={() => setIsBrainDrawerOpen(true)}
          className="p-1.5 rounded-md hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
          title="Settings & Brain"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>

        {/* Split Pane */}
        <button
          type="button"
          onClick={() => setIsContextPaneOpen((v) => !v)}
          className={`p-1.5 rounded-md transition-colors cursor-pointer ${
            isContextPaneOpen ? "bg-cyan-500/20 text-cyan-300" : "hover:bg-white/10 hover:text-white"
          }`}
          title="Toggle Context Pane (Ctrl+\)"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
          </svg>
        </button>

        {/* Git Review */}
        <button
          type="button"
          onClick={() => {
            setIsContextPaneOpen(true);
            setContextTab("review");
            fetchGitStatus();
          }}
          className={`p-1.5 rounded-md transition-colors cursor-pointer flex items-center gap-1 ${
            isContextPaneOpen && contextTab === "review" ? "bg-cyan-500/20 text-cyan-300" : "hover:bg-white/10 hover:text-white"
          }`}
          title="Toggle Git Review Diff Panel"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7a3 3 0 100-6 3 3 0 000 6zm0 0v10m0 0a3 3 0 100 6 3 3 0 000-6zm8-4a3 3 0 100-6 3 3 0 000 6zm0 0v3a4 4 0 01-4 4h-4" />
          </svg>
          {gitStatus && gitStatus.changed_count > 0 && (
            <span className="text-[10px] font-mono font-bold text-cyan-300">
              {gitStatus.changed_count}
            </span>
          )}
        </button>

        {/* Terminal Toggle */}
        <button
          type="button"
          onClick={() => {
            setIsContextPaneOpen(true);
            setContextTab("terminal");
            setIsTerminalOpen((v) => !v);
          }}
          className={`p-1.5 rounded-md transition-colors cursor-pointer ${
            isContextPaneOpen && contextTab === "terminal" ? "bg-cyan-500/20 text-cyan-300" : "hover:bg-white/10 hover:text-white"
          }`}
          title="Toggle Terminal Panel (Ctrl+`)"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </button>

        <span className="text-slate-700 mx-0.5">|</span>

        {/* Window Action Glyphs */}
        <div className="flex items-center gap-1 text-slate-500">
          <span className="px-1 text-xs select-none" title="Minimize">—</span>
          <span className="px-1 text-xs select-none" title="Maximize">▢</span>
          <span className="px-1 text-xs select-none hover:text-rose-400" title="Close">✕</span>
        </div>
      </div>
    </div>
  );
}
