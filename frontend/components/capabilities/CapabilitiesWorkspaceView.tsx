"use client";

import React, { useState, useEffect } from "react";
import BrainSkillsTab from "@/components/brain/agent/BrainSkillsTab";
import BrainToolsTab from "@/components/brain/agent/BrainToolsTab";
import BrainConnectorsTab from "@/components/brain/network/BrainConnectorsTab";
import BrainPluginsTab from "@/components/brain/agent/BrainPluginsTab";
import { BACKEND_URL } from "@/components/brain/types";

export type CapabilityTabId = "skills" | "tools" | "connectors" | "plugins";

export interface CapabilitiesWorkspaceViewProps {
  onClose?: () => void;
  initialTab?: CapabilityTabId;
}

export default function CapabilitiesWorkspaceView({
  onClose,
  initialTab = "skills",
}: CapabilitiesWorkspaceViewProps) {
  const [activeTab, setActiveTab] = useState<CapabilityTabId>(initialTab);
  const [skillsCount, setSkillsCount] = useState<number | null>(null);
  const [toolsCount, setToolsCount] = useState<number | null>(null);
  const [connectorsCount, setConnectorsCount] = useState<number | null>(null);
  const [pluginsCount, setPluginsCount] = useState<number | null>(null);

  useEffect(() => {
    // 1. Skills count
    fetch(`${BACKEND_URL}/api/brain/skills/v2`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setSkillsCount(Array.isArray(data) ? data.length : null))
      .catch(() => {});

    // 2. Tools count (desktop visible toolsets matching reference standard)
    fetch(`${BACKEND_URL}/api/brain/toolsets`)
      .then((r) => (r.ok ? r.json() : {}))
      .then((data: any) => {
        if (data && data.toolsets) {
          const desktopVisible = data.toolsets.filter(
            (ts: any) =>
              ![
                "messaging_telegram",
                "messaging_whatsapp",
                "messaging_discord",
                "messaging_slack",
                "custom_webhooks",
                "document_delivery",
              ].includes(ts.id)
          );
          setToolsCount(desktopVisible.length);
        }
      })
      .catch(() => {});

    // 3. Connectors count
    fetch(`${BACKEND_URL}/api/brain/connectors/catalog`)
      .then((r) => (r.ok ? r.json() : {}))
      .then((data: any) => {
        if (data && data.catalog) setConnectorsCount(data.catalog.length);
      })
      .catch(() => {});

    // 4. Plugins count
    fetch(`${BACKEND_URL}/api/brain/plugins`)
      .then((r) => (r.ok ? r.json() : {}))
      .then((data: any) => {
        if (data && data.plugins) setPluginsCount(data.plugins.length);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="flex-1 min-w-0 h-full flex flex-col overflow-hidden bg-[#060913] select-none font-sans relative">
      {/* ── Top Workspace Navigation Strip (1:1 Reference Standard) ── */}
      <header className="h-[38px] px-3 border-b border-white/[0.08] bg-[#070c18]/90 backdrop-blur-2xl flex items-center justify-between shrink-0 z-20">
        {/* Left Side: Segmented Tab Buttons */}
        <div className="flex items-center gap-0.5 p-0.5 rounded-md bg-black/40 border border-white/[0.08] text-[11px] font-mono">
          <button
            type="button"
            onClick={() => setActiveTab("skills")}
            className={`px-2.5 py-0.5 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "skills"
                ? "bg-white/[0.08] text-white font-semibold border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Skills</span>
            {skillsCount !== null && (
              <span className="text-[10px] text-slate-400 font-mono ml-0.5">{skillsCount}</span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("tools")}
            className={`px-2.5 py-0.5 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "tools"
                ? "bg-white/[0.08] text-white font-semibold border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Tools</span>
            {toolsCount !== null && (
              <span className="text-[10px] text-slate-400 font-mono ml-0.5">{toolsCount}</span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("connectors")}
            className={`px-2.5 py-0.5 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "connectors"
                ? "bg-white/[0.08] text-white font-semibold border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Connectors</span>
            {connectorsCount !== null && (
              <span className="text-[10px] text-slate-400 font-mono ml-0.5">{connectorsCount}</span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("plugins")}
            className={`px-2.5 py-0.5 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "plugins"
                ? "bg-white/[0.08] text-white font-semibold border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Plugins</span>
            {pluginsCount !== null && (
              <span className="text-[10px] text-slate-400 font-mono ml-0.5">{pluginsCount}</span>
            )}
          </button>
        </div>


      </header>

      {/* ── Main Tab Content Area (Full Bleed Master-Detail) ── */}
      <main className="flex-1 min-h-0 overflow-hidden relative">
        {activeTab === "skills" && (
          <div className="h-full w-full">
            <BrainSkillsTab />
          </div>
        )}
        {activeTab === "tools" && (
          <div className="h-full w-full">
            <BrainToolsTab />
          </div>
        )}
        {activeTab === "connectors" && (
          <div className="h-full w-full">
            <BrainConnectorsTab />
          </div>
        )}
        {activeTab === "plugins" && (
          <div className="h-full w-full">
            <BrainPluginsTab />
          </div>
        )}
      </main>
    </div>
  );
}