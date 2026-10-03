"use client";

import React from "react";
import Link from "next/link";
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
  isLeftOpen: boolean;
  setIsLeftOpen: React.Dispatch<React.SetStateAction<boolean>>;
  isTerminalOpen: boolean;
  setIsTerminalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  isRightOpen: boolean;
  setIsRightOpen: React.Dispatch<React.SetStateAction<boolean>>;
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
    <header className="h-[34px] shrink-0 px-3 border-b border-white/[0.08] flex items-center justify-between bg-[#060913]/95 backdrop-blur-2xl z-30 select-none shadow-[0_4px_24px_rgba(0,0,0,0.5)] relative">
      <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-cyan-400/25 to-transparent pointer-events-none" />

      {/* Left Side: Brand Logo, Workspace / Git Branch Badge, Session Switcher */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex items-center gap-2 shrink-0">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_10px_#22d3ee]" />
          <h1 className="text-xs font-bold font-mono text-white tracking-wider uppercase bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
            Anara Code
          </h1>
          {workspaceTree?.is_custom_folder && workspaceTree?.workspace_name ? (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-400/25 text-cyan-300 font-semibold tracking-tight flex items-center gap-1.5">
              <span>{workspaceTree.workspace_name}</span>
              {gitStatus?.is_git && gitStatus?.branch && (
                <>
                  <span className="text-slate-500">·</span>
                  <span className="text-slate-300 font-normal">{gitStatus.branch}</span>
                </>
              )}
            </span>
          ) : (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/10 text-slate-400 font-normal tracking-tight flex items-center gap-1.5">
              <span>No Workspace</span>
            </span>
          )}
        </div>

        <div className="h-3.5 w-px bg-white/10 shrink-0 mx-1" />

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

      {/* Right Side: View Toggles, 3D Companion Link, and Brain */}
      <div className="flex items-center gap-2 shrink-0">
        {/* View Toggles: Explorer, Terminal & Agent */}
        <div className="flex items-center p-0.5 rounded-md bg-white/[0.03] border border-white/[0.08] text-xs font-mono">
          <button
            type="button"
            onClick={() => setIsLeftOpen((v) => !v)}
            className={`flex items-center gap-1.5 px-2 py-0.5 rounded transition-all cursor-pointer ${
              isLeftOpen ? "bg-white/10 text-white font-medium shadow-sm" : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
            }`}
            title="Toggle File Explorer (Sidebar)"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <span className="hidden md:inline text-[11px]">Explorer</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setIsTerminalOpen((v) => {
                try {
                  localStorage.setItem("anara_studio_term_open", String(!v));
                  document.cookie = `anara_studio_term_open=${!v}; path=/; max-age=31536000; SameSite=Lax`;
                } catch {}
                return !v;
              });
            }}
            className={`flex items-center gap-1.5 px-2 py-0.5 rounded transition-all cursor-pointer ${
              isTerminalOpen ? "bg-white/10 text-white font-medium shadow-sm" : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
            }`}
            title="Toggle Integrated Terminal"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="hidden md:inline text-[11px]">Terminal</span>
          </button>
          <button
            type="button"
            onClick={() => setIsRightOpen((v) => !v)}
            className={`flex items-center gap-1.5 px-2 py-0.5 rounded transition-all cursor-pointer ${
              isRightOpen ? "bg-cyan-500/20 text-cyan-200 font-semibold border border-cyan-400/30 shadow-sm" : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
            }`}
            title="Toggle Anara Agent Console"
          >
            <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span className="hidden md:inline text-[11px]">Agent</span>
          </button>
        </div>

        {/* Connected Segmented Tab Control [SESSIONS | CODE | BOTS] with CODE active */}
        <div className="relative flex items-center p-0.5 rounded-lg bg-white/[0.04] border border-white/[0.08] backdrop-blur-md font-mono text-xs">
          <Link
            href={activeSessionId ? `/?session_id=${activeSessionId}` : "/"}
            className="relative z-10 px-2.5 py-1 text-[11px] font-semibold tracking-wider text-slate-400 hover:text-white transition-colors cursor-pointer"
            title="Switch to Chat & 3D Companion Studio"
          >
            SESSIONS
          </Link>

          <div
            className="relative z-10 px-2.5 py-1 text-[11px] font-bold tracking-wider text-cyan-300 rounded-[6px] bg-gradient-to-r from-cyan-500/20 via-blue-500/15 to-cyan-500/20 border border-cyan-400/35 shadow-[0_0_12px_rgba(34,211,238,0.2)] flex items-center gap-1.5"
            title="Active Coding Studio"
          >
            <svg className="w-3 h-3 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            <span>CODE</span>
          </div>

          <button
            type="button"
            onClick={() => setIsBrainDrawerOpen(true)}
            className="relative z-10 px-2.5 py-1 text-[11px] font-semibold tracking-wider text-slate-400 hover:text-white transition-colors cursor-pointer"
            title="Open Brain & Model Settings"
          >
            BOTS
          </button>
        </div>
      </div>
    </header>
  );
}
