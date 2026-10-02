"use client";

import React, { useState, useEffect, useCallback } from "react";
import { anaraApi, apiRequest } from "@/lib/apiClient";

function LockIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function KeyIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="7.5" cy="15.5" r="5.5" />
      <path d="m21 2-9.6 9.6" />
      <path d="m15.5 7.5 3 3L22 7l-3-3" />
    </svg>
  );
}

function ShieldCheckIcon({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function LaptopIcon({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 16V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v9m16 0H4m16 0 1.28 2.55a1 1 0 0 1-.9 1.45H3.62a1 1 0 0 1-.9-1.45L4 16" />
    </svg>
  );
}

function TerminalIcon({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 17 10 11 4 5" />
      <line x1="12" y1="19" x2="20" y2="19" />
    </svg>
  );
}

function AlertTriangleIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function EyeIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
      <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
      <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
      <line x1="2" x2="22" y1="2" y2="22" />
    </svg>
  );
}

interface ProviderMeta {
  id: string;
  name: string;
  protocol: string;
  placeholder: string;
  prefix: string;
  iconBg: string;
}

const SUPPORTED_PROVIDERS: ProviderMeta[] = [
  { id: "gemini", name: "Google Gemini", protocol: "Native SDK", placeholder: "AIzaSy...", prefix: "AIza", iconBg: "bg-blue-600/20 text-blue-400" },
  { id: "claude", name: "Anthropic Claude", protocol: "Direct API", placeholder: "sk-ant-api03-...", prefix: "sk-ant", iconBg: "bg-amber-600/20 text-amber-400" },
  { id: "openai", name: "OpenAI Official", protocol: "Official API", placeholder: "sk-proj-...", prefix: "sk-", iconBg: "bg-emerald-600/20 text-emerald-400" },
  { id: "openrouter", name: "OpenRouter", protocol: "Model Router", placeholder: "sk-or-v1-...", prefix: "sk-or", iconBg: "bg-purple-600/20 text-purple-400" },
  { id: "groq", name: "Groq LPU", protocol: "LPU Fast", placeholder: "gsk_...", prefix: "gsk_", iconBg: "bg-orange-600/20 text-orange-400" },
  { id: "deepseek", name: "DeepSeek API", protocol: "Direct API", placeholder: "sk-...", prefix: "sk-", iconBg: "bg-cyan-600/20 text-cyan-400" },
];

