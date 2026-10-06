"use client";

import React from "react";
import BrainIntegrationsTab from "@/components/brain/network/BrainIntegrationsTab";

export interface MessagingWorkspaceViewProps {
  onClose?: () => void;
}

export default function MessagingWorkspaceView({ onClose }: MessagingWorkspaceViewProps) {
  return (
    <div className="flex-1 min-w-0 h-full flex flex-col overflow-hidden bg-[#060913] select-none font-sans relative">
      {/* ── Top Workspace Header ── */}
      <header className="h-[44px] px-4 border-b border-white/[0.08] bg-[#070c18]/90 backdrop-blur-2xl flex items-center justify-between shrink-0 z-20">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
            <h3 className="text-xs sm:text-sm font-semibold text-white font-mono tracking-tight">
              Messaging Channels &amp; Omnichannel Media
            </h3>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300 hidden sm:inline">
            Telegram · WhatsApp · Google · CLI
          </span>
        </div>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-mono text-slate-300 hover:text-white transition-all cursor-pointer"
            title="Return to Chat Conversation"
          >
            <span>Back to Chat</span>
            <span className="text-slate-500 font-bold">✕</span>
          </button>
        )}
      </header>

      {/* ── Main View Content ── */}
      <main className="flex-1 min-h-0 overflow-y-auto p-6 select-text custom-scrollbar">
        <div className="max-w-5xl mx-auto">
          <BrainIntegrationsTab />
        </div>
      </main>
    </div>
  );
}
