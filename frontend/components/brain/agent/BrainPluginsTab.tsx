"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { BACKEND_URL } from "../types";

export interface PluginItem {
  id: string;
  name: string;
  title: string;
  version: string;
  category: string;
  author: string;
  description: string;
  enabled: boolean;
  default_enabled?: boolean;
}

export default function BrainPluginsTab() {
  const [plugins, setPlugins] = useState<PluginItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const fetchPlugins = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/plugins`);
      if (res.ok) {
        const data = await res.json();
        setPlugins(data.plugins || []);
      }
    } catch (e) {
      console.warn("[BrainPlugins] Error fetching plugins:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlugins();
  }, [fetchPlugins]);

  const handleTogglePlugin = async (id: string, currentEnabled: boolean) => {
    setTogglingId(id);
    const newEnabled = !currentEnabled;
    // Optimistic UI update
    setPlugins((prev) =>
      prev.map((p) => (p.id === id ? { ...p, enabled: newEnabled } : p))
    );

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/plugins/${id}/toggle`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: newEnabled }),
      });
      if (!res.ok) {
        fetchPlugins();
      } else {
        setNotice(`Plugin '${id}' ${newEnabled ? "enabled" : "disabled"}.`);
        setTimeout(() => setNotice(null), 3000);
      }
    } catch {
      fetchPlugins();
    } finally {
      setTogglingId(null);
    }
  };

  const visiblePlugins = useMemo(() => {
    return plugins.filter((p) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        p.name.toLowerCase().includes(q) ||
        p.title.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q)
      );
    });
  }, [plugins, searchQuery]);

  return (
    <div className="h-full w-full flex flex-col overflow-hidden select-none font-sans">
      {/* Top Header */}
      <div className="px-6 py-4 border-b border-white/[0.08] bg-[#050811]/95 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-white font-mono tracking-tight">
              Modular Plugins &amp; Extensions
            </h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-purple-500/10 text-purple-300 border border-purple-400/20 font-semibold">
              {plugins.length} Registered
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5 leading-relaxed font-sans">
            Modular extension packages with sandbox lifecycle hooks and background daemons.
          </p>
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-64">
          <svg
            className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search plugins..."
            className="w-full py-1.5 pl-8 pr-3 rounded-lg bg-black/40 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-400/40 transition-colors font-sans"
          />
        </div>
      </div>

      {/* Plugins List */}
      <div className="flex-1 min-h-0 overflow-y-auto p-6 custom-scrollbar font-sans space-y-3">
        {visiblePlugins.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-500 font-mono">
            {isLoading ? "Loading plugins..." : "No plugins registered"}
          </div>
        ) : (
          visiblePlugins.map((item) => (
            <div
              key={item.id}
              className={`p-4 rounded-xl border flex items-center justify-between gap-4 transition-all ${
                item.enabled
                  ? "bg-[#070e20]/80 border-purple-500/30 shadow-[0_0_15px_rgba(168,85,247,0.06)]"
                  : "bg-[#060913]/80 hover:bg-[#080d1a] border-white/[0.08] hover:border-white/[0.14]"
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h4 className="text-xs sm:text-sm font-bold text-white tracking-tight font-sans">
                    {item.title}
                  </h4>
                  <span className="px-1.5 py-0.2 rounded font-mono text-[10px] bg-white/[0.05] border border-white/[0.08] text-slate-300">
                    v{item.version}
                  </span>
                  <span className="px-1.5 py-0.2 rounded font-mono text-[9.5px] uppercase bg-purple-500/10 text-purple-300 border border-purple-400/20">
                    {item.category}
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">
                    by {item.author}
                  </span>
                </div>

                <p className="text-xs text-slate-300 mt-1 leading-relaxed font-sans">
                  {item.description}
                </p>
              </div>

              {/* Right Toggle Switch */}
              <div
                className="shrink-0 cursor-pointer"
                onClick={() => handleTogglePlugin(item.id, item.enabled)}
                title={item.enabled ? "Disable plugin" : "Enable plugin"}
              >
                <div
                  className={`w-9 h-5 rounded-full p-0.5 transition-colors duration-200 ease-in-out relative ${
                    item.enabled ? "bg-emerald-500" : "bg-slate-700/80"
                  } ${togglingId === item.id ? "opacity-50" : ""}`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                      item.enabled ? "translate-x-4" : "translate-x-0"
                    }`}
                  />
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Notice Toast */}
      {notice && (
        <div className="fixed bottom-6 right-6 z-50 p-3.5 px-4 rounded-xl bg-emerald-500/15 border border-emerald-400/30 text-emerald-200 text-xs font-mono shadow-2xl backdrop-blur-xl animate-fade-in flex items-center gap-2">
          <span>✓</span>
          <span>{notice}</span>
        </div>
      )}
    </div>
  );
}
