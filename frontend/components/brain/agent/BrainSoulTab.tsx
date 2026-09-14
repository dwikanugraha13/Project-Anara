"use client";

import React, { useState, useEffect } from "react";
import { BACKEND_URL, FileMemorySnapshot } from "../types";

export default function BrainSoulTab() {
  const [activeTab, setActiveTab] = useState<"soul" | "user" | "memory">("soul");
  const [fileMemory, setFileMemory] = useState<FileMemorySnapshot>({
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
          setFileMemory({
            soul: d.soul || "",
            user: d.user || "",
            memory: d.memory || "",
          });
        }
      })
      .catch(() => {});
  }, []);

  const handleSaveCurrentFile = async () => {
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
          setSaveMsg("✓ Berkas SOUL.md berhasil disimpan & di-hot-reload.");
        } else {
          setSaveMsg("Gagal menyimpan SOUL.md");
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
          setSaveMsg(`✓ Berkas ${activeTab.toUpperCase()}.md berhasil disimpan (tersanitasi).`);
        } else {
          setSaveMsg(`Gagal menyimpan ${activeTab.toUpperCase()}.md`);
        }
      }
      setTimeout(() => setSaveMsg(null), 4000);
    } catch (err: any) {
      setSaveMsg(`Error: ${err.message || String(err)}`);
    } finally {
      setIsSaving(false);
    }
  };

  const currentContent = fileMemory[activeTab] || "";
  const setCurrentContent = (val: string) => {
    setFileMemory((prev) => ({ ...prev, [activeTab]: val }));
  };

  const getFileBadge = () => {
    if (activeTab === "soul") return { label: "SOUL.md", desc: "Identitas, Kepribadian & Filosofi Agen (Global)", cap: "Bebas" };
    if (activeTab === "user") return { label: "USER.md", desc: "Profil & Preferensi Pengguna (Cap ~1.500 char)", cap: "~1.500 char" };
    return { label: "MEMORY.md", desc: "Catatan Fakta & Konteks Persisten (Cap ~2.200 char)", cap: "~2.200 char" };
  };

  const badge = getFileBadge();

  return (
    <div className="space-y-4 font-sans select-text">
      {/* Header & File Selector Ribbon */}
      <div className="p-4 rounded-2xl liquid-glass border border-white/10 space-y-3">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white font-mono">Arsitektur Memori 4-File (PRD Standar)</h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-emerald-500/15 border border-emerald-400/30 text-emerald-300">
                ● Persistent Markdown
              </span>
            </div>
            <p className="text-xs text-slate-400">
              {badge.desc}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={handleSaveCurrentFile}
              disabled={isSaving}
              className="px-4 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/35 border border-cyan-400/50 text-cyan-200 hover:text-white text-xs font-semibold font-mono transition-all active:scale-95 cursor-pointer shadow-md flex items-center gap-1.5"
            >
              {isSaving ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin text-cyan-300" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Menyimpan...</span>
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>Simpan {badge.label}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {saveMsg && (
          <div className="px-3 py-2 rounded-xl bg-emerald-500/15 border border-emerald-400/30 text-emerald-200 text-xs font-mono animate-fade-in">
            {saveMsg}
          </div>
        )}

        {/* 4-File Selector Pills */}
        <div className="flex items-center gap-2 flex-wrap pt-2 border-t border-white/5 text-xs font-mono">
          <span className="text-slate-500 text-[11px]">Berkas Memori:</span>
          <button
            type="button"
            onClick={() => setActiveTab("soul")}
            className={`px-3 py-1 rounded-xl transition-all cursor-pointer ${
              activeTab === "soul"
                ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/40 font-bold"
                : "bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-white border border-white/10"
            }`}
          >
            SOUL.md (Identitas)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("user")}
            className={`px-3 py-1 rounded-xl transition-all cursor-pointer ${
              activeTab === "user"
                ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/40 font-bold"
                : "bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-white border border-white/10"
            }`}
          >
            USER.md (Preferensi)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("memory")}
            className={`px-3 py-1 rounded-xl transition-all cursor-pointer ${
              activeTab === "memory"
                ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/40 font-bold"
                : "bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-white border border-white/10"
            }`}
          >
            MEMORY.md (Fakta)
          </button>
          <span className="text-[10px] text-slate-500 ml-auto hidden sm:inline">
            AGENTS.md otomatis aktif di root folder proyek
          </span>
        </div>
      </div>

      {/* Raw Markdown Editor Container */}
      <div className="rounded-2xl liquid-glass border border-white/10 overflow-hidden flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-4 py-2 bg-black/50 border-b border-white/10 text-xs font-mono text-slate-400 select-none">
          <div className="flex items-center gap-2">
            <span className="text-cyan-300 font-bold">{badge.label}</span>
            <span className="text-[10px] text-slate-500">• Cap: {badge.cap}</span>
          </div>
          <div className="flex items-center gap-3 text-[10px]">
            <span>{currentContent.length} karakter</span>
            <span>{currentContent ? currentContent.split("\n").length : 0} baris</span>
          </div>
        </div>
        <textarea
          value={currentContent}
          onChange={(e) => setCurrentContent(e.target.value)}
          rows={18}
          className="w-full bg-slate-950/80 p-4 font-mono text-xs text-slate-200 leading-relaxed custom-scrollbar border-none focus:outline-none resize-y selection:bg-cyan-500/30"
          placeholder={`# Tuliskan konten ${badge.label} di sini...`}
        />
        <div className="px-4 py-2 bg-black/40 border-t border-white/5 text-[11px] text-slate-400 font-mono flex items-center justify-between">
          <span>🔒 Privacy Filter aktif: Kredensial &amp; API key otomatis disensor sebelum disimpan.</span>
          <span>UTF-8 Markdown</span>
        </div>
      </div>
    </div>
  );
}
