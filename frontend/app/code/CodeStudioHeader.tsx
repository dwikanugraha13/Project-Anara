"use client";

import React from "react";
import Link from "next/link";
import SegmentedStudioTabs from "@/components/sidebar/SegmentedStudioTabs";
import type { WorkspaceTreeData, GitStatusData } from "@/components/sidebar/types";

export interface CodeStudioHeaderProps {
  workspaceTree: WorkspaceTreeData | null;
  gitStatus: GitStatusData | null;
  activeSession: any;
  activeSessionId: number | null;
  sessions: any[];
  sessionsLoading?: boolean;
  isSessionDropdownOpen: boolean;
  setIsSessionDropdownOpen: React.Dispatch<React.SetStateAction<boolean>>;
  sessionDropdownRef: React.RefObject<HTMLDivElement | null>;
  handleSelectSession: (id: number) => void;
  handleNewSession: () => void;
  isLeftOpen?: boolean;
  setIsLeftOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  isTerminalOpen?: boolean;
  setIsTerminalOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  isRightOpen?: boolean;
  setIsRightOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  setIsBrainDrawerOpen: (v: boolean) => void;
}

/**
 * CodeStudioHeader — Studio top navigation bar with project breadcrumbs,
 * session selector popover, view toggles, 3D Studio link, and Brain settings button.
 */
export function CodeStudioHeader({
  workspaceTree,
  gitStatus,
  activeSession,
  activeSessionId,
  sessions,
  sessionsLoading = false,
  isSessionDropdownOpen,
  setIsSessionDropdownOpen,
  sessionDropdownRef,
  handleSelectSession,
  handleNewSession,
  isLeftOpen,
  setIsLeftOpen,
  isTerminalOpen,
  setIsTerminalOpen,
  isRightOpen,
  setIsRightOpen,
  setIsBrainDrawerOpen,
}: CodeStudioHeaderProps) {
  return (
    <header className="h-[38px] shrink-0 px-3 border-b border-white/[0.08] flex items-center justify-between bg-[#060913]/95 backdrop-blur-2xl z-30 select-none shadow-[0_4px_24px_rgba(0,0,0,0.5)] relative">
      <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-cyan-400/25 to-transparent pointer-events-none" />

      {/* Left Side: Segmented Switcher [SESSIONS | CODE | BOTS] & Session Popover */}
      <div className="flex items-center gap-2.5 min-w-0">
        <SegmentedStudioTabs
          activeTab="code"
          activeSessionId={activeSessionId}
          onOpenBrain={() => setIsBrainDrawerOpen(true)}
        />

        {/* Optional Workspace / Git Branch Badge (if workspace is attached) */}
        {workspaceTree?.is_custom_folder && workspaceTree?.workspace_name && (
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-400/25 text-cyan-300 font-semibold tracking-tight flex items-center gap-1.5 shrink-0">
            <span>{workspaceTree.workspace_name}</span>
            {gitStatus?.is_git && gitStatus?.branch && (
              <>
                <span className="text-slate-500">·</span>
                <span className="text-slate-300 font-normal">{gitStatus.branch}</span>
              </>
            )}
          </span>
        )}

        <div className="h-3.5 w-px bg-white/10 shrink-0 mx-0.5" />

        {/* Session Selector Popover */}
        <div className="relative" ref={sessionDropdownRef as any}>
          {(() => {
            const cachedTitle = typeof window !== "undefined" ? localStorage.getItem("anara_active_session_title") || "" : "";
            const displayTitle = activeSession?.title || (activeSessionId ? cachedTitle || `Session #${activeSessionId}` : (sessionsLoading ? "Loading..." : "New Session"));
            return (
              <button
                type="button"
                onClick={() => setIsSessionDropdownOpen((v) => !v)}
                className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.08] hover:border-cyan-400/30 text-xs font-mono text-slate-200 hover:text-white transition-all cursor-pointer shadow-sm active:scale-95"
                title="Select or switch coding workspace session"
              >
                <svg className="w-3.5 h-3.5 text-cyan-400/80 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <span className="font-medium text-white truncate max-w-[150px]">
                  {displayTitle}
                </span>
                <svg className={`w-3 h-3 text-slate-400 transition-transform duration-150 ${isSessionDropdownOpen ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            );
          })()}

          {isSessionDropdownOpen && (
            <div className="absolute left-0 top-full mt-1.5 w-64 max-h-80 overflow-y-auto custom-scrollbar rounded-xl bg-[#060913]/95 backdrop-blur-2xl border border-white/15 shadow-2xl z-50 p-1.5 select-none font-mono animate-fade-in">
              <div className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-white/10 flex items-center justify-between">
                <span>Workspace Sessions</span>
                <span>{sessions.length} sessions</span>
              </div>

              <div className="py-1 space-y-0.5">
                {sessions.length === 0 ? (
                  <div className="p-3 text-center text-xs text-slate-500">No sessions yet</div>
                ) : (
                  sessions.map((s) => {
                    const isCur = s.id === activeSessionId;
                    return (
                      <div
                        key={s.id}
                        onClick={() => {
                          handleSelectSession(s.id);
                          setIsSessionDropdownOpen(false);
                        }}
                        className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
                          isCur
                            ? "bg-cyan-500/20 text-cyan-200 font-semibold border border-cyan-400/30"
                            : "hover:bg-white/[0.06] text-slate-300 hover:text-white"
                        }`}
                      >
                        <span className="truncate flex-1">{s.title || `Session #${s.id}`}</span>
                        <span className="text-[10px] text-slate-500 ml-2 shrink-0">
                          {s.message_count}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>

              <div className="pt-1 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => {
                    handleNewSession();
                    setIsSessionDropdownOpen(false);
                  }}
                  className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-xs font-semibold text-cyan-300 hover:text-white transition-colors cursor-pointer"
                >
                  <span>+ New Session</span>
                </button>
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={handleNewSession}
          className="flex items-center gap-1 px-2 py-1 rounded-md bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/25 hover:border-cyan-400/40 text-xs font-mono text-cyan-300 hover:text-cyan-100 transition-all cursor-pointer shadow-sm active:scale-95"
          title="Create new coding workspace session"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>New</span>
        </button>
      </div>
    </header>
  );
}
