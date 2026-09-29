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
    return memories;
  }, [memories]);

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
    <div className="space-y-4">
      {/* Information Metric Ribbon */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-3.5 rounded-xl bg-white/[0.025] border border-white/[0.08]">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Total Facts</span>
          <p className="text-base font-bold text-white mt-0.5">{memories.length} Nodes</p>
        </div>
        <div className="p-3.5 rounded-xl bg-white/[0.025] border border-white/[0.08]">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Active Categories</span>
          <p className="text-base font-bold text-cyan-300 mt-0.5">{categories.length || 1} Topics</p>
        </div>
        <div className="p-3.5 rounded-xl bg-white/[0.025] border border-white/[0.08]">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Storage Engine</span>
          <p className="text-base font-bold text-slate-200 mt-0.5 font-mono">SQLite (anara_brain.db)</p>
        </div>
      </div>

      {/* Semantic RAG Cognitive Inspector */}
      <form onSubmit={handleSemanticSearch} className="p-3.5 rounded-xl bg-white/[0.025] border border-white/[0.08] space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 font-semibold flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            Cognitive Semantic Search
          </span>
          <span className="text-[10px] font-mono text-slate-500 hidden sm:inline">Vector &amp; SQLite Hybrid Index</span>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            value={ragQuery}
            onChange={(e) => setRagQuery(e.target.value)}
            placeholder="Search any semantic memory (e.g. 'architecture style', 'database schema', 'preferences')..."
            className="flex-1 bg-black/40 border border-white/[0.08] rounded-lg py-2 px-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-white/20 transition-colors"
          />
          <button
            type="submit"
            disabled={isRagSearching}
            className="px-3.5 py-2 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.12] text-slate-200 hover:text-white font-medium text-xs transition-all cursor-pointer shrink-0 disabled:opacity-50"
          >
            {isRagSearching ? "Searching..." : "Search"}
          </button>
        </div>

        {ragResults.length > 0 && (
          <div className="space-y-2 pt-3 border-t border-white/[0.06] animate-fade-in">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Highest Rank Matches:</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {ragResults.map((item, idx) => (
                <div key={idx} className="p-2.5 rounded-lg bg-black/40 border border-white/[0.08] text-xs space-y-1">
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-cyan-300 font-mono uppercase font-semibold truncate">{item.title}</span>
                    <span className="text-emerald-400 font-mono font-bold shrink-0 ml-2">{item.score.toFixed(1)}</span>
                  </div>
                  <p className="text-slate-300 text-[11px] line-clamp-2">{item.content}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </form>

      {/* Filter & Action Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
        <div className="flex items-center gap-2 flex-1">
          <div className="relative flex-1">
            <svg className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter memories by key or content..."
              className="w-full bg-black/30 border border-white/[0.08] rounded-lg py-1.5 pl-9 pr-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-white/20 transition-colors"
            />
          </div>
          <LiquidGlassSelect
            value={selectedCategory}
            onChange={setSelectedCategory}
            options={categoryOptions}
            className="w-40 shrink-0"
          />
        </div>

        <button
          onClick={() => setIsAddMemoryOpen(true)}
          className="px-3.5 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.12] text-slate-200 hover:text-white text-xs font-medium flex items-center justify-center gap-1.5 cursor-pointer transition-all active:scale-[0.98] shrink-0"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>Add Fact</span>
        </button>
      </div>

      {/* Add Memory Inline Modal */}
      {isAddMemoryOpen && (
        <form onSubmit={handleSaveMemory} className="relative z-30 p-4 rounded-xl bg-[#080d1a] border border-white/[0.12] space-y-3 animate-fade-in shadow-lg">
          <h4 className="text-xs font-mono font-semibold text-cyan-400 uppercase tracking-wider">New Memory Node</h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <input
              type="text"
              value={newSpeaker}
              onChange={(e) => setNewSpeaker(e.target.value)}
              placeholder="Speaker/Namespace (e.g. User)"
              className="bg-black/40 border border-white/[0.08] rounded-lg py-2 px-3 text-xs text-white placeholder-slate-500 focus:outline-none"
              required
            />
            <input
              type="text"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="Key (e.g. favorite_stack)"
              className="bg-black/40 border border-white/[0.08] rounded-lg py-2 px-3 text-xs text-white placeholder-slate-500 focus:outline-none font-mono"
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
            placeholder="Value (e.g. Next.js, FastAPI, Obsidian Glass)"
            className="w-full bg-black/40 border border-white/[0.08] rounded-lg py-2 px-3 text-xs text-white placeholder-slate-500 focus:outline-none"
            required
          />
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setIsAddMemoryOpen(false)}
              className="px-3 py-1.5 rounded-lg border border-white/[0.08] text-slate-300 hover:text-white text-xs cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 rounded-lg bg-white/[0.08] hover:bg-white/[0.15] border border-white/[0.14] text-white font-medium text-xs cursor-pointer transition-all"
            >
              Save Fact
            </button>
          </div>
        </form>
      )}

      {/* Memory Cards Grid */}
      {filteredMemories.length === 0 ? (
        <div className="p-8 sm:p-12 rounded-xl bg-white/[0.02] border border-white/[0.08] text-center flex flex-col items-center justify-center gap-2">
          <div className="w-10 h-10 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-slate-400">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
            </svg>
          </div>
          <h4 className="text-xs font-semibold text-slate-200">
            {searchQuery ? "No matching memories found" : "No persistent memories recorded yet"}
          </h4>
          <p className="text-[11px] text-slate-400 max-w-sm">
            {searchQuery
              ? "Try adjusting search terms or resetting the category filter."
              : "Facts and context learned during chat or saved via MEMORY tools will appear here."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {filteredMemories.map((m) => (
            <div
              key={m.id}
              className="p-3.5 rounded-xl bg-white/[0.025] hover:bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all flex flex-col justify-between group shadow-sm"
            >
              <div>
                <div className="flex items-center justify-between gap-1.5 mb-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-white/[0.05] text-slate-300 border border-white/[0.08]">
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
                <h4 className="text-[11px] font-mono font-semibold text-slate-400 uppercase tracking-wider">
                  {m.key.replace(/_/g, " ")}
                </h4>
                <p className="text-xs sm:text-[13px] font-medium text-slate-100 mt-1 leading-relaxed">{m.value}</p>
              </div>
              <span className="text-[10px] font-mono text-slate-500 mt-3 pt-2 border-t border-white/[0.05]">
                Updated: {new Date(m.updated_at || m.created_at).toLocaleString("id-ID")}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
