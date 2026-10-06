"use client";

import React, { useState } from "react";
import BrainSkillsTab from "@/components/brain/agent/BrainSkillsTab";
import BrainToolsTab from "@/components/brain/agent/BrainToolsTab";
import BrainConnectorsTab from "@/components/brain/network/BrainConnectorsTab";
import BrainPluginsTab from "@/components/brain/agent/BrainPluginsTab";
import BrainProvidersTab from "@/components/brain/network/BrainProvidersTab";

export type CapabilityTabId = "skills" | "tools" | "connectors" | "plugins" | "providers";

export interface CapabilitiesWorkspaceViewProps {
  onClose?: () => void;
  initialTab?: CapabilityTabId;
}

export default function CapabilitiesWorkspaceView({
  onClose,
  initialTab = "skills",
}: CapabilitiesWorkspaceViewProps) {
  const [activeTab, setActiveTab] = useState<CapabilityTabId>(initialTab);

  return (
    <div className="flex-1 min-w-0 h-full flex flex-col overflow-hidden bg-[#060913] select-none font-sans relative">
      {/* ── Top Workspace Navigation Strip (1:1 Reference Standard) ── */}
      <header className="h-[42px] px-4 border-b border-white/[0.08] bg-[#070c18]/90 backdrop-blur-2xl flex items-center justify-between shrink-0 z-20">
        {/* Left Side: Segmented Tab Buttons */}
        <div className="flex items-center gap-1 p-0.5 rounded-lg bg-black/40 border border-white/[0.08] text-xs font-mono">
          <button
            type="button"
            onClick={() => setActiveTab("skills")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "skills"
                ? "bg-white/[0.08] text-white font-semibold border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Skills</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("tools")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "tools"
                ? "bg-white/[0.08] text-white font-semibold border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Tools</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("connectors")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "connectors"
                ? "bg-white/[0.08] text-white font-semibold border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Connectors</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("plugins")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "plugins"
                ? "bg-white/[0.08] text-white font-semibold border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Plugins</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("providers")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "providers"
                ? "bg-white/[0.08] text-white font-semibold border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Providers</span>
          </button>
        </div>

        {/* Right Side: Close to Chat Button */}
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

      {/* ── Main Workspace Body (Full-Bleed MasterDetail) ── */}
      <main className="flex-1 min-h-0 overflow-hidden relative">
        <div className={activeTab === "skills" ? "block h-full" : "hidden"}>
          <BrainSkillsTab />
        </div>
        <div className={activeTab === "tools" ? "block h-full" : "hidden"}>
          <BrainToolsTab />
        </div>
        <div className={activeTab === "connectors" ? "block h-full" : "hidden"}>
          <BrainConnectorsTab />
        </div>
        <div className={activeTab === "plugins" ? "block h-full" : "hidden"}>
          <BrainPluginsTab />
        </div>
        <div className={activeTab === "providers" ? "block h-full overflow-y-auto p-6 select-text custom-scrollbar" : "hidden"}>
          <BrainProvidersTab />
        </div>
      </main>
    </div>
  );
}
