"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  BACKEND_URL,
  BrainTabId,
  BrainStats,
  Speaker,
  AnaraBrainProps,
} from "./types";

import BrainSoulTab from "./agent/BrainSoulTab";
import BrainToolsTab from "./agent/BrainToolsTab";
import BrainSkillsTab from "./agent/BrainSkillsTab";
import BrainProvidersTab from "./network/BrainProvidersTab";
import BrainIntegrationsTab from "./network/BrainIntegrationsTab";

interface BrainNavTab {
  id: BrainTabId;
  label: string;
  icon: React.ReactNode;
  badge?: number;
}

const TAB_DESCRIPTIONS: Record<BrainTabId, { title: string; subtitle: string; category: string }> = {
  soul: {
    title: "Soul & Rules",
    subtitle: "Core directives, agent persona, user preferences, and persistent MEMORY.md",
    category: "Autonomous Agent",
  },
  tools: {
    title: "Tools & Automation",
    subtitle: "Execution instruments, autonomous task scheduler, and subagent swarms",
    category: "Autonomous Agent",
  },
  skills: {
    title: "Skills Catalog",
    subtitle: "Procedural workflows, custom capabilities, and extensible community hub",
    category: "Autonomous Agent",
  },
  providers: {
    title: "Providers & Keys",
    subtitle: "Dynamic multi-provider pool, model routing, and token telemetry",
    category: "AI Gateway & Network",
  },
  integrations: {
    title: "Integrations & Channels",
    subtitle: "Omnichannel gateways (Telegram, WhatsApp, CLI) and messaging channels",
    category: "AI Gateway & Network",
  },
};

