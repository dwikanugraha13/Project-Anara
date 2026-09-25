"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { BACKEND_URL, Memory, Speaker, LiquidGlassSelect, SelectOption } from "../types";

interface BrainMemoriesTabProps {
  activeSpeaker?: string | null;
  speakers: Speaker[];
  onRefreshStats?: () => void;
}

export default function BrainMemoriesTab({
  activeSpeaker,
  speakers,
  onRefreshStats,
}: BrainMemoriesTabProps) {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [isAddMemoryOpen, setIsAddMemoryOpen] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newCategory, setNewCategory] = useState("general");
  const [newSpeaker, setNewSpeaker] = useState(activeSpeaker || "Agnan");

  // Semantic RAG State
  const [ragQuery, setRagQuery] = useState("");
  const [ragResults, setRagResults] = useState<Array<{ title: string; content: string; score: number }>>([]);
  const [isRagSearching, setIsRagSearching] = useState(false);

  const fetchMemories = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/memories`);
      if (res.ok) {
        const data = await res.json();
        setMemories(data || []);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  useEffect(() => {
    if (activeSpeaker) {
      setNewSpeaker(activeSpeaker);
    }
  }, [activeSpeaker]);

  const handleSaveMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.trim() || !newValue.trim() || !newSpeaker.trim()) return;

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/memories`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          speaker_name: newSpeaker.trim(),
          key: newKey.trim(),
          value: newValue.trim(),
          category: newCategory,
        }),
      });

      if (res.ok) {
        setIsAddMemoryOpen(false);
        setNewKey("");
        setNewValue("");
        fetchMemories();
        onRefreshStats?.();
      }
    } catch (err) {
      console.error("Save memory error:", err);
    }
  };

  const handleDeleteMemory = async (id: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/memories/${id}`, { method: "DELETE" });
      if (res.ok) {
        setMemories((prev) => prev.filter((m) => m.id !== id));
        onRefreshStats?.();
      }
    } catch (err) {
      console.error("Delete memory error:", err);
    }
  };

  const handleSemanticSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!ragQuery.trim()) {
      setRagResults([]);
      return;
    }
    setIsRagSearching(true);
    try {
      const spParam = activeSpeaker ? `&speaker_name=${encodeURIComponent(activeSpeaker)}` : "";
      const res = await fetch(`${BACKEND_URL}/api/brain/semantic-search?query=${encodeURIComponent(ragQuery.trim())}${spParam}`);
      if (res.ok) {
        const data = await res.json();
        setRagResults(data || []);
      }
    } catch (err) {
      console.error("Semantic search error:", err);
    } finally {
      setIsRagSearching(false);
    }
  };

  const currentSpeakerMemories = useMemo(() => {
    if (!activeSpeaker) return memories;
    return memories.filter((m) => (m.speaker_name || "").toLowerCase() === activeSpeaker.toLowerCase());
  }, [memories, activeSpeaker]);

  const categories = useMemo(() => {
    const cats = new Set<string>();
    currentSpeakerMemories.forEach((m) => {
      if (m.category) cats.add(m.category);
    });
    return Array.from(cats);
  }, [currentSpeakerMemories]);

  const categoryOptions: SelectOption[] = useMemo(() => {
    return [
      { value: "all", label: "Semua Kategori" },
      ...categories.map((c) => ({
        value: c,
        label: c.charAt(0).toUpperCase() + c.slice(1),
      })),
    ];
  }, [categories]);

  const formCategoryOptions: SelectOption[] = [
    { value: "general", label: "General" },
    { value: "preference", label: "Preference" },
    { value: "bio", label: "Bio" },
    { value: "work", label: "Work" },
    { value: "personal", label: "Personal" },
  ];

  const filteredMemories = useMemo(() => {
    return currentSpeakerMemories.filter((m) => {
      const matchesSearch =
        m.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.value.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCat = selectedCategory === "all" || m.category === selectedCategory;
      return matchesSearch && matchesCat;
    });
  }, [currentSpeakerMemories, searchQuery, selectedCategory]);

  return (
    <div className="space-y-5">
      {/* Information Metric Ribbon */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 rounded-2xl liquid-glass-subtle">
          <span className="text-[10px] uppercase tracking-wider text-slate-400">Memory Nodes</span>
          <p className="text-base font-bold text-white mt-0.5">{currentSpeakerMemories.length} Facts</p>
        </div>
        <div className="p-4 rounded-2xl liquid-glass-subtle">
          <span className="text-[10px] uppercase tracking-wider text-slate-400">Session Profile</span>
          <p className={`text-base font-bold mt-0.5 truncate ${activeSpeaker ? "text-cyan-300" : "text-amber-300"}`}>
            {activeSpeaker || "Tamu"}
          </p>
        </div>
        <div className="p-4 rounded-2xl liquid-glass-subtle">
          <span className="text-[10px] uppercase tracking-wider text-slate-400">Session Status</span>
          <p className={`text-base font-bold mt-0.5 ${activeSpeaker ? "text-emerald-300" : "text-amber-300"}`}>
            {activeSpeaker ? "Authenticated" : "Guest Session"}
          </p>
        </div>
        <div className="p-4 rounded-2xl liquid-glass-subtle">
          <span className="text-[10px] uppercase tracking-wider text-slate-400">Penyimpanan</span>
          <p className="text-base font-bold text-indigo-300 mt-0.5">SQLite</p>
        </div>
      </div>

      {speakers.length === 0 ? (
        <div className="p-10 sm:p-14 rounded-3xl liquid-glass-subtle text-center flex flex-col items-center justify-center gap-3 animate-fade-in">
          <div className="w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-400/30 flex items-center justify-center text-cyan-300 shadow-[0_0_24px_rgba(34,211,238,0.2)]">
            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h4 className="text-sm sm:text-base font-bold text-white uppercase tracking-wider">
            No Profiles Registered Yet
          </h4>
          <p className="text-xs sm:text-sm text-slate-300 max-w-lg leading-relaxed">
            Enable microphone and introduce your name (contoh: <span className="text-cyan-300 font-semibold">&quot;Halo Anara, namaku Agnan&quot;</span>) or add a profile manually in the User Profile tab.
          </p>
          <span className="text-[11px] text-cyan-300/90 px-3.5 py-1.5 rounded-full bg-cyan-400/10 border border-cyan-400/25 mt-1">
            128-D Voice Biometric Engine &amp; Multi-Profile Active
          </span>
        </div>
      ) : (
        <>
          {/* Semantic RAG Cognitive Inspector */}
          <form onSubmit={handleSemanticSearch} className="p-4 rounded-2xl liquid-glass-subtle space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-wider text-cyan-300 font-semibold flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                Cognitive Semantic Search
              </span>
              <span className="text-[10px] text-slate-500 hidden sm:inline">Konsep &amp; lintas tabel</span>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="text"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                placeholder="Type any topic (e.g. 'project architecture', 'favorite food')..."
                className="flex-1 liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
              />
              <button
                type="submit"
                disabled={isRagSearching}
                className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white font-semibold text-xs transition-all hover:opacity-90 cursor-pointer shrink-0 disabled:opacity-50"
              >
                {isRagSearching ? "Searching..." : "Search"}
              </button>
            </div>

            {ragResults.length > 0 && (
              <div className="space-y-2 pt-3 border-t border-white/10 animate-fade-in">
                <span className="text-[10px] uppercase tracking-wider text-slate-400">Hasil temuan tertinggi:</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {ragResults.map((item, idx) => (
                    <div key={idx} className="p-3 rounded-xl bg-black/30 border border-white/10 text-xs space-y-1">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-cyan-300 uppercase font-semibold truncate">{item.title}</span>
                        <span className="text-emerald-400 font-bold shrink-0 ml-2">{item.score.toFixed(1)}</span>
                      </div>
                      <p className="text-slate-300 text-[11px] line-clamp-2">{item.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </form>

          {/* Filter & Action Toolbar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 flex-1">
              <div className="relative flex-1">
                <svg className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={activeSpeaker ? `Search memories of ${activeSpeaker}...` : "Search memories of all registered profiles..."}
                  className="w-full liquid-glass-input rounded-2xl py-2.5 pl-10 pr-4 text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none"
                />
              </div>
              <LiquidGlassSelect
                value={selectedCategory}
                onChange={setSelectedCategory}
                options={categoryOptions}
                className="w-44 shrink-0"
              />
            </div>

            <button
              onClick={() => setIsAddMemoryOpen(true)}
              className="px-5 py-2.5 rounded-2xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white text-xs sm:text-sm font-semibold flex items-center justify-center gap-2 cursor-pointer shadow-[0_4px_20px_rgba(34,211,238,0.3)] transition-all hover:opacity-90 active:scale-[0.98] shrink-0"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span>Tambah Fakta</span>
            </button>
          </div>

          {/* Add Memory Inline Modal */}
          {isAddMemoryOpen && (
            <form onSubmit={handleSaveMemory} className="relative z-30 p-5 rounded-2xl liquid-glass space-y-3.5 animate-fade-in">
              <h4 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">Fakta Kognitif Baru</h4>
              <div className="relative z-40 grid grid-cols-1 sm:grid-cols-3 gap-3">
                <input
                  type="text"
                  value={newSpeaker}
                  onChange={(e) => setNewSpeaker(e.target.value)}
                  placeholder="User Name"
                  className="liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                  required
                />
                <input
                  type="text"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder="Kunci (cth: band_favorit)"
                  className="liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                  required
                />
                <LiquidGlassSelect
                  value={newCategory}
                  onChange={setNewCategory}
                  options={formCategoryOptions}
                />
              </div>
              <input
                type="text"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                placeholder="Nilai (cth: Avenged Sevenfold)"
                className="w-full liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                required
              />
              <div className="flex justify-end gap-2.5 pt-1">
                <button
                  type="button"
                  onClick={() => setIsAddMemoryOpen(false)}
                  className="px-4 py-2 rounded-xl liquid-glass-subtle border border-white/10 text-slate-300 text-xs cursor-pointer"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white font-semibold text-xs cursor-pointer shadow-[0_4px_16px_rgba(34,211,238,0.3)] transition-all hover:opacity-90"
                >
                   Save
                </button>
              </div>
            </form>
          )}

          {/* Memory Cards Grid */}
          {filteredMemories.length === 0 ? (
            <div className="text-center py-16 rounded-2xl liquid-glass-subtle text-slate-400 text-xs">
              {activeSpeaker
                ? `No stored memory notes for ${activeSpeaker} yet.`
                : "No stored memory notes yet. Introduce yourself via microphone or select a profile in the User Profile tab."}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {filteredMemories.map((m) => (
                <div
                  key={m.id}
                  className="p-5 rounded-2xl liquid-glass-subtle hover:border-cyan-400/40 hover:shadow-[0_8px_30px_rgba(34,211,238,0.12)] transition-all duration-300 flex flex-col justify-between group"
                >
                  <div>
                    <div className="flex items-center justify-between gap-1.5 mb-2.5">
                      <span className="text-[10px] font-medium uppercase tracking-wider px-2.5 py-1 rounded-full bg-indigo-500/15 text-indigo-200 border border-indigo-400/25">
                        {m.category}
                      </span>
                      <button
                        onClick={() => handleDeleteMemory(m.id)}
                        className="text-slate-500 hover:text-rose-400 opacity-0 group-hover:opacity-100 transition-opacity p-1 cursor-pointer"
                        title="Delete memory"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <h4 className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                      {m.key.replace(/_/g, " ")}
                    </h4>
                    <p className="text-sm sm:text-[15px] font-semibold text-cyan-100 mt-1 leading-relaxed">{m.value}</p>
                  </div>
                  <span className="text-[10px] text-slate-500 mt-4 pt-2.5 border-t border-white/[0.07]">
                    Diperbarui: {new Date(m.updated_at || m.created_at).toLocaleString("id-ID")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
