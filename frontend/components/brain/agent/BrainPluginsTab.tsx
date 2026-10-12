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
  enabled?: boolean;
  desktop_enabled?: boolean;
  agent_enabled?: boolean;
  default_enabled?: boolean;
  source?: "bundled" | "agent" | "user" | "git" | "catalog";
  has_desktop_half?: boolean;
  has_agent_half?: boolean;
  file?: string;
  installed?: boolean;
  key?: string;
}

// Manageable bundled plugins matching reference desktop standard
const MANAGEABLE_BUNDLED_KEYS = new Set(["disk-cleanup", "security-guidance", "kanban", "anara-bots"]);

export function isDesktopRelevantPlugin(item: PluginItem): boolean {
  if (item.source === "bundled") {
    return MANAGEABLE_BUNDLED_KEYS.has(item.id || item.name);
  }
  return true;
}

export default function BrainPluginsTab() {
  const [plugins, setPlugins] = useState<PluginItem[]>([]);
  const [catalog, setCatalog] = useState<PluginItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRescanning, setIsRescanning] = useState(false);
  const [isOpeningFolder, setIsOpeningFolder] = useState(false);

  // Toggle & action tracking
  const [busyPluginId, setBusyPluginId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  // Bottom Catalog Drawer state (1:1 reference: collapsed by default)
  const [isCatalogOpen, setIsCatalogOpen] = useState(false);
  const [installingCatId, setInstallingCatId] = useState<string | null>(null);

  // Git Install Modal state
  const [isGitModalOpen, setIsGitModalOpen] = useState(false);
  const [gitRepo, setGitRepo] = useState("");
  const [gitBranch, setGitBranch] = useState("");
  const [isInstallingGit, setIsInstallingGit] = useState(false);

  // Plugin Settings / Inspector Modal
  const [inspectingPlugin, setInspectingPlugin] = useState<PluginItem | null>(null);

  const showNotice = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 3500);
  };

  const showError = (msg: string) => {
    setErrorNotice(msg);
    setTimeout(() => setErrorNotice(null), 4500);
  };

  const fetchPluginsAndCatalog = useCallback(async () => {
    setIsLoading(true);
    try {
      const [plugRes, catRes] = await Promise.allSettled([
        fetch(`${BACKEND_URL}/api/brain/plugins`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${BACKEND_URL}/api/brain/plugins/catalog`).then((r) => (r.ok ? r.json() : null)),
      ]);

      if (plugRes.status === "fulfilled" && plugRes.value?.plugins) {
        setPlugins(plugRes.value.plugins);
      }
      if (catRes.status === "fulfilled" && catRes.value?.catalog) {
        setCatalog(catRes.value.catalog);
      }
    } catch (e) {
      console.warn("[BrainPlugins] Error fetching plugins:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPluginsAndCatalog();
  }, [fetchPluginsAndCatalog]);

  // Dual Switch Toggle (Desktop vs Agent)
  const handleToggle = async (plugin: PluginItem, target: "desktop" | "agent") => {
    const actionKey = `${target}-${plugin.id}`;
    setBusyPluginId(actionKey);

    const currentVal = target === "desktop" ? Boolean(plugin.desktop_enabled) : Boolean(plugin.agent_enabled);
    const nextVal = !currentVal;

    // Optimistic UI update
    setPlugins((prev) =>
      prev.map((p) => {
        if (p.id !== plugin.id) return p;
        return {
          ...p,
          [target === "desktop" ? "desktop_enabled" : "agent_enabled"]: nextVal,
          enabled: target === "agent" ? nextVal : p.enabled,
        };
      })
    );

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/plugins/${encodeURIComponent(plugin.id)}/toggle`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target, enabled: nextVal }),
      });

      if (res.ok) {
        showNotice(`Plugin '${plugin.title}' ${target} switch ${nextVal ? "enabled" : "disabled"}.`);
      } else {
        showError(`Failed to toggle ${target} for '${plugin.title}'.`);
        await fetchPluginsAndCatalog();
      }
    } catch {
      showError(`Network error toggling ${target}.`);
      await fetchPluginsAndCatalog();
    } finally {
      setBusyPluginId(null);
    }
  };

  // Open Plugins Directory
  const handleOpenFolder = async () => {
    setIsOpeningFolder(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/plugins/open-folder`, { method: "POST" });
      if (res.ok) {
        showNotice("Opened plugins directory in Explorer.");
      } else {
        showError("Could not reveal plugins directory on host.");
      }
    } catch {
      showError("Failed to trigger folder reveal.");
    } finally {
      setIsOpeningFolder(false);
    }
  };

  // Rescan plugins on disk
  const handleRescan = async () => {
    setIsRescanning(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/plugins/rescan`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setPlugins(data.plugins || []);
        showNotice("Rescanned plugins directory.");
      } else {
        showError("Failed to rescan plugins directory.");
      }
    } catch {
      showError("Network error rescanning plugins.");
    } finally {
      setIsRescanning(false);
    }
  };

  // Install from Git
  const handleGitInstallSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gitRepo.trim()) return;

    setIsInstallingGit(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/plugins/install`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo: gitRepo.trim(), branch: gitBranch.trim() || undefined }),
      });

      if (res.ok) {
        showNotice(`Successfully installed plugin from ${gitRepo.trim()}.`);
        setIsGitModalOpen(false);
        setGitRepo("");
        setGitBranch("");
        await fetchPluginsAndCatalog();
      } else {
        const err = await res.json().catch(() => ({}));
        showError(err.detail || "Failed to install plugin from Git.");
      }
    } catch (err) {
      showError(`Install error: ${String(err)}`);
    } finally {
      setIsInstallingGit(false);
    }
  };

  // Install from Catalog
  const handleInstallCatalogPlugin = async (catItem: PluginItem) => {
    setInstallingCatId(catItem.id);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/plugins/install`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: catItem.id, catalog_id: catItem.id }),
      });

      if (res.ok) {
        showNotice(`Added '${catItem.title}' to this Agent.`);
        await fetchPluginsAndCatalog();
      } else {
        const err = await res.json().catch(() => ({}));
        showError(err.detail || `Could not install '${catItem.title}'.`);
      }
    } catch (err) {
      showError(`Error adding catalog plugin: ${String(err)}`);
    } finally {
      setInstallingCatId(null);
    }
  };

  // Uninstall plugin
  const handleUninstallPlugin = async (plugin: PluginItem) => {
    if (!confirm(`Are you sure you want to uninstall '${plugin.title}'?`)) return;

    setBusyPluginId(`uninstall-${plugin.id}`);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/plugins/${encodeURIComponent(plugin.id)}`, {
        method: "DELETE",
      });

      if (res.ok) {
        showNotice(`Uninstalled '${plugin.title}'.`);
        await fetchPluginsAndCatalog();
      } else {
        const err = await res.json().catch(() => ({}));
        showError(err.detail || `Failed to uninstall '${plugin.title}'.`);
      }
    } catch (err) {
      showError(`Uninstall error: ${String(err)}`);
    } finally {
      setBusyPluginId(null);
    }
  };

  // Manageable plugins matching reference
  const relevantPlugins = useMemo(() => {
    return plugins.filter(isDesktopRelevantPlugin);
  }, [plugins]);

  return (
    <div className="h-full w-full flex flex-col overflow-hidden select-none font-sans bg-[#030712] text-slate-200">
      {/* 1. Top Header Bar (1:1 Desktop Reference Standard: clean blurb + action buttons) */}
      <div className="px-4 py-2.5 border-b border-white/[0.08] bg-[#050811]/95 flex items-center justify-between gap-3 shrink-0">
        <p className="text-[11.5px] text-slate-400 font-sans leading-normal min-w-0 flex-1">
          Plugins extend Project Anara with tools, background processes, channels, and custom UI.
        </p>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={() => setIsGitModalOpen(true)}
            className="px-2.5 py-1 rounded-md bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.1] text-slate-200 text-xs font-mono font-medium transition-colors cursor-pointer shadow-sm"
          >
            Install from Git
          </button>

          <button
            type="button"
            onClick={handleOpenFolder}
            disabled={isOpeningFolder}
            title="Open plugins folder (%LOCALAPPDATA%\\anara\\plugins)"
            className="p-1.5 rounded-md bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.1] text-slate-300 hover:text-white transition-colors cursor-pointer shadow-sm"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </button>

          <button
            type="button"
            onClick={handleRescan}
            disabled={isRescanning}
            title="Rescan plugins directory"
            className="p-1.5 rounded-md bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.1] text-slate-300 hover:text-white transition-colors cursor-pointer shadow-sm"
          >
            <svg
              className={`w-3.5 h-3.5 ${isRescanning ? "animate-spin text-cyan-400" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* 2. Table Column Header (1:1 Desktop Reference Standard) */}
      <div className="flex items-center gap-3 border-b border-white/[0.08] bg-[#060913]/90 px-4 py-1.5 text-[10.5px] font-mono text-slate-400 shrink-0">
        <div className="min-w-0 flex-1 font-semibold uppercase tracking-wider" />

        {/* Desktop Switch Column Header */}
        <div className="flex w-20 shrink-0 items-center justify-center gap-1 font-medium text-slate-400">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <span>Desktop</span>
        </div>

        {/* Agent Switch Column Header */}
        <div className="flex w-20 shrink-0 items-center justify-center gap-1 font-medium text-slate-400">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          <span>Agent</span>
        </div>
      </div>

      {/* 3. Package Rows Table (1:1 Reference Standard) */}
      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar">
        {relevantPlugins.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-500 font-mono">
            {isLoading ? "Scanning plugins..." : "No plugins yet. Install a plugin below."}
          </div>
        ) : (
          <div className="divide-y divide-white/[0.06]">
            {relevantPlugins.map((item) => {
              const isRemovable = item.source === "user" || item.source === "git";
              const hasDesktop = item.has_desktop_half ?? false;
              const hasAgent = item.has_agent_half ?? true;
              const isBusyDesktop = busyPluginId === `desktop-${item.id}`;
              const isBusyAgent = busyPluginId === `agent-${item.id}`;

              return (
                <div
                  key={item.id}
                  className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.02] transition-colors"
                >
                  {/* Left Column: Package Details & Fixed Actions */}
                  <div className="min-w-0 flex-1 flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[12.5px] font-medium text-white tracking-tight font-sans">
                          {item.title}
                        </span>
                        {item.version && (
                          <span className="text-[10px] text-slate-500 font-mono">
                            v{item.version}
                          </span>
                        )}
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-white/[0.04] text-slate-400 border border-white/[0.08]">
                          {item.source || "bundled"}
                        </span>
                        {item.category && (
                          <span className="text-[9.5px] font-mono text-slate-500 capitalize">
                            {item.category}
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed font-sans line-clamp-1">
                        {item.description}
                      </p>
                    </div>

                    {/* Fixed Action Icons */}
                    <div className="flex items-center gap-0.5 shrink-0 pt-0.5">
                      {item.file && (
                        <button
                          type="button"
                          onClick={() => handleOpenFolder()}
                          className="p-1 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
                          title="Reveal folder"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                          </svg>
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={() => setInspectingPlugin(item)}
                        className="p-1 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
                        title="Plugin Settings"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </button>

                      {isRemovable && (
                        <button
                          type="button"
                          onClick={() => handleUninstallPlugin(item)}
                          className="p-1 text-slate-500 hover:text-rose-400 transition-colors cursor-pointer"
                          title="Uninstall plugin"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Desktop Switch Cell */}
                  <div className="w-20 shrink-0 flex items-center justify-center">
                    {hasDesktop ? (
                      <div
                        className="cursor-pointer"
                        onClick={() => handleToggle(item, "desktop")}
                        title={item.desktop_enabled ? "Disable desktop hook" : "Enable desktop hook"}
                      >
                        <div
                          className={`w-6.5 h-3.5 rounded-full p-0.5 transition-colors duration-200 relative ${
                            item.desktop_enabled ? "bg-cyan-500" : "bg-slate-700/80"
                          } ${isBusyDesktop ? "opacity-50" : ""}`}
                        >
                          <div
                            className={`w-2.5 h-2.5 rounded-full bg-white shadow-sm transition-transform duration-200 ${
                              item.desktop_enabled ? "translate-x-3" : "translate-x-0"
                            }`}
                          />
                        </div>
                      </div>
                    ) : (
                      <span className="font-mono text-slate-600 text-xs">—</span>
                    )}
                  </div>

                  {/* Agent Switch Cell */}
                  <div className="w-20 shrink-0 flex items-center justify-center">
                    {hasAgent ? (
                      <div
                        className="cursor-pointer"
                        onClick={() => handleToggle(item, "agent")}
                        title={item.agent_enabled ? "Disable agent tools" : "Enable agent tools"}
                      >
                        <div
                          className={`w-6.5 h-3.5 rounded-full p-0.5 transition-colors duration-200 relative ${
                            item.agent_enabled ? "bg-white/90" : "bg-slate-700/80"
                          } ${isBusyAgent ? "opacity-50" : ""}`}
                        >
                          <div
                            className={`w-2.5 h-2.5 rounded-full bg-black shadow-sm transition-transform duration-200 ${
                              item.agent_enabled ? "translate-x-3" : "translate-x-0"
                            }`}
                          />
                        </div>
                      </div>
                    ) : (
                      <span className="font-mono text-slate-600 text-xs">—</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Bottom Collapsible Catalog Drawer (1:1 Reference Standard: collapsed by default) */}
      <section className="relative flex flex-col border-t border-white/[0.08] bg-[#050811]/95 shrink-0">
        <div className="flex items-center justify-between px-4 py-2">
          <span className="text-[10px] font-mono font-medium tracking-wide uppercase text-slate-500">
            Plugin Catalog
          </span>

          <button
            type="button"
            onClick={() => setIsCatalogOpen(!isCatalogOpen)}
            className="text-[11px] font-mono text-slate-400 hover:text-white cursor-pointer transition-colors"
          >
            {isCatalogOpen ? "Hide catalog" : "Browse catalog"}
          </button>
        </div>

        {isCatalogOpen && (
          <div className="p-3 border-t border-white/[0.06] bg-black/40 max-h-56 overflow-y-auto custom-scrollbar">
            <div className="divide-y divide-white/[0.04]">
              {catalog.map((catItem) => {
                const isInstalled = plugins.some((p) => p.id === catItem.id);
                const isInstalling = installingCatId === catItem.id;

                return (
                  <div
                    key={catItem.id}
                    className="py-2 px-1 flex items-center justify-between gap-3 text-xs font-mono"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{catItem.title}</span>
                        <span className="text-[10px] text-slate-500">v{catItem.version}</span>
                        <span className="text-[9.5px] text-slate-400 capitalize">{catItem.category}</span>
                      </div>
                      <p className="text-[11px] text-slate-400 font-sans truncate mt-0.5">
                        {catItem.description}
                      </p>
                    </div>

                    <div className="shrink-0">
                      {isInstalled ? (
                        <span className="text-[10.5px] font-mono text-emerald-400">
                          ✓ Installed
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleInstallCatalogPlugin(catItem)}
                          disabled={isInstalling}
                          className="px-2.5 py-1 rounded text-[11px] font-mono bg-white/[0.08] hover:bg-white/[0.14] text-white border border-white/20 transition-colors cursor-pointer"
                        >
                          {isInstalling ? "Adding..." : "+ Add to this Agent"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>

      {/* 5. Git Install Modal */}
      {isGitModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="w-full max-w-md p-5 rounded-2xl bg-[#070c18] border border-white/[0.15] text-white space-y-4 font-sans shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <h3 className="text-sm font-bold text-white font-mono">Install Plugin from Git</h3>
              <button
                type="button"
                onClick={() => setIsGitModalOpen(false)}
                className="text-slate-400 hover:text-white font-mono text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleGitInstallSubmit} className="space-y-3">
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">
                  Repository URL <span className="text-cyan-400">*</span>
                </label>
                <input
                  required
                  value={gitRepo}
                  onChange={(e) => setGitRepo(e.target.value)}
                  placeholder="https://github.com/user/plugin-name"
                  className="w-full py-1.5 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">
                  Branch / Tag / Ref (Optional)
                </label>
                <input
                  value={gitBranch}
                  onChange={(e) => setGitBranch(e.target.value)}
                  placeholder="main, v1.0, or commit SHA"
                  className="w-full py-1.5 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setIsGitModalOpen(false)}
                  className="px-3 py-1.5 rounded-lg text-xs font-mono text-slate-400 hover:text-white transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isInstallingGit || !gitRepo.trim()}
                  className="px-4 py-1.5 rounded-lg text-xs font-mono font-medium bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 border border-cyan-400/40 transition-colors cursor-pointer disabled:opacity-50"
                >
                  {isInstallingGit ? "Installing..." : "Install"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 6. Plugin Inspector / Settings Modal */}
      {inspectingPlugin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="w-full max-w-lg p-5 rounded-2xl bg-[#070c18] border border-white/[0.15] text-white space-y-4 font-sans shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <div>
                <h3 className="text-sm font-bold text-white font-mono">{inspectingPlugin.title}</h3>
                <span className="text-[10px] text-slate-500 font-mono">{inspectingPlugin.id} · v{inspectingPlugin.version}</span>
              </div>
              <button
                type="button"
                onClick={() => setInspectingPlugin(null)}
                className="text-slate-400 hover:text-white font-mono text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2 text-xs font-mono text-slate-300">
              <div className="p-2.5 rounded-lg bg-black/40 border border-white/[0.06] space-y-1">
                <div><span className="text-slate-500">Category:</span> {inspectingPlugin.category}</div>
                <div><span className="text-slate-500">Author:</span> {inspectingPlugin.author}</div>
                <div><span className="text-slate-500">Provenance:</span> {inspectingPlugin.source || "bundled"}</div>
                {inspectingPlugin.file && (
                  <div className="truncate"><span className="text-slate-500">Path:</span> {inspectingPlugin.file}</div>
                )}
              </div>
              <p className="text-xs text-slate-300 font-sans leading-relaxed pt-1">
                {inspectingPlugin.description}
              </p>
            </div>

            <div className="flex items-center justify-end pt-2 border-t border-white/[0.08]">
              <button
                type="button"
                onClick={() => setInspectingPlugin(null)}
                className="px-3 py-1.5 rounded-lg text-xs font-mono bg-white/[0.06] text-white hover:bg-white/[0.1] border border-white/[0.1] cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 7. Action Toast Notification */}
      {notice && (
        <div className="fixed bottom-6 right-6 z-50 p-3 px-4 rounded-xl bg-emerald-500/15 border border-emerald-400/30 text-emerald-200 text-xs font-mono shadow-2xl backdrop-blur-xl animate-fade-in flex items-center gap-2">
          <span>✓</span>
          <span>{notice}</span>
        </div>
      )}
      {errorNotice && (
        <div className="fixed bottom-6 right-6 z-50 p-3 px-4 rounded-xl bg-rose-500/15 border border-rose-400/30 text-rose-200 text-xs font-mono shadow-2xl backdrop-blur-xl animate-fade-in flex items-center gap-2">
          <span>✕</span>
          <span>{errorNotice}</span>
        </div>
      )}
    </div>
  );
}
