"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { BACKEND_URL, BrandIcon, ProviderItem } from "../types";
import ProviderTokenSummary, { TokenSummaryData, TokenLogEntry } from "./providers/ProviderTokenSummary";
import ProviderDetailView from "./providers/ProviderDetailView";
import CustomProviderModal from "./providers/CustomProviderModal";
import CodexOAuthModal, { OAuthSessionData } from "./providers/CodexOAuthModal";
interface BrainProvidersTabProps {
  onRefreshAll?: () => void;
}

export default function BrainProvidersTab({ onRefreshAll }: BrainProvidersTabProps) {
  const [providersList, setProvidersList] = useState<Array<{
    id: string;
    name: string;
    badge: string;
    icon: string;
    description: string;
    auth_type: string;
    signup_url: string;
    signup_label: string;
    key_placeholder: string;
    help_text: string;
    is_connected: boolean;
    models_count: number;
    accounts_count?: number;
    accounts?: Array<{
      id: number;
      provider: string;
      account_label: string;
      masked_key: string;
      status: string;
      requests_count: number;
      is_enabled?: number;
    }>;
    models: Array<{
      id: string;
      name: string;
      category: string;
      badge: string;
      description: string;
      icon: string;
      is_active: boolean;
    }>;
    credit_info?: {
      total_credits?: number;
      total_usage?: number;
      remaining?: number;
    } | null;
    is_custom?: boolean;
    custom_data?: any;
  }>>([]);
  const [activeAiModelId, setActiveAiModelId] = useState<string>("gemini-3.1-flash-live-preview");
  const [providerKeyInputs, setProviderKeyInputs] = useState<Record<string, string>>({});
  const [providerLabelInputs, setProviderLabelInputs] = useState<Record<string, string>>({});
  const [providerSearchQueries, setProviderSearchQueries] = useState<Record<string, string>>({});
  const [isConnectingProvider, setIsConnectingProvider] = useState<string | null>(null);
  const [isRefreshingProviders, setIsRefreshingProviders] = useState(false);
  const [providersError, setProvidersError] = useState<string | null>(null);
  const [providerActionMsg, setProviderActionMsg] = useState<{ id: string; text: string } | null>(null);

  // ── Load cached providers from sessionStorage on client mount for instant 0ms render ──
  useEffect(() => {
    try {
      const cached = sessionStorage.getItem("anara_cached_providers");
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setProvidersList(parsed);
        }
      }
    } catch {}
  }, []);

  // ── Custom Provider Modal State (9Router Style) ──
  const [isCustomProviderModalOpen, setIsCustomProviderModalOpen] = useState(false);
  const [customProviderType, setCustomProviderType] = useState<"openai" | "anthropic">("openai");

  // ── Sub-Tab State per Provider Card ('models' | 'accounts') ──
  const [providerCardTabs, setProviderCardTabs] = useState<Record<string, "models" | "accounts">>({});
  const [hiddenModelsByProvider, setHiddenModelsByProvider] = useState<Record<string, string[]>>({});
  const [showHiddenSection, setShowHiddenSection] = useState(false);
  const [showHiddenForProvider, setShowHiddenForProvider] = useState<Record<string, boolean>>({});

  // ── 9Router-Style Provider Detail & Filter State ──
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  const [providerDetailTab, setProviderDetailTab] = useState<"accounts" | "models" | "endpoint">("accounts");
  const [providerGlobalSearch, setProviderGlobalSearch] = useState("");
  const [detailModelSearch, setDetailModelSearch] = useState("");

  // ── Codex OAuth PKCE Monitor State ──
  const [activeOAuthSession, setActiveOAuthSession] = useState<{
    providerId: string;
    state: string;
    authUrl: string;
    codeVerifier?: string;
  } | null>(null);

  // ── Token Usage & Credit Tracker State ──
  const [tokenSummary, setTokenSummary] = useState<{
    overall?: { total_tokens: number; total_prompt: number; total_completion: number; total_requests: number };
    today?: { today_tokens: number; today_requests: number };
    by_provider?: Array<{ provider: string; requests: number; total_tokens: number }>;
    top_models?: Array<{ model_id: string; requests: number; total_tokens: number }>;
  } | null>(null);
  const [tokenLogs, setTokenLogs] = useState<Array<{
    id: number;
    session_id?: number;
    model_id: string;
    provider: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    created_at: string;
  }>>([]);
  const [showTokenHistory, setShowTokenHistory] = useState(false);

  // ── WhatsApp & Media Integrations State ──

  const fetchProviders = async (forceRefresh: boolean = false) => {
    if (forceRefresh) setIsRefreshingProviders(true);
    setProvidersError(null);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);

    try {
      const url = forceRefresh ? `${BACKEND_URL}/api/providers?refresh=true` : `${BACKEND_URL}/api/providers`;
      
      // Parallel execution of all 4 provider/token/hidden endpoints with 12s timeout
      const [res, hRes, tRes, tlRes] = await Promise.all([
        fetch(url, { signal: controller.signal }).catch(() => null),
        fetch(`${BACKEND_URL}/api/models/hidden`, { signal: controller.signal }).catch(() => null),
        fetch(`${BACKEND_URL}/api/tokens/summary`, { signal: controller.signal }).catch(() => null),
        fetch(`${BACKEND_URL}/api/tokens/history?limit=50`, { signal: controller.signal }).catch(() => null),
      ]);

      if (res && res.ok) {
        const data = await res.json();
        const list = data.providers || [];
        setProvidersList(list);
        if (data.active_model_id) setActiveAiModelId(data.active_model_id);
        try {
          sessionStorage.setItem("anara_cached_providers", JSON.stringify(list));
        } catch {}
      } else if (!res && providersList.length === 0) {
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

      if (tRes && tRes.ok) {
        const tData = await tRes.json();
        setTokenSummary(tData);
      }

      if (tlRes && tlRes.ok) {
        const tlData = await tlRes.json();
        setTokenLogs(tlData.logs || []);
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
        alert(errData.detail || "Failed to get authorization URL.");
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
      alert(`OAuth Login error: ${err.message}`);
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
        setProviderActionMsg({ id: providerId, text: "✓ Account Successfully Added to Pool!" });
        setProviderKeyInputs((prev) => ({ ...prev, [providerId]: "" }));
        setProviderLabelInputs((prev) => ({ ...prev, [providerId]: "" }));
        setTimeout(() => setProviderActionMsg(null), 4000);
        if (data.providers && Array.isArray(data.providers)) {
          setProvidersList(data.providers);
          try {
            sessionStorage.setItem("anara_cached_providers", JSON.stringify(data.providers));
          } catch {}
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
        setProviderActionMsg({ id: providerId, text: "✓ Status Akun Diperbarui" });
        setTimeout(() => setProviderActionMsg(null), 3000);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("anara-models-sync"));
        }
        fetchProviders(true);
      }
    } catch (err) {
      console.error("Toggle account error:", err);
    }
  };

  const handleDeleteAccount = async (providerId: string, accountId: number, label: string) => {
    if (!confirm(`Delete account "${label}" from pool provider ${providerId.toUpperCase()}?`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/providers/${providerId}/accounts/${accountId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setProviderActionMsg({ id: providerId, text: "✓ Account Deleted" });
        setTimeout(() => setProviderActionMsg(null), 3000);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("anara-models-sync"));
        }
        fetchProviders(true);
      }
    } catch (err) {
      console.error("Delete account error:", err);
    }
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

  const handleDeleteCustomProvider = async (providerId: number, name: string) => {
    if (!confirm(`Delete custom provider "${name}" along with all its models?`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/providers/custom/${providerId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.providers && Array.isArray(data.providers)) {
          setProvidersList(data.providers);
          try {
            sessionStorage.setItem("anara_cached_providers", JSON.stringify(data.providers));
          } catch {}
        }
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("anara-models-sync"));
        }
        if (selectedProviderId === String(providerId)) {
          setSelectedProviderId(null);
        }
        fetchProviders(false);
      }
    } catch (e) {
      console.error("Delete custom provider error:", e);
    }
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
          try {
            sessionStorage.setItem("anara_cached_providers", JSON.stringify(data.providers));
          } catch {}
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
        setProviderActionMsg({ id: providerId, text: "✓ Connected & Models Successfully Fetched!" });
        setProviderKeyInputs((prev) => ({ ...prev, [providerId]: "" }));
        setProviderLabelInputs((prev) => ({ ...prev, [providerId]: "" }));
        setTimeout(() => setProviderActionMsg(null), 4000);
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

  const handleDisconnectProvider = async (providerId: string) => {
    if (!confirm(`Disconnect provider ${providerId.toUpperCase()}? All accounts in the pool and their models will be deactivated.`)) return;
    setIsConnectingProvider(providerId);
    try {
      const res = await fetch(`${BACKEND_URL}/api/providers/${providerId}/disconnect`, {
        method: "POST",
      });
      if (res.ok) {
        setProviderActionMsg({ id: providerId, text: "✓ Diputuskan Sepenuhnya" });
        setTimeout(() => setProviderActionMsg(null), 3000);
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
      {/* 9Router-Style Providers Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-4 rounded-2xl liquid-glass border border-white/10 shadow-lg">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="w-7 h-7 rounded-xl bg-white/[0.05] border border-white/10 flex items-center justify-center text-cyan-300">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
                </svg>
              </span>
              <h3 className="text-sm sm:text-base font-bold text-white tracking-wide">
                Providers &amp; Gateway
              </h3>
              {providerActionMsg && (
                <span className="px-2.5 py-0.5 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-400/30 text-[10px] font-mono font-medium">
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
                className="w-40 sm:w-48 px-3 py-1.5 pl-8 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-400 font-mono"
              />
              <svg className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
    
            <button
              onClick={() => {
                setCustomProviderType("anthropic");
                setIsCustomProviderModalOpen(true);
              }}
              className="px-3 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 hover:text-rose-100 border border-rose-400/30 text-xs font-medium font-mono transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
            >
              <span>+ Add Anthropic Compatible</span>
            </button>
            <button
              onClick={() => {
                setCustomProviderType("openai");
                setIsCustomProviderModalOpen(true);
              }}
              className="px-3 py-1.5 rounded-xl bg-white text-black hover:bg-slate-200 text-xs font-semibold font-mono transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
            >
              <span>+ Add OpenAI Compatible</span>
            </button>
            <button
              onClick={() => fetchProviders(true)}
              disabled={isRefreshingProviders}
              className="px-2.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white border border-white/10 text-xs font-mono transition-all cursor-pointer flex items-center gap-1 disabled:opacity-50"
              title="Rescan models and live connection status"
            >
              <svg className={`w-3.5 h-3.5 text-cyan-400 ${isRefreshingProviders ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>
    
        {/* ── Token Usage & Credit Tracking Summary Cards & Accordion ── */}
        <ProviderTokenSummary
          tokenSummary={tokenSummary}
          tokenLogs={tokenLogs}
        />

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
                onBack={() => { setSelectedProviderId(null); setDetailModelSearch(""); }}
                activeAiModelId={activeAiModelId}
                onSelectModel={handleSelectModelFromBrain}
                handleHideModel={handleHideModel}
                handleUnhideModel={handleUnhideModel}
                handleRestoreAllHidden={handleRestoreAllHidden}
                handleDeleteCustomProvider={handleDeleteCustomProvider}
                handleToggleCustomProvider={handleToggleCustomProvider}
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
                  <div className="p-6 rounded-2xl border border-dashed border-white/10 liquid-glass-subtle text-center text-xs font-mono text-slate-500">
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
                          onClick={() => { setSelectedProviderId(p.id); setProviderDetailTab("accounts"); }}
                          className={`p-3.5 rounded-2xl border transition-all cursor-pointer flex items-center justify-between gap-3 group select-none ${
                            isActive
                              ? "liquid-glass border-white/15 hover:border-cyan-400/50 hover:shadow-[0_0_20px_rgba(34,211,238,0.12)]"
                              : "liquid-glass-subtle border-white/5 opacity-60 hover:opacity-100 hover:border-white/20"
                          }`}
                        >
                          <div className="flex items-center gap-3 min-w-0 flex-1">
                            <div className="w-9 h-9 rounded-xl bg-white/[0.06] border border-white/10 flex items-center justify-center text-cyan-300 shrink-0 shadow-inner group-hover:scale-105 transition-transform">
                              <BrandIcon name={p.id} className="w-5 h-5" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <h5 className="text-xs font-bold text-white truncate group-hover:text-cyan-200 transition-colors">
                                {p.name}
                              </h5>
                              <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                                {isActive ? (
                                  <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 font-semibold">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                    {p.models_count > 0 ? `${p.models_count} Models` : "Connected"}
                                  </span>
                                ) : (
                                  <span className="text-[10px] font-mono text-slate-500 font-medium flex items-center gap-1">
                                    ⏸ Disabled
                                  </span>
                                )}
                                <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-white/5 text-slate-400 border border-white/10">
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
                            className={`w-9 h-5 rounded-full p-0.5 transition-colors cursor-pointer shrink-0 ${
                              isActive ? "bg-emerald-500" : "bg-slate-700/60"
                            }`}
                            title={isActive ? "Deactivate this provider" : "Activate this provider"}
                          >
                            <div
                              className={`w-4 h-4 rounded-full bg-white transition-transform shadow-sm ${
                                isActive ? "translate-x-4" : "translate-x-0"
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
                    <h4 className="text-sm font-bold text-white font-mono">
                      OAuth &amp; Official Providers
                    </h4>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/10 text-slate-400 font-semibold">
                      {officialProviders.length}
                    </span>
                  </div>
                </div>
    
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {officialProviders.map((p) => {
                    const isConnected = p.is_connected;
                    const count = p.accounts?.length || 0;
                    const badge = p.id === "codex" ? "OAuth PKCE" : p.id === "gemini" ? "Live Voice AI" : "Claude Direct";
                    return (
                      <div
                        key={p.id}
                        onClick={() => { setSelectedProviderId(p.id); setProviderDetailTab("accounts"); }}
                        className={`p-3.5 rounded-2xl border transition-all cursor-pointer flex items-center justify-between gap-3 group select-none ${
                          isConnected
                            ? "liquid-glass border-emerald-500/30 hover:border-emerald-400/50 shadow-[0_0_20px_rgba(16,185,129,0.08)]"
                            : "liquid-glass-subtle border-white/10 hover:border-white/25 hover:bg-white/[0.04]"
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 shadow-inner group-hover:scale-105 transition-transform ${
                            p.id === "codex"
                              ? "bg-emerald-500/15 border border-emerald-400/30 text-emerald-400"
                              : p.id === "gemini"
                              ? "bg-cyan-500/15 border border-cyan-400/30 text-cyan-300"
                              : "bg-amber-500/15 border border-amber-400/30 text-amber-300"
                          }`}>
                            <BrandIcon name={p.id} className="w-5 h-5" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <h5 className="text-xs font-bold text-white truncate group-hover:text-cyan-200 transition-colors">
                              {p.name}
                            </h5>
                            <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                              {isConnected ? (
                                <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 font-semibold">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                  {count > 0 ? `${count} Connected` : `${p.models_count} Models`}
                                </span>
                              ) : (
                                <span className="text-[10px] font-mono text-slate-500 font-medium">
                                  No connections
                                </span>
                              )}
                              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-white/5 text-slate-400 border border-white/10">
                                {badge}
                              </span>
                            </div>
                          </div>
                        </div>
    
                        <div className="text-slate-500 group-hover:text-white transition-colors text-sm font-mono shrink-0 pr-1">
                          ›
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
            try {
              sessionStorage.setItem("anara_cached_providers", JSON.stringify(updatedProviders));
            } catch {}
          }
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("anara-models-sync"));
          }
          fetchProviders(false);
        }}
      />

      {/* ── Codex OAuth PKCE Modal ── */}
      <CodexOAuthModal
        session={activeOAuthSession}
        onClose={() => setActiveOAuthSession(null)}
        onSuccess={(updatedProviders) => {
          setProviderActionMsg({ id: activeOAuthSession?.providerId || "codex", text: "✓ OAuth Login Successfully Connected!" });
          setTimeout(() => setProviderActionMsg(null), 4000);
          if (updatedProviders && Array.isArray(updatedProviders)) {
            setProvidersList(updatedProviders);
            try {
              sessionStorage.setItem("anara_cached_providers", JSON.stringify(updatedProviders));
            } catch {}
          }
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("anara-models-sync"));
          }
          fetchProviders(false);
        }}
      />

    </div>
  );
}