export function GatewayAuthModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"gateway" | "providers">("gateway");

  // Gateway Password State
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [gatewayStatus, setGatewayStatus] = useState<{ is_local: boolean; authenticated: boolean; client_ip?: string } | null>(null);

  // Provider Keys State
  const [providersList, setProvidersList] = useState<Array<{ id: string; name: string; is_connected: boolean; accounts_count?: number }>>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<string>("gemini");
  const [providerKeyInput, setProviderKeyInput] = useState("");
  const [showProviderKey, setShowProviderKey] = useState(false);
  const [isConnectingKey, setIsConnectingKey] = useState(false);
  const [providerFeedback, setProviderFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Fetch Gateway & Providers Status
  const fetchGatewayAndProviders = useCallback(async () => {
    try {
      const res = await anaraApi.gateway.getStatus();
      setGatewayStatus(res);
      if (res && res.auth_required && !res.authenticated) {
        setIsOpen(true);
      }
    } catch {
      // Ignored
    }

    try {
      const pRes = await apiRequest<{ providers: any[] }>("/api/providers");
      if (pRes?.providers && Array.isArray(pRes.providers)) {
        setProvidersList(pRes.providers);
      }
    } catch {
      // Ignored
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    fetchGatewayAndProviders();

    const handleUnauthorized = () => {
      if (isMounted) {
        setIsOpen(true);
        setActiveTab("gateway");
        setErrorMsg("Session has expired or requires gateway authentication.");
      }
    };

    const handleManualOpen = (e: Event) => {
      if (isMounted) {
        setIsOpen(true);
        const detail = (e as CustomEvent)?.detail;
        if (detail?.tab === "providers") {
          setActiveTab("providers");
        }
      }
    };

    window.addEventListener("anara_gateway_unauthorized", handleUnauthorized);
    window.addEventListener("open_gateway_auth", handleManualOpen);
    return () => {
      isMounted = false;
      window.removeEventListener("anara_gateway_unauthorized", handleUnauthorized);
      window.removeEventListener("open_gateway_auth", handleManualOpen);
    };
  }, [fetchGatewayAndProviders]);

  // Handle Master Gateway Password Login
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim() || isLoading) return;

    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await anaraApi.gateway.login(password.trim());
      setPassword("");
      if (res && res.token) {
        try {
          localStorage.setItem("anara_gateway_token", res.token);
        } catch {
          console.warn("[Gateway] LocalStorage write blocked.");
        }
        setIsSuccess(true);
        setTimeout(() => {
          setIsOpen(false);
          window.location.reload();
        }, 600);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Incorrect gateway password.";
      setErrorMsg(message);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Provider API Key Connection & Handshake
  const handleConnectProviderKey = async (e: React.FormEvent) => {
    e.preventDefault();
    const key = providerKeyInput.trim();
    if (!key || isConnectingKey) return;

    setIsConnectingKey(true);
    setProviderFeedback(null);
    try {
      const res = await anaraApi.models.connectProvider(selectedProviderId, { api_key: key });
      setProviderKeyInput("");
      setProviderFeedback({
        type: "success",
        message: `Successfully connected ${selectedProviderId.toUpperCase()}! Models are live.`,
      });
      // Refresh provider list
      if (res?.providers) {
        setProvidersList(res.providers);
      } else {
        fetchGatewayAndProviders();
      }
      setTimeout(() => setProviderFeedback(null), 4000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to connect API key.";
      setProviderFeedback({ type: "error", message });
    } finally {
      setIsConnectingKey(false);
    }
  };

  if (!isOpen) return null;

  const currentProviderMeta = SUPPORTED_PROVIDERS.find((p) => p.id === selectedProviderId) || SUPPORTED_PROVIDERS[0];
  const liveProviderInfo = providersList.find((p) => p.id === selectedProviderId);
  const isSelectedConnected = Boolean(liveProviderInfo?.is_connected);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Gateway Authentication & Provider Keys"
      className="fixed inset-0 z-[99999] flex items-center justify-center bg-[#030712]/80 backdrop-blur-2xl p-4 animate-in fade-in duration-200 select-none"
    >
      <div className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-white/[0.10] bg-[#060913]/95 p-6 shadow-[0_24px_64px_rgba(0,0,0,0.85),0_0_24px_rgba(34,211,238,0.08)] backdrop-blur-2xl font-sans">
        {/* Specular Top Hairline */}
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-cyan-400/30 to-transparent pointer-events-none" />

        {/* Modal Close Button (if already authenticated or dismissed) */}
        {gatewayStatus?.authenticated && (
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
            title="Close modal"
          >
            ✕
          </button>
        )}

        {/* Tab Navigation: Gateway Access vs Provider API Keys */}
        <div className="flex items-center justify-center mb-6">
          <div className="inline-flex p-1 rounded-xl bg-black/40 border border-white/[0.08]">
            <button
              type="button"
              onClick={() => {
                setActiveTab("gateway");
                setErrorMsg(null);
              }}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                activeTab === "gateway"
                  ? "bg-white/[0.10] text-white shadow-sm font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <LockIcon className="w-3.5 h-3.5 text-cyan-400" />
              <span>Gateway Access</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab("providers");
                setProviderFeedback(null);
              }}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                activeTab === "providers"
                  ? "bg-white/[0.10] text-white shadow-sm font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <KeyIcon className="w-3.5 h-3.5 text-purple-400" />
              <span>Provider API Keys</span>
            </button>
          </div>
        </div>

        {/* ── TAB 1: REMOTE GATEWAY ACCESS ── */}
        {activeTab === "gateway" && (
          <div className="flex flex-col items-center text-center animate-in fade-in duration-150">
            <div className="mb-3.5 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/[0.10] bg-cyan-950/30 text-cyan-400 shadow-[inset_0_1px_0_rgba(255,255,255,0.10)]">
              <LockIcon className="h-7 w-7" />
            </div>

            <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
              <span>Anara Remote Gateway</span>
              <ShieldCheckIcon className="h-5 w-5 text-cyan-400" />
            </h2>
            <p className="mt-1 text-xs text-slate-400 leading-relaxed max-w-sm">
              Remote access detected. Enter your Gateway Master Password to establish an authenticated session.
            </p>

            <form onSubmit={handleLogin} className="mt-5 w-full space-y-3.5">
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">
                  <KeyIcon className="h-4 w-4" />
                </span>
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter Gateway Password..."
                  autoFocus
                  className="w-full rounded-xl border border-white/10 bg-black/40 py-2.5 pl-10 pr-10 text-xs text-slate-100 placeholder-slate-500 outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-500/30 font-mono transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors cursor-pointer p-1"
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOffIcon className="w-3.5 h-3.5" /> : <EyeIcon className="w-3.5 h-3.5" />}
                </button>
              </div>

              {errorMsg && (
                <div className="rounded-xl border border-rose-500/30 bg-rose-950/30 px-3 py-2 text-left text-xs text-rose-300 animate-in fade-in flex items-center gap-2">
                  <AlertTriangleIcon className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {isSuccess && (
                <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/30 px-3 py-2 text-left text-xs text-emerald-300 animate-in fade-in flex items-center gap-2">
                  <ShieldCheckIcon className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>Gateway authenticated successfully! Reloading session...</span>
                </div>
              )}

              {/* Luminous single-accent action button (anti-rainbow discipline) */}
              <button
                type="submit"
                disabled={isLoading || isSuccess || !password.trim()}
                className="w-full rounded-xl bg-cyan-400 hover:bg-cyan-300 py-2.5 text-xs font-semibold text-black shadow-[0_0_14px_rgba(34,211,238,0.3)] transition-all cursor-pointer disabled:opacity-50 disabled:pointer-events-none"
              >
                {isLoading ? "Verifying..." : isSuccess ? "Authenticated ✓" : "Connect Gateway"}
              </button>
            </form>

            <div className="mt-5 flex items-center justify-between w-full pt-3.5 border-t border-white/[0.08] text-[11px] font-mono text-slate-500">
              <div className="flex items-center gap-1.5">
                <LaptopIcon className="h-3.5 w-3.5 text-cyan-400" />
                <span>Host: {typeof window !== "undefined" ? window.location.hostname : "localhost"}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <TerminalIcon className="h-3.5 w-3.5 text-slate-400" />
                <span>Port: {typeof window !== "undefined" ? window.location.port || "3000" : "3000"}</span>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 2: PROVIDER API KEYS & HANDSHAKE ── */}
        {activeTab === "providers" && (
          <div className="flex flex-col animate-in fade-in duration-150 text-left">
            <div className="mb-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <span>AI Gateway Provider Keys</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-400/20">
                  Secure Handshake
                </span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Connect and verify API keys for autonomous multi-model routing across Claude, Gemini, OpenAI, and DeepSeek.
              </p>
            </div>

            {/* Provider Selection Pills */}
            <div className="grid grid-cols-3 gap-1.5 mb-4">
              {SUPPORTED_PROVIDERS.map((p) => {
                const isSelected = selectedProviderId === p.id;
                const isConnected = Boolean(providersList.find((item) => item.id === p.id)?.is_connected);
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setSelectedProviderId(p.id);
                      setProviderKeyInput("");
                      setProviderFeedback(null);
                    }}
                    className={`flex items-center justify-between p-2 rounded-xl border text-left transition-colors cursor-pointer ${
                      isSelected
                        ? "bg-white/[0.08] border-cyan-400/40 text-white shadow-sm"
                        : "bg-black/30 border-white/[0.06] text-slate-400 hover:text-white hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="truncate pr-1">
                      <p className="text-[11px] font-semibold truncate leading-tight">{p.name}</p>
                      <p className="text-[9px] font-mono text-slate-500 uppercase">{p.protocol}</p>
                    </div>
                    {isConnected ? (
                      <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" title="Connected & Active" />
                    ) : (
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-600 shrink-0" title="Not connected" />
                    )}
                  </button>
                );
              })}
            </div>

            {/* API Key Form for Selected Provider */}
            <form onSubmit={handleConnectProviderKey} className="space-y-3 bg-black/40 border border-white/[0.06] rounded-xl p-3.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-200">
                  {currentProviderMeta.name} Key
                </span>
                <span className={`text-[10px] font-mono font-medium px-1.5 py-0.2 rounded ${
                  isSelectedConnected
                    ? "bg-emerald-950/40 text-emerald-400 border border-emerald-500/20"
                    : "bg-zinc-900 text-slate-400 border border-white/10"
                }`}>
                  {isSelectedConnected ? "Connected ✓" : "Unconfigured"}
                </span>
              </div>

              <div className="relative">
                <input
                  type={showProviderKey ? "text" : "password"}
                  value={providerKeyInput}
                  onChange={(e) => setProviderKeyInput(e.target.value)}
                  placeholder={currentProviderMeta.placeholder}
                  className="w-full rounded-lg border border-white/10 bg-black/60 py-2 pl-3 pr-10 text-xs text-slate-100 placeholder-slate-600 outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-500/30 font-mono transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowProviderKey((v) => !v)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors cursor-pointer p-1"
                  title={showProviderKey ? "Hide key" : "Show key"}
                >
                  {showProviderKey ? <EyeOffIcon className="w-3.5 h-3.5" /> : <EyeIcon className="w-3.5 h-3.5" />}
                </button>
              </div>

              {providerFeedback && (
                <div
                  className={`rounded-lg border px-3 py-2 text-xs flex items-center gap-2 animate-in fade-in ${
                    providerFeedback.type === "success"
                      ? "border-emerald-500/30 bg-emerald-950/30 text-emerald-300"
                      : "border-rose-500/30 bg-rose-950/30 text-rose-300"
                  }`}
                >
                  {providerFeedback.type === "success" ? (
                    <ShieldCheckIcon className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <AlertTriangleIcon className="w-4 h-4 text-rose-400 shrink-0" />
                  )}
                  <span>{providerFeedback.message}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={isConnectingKey || !providerKeyInput.trim()}
                className="w-full rounded-lg bg-cyan-400 hover:bg-cyan-300 py-2 text-xs font-semibold text-black shadow-[0_0_12px_rgba(34,211,238,0.25)] transition-all cursor-pointer disabled:opacity-50 disabled:pointer-events-none"
              >
                {isConnectingKey ? "Verifying Key Handshake..." : "Save & Verify Handshake"}
              </button>
            </form>

            <div className="mt-3.5 flex items-center justify-between text-[10px] font-mono text-slate-500">
              <span>Credentials encrypted in SQLite keystore</span>
              <span className="text-cyan-400/70">Zero cleartext caching</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
