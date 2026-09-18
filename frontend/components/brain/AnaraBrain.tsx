"use client";

import React, { useState, useEffect, useCallback } from "react";
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

import BrainMemoriesTab from "./context/BrainMemoriesTab";
import BrainTodosTab from "./context/BrainTodosTab";
import BrainProjectsTab from "./context/BrainProjectsTab";
import BrainSpeakersTab from "./context/BrainSpeakersTab";

import BrainProvidersTab from "./network/BrainProvidersTab";
import BrainIntegrationsTab from "./network/BrainIntegrationsTab";

import BrainConversationsTab from "./system/BrainConversationsTab";
import BrainAnimationsTab from "./system/BrainAnimationsTab";

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

  const fetchBrainData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/overview`);
      if (res.ok) {
        const data = await res.json();
        setStats(data.stats || null);
        setSpeakers(data.speakers || []);
      }
    } catch (err) {
      console.warn("[AnaraBrain] Overview fetch skipped or reconnecting:", err);
    } finally {
      setLoading(false);
    }
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
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 lg:p-6 bg-black/65 backdrop-blur-md pointer-events-auto animate-fade-in select-none"
      onClick={onClose}
    >
      {/* ── Ambient Liquid Light Blobs ── */}
      <div className="absolute top-0 left-1/4 w-[560px] h-[560px] bg-cyan-500/[0.04] rounded-full blur-[160px] pointer-events-none animate-liquid-1 [transform:translateZ(0)] [will-change:transform]" />
      <div className="absolute bottom-0 right-1/5 w-[520px] h-[520px] bg-indigo-600/[0.06] rounded-full blur-[160px] pointer-events-none animate-liquid-2 [transform:translateZ(0)] [will-change:transform]" />
      <div className="absolute top-1/3 right-1/3 w-[380px] h-[380px] bg-purple-600/[0.03] rounded-full blur-[140px] pointer-events-none animate-liquid-3 [transform:translateZ(0)] [will-change:transform]" />

      {/* ── Main Framed Window ── */}
      <div
        className="relative w-full h-full max-w-7xl max-h-[92vh] rounded-2xl border border-white/10 bg-[#070c18] shadow-[0_20px_70px_rgba(0,0,0,0.85)] overflow-hidden flex flex-col md:flex-row pointer-events-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Specular Sheen Highlight */}
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent pointer-events-none z-20" />

        {/* ── SIDEBAR KIRI: 4 Pilar Navigasi ── */}
        <div className="w-full md:w-60 shrink-0 border-b md:border-b-0 md:border-r border-white/10 bg-slate-950/70 flex flex-col overflow-y-auto no-scrollbar p-3 space-y-4 select-none">
          {/* Section 1: AGEN OTONOM */}
          <div className="space-y-1">
            <span className="px-2.5 text-[10px] font-mono font-bold tracking-wider text-slate-500 uppercase">
              Agen Otonom
            </span>
            <div className="space-y-0.5 font-mono">
              {[
                {
                  id: "soul" as BrainTabId,
                  label: "Soul & Aturan",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                  ),
                },
                {
                  id: "tools" as BrainTabId,
                  label: "Katalog Alat",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  ),
                },
                {
                  id: "skills" as BrainTabId,
                  label: "Skills Anara",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  ),
                },
              ].map((item) => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium border transition-colors duration-150 ease-out cursor-pointer select-none ${
                      isActive
                        ? "bg-white/[0.12] text-white border-white/15 shadow-sm"
                        : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] hover:border-white/[0.06]"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className={`transition-colors duration-150 ${isActive ? "text-cyan-300" : "text-slate-400"}`}>{item.icon}</span>
                      <span className="truncate">{item.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Section 2: MEMORI & KONTEKS */}
          <div className="space-y-1">
            <span className="px-2.5 text-[10px] font-mono font-bold tracking-wider text-slate-500 uppercase">
              Memori &amp; Konteks
            </span>
            <div className="space-y-0.5 font-mono">
              {[
                {
                  id: "memories" as BrainTabId,
                  label: "Ingatan & Fakta",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                  ),
                },
                {
                  id: "todos" as BrainTabId,
                  label: "Catatan & Tugas",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                    </svg>
                  ),
                },
                {
                  id: "projects" as BrainTabId,
                  label: "Proyek Aktif",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                  ),
                },
                {
                  id: "speakers" as BrainTabId,
                  label: "Profil Pengguna",
                  badge: stats?.speakers_count,
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  ),
                },
              ].map((item) => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium border transition-colors duration-150 ease-out cursor-pointer select-none ${
                      isActive
                        ? "bg-white/[0.12] text-white border-white/15 shadow-sm"
                        : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] hover:border-white/[0.06]"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className={`transition-colors duration-150 ${isActive ? "text-cyan-300" : "text-slate-400"}`}>{item.icon}</span>
                      <span className="truncate">{item.label}</span>
                    </div>
                    {item.badge !== undefined && item.badge > 0 && (
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono transition-colors duration-150 ${isActive ? "bg-cyan-400/20 text-cyan-200" : "bg-white/[0.08] text-slate-400"}`}>
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Section 3: AI & JARINGAN */}
          <div className="space-y-1">
            <span className="px-2.5 text-[10px] font-mono font-bold tracking-wider text-slate-500 uppercase">
              AI &amp; Jaringan
            </span>
            <div className="space-y-0.5 font-mono">
              {[
                {
                  id: "providers" as BrainTabId,
                  label: "Providers & Token",
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  ),
                },
                {
                  id: "integrations" as BrainTabId,
                  label: "Koneksi Media",
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
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium border transition-colors duration-150 ease-out cursor-pointer select-none ${
                      isActive
                        ? "bg-white/[0.12] text-white border-white/15 shadow-sm"
                        : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] hover:border-white/[0.06]"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className={`transition-colors duration-150 ${isActive ? "text-cyan-300" : "text-slate-400"}`}>{item.icon}</span>
                      <span className="truncate">{item.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Section 4: AUDIT & SISTEM */}
          <div className="space-y-1">
            <span className="px-2.5 text-[10px] font-mono font-bold tracking-wider text-slate-500 uppercase">
              Audit &amp; Sistem
            </span>
            <div className="space-y-0.5 font-mono">
              {[
                {
                  id: "conversations" as BrainTabId,
                  label: "Log Percakapan",
                  badge: stats?.conversations_count,
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  ),
                },
                {
                  id: "animations" as BrainTabId,
                  label: "Animasi 3D Avatar",
                  badge: stats?.animations_count,
                  icon: (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  ),
                },
              ].map((item) => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium border transition-colors duration-150 ease-out cursor-pointer select-none ${
                      isActive
                        ? "bg-white/[0.12] text-white border-white/15 shadow-sm"
                        : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] hover:border-white/[0.06]"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className={`transition-colors duration-150 ${isActive ? "text-cyan-300" : "text-slate-400"}`}>{item.icon}</span>
                      <span className="truncate">{item.label}</span>
                    </div>
                    {item.badge !== undefined && item.badge > 0 && (
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono transition-colors duration-150 ${isActive ? "bg-cyan-400/20 text-cyan-200" : "bg-white/[0.08] text-slate-400"}`}>
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Bottom Status Row */}
          <div className="mt-auto pt-3 border-t border-white/5 flex items-center justify-between text-[10px] font-mono text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>SQLite Terhubung</span>
            </span>
            <span>v2.5</span>
          </div>
        </div>

        {/* ── PANEL KANAN (KONTEN AKTIF & HEADER MINIMALIS) ── */}
        <div className="flex-1 min-w-0 flex flex-col h-full overflow-hidden bg-slate-950/40">
          {/* Top minimal action bar */}
          <div className="flex items-center justify-end gap-2 px-6 py-3 border-b border-white/10 shrink-0 select-none">
            <button
              onClick={fetchBrainData}
              className="px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-slate-300 hover:text-white text-xs font-mono flex items-center gap-1.5 cursor-pointer transition-all active:scale-95"
              title="Sinkronkan database"
            >
              <svg className={`w-3.5 h-3.5 text-cyan-300 ${loading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Sinkronkan</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-xl bg-white/[0.04] hover:bg-rose-500/20 text-slate-400 hover:text-rose-200 border border-white/10 hover:border-rose-500/30 cursor-pointer transition-all active:scale-95"
              title="Tutup (Esc)"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Main Content Scrollable Viewport with Hardware Layer Isolation */}
          <div className="flex-1 overflow-y-auto p-5 sm:p-7 select-text custom-scrollbar [contain:content] [overscroll-behavior:contain] [transform:translateZ(0)]">
            {activeTab === "soul" && <BrainSoulTab />}
            {activeTab === "tools" && <BrainToolsTab />}
            {activeTab === "skills" && <BrainSkillsTab />}
            {activeTab === "memories" && (
              <BrainMemoriesTab
                activeSpeaker={activeSpeaker}
                speakers={speakers}
                onRefreshStats={fetchBrainData}
              />
            )}
            {activeTab === "todos" && (
              <BrainTodosTab
                activeSpeaker={activeSpeaker}
                onRefreshAll={fetchBrainData}
              />
            )}
            {activeTab === "projects" && (
              <BrainProjectsTab
                activeSpeaker={activeSpeaker}
                onRefreshAll={fetchBrainData}
              />
            )}
            {activeTab === "speakers" && (
              <BrainSpeakersTab
                activeSpeaker={activeSpeaker}
                onRefreshAll={fetchBrainData}
              />
            )}
            {activeTab === "providers" && <BrainProvidersTab onRefreshAll={fetchBrainData} />}
            {activeTab === "integrations" && <BrainIntegrationsTab onRefreshAll={fetchBrainData} />}
            {activeTab === "conversations" && (
              <BrainConversationsTab
                activeSpeaker={activeSpeaker}
                onRefreshAll={fetchBrainData}
              />
            )}
            {activeTab === "animations" && (
              <BrainAnimationsTab onTriggerAnimation={onTriggerAnimation} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
