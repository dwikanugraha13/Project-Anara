"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { BACKEND_URL, FileMemorySnapshot } from "../types";

export default function BrainSoulTab() {
  const [activeTab, setActiveTab] = useState<"soul" | "user" | "memory">("soul");
  const [fileMemory, setFileMemory] = useState<FileMemorySnapshot>({
    soul: "",
    user: "",
    memory: "",
  });
  const savedMemoryRef = useRef<FileMemorySnapshot>({
    soul: "",
    user: "",
    memory: "",
  });
  const [isSaving, setIsSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/brain/file-memory`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) {
          const loaded = {
            soul: d.soul || "",
            user: d.user || "",
            memory: d.memory || "",
          };
          setFileMemory(loaded);
          savedMemoryRef.current = { ...loaded };
        }
      })
      .catch(() => {});
  }, []);

  const handleSaveCurrentFile = useCallback(async () => {
    setIsSaving(true);
    setSaveMsg(null);
    try {
      if (activeTab === "soul") {
        const res = await fetch(`${BACKEND_URL}/api/agent/soul`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: fileMemory.soul }),
        });
        if (res.ok) {
          savedMemoryRef.current.soul = fileMemory.soul;
          setSaveMsg("✓ SOUL.md file saved & hot-reloaded successfully.");
        } else {
          setSaveMsg("Failed to save SOUL.md");
        }
      } else {
        const res = await fetch(`${BACKEND_URL}/api/brain/file-memory`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            file_type: activeTab,
            content: fileMemory[activeTab],
          }),
        });
        if (res.ok) {
          savedMemoryRef.current[activeTab] = fileMemory[activeTab];
          setSaveMsg(`✓ ${activeTab.toUpperCase()}.md saved successfully (sanitized).`);
        } else {
          setSaveMsg(`Failed to save ${activeTab.toUpperCase()}.md`);
        }
      }
      setTimeout(() => setSaveMsg(null), 4000);
    } catch (err: any) {
      setSaveMsg(`Error: ${err.message || String(err)}`);
    } finally {
      setIsSaving(false);
    }
  }, [activeTab, fileMemory]);

  // Global Ctrl+S / Cmd+S handler
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        handleSaveCurrentFile();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleSaveCurrentFile]);

  const currentContent = fileMemory[activeTab] || "";
  const isDirty = fileMemory[activeTab] !== savedMemoryRef.current[activeTab];

  const setCurrentContent = (val: string) => {
    setFileMemory((prev) => ({ ...prev, [activeTab]: val }));
  };

  const getFileBadge = () => {
    if (activeTab === "soul") return { label: "SOUL.md", desc: "Agent Identity, Personality & Core Directives (Global)", cap: "No limit", max: 0 };
    if (activeTab === "user") return { label: "USER.md", desc: "User Profile & Learned Preferences (Global)", cap: "~1,500 chars", max: 1500 };
    return { label: "MEMORY.md", desc: "Persistent Facts & Context Notes (Global)", cap: "~2,200 chars", max: 2200 };
  };

  const badge = getFileBadge();
  const isOverBudget = badge.max > 0 && currentContent.length > badge.max;

  return (
    <div className="flex flex-col h-full space-y-3 font-sans select-text">
      {/* Studio Action Toolbar (Single Flat Layer) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-white/[0.08]">
        {/* Segmented Glass File Switcher */}
        <div className="inline-flex p-0.5 rounded-lg bg-black/40 border border-white/[0.08] backdrop-blur-md font-mono text-xs">
          {(["soul", "user", "memory"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-all cursor-pointer ${
                activeTab === tab
                  ? "bg-white/[0.12] text-white shadow-sm border border-white/[0.12]"
                  : "text-slate-400 hover:text-slate-200 border border-transparent"
              }`}
            >
              {tab.toUpperCase()}.md
            </button>
          ))}
        </div>

        {/* Right: Unsaved status indicator & Save Action */}
        <div className="flex items-center gap-3 shrink-0">
          {saveMsg && (
            <span className="text-xs font-mono text-emerald-300 animate-fade-in">
              {saveMsg}
            </span>
          )}
          {isDirty && !saveMsg && (
            <span className="flex items-center gap-1.5 text-[11px] font-sans text-amber-400">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              Unsaved changes
            </span>
          )}
          <button
            type="button"
            onClick={handleSaveCurrentFile}
            disabled={isSaving || !isDirty}
            className="px-3.5 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-medium font-sans transition-all active:scale-95 disabled:opacity-40 disabled:pointer-events-none flex items-center gap-1.5 shadow-[0_0_12px_rgba(56,189,248,0.15)] cursor-pointer"
            title="Save directive (Ctrl+S / Cmd+S)"
          >
            {isSaving ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin text-cyan-300" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Saving...</span>
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span>Save Directive</span>
                <kbd className="hidden sm:inline px-1 py-0.5 rounded bg-black/40 text-[10px] font-mono border border-cyan-500/20 text-cyan-200">
                  Ctrl+S
                </kbd>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Studio Code Canvas with Glass Bevel */}
      <div className="flex-1 rounded-xl border border-white/[0.08] bg-[#050811]/90 shadow-[inset_0_1px_2px_rgba(0,0,0,0.8),inset_0_1px_0_rgba(255,255,255,0.06)] flex flex-col overflow-hidden min-h-[460px]">
        {/* Editor Sub-Header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-white/[0.06] bg-white/[0.015] text-[11px] font-mono select-none">
          <div className="flex items-center gap-2">
            <span className="text-white font-semibold">{badge.label}</span>
            <span className="text-slate-600">•</span>
            <span className="text-slate-400 font-sans text-xs">{badge.desc}</span>
          </div>

          {/* Discrete Capacity Meter */}
          <div className="flex items-center gap-2.5">
            {badge.max > 0 && (
              <div className="w-16 h-1.5 rounded-full bg-white/[0.08] overflow-hidden">
                <div
                  className={`h-full transition-all ${
                    isOverBudget ? "bg-rose-500" : "bg-cyan-400"
                  }`}
                  style={{ width: `${Math.min(100, (currentContent.length / badge.max) * 100)}%` }}
                />
              </div>
            )}
            <span className={`tabular-nums ${isOverBudget ? "text-rose-400 font-semibold" : "text-slate-400"}`}>
              {currentContent.length.toLocaleString()}{badge.max ? ` / ${badge.max.toLocaleString()}` : ""} chars
            </span>
          </div>
        </div>

        {/* Textarea Surface */}
        <div className="relative flex-1 flex">
          <textarea
            value={currentContent}
            onChange={(e) => setCurrentContent(e.target.value)}
            spellCheck={false}
            className="w-full h-full p-4 bg-transparent font-mono text-[13px] text-slate-100 leading-[1.65] resize-none focus:outline-none custom-scrollbar selection:bg-cyan-500/25 min-h-[380px]"
            placeholder={`# Enter ${badge.label} directives...`}
          />
        </div>

        {/* Micro-Telemetry Footer */}
        <div className="flex items-center justify-between px-4 py-1.5 border-t border-white/[0.05] bg-black/40 text-[10.5px] font-mono text-slate-500 select-none">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="font-sans">Sanitizer &amp; Secret Guard Armed</span>
          </div>
          <div className="flex items-center gap-3">
            <span>UTF-8</span>
            <span>Markdown</span>
            <span>{currentContent ? currentContent.split("\n").length : 0} lines</span>
          </div>
        </div>
      </div>
    </div>
  );
}
