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

      {/* Left Side: Segmented Switcher [SESSIONS | CODE | BOTS] */}
      <div className="flex items-center gap-2.5 min-w-0">
        <SegmentedStudioTabs
          activeTab="code"
          activeSessionId={activeSessionId}
          onOpenBrain={() => setIsBrainDrawerOpen(true)}
        />
      </div>
    </header>
  );
}
