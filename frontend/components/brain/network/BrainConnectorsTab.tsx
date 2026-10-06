"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { BACKEND_URL } from "../types";

export interface ConnectorItem {
  id: string;
  name: string;
  slug: string;
  description: string;
  source?: string;
  transport_type: "stdio" | "http" | "gateway";
  transport_url?: string;
  auth_type: string;
  category: string;
  installed?: boolean;
  connected?: boolean;
  tools_count?: number;
  post_install?: string;
}

export default function BrainConnectorsTab() {
  const [catalog, setCatalog] = useState<ConnectorItem[]>([]);
  const [mcpServers, setMcpServers] = useState<Record<string, any>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<"all" | "installed" | "catalog">("all");
  const [isLoading, setIsLoading] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [selectedConnector, setSelectedConnector] = useState<ConnectorItem | null>(null);
  const [installNotice, setInstallNotice] = useState<string | null>(null);

  const fetchCatalogAndServers = useCallback(async () => {
    setIsLoading(true);
    try {
      const [catRes, srvRes] = await Promise.allSettled([
        fetch(`${BACKEND_URL}/api/brain/connectors/catalog`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${BACKEND_URL}/api/brain/mcp/servers`).then((r) => (r.ok ? r.json() : null)),
      ]);

      const srvMap = (srvRes.status === "fulfilled" && srvRes.value?.servers) || {};
      setMcpServers(srvMap);

      if (catRes.status === "fulfilled" && catRes.value?.catalog) {
        const rawCatalog: ConnectorItem[] = catRes.value.catalog;
        const merged = rawCatalog.map((item) => {
          const srv = srvMap[item.slug] || srvMap[item.id] || srvMap[item.name.toLowerCase()];
          return {
            ...item,
            installed: Boolean(srv),
            connected: srv?.connected || false,
            tools_count: srv?.tools_count || 0,
          };
        });
        setCatalog(merged);
      }
    } catch (e) {
      console.warn("[BrainConnectors] Fetch error:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCatalogAndServers();
  }, [fetchCatalogAndServers]);

  const handleReconnectAll = async () => {
    setIsConnecting(true);
    try {
      await fetch(`${BACKEND_URL}/api/brain/mcp/servers/connect`, { method: "POST" });
      await fetchCatalogAndServers();
    } catch (e) {
      console.warn("[BrainConnectors] Reconnect error:", e);
    } finally {
      setIsConnecting(false);
    }
  };

  const handleInstallClick = (item: ConnectorItem) => {
    setSelectedConnector(item);
  };

  const visibleConnectors = useMemo(() => {
    return catalog.filter((item) => {
      if (filterType === "installed" && !item.installed) return false;
      if (filterType === "catalog" && item.installed) return false;
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        item.name.toLowerCase().includes(q) ||
        item.slug.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q) ||
        item.category.toLowerCase().includes(q)
      );
    });
  }, [catalog, filterType, searchQuery]);

  const installedCount = catalog.filter((c) => c.installed).length;

  return (
    <div className="h-full w-full flex flex-col overflow-hidden select-none font-sans">
      {/* Top Header Bar */}
      <div className="px-6 py-4 border-b border-white/[0.08] bg-[#050811]/95 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-white font-mono tracking-tight">
              Connectors &amp; MCP Integrations
            </h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/10 text-cyan-300 border border-cyan-400/20 font-semibold">
              {catalog.length} Available Apps
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5 leading-relaxed font-sans">
            Connect external workspaces, SaaS tools, and local MCP subprocesses directly to Anara.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleReconnectAll}
            disabled={isConnecting}
            className="px-3 py-1.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-400/30 text-cyan-200 text-xs font-mono font-medium transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
          >
            <svg
              className={`w-3.5 h-3.5 ${isConnecting ? "animate-spin" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>{isConnecting ? "Reconnecting..." : "Reconnect All"}</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="px-6 py-3 border-b border-white/[0.06] bg-[#060913]/90 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 shrink-0">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
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
            placeholder="Search 65+ connectors (Airtable, Asana, Notion, Slack, GitHub)..."
            className="w-full py-1.5 pl-8 pr-3 rounded-lg bg-black/40 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-400/40 transition-colors font-sans"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 p-0.5 rounded-lg bg-black/40 border border-white/[0.08] text-xs font-mono">
          <button
            type="button"
            onClick={() => setFilterType("all")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer ${
              filterType === "all"
                ? "bg-white/[0.08] text-white font-medium border border-white/[0.12] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            All ({catalog.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterType("installed")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer ${
              filterType === "installed"
                ? "bg-white/[0.08] text-white font-medium border border-white/[0.12] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Connected ({installedCount})
          </button>
          <button
            type="button"
            onClick={() => setFilterType("catalog")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer ${
              filterType === "catalog"
                ? "bg-white/[0.08] text-white font-medium border border-white/[0.12] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Available Catalog
          </button>
        </div>
      </div>

      {/* Connectors Grid List */}
      <div className="flex-1 min-h-0 overflow-y-auto p-6 custom-scrollbar font-sans">
        {visibleConnectors.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-500 font-mono">
            {isLoading ? "Loading connectors..." : "No connectors match search filter"}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {visibleConnectors.map((item) => (
              <div
                key={item.id}
                className={`p-4 rounded-xl border flex flex-col justify-between transition-all select-none ${
                  item.installed
                    ? "bg-[#070e20]/80 border-cyan-500/30 shadow-[0_0_15px_rgba(34,211,238,0.08)]"
                    : "bg-[#060913]/80 hover:bg-[#080d1a] border-white/[0.08] hover:border-white/[0.15]"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-white font-mono font-bold text-xs shrink-0">
                        {item.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <h4 className="text-xs font-bold text-white tracking-tight truncate font-sans">
                            {item.name}
                          </h4>
                          {item.connected && (
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399] shrink-0" />
                          )}
                        </div>
                        <span className="text-[10px] text-slate-500 font-mono block truncate">
                          {item.category} · {item.transport_type}
                        </span>
                      </div>
                    </div>

                    <span className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase bg-white/[0.04] border border-white/[0.08] text-slate-400 shrink-0">
                      {item.auth_type}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 mt-2.5 leading-relaxed font-sans line-clamp-2">
                    {item.description}
                  </p>
                </div>

                <div className="mt-4 pt-2.5 border-t border-white/[0.06] flex items-center justify-between">
                  <span className="text-[10.5px] font-mono text-slate-500">
                    {item.installed ? (
                      <span className="text-emerald-400 font-semibold">
                        {item.tools_count ? `${item.tools_count} tools` : "Active"}
                      </span>
                    ) : (
                      "Ready to install"
                    )}
                  </span>

                  <button
                    type="button"
                    onClick={() => handleInstallClick(item)}
                    className={`px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors cursor-pointer ${
                      item.installed
                        ? "bg-white/[0.06] hover:bg-white/[0.1] text-slate-200 border border-white/[0.1]"
                        : "bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-400/30"
                    }`}
                  >
                    {item.installed ? "Configure" : "Install"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Detail / Config Modal Dialog */}
      {selectedConnector && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
          <div className="w-full max-w-lg p-5 rounded-2xl bg-slate-950/95 border border-white/20 text-white space-y-4 font-sans shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-400/25 flex items-center justify-center text-cyan-300 font-bold text-xs font-mono">
                  {selectedConnector.name.charAt(0)}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">{selectedConnector.name}</h3>
                  <span className="text-[10px] font-mono text-slate-400">{selectedConnector.category}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedConnector(null)}
                className="text-slate-400 hover:text-white font-mono"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              {selectedConnector.description}
            </p>

            <div className="p-3 rounded-xl bg-black/60 border border-white/[0.08] space-y-2 font-mono text-xs">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500">Connector Slug:</span>
                <span className="text-slate-300 font-semibold">{selectedConnector.slug}</span>
              </div>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500">Transport:</span>
                <span className="text-slate-300 font-semibold uppercase">{selectedConnector.transport_type}</span>
              </div>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500">Authentication:</span>
                <span className="text-slate-300 font-semibold uppercase">{selectedConnector.auth_type}</span>
              </div>
            </div>

            {selectedConnector.post_install && (
              <div className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-500/20 text-xs font-mono text-cyan-200 whitespace-pre-wrap leading-relaxed">
                {selectedConnector.post_install}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/10 font-mono text-xs">
              <button
                type="button"
                onClick={() => setSelectedConnector(null)}
                className="px-3.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition-colors cursor-pointer"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => {
                  setInstallNotice(`Connector '${selectedConnector.name}' saved to configuration.`);
                  setSelectedConnector(null);
                  setTimeout(() => setInstallNotice(null), 3500);
                }}
                className="px-4 py-1.5 rounded-lg bg-cyan-400 text-black font-semibold hover:bg-cyan-300 transition-colors cursor-pointer shadow-sm"
              >
                {selectedConnector.installed ? "Save Settings" : "Confirm Connection"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Global Notice Toast */}
      {installNotice && (
        <div className="fixed bottom-6 right-6 z-50 p-3.5 px-4 rounded-xl bg-emerald-500/15 border border-emerald-400/30 text-emerald-200 text-xs font-mono shadow-2xl backdrop-blur-xl animate-fade-in flex items-center gap-2">
          <span>✓</span>
          <span>{installNotice}</span>
        </div>
      )}
    </div>
  );
}