export default function AnaraBrain({
  isOpen,
  onClose,
  onTriggerAnimation,
  activeSpeaker,
}: AnaraBrainProps) {
  const [activeTab, setActiveTab] = useState<BrainTabId>("soul");
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<BrainStats | null>(null);
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [isConnected, setIsConnected] = useState(true);
  const isMountedRef = useRef(true);

  const currentMeta = TAB_DESCRIPTIONS[activeTab] || TAB_DESCRIPTIONS.soul;

  const fetchBrainData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/overview`);
      if (res.ok && isMountedRef.current) {
        const data = await res.json();
        setStats(data.stats || null);
        setSpeakers(data.speakers || []);
        setIsConnected(true);
      } else if (isMountedRef.current) {
        setIsConnected(false);
      }
    } catch (err) {
      if (isMountedRef.current) setIsConnected(false);
      console.warn("[AnaraBrain] Overview fetch skipped or reconnecting:", err);
    } finally {
      if (isMountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchBrainData();
    }
  }, [isOpen, fetchBrainData]);

  // Live WebSocket Brain Synchronization
  useEffect(() => {
    const handleBrainSync = () => {
      if (!isOpen) return;
      fetchBrainData();
    };

    window.addEventListener("anara-brain-sync", handleBrainSync);
    return () => {
      window.removeEventListener("anara-brain-sync", handleBrainSync);
    };
  }, [isOpen, fetchBrainData]);

  // Escape key closes modal
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center p-3 sm:p-5 lg:p-6 bg-black/75 backdrop-blur-xl pointer-events-auto animate-fade-in select-none"
      onClick={onClose}
    >
      {/* Restrained Ambient Radial Sheen (Zero GPU Thrashing, Pure Obsidian) */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_0%,rgba(56,189,248,0.05),transparent_70%)] pointer-events-none" />

      {/* ── Main Framed Window (Liquid Glass Obsidian Studio) ── */}
      <div
        className="relative w-full h-full max-w-7xl max-h-[92vh] rounded-2xl border border-white/[0.10] bg-[#060913]/90 shadow-[0_24px_80px_rgba(0,0,0,0.9),inset_0_1px_0_rgba(255,255,255,0.10)] overflow-hidden flex flex-col md:flex-row pointer-events-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Specular Sheen Highlight */}
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/[0.15] to-transparent pointer-events-none z-20" />

        {/* ── SIDEBAR KIRI: Navigasi Terpusat ── */}
        <div className="w-full md:w-60 shrink-0 border-b md:border-b-0 md:border-r border-white/[0.08] bg-[#080d1a]/80 backdrop-blur-xl flex flex-col overflow-y-auto no-scrollbar p-3 space-y-4 select-none">
          {/* Section 1: AUTONOMOUS AGENT */}
          <div className="space-y-1">
            <span className="px-2.5 text-[11px] font-sans font-semibold tracking-wider text-slate-400 uppercase">
              Autonomous Agent
            </span>
            <div className="space-y-0.5 font-sans">
              {([
                {
                  id: "soul" as BrainTabId,
                  label: "Soul & Rules",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                  ),
                },
                {
                  id: "tools" as BrainTabId,
                  label: "Tools & Automation",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  ),
                },
                {
                  id: "skills" as BrainTabId,
                  label: "Skills Catalog",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  ),
                },
              ] as BrainNavTab[]).map((item) => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`w-full group relative flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium border transition-all cursor-pointer select-none ${
                      isActive
                        ? "bg-white/[0.08] text-white border-white/[0.12] shadow-[inset_0_1px_0_rgba(255,255,255,0.10)]"
                        : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]"
                    }`}
                  >
                    {isActive && (
                      <span className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r bg-cyan-400 shadow-[0_0_8px_rgba(56,189,248,0.8)]" />
                    )}
                    <div className="flex items-center gap-2.5 min-w-0 pl-1">
                      <span className={`transition-colors duration-150 ${isActive ? "text-cyan-300" : "text-slate-400 group-hover:text-slate-300"}`}>{item.icon}</span>
                      <span className="truncate">{item.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Section 2: AI GATEWAY & NETWORK */}
          <div className="space-y-1">
            <span className="px-2.5 text-[11px] font-sans font-semibold tracking-wider text-slate-400 uppercase">
              AI Gateway &amp; Network
            </span>
            <div className="space-y-0.5 font-sans">
              {[
                {
                  id: "providers" as BrainTabId,
                  label: "Providers & Keys",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  ),
                },
                {
                  id: "integrations" as BrainTabId,
                  label: "Integrations & Channels",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                  ),
                },
              ].map((item) => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`w-full group relative flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium border transition-all cursor-pointer select-none ${
                      isActive
                        ? "bg-white/[0.08] text-white border-white/[0.12] shadow-[inset_0_1px_0_rgba(255,255,255,0.10)]"
                        : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]"
                    }`}
                  >
                    {isActive && (
                      <span className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r bg-cyan-400 shadow-[0_0_8px_rgba(56,189,248,0.8)]" />
                    )}
                    <div className="flex items-center gap-2.5 min-w-0 pl-1">
                      <span className={`transition-colors duration-150 ${isActive ? "text-cyan-300" : "text-slate-400 group-hover:text-slate-300"}`}>{item.icon}</span>
                      <span className="truncate">{item.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Bottom Status Row */}
          <div className="mt-auto pt-3 border-t border-white/[0.06] flex items-center justify-between text-[10px] font-mono text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-emerald-400 shadow-[0_0_6px_#34d399]" : "bg-amber-400"}`} />
              <span>{isConnected ? "Core Engine Connected" : "Connecting..."}</span>
            </span>
            <span>{stats?.memories_count !== undefined ? `${stats.memories_count} nodes` : "v2.5"}</span>
          </div>
        </div>

        {/* ── RIGHT PANEL (ACTIVE CONTENT & REFINED HEADER) ── */}
        <div className="flex-1 min-w-0 flex flex-col h-full overflow-hidden bg-[#060913]/60">
          {/* Top minimal action bar with clear tab identity & status */}
          <div className="flex items-center justify-between gap-3 px-6 py-3 border-b border-white/[0.08] bg-[#070c18]/80 shrink-0 select-none">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="text-[10.5px] font-mono uppercase tracking-wider text-slate-500 hidden sm:inline">
                {currentMeta.category}
              </span>
              <span className="text-slate-600 hidden sm:inline">/</span>
              <h2 className="text-xs sm:text-sm font-semibold text-white tracking-tight truncate">
                {currentMeta.title}
              </h2>
              <span className="text-[11px] text-slate-400 truncate hidden md:inline font-sans">
                — {currentMeta.subtitle}
              </span>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={fetchBrainData}
                disabled={loading}
                className="px-2.5 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 hover:text-white text-xs font-mono flex items-center gap-1.5 cursor-pointer transition-all active:scale-95 disabled:opacity-50"
                title="Sync database & refresh"
              >
                <svg className={`w-3.5 h-3.5 text-cyan-400 ${loading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <span>Sync</span>
              </button>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-rose-500/20 text-slate-400 hover:text-rose-200 border border-white/[0.08] hover:border-rose-500/30 cursor-pointer transition-all active:scale-95"
                title="Close (Esc)"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Main Content Scrollable Viewport with Hardware Layer Isolation */}
          <div className="flex-1 overflow-y-auto p-5 sm:p-7 select-text custom-scrollbar [contain:content] [overscroll-behavior:contain] [transform:translateZ(0)]">
            <div className={activeTab === "soul" ? "block h-full" : "hidden"}>
              <BrainSoulTab />
            </div>
            <div className={activeTab === "tools" ? "block" : "hidden"}>
              <BrainToolsTab />
            </div>
            <div className={activeTab === "skills" ? "block" : "hidden"}>
              <BrainSkillsTab />
            </div>
            <div className={activeTab === "providers" ? "block" : "hidden"}>
              <BrainProvidersTab onRefreshAll={fetchBrainData} />
            </div>
            <div className={activeTab === "integrations" ? "block" : "hidden"}>
              <BrainIntegrationsTab onRefreshAll={fetchBrainData} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
