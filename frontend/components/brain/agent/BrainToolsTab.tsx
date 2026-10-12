"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { BACKEND_URL, ToolItem } from "../types";
import {
  MasterDetail,
  ListColumn,
  DetailColumn,
  CapRow,
  SortButton,
  ToolChip,
} from "../shared/MasterDetail";

export interface ToolsetInfo {
  id: string;
  name?: string;
  title: string;
  description: string;
  icon?: string;
  category: string;
  default_enabled: boolean;
  tools: string[];
  enabled: boolean;
  tool_count: number;
  total_calls?: number;
  tool_calls?: Record<string, number>;
  configured?: boolean;
}

export interface ToolEnvVar {
  key: string;
  prompt: string;
  url?: string;
  default?: string;
  is_set: boolean;
}

export interface ToolProvider {
  name: string;
  badge?: string;
  tag?: string;
  env_vars: ToolEnvVar[];
  post_setup?: string;
  is_active: boolean;
  status: "ready" | "needs_keys" | "needs_setup" | "needs_auth";
  web_backend?: string;
  capabilities?: string[];
  tts_provider?: string;
  stt_provider?: string;
  browser_provider?: string;
  computer_use_backend?: string;
  driver_status?: {
    version: string;
    ready: boolean;
    platform: string;
    platform_note?: string;
  };
}

export interface ToolsetConfig {
  name: string;
  has_category: boolean;
  active_provider?: string;
  active_search_backend?: string;
  active_extract_backend?: string;
  providers: ToolProvider[];
}

export interface ToolModel {
  id: string;
  display: string;
  speed: string;
  strengths: string;
  price: string;
}

export interface ToolModelsData {
  name: string;
  has_models: boolean;
  provider: string;
  models: ToolModel[];
  current?: string;
  default?: string;
}

// Curation for desktop capabilities matching reference standard (25 toolsets visible on desktop)
export const DESKTOP_HIDDEN_TOOLSETS = new Set([
  "discord",
  "discord_admin",
  "yuanbao",
  "context_engine",
  "moa",
  "messaging_telegram",
  "messaging_whatsapp",
  "messaging_discord",
  "messaging_slack",
  "custom_webhooks",
  "document_delivery",
]);

export function isDesktopToolsetVisible(id: string): boolean {
  return !DESKTOP_HIDDEN_TOOLSETS.has(id);
}

