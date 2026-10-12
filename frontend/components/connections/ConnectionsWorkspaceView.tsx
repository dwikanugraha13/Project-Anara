"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { ConnectionPlatform, ConnectionFilter, ConnectionScope } from "./types";
import { DEFAULT_PLATFORMS } from "./defaultPlatforms";
import { ConnectionListPane } from "./ConnectionListPane";
import { ConnectionDetailPane } from "./ConnectionDetailPane";
import { WhatsAppQrModal } from "./sub-components/WhatsAppQrModal";
import { anaraApi } from "@/lib/apiClient";
import { BACKEND_URL } from "@/components/brain/types";

export interface ConnectionsWorkspaceViewProps {
  onClose?: () => void;
}

export default function ConnectionsWorkspaceView({ onClose }: ConnectionsWorkspaceViewProps) {
  const [platforms, setPlatforms] = useState<ConnectionPlatform[]>(DEFAULT_PLATFORMS);
  const [selectedPlatformId, setSelectedPlatformId] = useState<string>("telegram");
  const [selectedScope, setSelectedScope] = useState<ConnectionScope>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeFilter, setActiveFilter] = useState<ConnectionFilter>("all");
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isWaModalOpen, setIsWaModalOpen] = useState<boolean>(false);

  // ── Sync Platform Statuses from Backend ──
  const syncPlatformStatuses = useCallback(async () => {
    try {
      // 1. Check for Unified Endpoint if available
      try {
        const unifiedRes = await fetch(`${BACKEND_URL}/api/integrations/connections`);
        if (unifiedRes.ok) {
          const unifiedData = await unifiedRes.json();
          if (Array.isArray(unifiedData.connections)) {
            setPlatforms((prev) =>
              prev.map((p) => {
                const match = unifiedData.connections.find((u: { id?: string }) => u?.id === p.id);
                if (match) {
                  return {
                    ...p,
                    status: match.status || p.status,
                    enabled: match.enabled !== undefined ? match.enabled : p.enabled,
                    config: { ...p.config, ...match.config },
                  };
                }
                return p;
              })
            );
            return;
          }
        }
      } catch {
        // Unified not available yet, fall through to granular endpoints
      }

      // 2. Fallback to granular endpoints (Telegram, WhatsApp, Google)
      // Telegram
      const tgData = await anaraApi.integrations.getTelegramStatus().catch(() => null);
      // WhatsApp
      const waRes = await fetch(`${BACKEND_URL}/api/integrations/whatsapp/status`).catch(() => null);
      const waData = waRes && waRes.ok ? await waRes.json().catch(() => null) : null;
      const waCfgRes = await fetch(`${BACKEND_URL}/api/integrations/whatsapp/config`).catch(() => null);
      const waCfg = waCfgRes && waCfgRes.ok ? await waCfgRes.json().catch(() => null) : null;
      // Google
      const gRes = await fetch(`${BACKEND_URL}/api/integrations/google/status`).catch(() => null);
      const gData = gRes && gRes.ok ? await gRes.json().catch(() => null) : null;

      setPlatforms((prev) =>
        prev.map((p) => {
          if (p.id === "telegram" && tgData) {
            const isConnected = tgData.status === "connected";
            return {
              ...p,
              status: isConnected ? "connected" : "disconnected",
              config: {
                ...p.config,
                token: tgData.bot ? "••••••••••••••••" : p.config?.token,
                chat_id: tgData.default_chat_id || p.config?.chat_id || "",
                admin_ids: tgData.admin_ids || p.config?.admin_ids || "",
              },
            };
          }
          if (p.id === "whatsapp" && waData) {
            const isConnected = Boolean(waData.user) && (waData.status === "connected" || !waData.status);
            return {
              ...p,
              status: isConnected ? "connected" : waData.status === "connecting" ? "connecting" : "disconnected",
              config: {
                ...p.config,
                allowed_numbers: waCfg?.allowed_numbers || p.config?.allowed_numbers || "",
              },
            };
          }
          if (p.id === "google" && gData) {
            return {
              ...p,
              status: gData.status === "connected" ? "connected" : "disconnected",
              config: {
                ...p.config,
                email: gData.email || p.config?.email || "",
              },
            };
          }
          return p;
        })
      );
    } catch (e) {
      console.warn("[Connections] status sync error:", e);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      void syncPlatformStatuses();
    }, 0);
    return () => clearTimeout(timer);
  }, [syncPlatformStatuses]);

  // ── Handle Save Configuration ──
  const handleSaveConfig = async (
    platformId: string,
    config: Record<string, unknown>,
    enabled: boolean
  ) => {
    setIsSaving(true);
    try {
      // 1. Try unified endpoint first
      try {
        const unifiedRes = await fetch(`${BACKEND_URL}/api/integrations/connections/${platformId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ config, enabled }),
        });
        if (unifiedRes.ok) {
          await syncPlatformStatuses();
          setIsSaving(false);
          return;
        }
      } catch {
        // Fallback to granular endpoint
      }

      // 2. Granular endpoints fallback
      const getStr = (val: unknown) => (typeof val === "string" ? val.trim() : undefined);
      if (platformId === "telegram") {
        await anaraApi.integrations.saveTelegramConfig({
          token: getStr(config.token),
          bot_token: getStr(config.token),
          chat_id: getStr(config.chat_id),
          default_chat_id: getStr(config.chat_id),
          admin_ids: getStr(config.admin_ids),
          telegram_admin_ids: getStr(config.admin_ids),
        });
      } else if (platformId === "whatsapp") {
        await fetch(`${BACKEND_URL}/api/integrations/whatsapp/config`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ allowed_numbers: getStr(config.allowed_numbers) || "" }),
        });
      } else if (platformId === "google") {
        await fetch(`${BACKEND_URL}/api/integrations/google/config`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: getStr(config.email) || "" }),
        });
      }

      // Update local state
      setPlatforms((prev) =>
        prev.map((p) =>
          p.id === platformId
            ? { ...p, config: { ...p.config, ...config }, enabled }
            : p
        )
      );

      await syncPlatformStatuses();
    } catch (err) {
      console.error("[Connections] save error:", err);
    } finally {
      setIsSaving(false);
    }
  };

  // ── Handle Quick Setup Trigger ──
  const handleTriggerQuickSetup = (platformId: string) => {
    if (platformId === "whatsapp") {
      setIsWaModalOpen(true);
    } else if (platformId === "telegram") {
      // Direct focus / test
      syncPlatformStatuses();
    } else if (platformId === "google") {
      const email = prompt("Enter your Google Account email to link with Anara:");
      if (email) {
        handleSaveConfig("google", { email }, true);
      }
    } else if (platformId === "spotify") {
      alert("Spotify Desktop integration is active. Try saying 'Play Music' via voice or chat!");
    } else {
      alert(`Quick setup initiated for ${platformId}. Check the required fields below.`);
    }
  };

  // ── Filtered Platforms ──
  const filteredPlatforms = useMemo(() => {
    return platforms.filter((p) => {
      // 1. Search Query
      if (searchQuery.trim().length > 0) {
        const q = searchQuery.toLowerCase().trim();
        const matchesName = p.name.toLowerCase().includes(q);
        const matchesDesc = p.description.toLowerCase().includes(q);
        const matchesCategory = p.category.toLowerCase().includes(q);
        if (!matchesName && !matchesDesc && !matchesCategory) {
          return false;
        }
      }

      // 2. Connection Status Filter
      if (activeFilter === "connected" && p.status !== "connected") {
        return false;
      }
      if (activeFilter === "inactive" && p.status === "connected") {
        return false;
      }

      // 3. Scope Filter
      if (selectedScope !== "all" && !p.appliesTo.includes(selectedScope)) {
        return false;
      }

      return true;
    });
  }, [platforms, searchQuery, activeFilter, selectedScope]);

  const selectedPlatform = useMemo(() => {
    return platforms.find((p) => p.id === selectedPlatformId) || platforms[0];
  }, [platforms, selectedPlatformId]);

  return (
    <div className="flex-1 min-w-0 h-full flex flex-col overflow-hidden bg-[#060913] select-none font-sans relative">
      {/* ── Top Workspace Header ── */}
      <header className="h-[48px] px-4 border-b border-white/[0.08] bg-[#070c18]/90 backdrop-blur-2xl flex items-center justify-between shrink-0 z-20 gap-4">
        {/* Left: Title & Badge */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
            <h3 className="text-xs sm:text-sm font-semibold text-white font-mono tracking-tight">
              Connections
            </h3>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300 hidden md:inline">
            Omnichannel &amp; Platforms
          </span>
        </div>

        {/* Center: Search Bar (Try "discord") */}
        <div className="flex-1 max-w-md mx-2">
          <div className="relative flex items-center">
            <span className="absolute left-3 text-slate-500 pointer-events-none">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </span>
            <input
              type="text"
              placeholder='Try "discord"'
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-8 py-1.5 rounded-xl bg-black/40 border border-white/10 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-400/60 font-mono transition-all"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2.5 text-slate-500 hover:text-white text-xs cursor-pointer"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Right: Filter Segmented Control & Back to Chat */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Segmented Filter: All | Connected | Inactive */}
          <div className="flex items-center p-0.5 rounded-lg bg-black/40 border border-white/10 text-xs font-mono">
            {(["all", "connected", "inactive"] as ConnectionFilter[]).map((f) => {
              const isActive = activeFilter === f;
              return (
                <button
                  key={f}
                  type="button"
                  onClick={() => setActiveFilter(f)}
                  className={`px-2.5 py-1 rounded-md text-[11px] capitalize transition-all cursor-pointer ${
                    isActive
                      ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30 font-medium shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {f}
                </button>
              );
            })}
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-mono text-slate-300 hover:text-white transition-all cursor-pointer"
              title="Return to Chat Conversation"
            >
              <span className="hidden sm:inline">Back to Chat</span>
              <span className="text-slate-500 font-bold">✕</span>
            </button>
          )}
        </div>
      </header>

      {/* ── Main View Content (2-Pane Split) ── */}
      <main className="flex-1 min-h-0 flex overflow-hidden">
        {/* Left / Middle Pane: Platform Selector List */}
        <ConnectionListPane
          platforms={filteredPlatforms}
          selectedPlatformId={selectedPlatformId}
          onSelectPlatform={setSelectedPlatformId}
          selectedScope={selectedScope}
          onSelectScope={setSelectedScope}
        />

        {/* Right Pane: Configuration & Quick Setup Detail */}
        {selectedPlatform ? (
          <ConnectionDetailPane
            key={selectedPlatform.id}
            platform={selectedPlatform}
            onSaveConfig={handleSaveConfig}
            onTriggerQuickSetup={handleTriggerQuickSetup}
            isSaving={isSaving}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center text-xs text-slate-500 font-mono">
            Select a connection platform to view settings.
          </div>
        )}
      </main>

      {/* ── WhatsApp QR Pairing Modal ── */}
      <WhatsAppQrModal
        isOpen={isWaModalOpen}
        onClose={() => setIsWaModalOpen(false)}
        onConnected={syncPlatformStatuses}
      />
    </div>
  );
}
