"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { BACKEND_URL, BrandIcon, ProviderItem } from "../types";
import ProviderDetailView from "./providers/ProviderDetailView";
import CustomProviderModal from "./providers/CustomProviderModal";
import CodexOAuthModal, { OAuthSessionData } from "./providers/CodexOAuthModal";
interface BrainProvidersTabProps {
  onRefreshAll?: () => void;
}

export default function BrainProvidersTab({ onRefreshAll }: BrainProvidersTabProps) {
  const [providersList, setProvidersList] = useState<ProviderItem[]>([]);
  const [activeAiModelId, setActiveAiModelId] = useState<string>("gemini-3.1-flash-live-preview");
  const [providerKeyInputs, setProviderKeyInputs] = useState<Record<string, string>>({});
  const [providerLabelInputs, setProviderLabelInputs] = useState<Record<string, string>>({});
  const [isConnectingProvider, setIsConnectingProvider] = useState<string | null>(null);
  const [isRefreshingProviders, setIsRefreshingProviders] = useState(false);
  const [providersError, setProvidersError] = useState<string | null>(null);
  const [providerActionMsg, setProviderActionMsg] = useState<{ id: string; text: string } | null>(null);
  const actionTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  const showActionMessage = useCallback((id: string, text: string, durationMs: number = 3500) => {
    if (actionTimeoutRef.current) clearTimeout(actionTimeoutRef.current);
    setProviderActionMsg({ id, text });
    actionTimeoutRef.current = setTimeout(() => setProviderActionMsg(null), durationMs);
  }, []);

  useEffect(() => {
    return () => {
      if (actionTimeoutRef.current) clearTimeout(actionTimeoutRef.current);
    };
  }, []);

  // ── Custom Provider Modal State ──
  const [isCustomProviderModalOpen, setIsCustomProviderModalOpen] = useState(false);
  const [customProviderType, setCustomProviderType] = useState<"openai" | "anthropic">("openai");

  // ── Sub-Tab State & Models ──
  const [hiddenModelsByProvider, setHiddenModelsByProvider] = useState<Record<string, string[]>>({});

  // ── Provider Detail & Filter State ──
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  const [providerGlobalSearch, setProviderGlobalSearch] = useState("");

  // ── Confirmation Modal State ──
  const [deleteConfirm, setDeleteConfirm] = useState<{
    type: "account" | "provider" | "disconnect";
    id: string | number;
    extraId?: number;
    label: string;
  } | null>(null);

  // ── Codex OAuth PKCE Monitor State ──
  const [activeOAuthSession, setActiveOAuthSession] = useState<{
    providerId: string;
    state: string;
    authUrl: string;
    codeVerifier?: string;
  } | null>(null);

  const handleCloseOAuth = useCallback(() => {
    setActiveOAuthSession(null);
  }, []);

  const handleSuccessOAuth = useCallback((updatedProviders?: ProviderItem[]) => {
    if (activeOAuthSession) {
      showActionMessage(activeOAuthSession.providerId, "OAuth Login Connected!");
    }
    if (updatedProviders && Array.isArray(updatedProviders)) {
      setProvidersList(updatedProviders);
    }
    fetchProviders(false);
    if (onRefreshAll) onRefreshAll();
  }, [activeOAuthSession, onRefreshAll, showActionMessage]);

  const fetchProviders = async (forceRefresh: boolean = false) => {
    if (forceRefresh) setIsRefreshingProviders(true);
    setProvidersError(null);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);

    try {
      const url = forceRefresh ? `${BACKEND_URL}/api/providers?refresh=true` : `${BACKEND_URL}/api/providers`;
      
      // Parallel execution of provider and hidden models endpoints with 12s timeout
      const [res, hRes] = await Promise.all([
        fetch(url, { signal: controller.signal }).catch(() => null),
        fetch(`${BACKEND_URL}/api/models/hidden`, { signal: controller.signal }).catch(() => null),
      ]);

      if (res && res.ok) {
        const data = await res.json();
        const list = data.providers || [];
        setProvidersList(list);
        if (data.active_model_id) setActiveAiModelId(data.active_model_id);
      } else if ((!res || !res.ok) && providersList.length === 0) {
        setProvidersError("Failed to connect to providers server.");
      }

      if (hRes && hRes.ok) {
        const hData = await hRes.json();
        const grouped: Record<string, string[]> = {};
        (hData.hidden_models || []).forEach((item: any) => {
          const provider = item.provider || 'unknown';
          if (!grouped[provider]) grouped[provider] = [];
          grouped[provider].push(item.model_id);
        });
        setHiddenModelsByProvider(grouped);
      }
    } catch (err: any) {
      if (err?.name === "AbortError") {
        setProvidersError("Provider loading timed out (12s). Please click 'Rescan'.");
      } else {
        console.error("fetchProviders error:", err);
      }
    } finally {
      clearTimeout(timeoutId);
      if (forceRefresh) setIsRefreshingProviders(false);
    }
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  const handleOAuthLogin = async (providerId: string) => {
    setIsConnectingProvider(providerId);
    try {
      const authRes = await fetch(`${BACKEND_URL}/api/auth/${providerId}/authorize-url`);
      if (!authRes.ok) {
        const errData = await authRes.json().catch(() => ({}));
        showActionMessage(providerId, errData.detail || "Failed to get authorization URL.");
        return;
      }
      const authData = await authRes.json();
      if (authData.authorize_url) {
        if (typeof window !== "undefined") {
          window.open(authData.authorize_url, "OpenAI_Codex_Login", "width=600,height=750,left=200,top=100");
        }
        setActiveOAuthSession({
          providerId,
          state: authData.state,
          authUrl: authData.authorize_url,
          codeVerifier: authData.code_verifier,
        });
      }
    } catch (err: any) {
      showActionMessage(providerId, `OAuth error: ${err.message || String(err)}`);
    } finally {
      setIsConnectingProvider(null);
    }
  };

  const handleAddAccount = async (providerId: string) => {
    const keyVal = (providerKeyInputs[providerId] || "").trim();
    const labelVal = (providerLabelInputs[providerId] || "").trim();
    if (!keyVal) return;
    setIsConnectingProvider(providerId);
    try {
      const res = await fetch(`${BACKEND_URL}/api/providers/${providerId}/accounts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_label: labelVal || `${providerId.toUpperCase()} Account`,
          api_key: keyVal,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        showActionMessage(providerId, "Account added to pool");
        setProviderKeyInputs((prev) => ({ ...prev, [providerId]: "" }));
        setProviderLabelInputs((prev) => ({ ...prev, [providerId]: "" }));
        if (data.providers && Array.isArray(data.providers)) {
          setProvidersList(data.providers);
        }
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("anara-models-sync"));
        }
        fetchProviders(false);
      }
    } catch (err) {
      console.error("Add account error:", err);
    } finally {
      setIsConnectingProvider(null);
    }
  };

  const handleToggleAccount = async (providerId: string, accountId: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/providers/${providerId}/accounts/${accountId}/toggle`, {
        method: "PATCH",
      });
      if (res.ok) {
        showActionMessage(providerId, "Account status updated");
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("anara-models-sync"));
        }
        fetchProviders(true);
      }
    } catch (err) {
      console.error("Toggle account error:", err);
    }
  };

  const handleDeleteAccount = (providerId: string, accountId: number, label: string) => {
    setDeleteConfirm({
      type: "account",
      id: providerId,
      extraId: accountId,
      label: label || `${providerId.toUpperCase()} Account`,
    });
  };

  const handleHideModel = async (modelId: string, provider: string) => {
    // 1. Instant Optimistic UI Update (0ms): immediately remove model from active view
    setProvidersList((prev) =>
      prev.map((p) => {
        if (p.id === provider) {
          const updatedModels = (p.models || []).filter((m) => m.id !== modelId);
          return {
            ...p,
            models: updatedModels,
            models_count: updatedModels.length,
          };
        }
        return p;
      })
    );

    // 2. Instant Optimistic UI Update (0ms): add model to hidden list
    setHiddenModelsByProvider((prev) => {
      const updated = { ...prev };
      if (!updated[provider]) updated[provider] = [];
      if (!updated[provider].includes(modelId)) {
        updated[provider] = [...updated[provider], modelId];
      }
      return updated;
    });

    // 3. Persist to backend in background (non-blocking, fast local SQLite write)
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("anara-models-sync"));
    }
    try {
      await fetch(`${BACKEND_URL}/api/models/hide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId, provider }),
      });
    } catch (err) {
      console.error("Hide model error:", err);
    }
  };

  const handleUnhideModel = async (modelId: string, provider: string) => {
    // 1. Instant Optimistic UI Update (0ms): remove from hidden models list
    setHiddenModelsByProvider((prev) => {
      const updated = { ...prev };
      if (updated[provider]) {
        updated[provider] = updated[provider].filter((id) => id !== modelId);
        if (updated[provider].length === 0) delete updated[provider];
      }
      return updated;
    });

    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("anara-models-sync"));
    }

    // 2. Persist to backend and re-sync from RAM cache (fast local query)
    try {
      const res = await fetch(`${BACKEND_URL}/api/models/hide/${encodeURIComponent(modelId)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        fetchProviders(false);
      }
    } catch (err) {
      console.error("Unhide model error:", err);
    }
  };

  const handleRestoreAllHidden = async (provider?: string) => {
    // 1. Instant Optimistic UI Update (0ms)
    if (provider) {
      setHiddenModelsByProvider((prev) => {
        const updated = { ...prev };
        delete updated[provider];
        return updated;
      });
    } else {
      setHiddenModelsByProvider({});
    }

    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("anara-models-sync"));
    }

    // 2. Persist to backend and re-sync from RAM cache
    try {
      const url = provider
        ? `${BACKEND_URL}/api/models/hidden/restore-all?provider=${encodeURIComponent(provider)}`
        : `${BACKEND_URL}/api/models/hidden/restore-all`;
      const res = await fetch(url, { method: "POST" });
      if (res.ok) {
        fetchProviders(false);
      }
    } catch (err) {
      console.error("Restore all hidden models error:", err);
    }
  };

  const handleDeleteCustomProvider = (providerId: number, name: string) => {
    setDeleteConfirm({
      type: "provider",
      id: providerId,
      label: name,
    });
  };

  const handleToggleCustomProvider = async (providerId: number, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const res = await fetch(`${BACKEND_URL}/api/providers/custom/${providerId}/toggle`, {
        method: "PATCH",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.providers && Array.isArray(data.providers)) {
          setProvidersList(data.providers);
        }
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("anara-models-sync"));
        }
        fetchProviders(false);
      }
    } catch (err) {
      console.error("Toggle custom provider error:", err);
    }
  };

  const handleConnectProvider = async (providerId: string, keyVal: string) => {
    if (!keyVal.trim()) return;
    setIsConnectingProvider(providerId);
    try {
      const labelVal = (providerLabelInputs[providerId] || "").trim();
      const res = await fetch(`${BACKEND_URL}/api/providers/${providerId}/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: providerId,
          api_key: keyVal.trim(),
          account_label: labelVal || `${providerId.toUpperCase()} Account`,
        }),
      });
      if (res.ok) {
        showActionMessage(providerId, "Connected & models fetched");
        setProviderKeyInputs((prev) => ({ ...prev, [providerId]: "" }));
        setProviderLabelInputs((prev) => ({ ...prev, [providerId]: "" }));
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("anara-models-sync"));
        }
        fetchProviders(true);
      }
    } catch (err) {
      console.error("Connect provider error:", err);
    } finally {
      setIsConnectingProvider(null);
    }
  };

  const handleDisconnectProvider = (providerId: string) => {
    setDeleteConfirm({
      type: "disconnect",
      id: providerId,
      label: providerId.toUpperCase(),
    });
  };

  const handleConfirmDeleteAction = async () => {
    if (!deleteConfirm) return;
    const { type, id, extraId, label } = deleteConfirm;
    setDeleteConfirm(null);

    if (type === "account") {
      try {
        const res = await fetch(`${BACKEND_URL}/api/providers/${id}/accounts/${extraId}`, {
          method: "DELETE",
        });
        if (res.ok) {
          showActionMessage(String(id), "Account deleted from pool");
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("anara-models-sync"));
          }
          fetchProviders(true);
        }
      } catch (err) {
        console.error("Delete account error:", err);
      }
    } else if (type === "provider") {
      try {
        const res = await fetch(`${BACKEND_URL}/api/providers/custom/${id}`, {
          method: "DELETE",
        });
        if (res.ok) {
          const data = await res.json();
          if (data.providers && Array.isArray(data.providers)) {
            setProvidersList(data.providers);
          }
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("anara-models-sync"));
          }
          if (selectedProviderId === String(id)) {
            setSelectedProviderId(null);
          }
          showActionMessage("custom", `Custom provider '${label}' deleted`);
          fetchProviders(false);
        }
      } catch (e) {
        console.error("Delete custom provider error:", e);
      }
    } else if (type === "disconnect") {
      setIsConnectingProvider(String(id));
      try {
        const res = await fetch(`${BACKEND_URL}/api/providers/${id}/disconnect`, {
          method: "POST",
        });
        if (res.ok) {
          showActionMessage(String(id), "Provider disconnected");
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("anara-models-sync"));
          }
          fetchProviders(true);
        }
      } catch (err) {
        console.error("Disconnect provider error:", err);
      } finally {
        setIsConnectingProvider(null);
      }
    }
  };

  const handleSelectModelFromBrain = async (modelId: string) => {
    setActiveAiModelId(modelId);
    try {
      await fetch(`${BACKEND_URL}/api/models/active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId }),
      });
      fetchProviders();
    } catch {}
  };

  return (
    <div className="space-y-4">
      {/* Dynamic Gateway Providers Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-3.5 rounded-xl bg-white/[0.025] border border-white/[0.08] shadow-lg">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="w-6 h-6 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-cyan-300">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
                </svg>
              </span>
              <h3 className="text-xs sm:text-sm font-semibold text-white tracking-wide">
                Providers &amp; Keys
              </h3>
              {providerActionMsg && (
                <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-400/20 text-[10px] font-mono font-medium">
                  {providerActionMsg.text}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Manage your AI provider connections and proxy endpoints
            </p>
          </div>
    
          <div className="flex items-center gap-2 flex-wrap">
            {/* Search Bar */}
            <div className="relative">
              <input
                type="text"
                placeholder="Search providers..."
                value={providerGlobalSearch}
                onChange={(e) => setProviderGlobalSearch(e.target.value)}
                className="w-40 sm:w-48 px-3 py-1.5 pl-8 rounded-lg bg-black/40 border border-white/[0.08] text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-white/20 font-mono transition-colors"
              />
              <svg className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
    
            <button
              onClick={() => {
                setCustomProviderType("anthropic");
                setIsCustomProviderModalOpen(true);
              }}
              className="px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] text-slate-200 hover:text-white border border-white/[0.12] text-xs font-medium font-mono transition-all cursor-pointer flex items-center gap-1.5 shadow-sm active:scale-[0.98]"
            >
              <span>+ Anthropic Compatible</span>
            </button>
            <button
              onClick={() => {
                setCustomProviderType("openai");
                setIsCustomProviderModalOpen(true);
              }}
              className="px-3 py-1.5 rounded-lg bg-white/[0.08] hover:bg-white/[0.15] text-white border border-white/[0.14] text-xs font-semibold font-mono transition-all cursor-pointer flex items-center gap-1.5 shadow-sm active:scale-[0.98]"
            >
              <span>+ OpenAI Compatible</span>
            </button>
          </div>
        </div>

        {/* 9Router-Style Categorized Provider Grids & Interactive Detail View */}
        {(() => {
          const q = providerGlobalSearch.toLowerCase().trim();
          const filtered = providersList.filter((p) =>
            !q ||
            p.name.toLowerCase().includes(q) ||
            p.id.toLowerCase().includes(q) ||
            (p.badge || "").toLowerCase().includes(q) ||
            (p.description || "").toLowerCase().includes(q)
          );
          const customProviders = filtered.filter((p) => p.is_custom);
          const officialProviders = filtered.filter((p) => !p.is_custom);
          const selectedProvider = providersList.find((p) => p.id === selectedProviderId) || null;
    
          // ── FULLSCREEN INLINE PROVIDER DETAIL VIEW (NOT FLOATING POPUP) ──
          if (selectedProvider) {
            return (
              <ProviderDetailView
                selectedProvider={selectedProvider}
                onBack={() => setSelectedProviderId(null)}
                handleHideModel={handleHideModel}
                handleUnhideModel={handleUnhideModel}
                handleRestoreAllHidden={handleRestoreAllHidden}
                handleDeleteCustomProvider={handleDeleteCustomProvider}
                handleDisconnectProvider={handleDisconnectProvider}
                handleOAuthLogin={handleOAuthLogin}
                handleAddAccount={handleAddAccount}
                handleToggleAccount={handleToggleAccount}
                handleDeleteAccount={handleDeleteAccount}
                providerLabelInputs={providerLabelInputs}
                setProviderLabelInputs={setProviderLabelInputs}
                providerKeyInputs={providerKeyInputs}
                setProviderKeyInputs={setProviderKeyInputs}
                isConnectingProvider={isConnectingProvider}
                hiddenModelsByProvider={hiddenModelsByProvider}
              />
            );
          }

          // ── OVERVIEW GRID (WHEN NO PROVIDER SELECTED) ──
          return (
            <div className="space-y-6">
              {/* SECTION 1: CUSTOM PROVIDERS (OPENAI/ANTHROPIC COMPATIBLE) */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-white font-mono">
                      Custom Providers (OpenAI/Anthropic Compatible)
                    </h4>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/10 text-slate-400 font-semibold">
                      {customProviders.length}
                    </span>
                  </div>
                </div>
    
                {customProviders.length === 0 ? (
                  <div className="p-6 rounded-xl border border-dashed border-white/[0.08] bg-white/[0.015] text-center text-xs font-mono text-slate-500">
                    No custom providers yet. Use the button above to add a proxy like 9Router Proxy, Ollama, or vLLM.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                    {customProviders.map((p) => {
                      const isActive = p.is_connected && (p.custom_data?.is_active ?? 1) === 1;
                      const apiType = p.custom_data?.api_type === "responses" ? "Responses" : "Chat";
                      return (
                        <div
                          key={p.id}
                          onClick={() => setSelectedProviderId(p.id)}
                          className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 group select-none shadow-sm ${
                            isActive
                              ? "bg-white/[0.035] border-white/[0.12] hover:border-cyan-400/40 hover:shadow-[0_0_20px_rgba(34,211,238,0.08)]"
                              : "bg-white/[0.015] border-white/[0.06] opacity-60 hover:opacity-100 hover:border-white/15"
                          }`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0 flex-1">
                            <div className="w-8 h-8 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-cyan-300 shrink-0 shadow-inner group-hover:scale-105 transition-transform">
                              <BrandIcon name={p.id} className="w-4 h-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <h5 className="text-xs font-semibold text-white truncate group-hover:text-cyan-200 transition-colors">
                                {p.name}
                              </h5>
                              <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                                {isActive ? (
                                  <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 font-medium">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                    {p.models_count > 0 ? `${p.models_count} Models` : "Connected"}
                                  </span>
                                ) : (
                                  <span className="text-[10px] font-mono text-slate-500 font-medium flex items-center gap-1">
                                    <svg className="w-2.5 h-2.5 text-slate-500" fill="currentColor" viewBox="0 0 24 24">
                                      <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                                    </svg>
                                    <span>Disabled</span>
                                  </span>
                                )}
                                <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-white/[0.04] text-slate-400 border border-white/[0.06]">
                                  {apiType}
                                </span>
                              </div>
                            </div>
                          </div>
    
                          {/* Toggle Switch */}
                          <div
                            onClick={(e) => {
                              e.stopPropagation();
                              if (p.custom_data?.id) {
                                handleToggleCustomProvider(p.custom_data.id, e);
                              }
                            }}
                            className={`w-8 h-4.5 rounded-full p-0.5 transition-colors cursor-pointer shrink-0 ${
                              isActive ? "bg-emerald-500" : "bg-slate-700/60"
                            }`}
                            title={isActive ? "Deactivate this provider" : "Activate this provider"}
                          >
                            <div
                              className={`w-3.5 h-3.5 rounded-full bg-white transition-transform shadow-sm ${
                                isActive ? "translate-x-3.5" : "translate-x-0"
                              }`}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
    
              {/* SECTION 2: OAUTH & OFFICIAL PROVIDERS */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs sm:text-sm font-semibold text-white font-mono">
                      OAuth &amp; Official Providers
                    </h4>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.06] text-slate-400 font-medium">
                      {officialProviders.length}
                    </span>
                  </div>
                </div>
    
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {officialProviders.map((p) => {
                    const isConnected = p.is_connected;
                    const count = p.accounts?.length || 0;
                    const getBadge = (id: string) => {
                      switch (id.toLowerCase()) {
                        case "gemini": return "Native SDK";
                        case "claude":
                        case "anthropic": return "Direct API";
                        case "codex": return "OAuth PKCE";
                        case "openai": return "Official API";
                        case "openrouter": return "Model Router";
                        case "groq": return "LPU Fast";
                        case "deepseek": return "DeepSeek API";
                        case "xai": return "xAI Grok";
                        default: return "API Gateway";
                      }
                    };
                    const getBrandTheme = (id: string) => {
                      switch (id.toLowerCase()) {
                        case "gemini": return "bg-cyan-500/15 border-cyan-400/30 text-cyan-300";
                        case "claude":
                        case "anthropic": return "bg-amber-500/15 border-amber-400/30 text-amber-300";
                        case "codex":
                        case "openai": return "bg-emerald-500/15 border-emerald-400/30 text-emerald-400";
                        case "groq": return "bg-orange-500/15 border-orange-400/30 text-orange-400";
                        case "deepseek": return "bg-sky-500/15 border-sky-400/30 text-sky-300";
                        case "xai": return "bg-purple-500/15 border-purple-400/30 text-purple-300";
                        case "openrouter": return "bg-indigo-500/15 border-indigo-400/30 text-indigo-300";
                        default: return "bg-white/10 border-white/20 text-slate-300";
                      }
                    };
                    const badge = getBadge(p.id);
                    return (
                      <div
                        key={p.id}
                        onClick={() => setSelectedProviderId(p.id)}
                        className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 group select-none shadow-sm ${
                          isConnected
                            ? "bg-white/[0.035] border-emerald-500/25 hover:border-emerald-400/40 shadow-[0_0_20px_rgba(16,185,129,0.06)]"
                            : "bg-white/[0.015] border-white/[0.06] hover:border-white/15 hover:bg-white/[0.03]"
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0 flex-1">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-inner group-hover:scale-105 transition-transform border ${getBrandTheme(p.id)}`}>
                            <BrandIcon name={p.id} className="w-4 h-4" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <h5 className="text-xs font-semibold text-white truncate group-hover:text-cyan-200 transition-colors">
                              {p.name}
                            </h5>
                            <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                              {isConnected ? (
                                <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 font-medium">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                  {count > 0 ? `${count} Connected` : `${p.models_count} Models`}
                                </span>
                              ) : (
                                <span className="text-[10px] font-mono text-slate-500 font-medium">
                                  No connections
                                </span>
                              )}
                              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-white/[0.04] text-slate-400 border border-white/[0.06]">
                                {badge}
                              </span>
                            </div>
                          </div>
                        </div>
    
                        <div className="text-slate-500 group-hover:text-cyan-300 transition-colors shrink-0 pr-1">
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })()}
    
      {/* ── Custom Provider Modal ── */}
      <CustomProviderModal
        isOpen={isCustomProviderModalOpen}
        onClose={() => setIsCustomProviderModalOpen(false)}
        providerType={customProviderType}
        onSuccess={(updatedProviders) => {
          if (updatedProviders && Array.isArray(updatedProviders)) {
            setProvidersList(updatedProviders);
          }
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("anara-models-sync"));
          }
          fetchProviders(false);
          if (onRefreshAll) onRefreshAll();
        }}
      />

      {/* ── Codex OAuth PKCE Modal ── */}
      <CodexOAuthModal
        session={activeOAuthSession}
        onClose={handleCloseOAuth}
        onSuccess={handleSuccessOAuth}
      />

      {/* In-app Confirmation Modal */}
      {deleteConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in select-none"
        >
          <div className="w-full max-w-sm p-5 rounded-2xl bg-slate-950/95 border border-white/20 shadow-[0_0_40px_rgba(0,0,0,0.8)] text-white space-y-4 font-sans">
            <div className="flex items-center gap-2.5 text-rose-400 font-mono text-xs font-semibold">
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>Confirm Action</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              {deleteConfirm.type === "account" && (
                <>Delete account <b className="text-white font-mono">&apos;{deleteConfirm.label}&apos;</b> from provider pool?</>
              )}
              {deleteConfirm.type === "provider" && (
                <>Delete custom provider <b className="text-white font-mono">&apos;{deleteConfirm.label}&apos;</b> along with all its registered models?</>
              )}
              {deleteConfirm.type === "disconnect" && (
                <>Disconnect provider <b className="text-white font-mono">&apos;{deleteConfirm.label}&apos;</b>? All pool accounts and active models will be deactivated.</>
              )}
            </p>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/10 font-mono text-xs">
              <button
                type="button"
                onClick={() => setDeleteConfirm(null)}
                className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDeleteAction}
                className="px-3.5 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/40 font-semibold transition-all cursor-pointer shadow-sm active:scale-95"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