export default function BrainToolsTab() {
  const [toolsets, setToolsets] = useState<ToolsetInfo[]>([]);
  const [toolsCatalog, setToolsCatalog] = useState<ToolItem[]>([]);
  const [selectedToolsetId, setSelectedToolsetId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortDesc, setSortDesc] = useState(true);
  const [expandedToolSchema, setExpandedToolSchema] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  // Provider configuration & models catalog state
  const [toolsetConfig, setToolsetConfig] = useState<ToolsetConfig | null>(null);
  const [toolsetModels, setToolsetModels] = useState<ToolModelsData | null>(null);
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
  const [editingEnvKey, setEditingEnvKey] = useState<Record<string, string>>({});
  const [isSavingEnv, setIsSavingEnv] = useState<string | null>(null);
  const [isSelectingProvider, setIsSelectingProvider] = useState<string | null>(null);
  const [isSelectingModel, setIsSelectingModel] = useState<string | null>(null);
  const [isRecheckingDriver, setIsRecheckingDriver] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const fetchToolsets = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/toolsets`);
      if (res.ok) {
        const data = await res.json();
        setToolsets(data.toolsets || []);
      }
    } catch (e) {
      console.warn("[BrainTools] Error fetching toolsets:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchToolsCatalog = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/agent/tools`);
      if (res.ok) {
        const data = await res.json();
        setToolsCatalog(data.tools || []);
      }
    } catch (e) {
      console.warn("[BrainTools] Error fetching tools catalog:", e);
    }
  }, []);

  useEffect(() => {
    fetchToolsets();
    fetchToolsCatalog();
  }, [fetchToolsets, fetchToolsCatalog]);

  // Filter toolsets
  const visibleToolsets = useMemo(() => {
    return toolsets
      .filter((ts) => isDesktopToolsetVisible(ts.id || ts.name || ""))
      .filter((ts) => {
        if (!searchQuery.trim()) return true;
        const q = searchQuery.toLowerCase();
        return (
          (ts.title || ts.name || "").toLowerCase().includes(q) ||
          (ts.description || "").toLowerCase().includes(q) ||
          (ts.tools || []).some((t) => t.toLowerCase().includes(q))
        );
      })
      .sort((a, b) => {
        const callsA = a.total_calls || 0;
        const callsB = b.total_calls || 0;
        return sortDesc ? callsB - callsA : callsA - callsB;
      });
  }, [toolsets, searchQuery, sortDesc]);

  // Active Toolset
  const activeToolset = useMemo(() => {
    if (!visibleToolsets.length) return null;
    if (!selectedToolsetId) return visibleToolsets[0];
    return (
      visibleToolsets.find((ts) => (ts.id || ts.name) === selectedToolsetId) ||
      visibleToolsets[0]
    );
  }, [visibleToolsets, selectedToolsetId]);

  // Load provider config and models catalog when active toolset changes
  const fetchToolsetProviders = useCallback(async (toolsetName: string) => {
    try {
      const [cfgRes, modRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/brain/toolsets/${encodeURIComponent(toolsetName)}/config`),
        fetch(`${BACKEND_URL}/api/brain/toolsets/${encodeURIComponent(toolsetName)}/models`),
      ]);

      if (cfgRes.ok) {
        const cfgData = await cfgRes.json();
        setToolsetConfig(cfgData);
        if (cfgData.active_provider) {
          setExpandedProvider(cfgData.active_provider);
        } else if (cfgData.providers && cfgData.providers.length > 0) {
          setExpandedProvider(cfgData.providers[0].name);
        }
      } else {
        setToolsetConfig(null);
      }

      if (modRes.ok) {
        const modData = await modRes.json();
        setToolsetModels(modData.has_models ? modData : null);
      } else {
        setToolsetModels(null);
      }
    } catch (e) {
      console.warn("[BrainTools] Error fetching provider matrix:", e);
      setToolsetConfig(null);
      setToolsetModels(null);
    }
  }, []);

  useEffect(() => {
    if (activeToolset) {
      const tid = activeToolset.id || activeToolset.name || "";
      fetchToolsetProviders(tid);
      setExpandedToolSchema(null);
    }
  }, [activeToolset, fetchToolsetProviders]);

  // Toggle single toolset
  const handleToggleToolset = async (id: string, currentState: boolean) => {
    const newState = !currentState;
    setTogglingId(id);

    // Optimistic UI update
    setToolsets((prev) =>
      prev.map((ts) => ((ts.id || ts.name) === id ? { ...ts, enabled: newState } : ts))
    );

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/toolsets/${id}/toggle`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: newState }),
      });
      if (!res.ok) {
        // Revert on error
        setToolsets((prev) =>
          prev.map((ts) => ((ts.id || ts.name) === id ? { ...ts, enabled: currentState } : ts))
        );
      }
    } catch (e) {
      console.warn("[BrainTools] Failed to toggle toolset:", e);
      setToolsets((prev) =>
        prev.map((ts) => ((ts.id || ts.name) === id ? { ...ts, enabled: currentState } : ts))
      );
    } finally {
      setTogglingId(null);
    }
  };

  // Bulk toggle
  const handleBulkToggle = async (targetEnabled: boolean) => {
    if (bulkBusy) return;
    setBulkBusy(true);

    const candidates = toolsets.filter(
      (ts) => isDesktopToolsetVisible(ts.id || ts.name || "") && ts.enabled !== targetEnabled
    );

    setToolsets((prev) =>
      prev.map((ts) =>
        isDesktopToolsetVisible(ts.id || ts.name || "") ? { ...ts, enabled: targetEnabled } : ts
      )
    );

    try {
      for (const ts of candidates) {
        const tid = ts.id || ts.name || "";
        await fetch(`${BACKEND_URL}/api/brain/toolsets/${tid}/toggle`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: targetEnabled }),
        });
      }
    } catch (e) {
      console.warn("[BrainTools] Bulk toggle interrupted:", e);
      fetchToolsets();
    } finally {
      setBulkBusy(false);
    }
  };

  // Select active provider
  const handleSelectProvider = async (providerName: string, capability?: string) => {
    if (!activeToolset) return;
    const tid = activeToolset.id || activeToolset.name || "";
    setIsSelectingProvider(providerName);
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/brain/toolsets/${encodeURIComponent(tid)}/provider`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: providerName, capability }),
        }
      );
      if (res.ok) {
        setActionNotice(`Switched active backend to ${providerName}`);
        setTimeout(() => setActionNotice(null), 3000);
        await fetchToolsetProviders(tid);
      }
    } catch (e) {
      console.warn("[BrainTools] Failed to select provider:", e);
    } finally {
      setIsSelectingProvider(null);
    }
  };

  // Save environment variable
  const handleSaveEnv = async (key: string) => {
    if (!activeToolset) return;
    const tid = activeToolset.id || activeToolset.name || "";
    const value = editingEnvKey[key];
    if (value === undefined) return;
    setIsSavingEnv(key);
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/brain/toolsets/${encodeURIComponent(tid)}/env`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ env_vars: { [key]: value } }),
        }
      );
      if (res.ok) {
        setActionNotice(`Saved key for ${key}`);
        setTimeout(() => setActionNotice(null), 3000);
        setEditingEnvKey((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
        await fetchToolsetProviders(tid);
      }
    } catch (e) {
      console.warn("[BrainTools] Failed to save env var:", e);
    } finally {
      setIsSavingEnv(null);
    }
  };

  // Clear environment variable
  const handleClearEnv = async (key: string) => {
    if (!activeToolset) return;
    const tid = activeToolset.id || activeToolset.name || "";
    setIsSavingEnv(key);
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/brain/toolsets/${encodeURIComponent(tid)}/env`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ env_vars: { [key]: "" } }),
        }
      );
      if (res.ok) {
        setActionNotice(`Cleared ${key}`);
        setTimeout(() => setActionNotice(null), 3000);
        await fetchToolsetProviders(tid);
      }
    } catch (e) {
      console.warn("[BrainTools] Failed to clear env var:", e);
    } finally {
      setIsSavingEnv(null);
    }
  };

  // Select active model
  const handleSelectModel = async (modelId: string) => {
    if (!activeToolset) return;
    const tid = activeToolset.id || activeToolset.name || "";
    setIsSelectingModel(modelId);
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/brain/toolsets/${encodeURIComponent(tid)}/model`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model: modelId }),
        }
      );
      if (res.ok) {
        setActionNotice(`Active model updated`);
        setTimeout(() => setActionNotice(null), 3000);
        await fetchToolsetProviders(tid);
      }
    } catch (e) {
      console.warn("[BrainTools] Failed to select model:", e);
    } finally {
      setIsSelectingModel(null);
    }
  };

  // Recheck driver
  const handleRecheckDriver = async () => {
    if (!activeToolset) return;
    const tid = activeToolset.id || activeToolset.name || "";
    setIsRecheckingDriver(true);
    try {
      await fetchToolsetProviders(tid);
      setActionNotice("Driver health checked");
      setTimeout(() => setActionNotice(null), 2500);
    } finally {
      setIsRecheckingDriver(false);
    }
  };

  // Map tools in active toolset
  const activeMemberTools = useMemo(() => {
    if (!activeToolset) return [];
    return (activeToolset.tools || []).map((tName) => {
      const spec = toolsCatalog.find((tc) => tc.name === tName);
      const calls = activeToolset.tool_calls?.[tName] || 0;
      return {
        name: tName,
        description: spec?.description || "Executable platform operation tool.",
        parameters: spec?.parameters || null,
        is_read_only: spec?.is_read_only ?? false,
        calls,
      };
    });
  }, [activeToolset, toolsCatalog]);

  const selectedToolSpec = useMemo(() => {
    if (!expandedToolSchema) return null;
    return activeMemberTools.find((m) => m.name === expandedToolSchema) || null;
  }, [expandedToolSchema, activeMemberTools]);

  const allEnabled = useMemo(() => {
    return visibleToolsets.length > 0 && visibleToolsets.every((ts) => ts.enabled);
  }, [visibleToolsets]);

  const toolsetId = activeToolset ? (activeToolset.id || activeToolset.name || "") : "";

  return (
    <div className="h-full flex flex-col font-sans select-none bg-[#030712] text-slate-100">
      <div className="flex-1 min-h-0">
        <MasterDetail defaultLeftWidth={360} resizeId="tools-split">
          {/* ── LEFT COLUMN: Toolsets Rail ── */}
          <ListColumn>
            {/* Header Strip with Search & Sort */}
            <div className="shrink-0 pb-1.5 space-y-1.5 border-b border-white/[0.08]">
              <div className="flex items-center gap-1.5">
                <div className="relative flex-1">
                  <span className="absolute inset-y-0 left-2 flex items-center pointer-events-none text-slate-500 text-xs">
                    🔍
                  </span>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search toolsets..."
                    className="w-full py-1 pl-7 pr-2 rounded-md bg-black/40 border border-white/[0.08] text-[11px] text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-white/20 transition-colors"
                  />
                </div>
                <SortButton
                  desc={sortDesc}
                  onToggle={() => setSortDesc(!sortDesc)}
                  label={sortDesc ? "Most used" : "Least used"}
                />
              </div>

              {/* Toolsets summary & bulk master switch */}
              <div className="flex items-center justify-between px-1 text-[10px] font-mono text-slate-400">
                <span>
                  {visibleToolsets.length} toolsets ({visibleToolsets.filter((t) => t.enabled).length} active)
                </span>
                <button
                  type="button"
                  onClick={() => handleBulkToggle(!allEnabled)}
                  disabled={bulkBusy}
                  className="hover:text-white transition-colors cursor-pointer flex items-center gap-1"
                >
                  <span>{allEnabled ? "Disable All" : "Enable All"}</span>
                </button>
              </div>
            </div>

            {/* Toolsets List */}
            {visibleToolsets.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 font-mono">
                {isLoading ? "Loading toolsets..." : "No matching toolsets found"}
              </div>
            ) : (
              visibleToolsets.map((ts) => {
                const tid = ts.id || ts.name || "";
                const calls = ts.total_calls || 0;
                return (
                  <CapRow
                    key={tid}
                    title={ts.title || ts.name || tid}
                    subtitle={ts.description}
                    active={toolsetId === tid}
                    enabled={ts.enabled}
                    meta={calls > 0 ? `×${calls}` : `${(ts.tools || []).length} tools`}
                    busy={togglingId === tid || bulkBusy}
                    onSelect={() => setSelectedToolsetId(tid)}
                    onToggle={() => handleToggleToolset(tid, ts.enabled)}
                  />
                );
              })
            )}
          </ListColumn>

          {/* ── RIGHT COLUMN: Detail Pane (Compact IDE Standards 1:1) ── */}
          <DetailColumn>
            {activeToolset ? (
              <div className="h-full w-full flex flex-col min-h-0 space-y-2.5 animate-fade-in custom-scrollbar overflow-y-auto pr-1">
                {/* 1. Header Banner */}
                <div className="shrink-0 border-b border-white/[0.08] pb-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-[13.5px] font-semibold text-white tracking-tight font-sans">
                      {activeToolset.title || activeToolset.name}
                    </h2>
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[9.5px] font-mono font-medium ${
                          activeToolset.enabled
                            ? "bg-emerald-500/10 border border-emerald-400/25 text-emerald-300"
                            : "bg-white/[0.04] border border-white/[0.08] text-slate-400"
                        }`}
                      >
                        {activeToolset.enabled ? "Enabled" : "Disabled"}
                      </span>
                      {activeToolset.category && (
                        <span className="px-2 py-0.5 rounded text-[9.5px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300 capitalize">
                          {activeToolset.category}
                        </span>
                      )}
                      {(activeToolset.total_calls || 0) > 0 && (
                        <span className="px-2 py-0.5 rounded text-[9.5px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300 font-medium">
                          ×{activeToolset.total_calls} calls
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5 leading-normal font-sans">
                    {activeToolset.description}
                  </p>

                  {/* Toast Notification */}
                  {actionNotice && (
                    <div className="mt-1 text-[10.5px] font-mono text-emerald-300 bg-emerald-950/30 border border-emerald-500/30 px-2 py-0.5 rounded animate-fade-in flex items-center gap-1.5">
                      <span>✓</span>
                      <span>{actionNotice}</span>
                    </div>
                  )}
                </div>

                {/* 2. Member Tools Breakdown Chips */}
                <div className="space-y-1 shrink-0">
                  <div className="flex flex-wrap gap-1">
                    {activeMemberTools.map((m) => {
                      const isExpanded = expandedToolSchema === m.name;
                      return (
                        <ToolChip
                          key={m.name}
                          onClick={() => setExpandedToolSchema(isExpanded ? null : m.name)}
                        >
                          <span className={isExpanded ? "text-white font-semibold" : ""}>{m.name}</span>
                          {m.calls > 0 && (
                            <span className="ml-1 text-slate-500">×{m.calls}</span>
                          )}
                        </ToolChip>
                      );
                    })}
                  </div>

                  {/* Inline Schema Drawer for Clicked Tool */}
                  {selectedToolSpec && (
                    <div className="mt-1.5 p-2.5 rounded-lg border border-white/[0.12] bg-[#050811]/95 text-[11px] font-mono space-y-1.5 animate-fade-in shadow-inner">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white">{selectedToolSpec.name}</span>
                          <span
                            className={`px-1.5 py-0.2 rounded text-[9px] uppercase ${
                              selectedToolSpec.is_read_only
                                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-400/25"
                                : "bg-white/[0.06] text-slate-300 border border-white/[0.1]"
                            }`}
                          >
                            {selectedToolSpec.is_read_only ? "read-only" : "state-mutating"}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => setExpandedToolSchema(null)}
                          className="text-[10px] text-slate-400 hover:text-white cursor-pointer"
                        >
                          ✕ Close
                        </button>
                      </div>
                      <p className="text-[11px] text-slate-300 font-sans leading-relaxed">
                        {selectedToolSpec.description}
                      </p>
                      {selectedToolSpec.parameters && (
                        <div className="mt-1 p-2 rounded bg-[#03060c] border border-white/[0.08] text-[10px] text-slate-200 overflow-x-auto select-text whitespace-pre-wrap max-h-48 custom-scrollbar">
                          {JSON.stringify(selectedToolSpec.parameters, null, 2)}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* ── 3. COMPUTER USE PREFLIGHT PANEL (1:1 Reference Standard) ── */}
                {toolsetId === "computer_use" && (
                  <div className="space-y-2 shrink-0 pt-1">
                    {/* Platform Warning Note */}
                    <p className="text-[10.5px] text-slate-400 font-sans leading-relaxed">
                      First run may trigger a Windows SmartScreen prompt for the cua-driver UIAccess worker — allow it.
                    </p>

                    {/* Driver Health Bar with Version & Recheck */}
                    <div className="flex items-center justify-between gap-3 px-2.5 py-1.5 rounded-lg bg-black/40 border border-white/[0.08]">
                      <div className="flex items-center gap-2.5 text-[11px] font-mono">
                        <span className="text-slate-300 font-medium">Driver health</span>
                        <span className="px-1.5 py-0.5 rounded text-[9.5px] font-mono bg-emerald-500/15 border border-emerald-400/30 text-emerald-300 font-semibold flex items-center gap-1">
                          <span>✓</span>
                          <span>Ready</span>
                        </span>
                        <span className="text-slate-500 text-[10px]">cua-driver 0.2.1.0</span>
                      </div>
                      <button
                        type="button"
                        onClick={handleRecheckDriver}
                        disabled={isRecheckingDriver}
                        className="px-2 py-0.5 rounded text-[10px] font-mono text-slate-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors cursor-pointer flex items-center gap-1 disabled:opacity-50"
                      >
                        {isRecheckingDriver ? "Checking..." : "Recheck"}
                      </button>
                    </div>

                    <p className="text-[10.5px] text-slate-400 font-sans leading-relaxed">
                      Computer Use is ready. Ask the agent to capture an app and click around.
                    </p>

                    {/* Backend Card: cua-driver (background) */}
                    <div className="rounded-lg border border-white/20 bg-[#050811]/95 p-3 space-y-2 font-mono text-[11px]">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-white text-xs">cua-driver (background)</span>
                        <div className="flex items-center gap-1">
                          <span className="px-1.5 py-0.2 rounded text-[9px] bg-white/[0.06] border border-white/[0.1] text-slate-300">
                            recommended
                          </span>
                          <span className="px-1.5 py-0.2 rounded text-[9px] bg-white/[0.06] border border-white/[0.1] text-slate-300">
                            free
                          </span>
                          <span className="px-1.5 py-0.2 rounded text-[9px] bg-white/[0.06] border border-white/[0.1] text-slate-300">
                            local
                          </span>
                          <span className="px-1.5 py-0.2 rounded text-[9px] bg-emerald-500/15 border border-emerald-400/30 text-emerald-300 font-semibold">
                            Active
                          </span>
                        </div>
                      </div>

                      <p className="text-[11px] text-slate-300 font-sans leading-relaxed">
                        Background computer-use via cua-driver — does NOT steal your cursor or focus. Works with any model.
                      </p>

                      <div className="text-[10.5px] space-y-0.5 text-slate-400 font-sans border-t border-white/[0.06] pt-1.5">
                        <div className="flex items-center gap-1.5 text-slate-200">
                          <span>✓</span>
                          <span>This is your active backend</span>
                        </div>
                        <div>No API key required</div>
                        <div className="text-slate-500">Installed. Re-run setup only if something is broken.</div>
                      </div>

                      <div className="flex items-center justify-end gap-1.5 pt-1">
                        <button
                          type="button"
                          className="px-2.5 py-0.5 rounded text-[10.5px] font-mono bg-white/[0.12] text-white border border-white/20 font-medium flex items-center gap-1 cursor-default"
                        >
                          <span>✓</span>
                          <span>Installed</span>
                        </button>
                        <button
                          type="button"
                          onClick={handleRecheckDriver}
                          className="px-2.5 py-0.5 rounded text-[10.5px] font-mono text-slate-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors cursor-pointer"
                        >
                          Re-run setup
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* ── 4. MODEL CATALOG PANEL (For Image & Video Generation) ── */}
                {toolsetModels && toolsetModels.has_models && toolsetModels.models.length > 0 && (
                  <div className="space-y-1.5 shrink-0 pt-1">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center justify-between">
                      <span>Available Models ({toolsetModels.models.length} models)</span>
                      <span className="text-[9px] text-slate-500 font-mono">
                        Active: {toolsetModels.current || toolsetModels.default || "Default"}
                      </span>
                    </div>

                    <div className="rounded-lg border border-white/[0.08] bg-black/40 divide-y divide-white/[0.06] max-h-64 overflow-y-auto custom-scrollbar">
                      {toolsetModels.models.map((m) => {
                        const isCurrent =
                          m.id === (toolsetModels.current || toolsetModels.default);
                        return (
                          <div
                            key={m.id}
                            onClick={() => handleSelectModel(m.id)}
                            className={`p-2 transition-colors cursor-pointer flex items-center justify-between gap-2.5 text-[11px] font-mono ${
                              isCurrent ? "bg-white/[0.06]" : "hover:bg-white/[0.03]"
                            }`}
                          >
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <div className="flex items-center gap-1.5">
                                <span className={`font-medium ${isCurrent ? "text-white" : "text-slate-300"}`}>
                                  {m.display}
                                </span>
                                {isCurrent && (
                                  <span className="px-1.5 py-0.2 rounded text-[8.5px] bg-white/[0.1] border border-white/20 text-white font-semibold">
                                    in use
                                  </span>
                                )}
                                {m.speed && (
                                  <span className="text-[9.5px] text-slate-500">
                                    {m.speed}
                                  </span>
                                )}
                              </div>
                              <p className="text-[10.5px] text-slate-400 font-sans truncate">
                                {m.strengths}
                              </p>
                            </div>
                            <div className="text-right shrink-0">
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300">
                                {m.price}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* ── 5. PROVIDER MATRIX CARDS (Free vs Paid / Local vs Cloud) ── */}
                {toolsetConfig &&
                  toolsetConfig.providers &&
                  toolsetConfig.providers.length > 0 &&
                  toolsetId !== "computer_use" && (
                    <div className="space-y-1.5 shrink-0 pt-1">
                      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center justify-between">
                        <span>Provider &amp; Backend Matrix</span>
                        {(toolsetId === "web_search_scraping" || toolsetId === "web") && (
                          <div className="flex items-center gap-1.5 text-[9px] font-mono text-slate-400">
                            <span>Search: {toolsetConfig.active_search_backend || "ddgs"}</span>
                            <span>•</span>
                            <span>Extract: {toolsetConfig.active_extract_backend || "tavily"}</span>
                          </div>
                        )}
                      </div>

                      <div className="space-y-1.5">
                        {toolsetConfig.providers.map((prov) => {
                          const isExpanded = expandedProvider === prov.name;
                          const isActive = prov.is_active;

                          return (
                            <div
                              key={prov.name}
                              className={`rounded-lg border transition-all ${
                                isActive
                                  ? "border-white/20 bg-[#050811]/95"
                                  : "border-white/[0.08] bg-[#070b16]/70 hover:border-white/15"
                              } overflow-hidden`}
                            >
                              {/* Row Header */}
                              <div
                                onClick={() =>
                                  setExpandedProvider(isExpanded ? null : prov.name)
                                }
                                className="flex items-center justify-between gap-2.5 px-3 py-2 cursor-pointer hover:bg-white/[0.02] transition-colors"
                              >
                                <div className="flex items-center gap-2 min-w-0">
                                  <span className="text-[11.5px] font-semibold text-white truncate font-mono">
                                    {prov.name}
                                  </span>
                                  {prov.badge && (
                                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-400">
                                      {prov.badge}
                                    </span>
                                  )}
                                  {isActive && (
                                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-emerald-500/15 border border-emerald-400/30 text-emerald-300 font-semibold flex items-center gap-1">
                                      <span>✓</span>
                                      <span>Active</span>
                                    </span>
                                  )}
                                  {prov.status === "ready" && !isActive && (
                                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-400">
                                      Ready
                                    </span>
                                  )}
                                  {prov.status === "needs_keys" && (
                                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-amber-500/15 border border-amber-400/30 text-amber-300">
                                      Needs keys
                                    </span>
                                  )}
                                  {prov.status === "needs_setup" && (
                                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-amber-500/15 border border-amber-400/30 text-amber-300">
                                      Setup required
                                    </span>
                                  )}
                                </div>

                                <div className="flex items-center gap-1.5 shrink-0">
                                  {/* Web Specific capability switcher */}
                                  {(toolsetId === "web_search_scraping" || toolsetId === "web") && (
                                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                                      <button
                                        type="button"
                                        onClick={() => handleSelectProvider(prov.name, "search")}
                                        className="px-1.5 py-0.5 rounded text-[9.5px] font-mono text-slate-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors cursor-pointer"
                                      >
                                        Search
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => handleSelectProvider(prov.name, "extract")}
                                        className="px-1.5 py-0.5 rounded text-[9.5px] font-mono text-slate-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors cursor-pointer"
                                      >
                                        Extract
                                      </button>
                                    </div>
                                  )}

                                  {/* General Use Backend Button */}
                                  {!isActive && toolsetId !== "web_search_scraping" && toolsetId !== "web" && (
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleSelectProvider(prov.name);
                                      }}
                                      disabled={isSelectingProvider === prov.name}
                                      className="px-2 py-0.5 rounded text-[10px] font-mono text-slate-300 hover:text-white bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.1] transition-colors cursor-pointer disabled:opacity-50"
                                    >
                                      {isSelectingProvider === prov.name ? "Selecting..." : "Use this backend"}
                                    </button>
                                  )}

                                  <span className="text-slate-500 text-[10px]">
                                    {isExpanded ? "▲" : "▼"}
                                  </span>
                                </div>
                              </div>

                              {/* Expanded Provider Drawer */}
                              {isExpanded && (
                                <div className="px-3 pb-2.5 pt-1 border-t border-white/[0.06] bg-black/40 space-y-2 text-[11px] font-mono">
                                  {prov.tag && (
                                    <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
                                      {prov.tag}
                                    </p>
                                  )}

                                  {/* Environment Variables / Credentials Form */}
                                  {prov.env_vars.length === 0 ? (
                                    <div className="text-[10.5px] text-slate-500 font-sans flex items-center gap-1.5">
                                      <span>✓</span>
                                      <span>No API key required</span>
                                    </div>
                                  ) : (
                                    <div className="space-y-1.5 pt-0.5">
                                      {prov.env_vars.map((ev) => {
                                        const currentValue =
                                          editingEnvKey[ev.key] !== undefined
                                            ? editingEnvKey[ev.key]
                                            : "";
                                        return (
                                          <div
                                            key={ev.key}
                                            className="space-y-1 p-1.5 rounded-md bg-black/50 border border-white/[0.06]"
                                          >
                                            <div className="flex items-center justify-between text-[10.5px]">
                                              <span className="text-slate-300 font-medium font-mono">
                                                {ev.prompt || ev.key}
                                              </span>
                                              <span
                                                className={`text-[9px] font-mono ${
                                                  ev.is_set ? "text-emerald-400" : "text-amber-400"
                                                }`}
                                              >
                                                {ev.is_set ? "● Set" : "● Not set"}
                                              </span>
                                            </div>
                                            <div className="flex items-center gap-1.5">
                                              <input
                                                type="password"
                                                value={currentValue}
                                                onChange={(e) =>
                                                  setEditingEnvKey({
                                                    ...editingEnvKey,
                                                    [ev.key]: e.target.value,
                                                  })
                                                }
                                                placeholder={ev.is_set ? "••••••••••••••••" : `Enter ${ev.key}...`}
                                                className="flex-1 py-0.5 px-2 rounded bg-black/60 border border-white/[0.08] text-[10.5px] font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-white/20"
                                              />
                                              <button
                                                type="button"
                                                onClick={() => handleSaveEnv(ev.key)}
                                                disabled={isSavingEnv === ev.key || !currentValue}
                                                className="px-2 py-0.5 rounded text-[10.5px] font-mono bg-white/[0.12] hover:bg-white/[0.18] text-white border border-white/20 font-medium transition-colors cursor-pointer disabled:opacity-40"
                                              >
                                                {isSavingEnv === ev.key ? "Saving..." : "Save"}
                                              </button>
                                              {ev.is_set && (
                                                <button
                                                  type="button"
                                                  onClick={() => handleClearEnv(ev.key)}
                                                  disabled={isSavingEnv === ev.key}
                                                  className="px-2 py-0.5 rounded text-[10.5px] font-mono text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors cursor-pointer disabled:opacity-40"
                                                >
                                                  Clear
                                                </button>
                                              )}
                                            </div>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  )}

                                  {/* Post Setup Button */}
                                  {prov.post_setup && (
                                    <div className="pt-0.5 flex items-center justify-between text-[10.5px] text-slate-500">
                                      <span>Setup status: {prov.status === "ready" ? "Installed" : "Action required"}</span>
                                      <button
                                        type="button"
                                        onClick={() => handleRecheckDriver()}
                                        className="px-2 py-0.5 rounded text-[10px] font-mono text-slate-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors cursor-pointer"
                                      >
                                        Run setup
                                      </button>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
              </div>
            ) : (
              <div className="p-12 text-center text-xs text-slate-500 font-mono">
                Select a toolset from the left rail to view member tools and parameter schemas.
              </div>
            )}
          </DetailColumn>
        </MasterDetail>
      </div>
    </div>
  );
}
