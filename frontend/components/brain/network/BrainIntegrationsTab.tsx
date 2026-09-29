"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BACKEND_URL, BrandIcon } from "../types";

interface BrainIntegrationsTabProps {
  onRefreshAll?: () => void;
}

export default function BrainIntegrationsTab({ onRefreshAll }: BrainIntegrationsTabProps) {
  const [waStatus, setWaStatus] = useState<"connected" | "connecting" | "disconnected">("disconnected");
  const [waUser, setWaUser] = useState<{ name?: string; phone?: string } | null>(null);
  const [waQrUrl, setWaQrUrl] = useState<string | null>(null);
  const [isWaModalOpen, setIsWaModalOpen] = useState(false);
  const [isWaLoading, setIsWaLoading] = useState(false);

  // ── Telegram & Google Integrations State ──
  const [tgStatus, setTgStatus] = useState<"connected" | "error" | "disconnected">("disconnected");
  const [tgBot, setTgBot] = useState<{ username?: string; first_name?: string } | null>(null);
  const [tgTokenInput, setTgTokenInput] = useState("");
  const [tgChatIdInput, setTgChatIdInput] = useState("");
  const [tgAdminIdsInput, setTgAdminIdsInput] = useState("");
  const [isTgModalOpen, setIsTgModalOpen] = useState(false);
  const [isTgLoading, setIsTgLoading] = useState(false);
  const [tgErrorMsg, setTgErrorMsg] = useState<string | null>(null);
  const [waAllowedNumbersInput, setWaAllowedNumbersInput] = useState("");
  const [isWaConfigSaved, setIsWaConfigSaved] = useState(false);

  const [googleStatus, setGoogleStatus] = useState<"connected" | "disconnected">("disconnected");
  const [googleEmail, setGoogleEmail] = useState<string | null>(null);
  const [googleEmailInput, setGoogleEmailInput] = useState("");
  const [isGoogleModalOpen, setIsGoogleModalOpen] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);



  const fetchWhatsAppStatus = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/whatsapp/status`);
      if (res.ok) {
        const data = await res.json();
        const effectiveStatus = data.user ? (data.status || "connected") : "disconnected";
        setWaStatus(effectiveStatus);
        setWaUser(data.user || null);
        if (data.status === "connected" && data.user) {
          setIsWaModalOpen(false);
        }
      }
      const cfgRes = await fetch(`${BACKEND_URL}/api/integrations/whatsapp/config`);
      if (cfgRes.ok) {
        const cfgData = await cfgRes.json();
        if (cfgData.allowed_numbers !== undefined) {
          setWaAllowedNumbersInput(cfgData.allowed_numbers || "");
        }
      }
    } catch {}
  };

  // Live polling while WhatsApp QR pairing modal is open
  useEffect(() => {
    if (!isWaModalOpen) return;
    const interval = setInterval(() => {
      fetch(`${BACKEND_URL}/api/integrations/whatsapp/qr`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (d && d.qr_data_url) {
            setWaQrUrl(d.qr_data_url);
          }
          if (d && d.status === "connected" && d.user) {
            setWaStatus("connected");
            setWaUser(d.user);
            setIsWaModalOpen(false);
          }
        })
        .catch(() => {});
    }, 2500);
    return () => clearInterval(interval);
  }, [isWaModalOpen]);

  const handleSaveWhatsAppConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/whatsapp/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allowed_numbers: waAllowedNumbersInput.trim() }),
      });
      if (res.ok) {
        setIsWaConfigSaved(true);
        setTimeout(() => setIsWaConfigSaved(false), 3000);
      }
    } catch (e) {
      console.error("[WhatsApp] save config error:", e);
    }
  };

  const openWhatsAppModal = async () => {
    setIsWaModalOpen(true);
    setIsWaLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/whatsapp/qr`);
      if (res.ok) {
        const data = await res.json();
        setWaStatus(data.status || "disconnected");
        setWaQrUrl(data.qr_data_url || null);
        setWaUser(data.user || null);
      }
    } catch (e) {
      console.error("[WhatsApp] fetch QR error:", e);
    } finally {
      setIsWaLoading(false);
    }
  };

  const handleWhatsAppLogout = async () => {
    if (!confirm("Are you sure you want to disconnect WhatsApp? The session will be deleted.")) return;
    setIsWaLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/whatsapp/logout`, { method: "POST" });
      if (res.ok) {
        setWaStatus("disconnected");
        setWaUser(null);
        setWaQrUrl(null);
      }
    } catch (e) {
      console.error("[WhatsApp] logout error:", e);
    } finally {
      setIsWaLoading(false);
    }
  };

  const fetchTelegramStatus = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/telegram/status`);
      if (res.ok) {
        const data = await res.json();
        setTgStatus(data.status || "disconnected");
        setTgBot(data.bot || null);
        if (data.default_chat_id) setTgChatIdInput(data.default_chat_id);
        if (data.admin_ids) setTgAdminIdsInput(data.admin_ids);
      }
    } catch {}
  };

  const handleSaveTelegramConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tgTokenInput.trim()) return;
    setIsTgLoading(true);
    setTgErrorMsg(null);
    try {
      const cleanToken = tgTokenInput.trim();
      const cleanChatId = tgChatIdInput.trim();
      const cleanAdminIds = tgAdminIdsInput.trim();
      const res = await fetch(`${BACKEND_URL}/api/integrations/telegram/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: cleanToken,
          bot_token: cleanToken,
          chat_id: cleanChatId || undefined,
          default_chat_id: cleanChatId || undefined,
          admin_ids: cleanAdminIds || undefined,
          telegram_admin_ids: cleanAdminIds || undefined,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setTgStatus(data.status || "disconnected");
        setTgBot(data.bot || null);
        if (data.admin_ids) setTgAdminIdsInput(data.admin_ids);
        if (data.status === "connected") {
          setIsTgModalOpen(false);
          setTgErrorMsg(null);
        } else {
          setTgErrorMsg(data.message || "Token is not valid according to Telegram Bot API.");
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        setTgErrorMsg(errData.detail || "Failed to connect to backend server.");
      }
    } catch (err: any) {
      console.error("Save telegram error:", err);
      setTgErrorMsg(err.message || String(err));
    } finally {
      setIsTgLoading(false);
    }
  };

  const fetchGoogleStatus = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/google/status`);
      if (res.ok) {
        const data = await res.json();
        setGoogleStatus(data.status || "disconnected");
        setGoogleEmail(data.email || null);
      }
    } catch {}
  };

  const handleSaveGoogleConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!googleEmailInput.trim()) return;
    setIsGoogleLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/google/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: googleEmailInput }),
      });
      if (res.ok) {
        const data = await res.json();
        setGoogleStatus(data.status || "disconnected");
        setGoogleEmail(data.email || null);
        setIsGoogleModalOpen(false);
      }
    } catch (err) {
      console.error("Save google error:", err);
    } finally {
      setIsGoogleLoading(false);
    }
  };

  const handleGoogleDisconnect = async () => {
    if (!confirm("Putuskan tautan akun Google?")) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/google/disconnect`, { method: "POST" });
      if (res.ok) {
        setGoogleStatus("disconnected");
        setGoogleEmail(null);
      }
    } catch {}
  };

  useEffect(() => {
    fetchWhatsAppStatus();
    fetchTelegramStatus();
    fetchGoogleStatus();
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (isWaModalOpen) {
          setIsWaModalOpen(false);
          e.stopPropagation();
        } else if (isTgModalOpen) {
          setIsTgModalOpen(false);
          e.stopPropagation();
        } else if (isGoogleModalOpen) {
          setIsGoogleModalOpen(false);
          e.stopPropagation();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isWaModalOpen, isTgModalOpen, isGoogleModalOpen]);

  return (
    <>
      <div className="space-y-4">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-3.5 sm:p-4 rounded-xl bg-white/[0.025] border border-white/[0.08] shadow-lg">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <h3 className="text-xs sm:text-sm font-semibold text-white tracking-wide">
                Service &amp; Media Integrations
              </h3>
            </div>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Connect WhatsApp, Telegram, Google Workspace, or Spotify for direct message sync and media control.
            </p>
          </div>
        </div>
    
        {/* Grid Kartu Integrasi */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {/* 1. KARTU WHATSAPP */}
          <div className={`p-4 rounded-xl border transition-all flex flex-col justify-between shadow-sm ${
            waStatus === "connected"
              ? "bg-white/[0.035] border-emerald-500/30 shadow-[0_0_20px_rgba(52,211,153,0.06)]"
              : "bg-white/[0.02] border-white/[0.08] hover:border-white/[0.15]"
          }`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3.5">
                <div className="w-11 h-11 rounded-2xl bg-emerald-500/15 border border-emerald-400/30 flex items-center justify-center text-emerald-400 shadow-md shrink-0">
                  <BrandIcon name="whatsapp" className="w-6 h-6" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-white">WhatsApp Web</h4>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase border flex items-center gap-1.5 ${
                      waStatus === "connected" && waUser
                        ? "bg-emerald-500/10 text-emerald-300 border-emerald-400/30"
                        : waStatus === "connecting" && waUser
                        ? "bg-amber-500/10 text-amber-300 border-amber-400/30 animate-pulse"
                        : "bg-white/[0.04] text-slate-400 border-white/10"
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${waStatus === "connected" && waUser ? "bg-emerald-400" : waStatus === "connecting" && waUser ? "bg-amber-400" : "bg-slate-500"}`} />
                      {waStatus === "connected" && waUser ? "Connected" : waStatus === "connecting" && waUser ? "Connecting..." : "Not Active"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {waStatus === "connected" && waUser
                      ? `${waUser.name || "Account"} (+${waUser.phone})`
                      : "Scan QR code to read and send messages"}
                  </p>
                </div>
              </div>
            </div>
    
            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between gap-2">
              {waStatus === "connected" ? (
                <>
                  <button
                    onClick={fetchWhatsAppStatus}
                    className="px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] text-slate-300 hover:text-white text-xs font-medium transition-all cursor-pointer"
                  >
                    Check Status
                  </button>
                  <button
                    onClick={handleWhatsAppLogout}
                    disabled={isWaLoading}
                    className="px-3 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 hover:text-white border border-rose-500/30 text-xs font-medium transition-all cursor-pointer"
                  >
                    Disconnect
                  </button>
                </>
              ) : (
                <button
                  onClick={openWhatsAppModal}
                  disabled={isWaLoading}
                  className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/40 text-emerald-100 hover:text-white text-xs font-medium transition-all cursor-pointer"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                  </svg>
                  Connect WhatsApp (Scan QR)
                </button>
              )}
            </div>

            {/* Whitelist Nomor WhatsApp */}
            <form onSubmit={handleSaveWhatsAppConfig} className="mt-3 pt-3 border-t border-white/10 space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-mono text-slate-300">
                  Authorized Numbers (Whitelist)
                </label>
                {isWaConfigSaved && (
                  <span className="text-[10px] font-mono text-emerald-300 animate-fade-in">
                    ✓ Saved
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g. 6281234567890 (leave empty to allow all)"
                  value={waAllowedNumbersInput}
                  onChange={(e) => setWaAllowedNumbersInput(e.target.value)}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-black/40 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-emerald-400 font-mono"
                />
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-200 border border-emerald-400/40 text-xs font-mono font-semibold transition-all cursor-pointer shrink-0"
                >
                  Save
                </button>
              </div>
              <p className="text-[10px] text-slate-400 leading-relaxed">
                Only numbers above will be responded to by Anara (safe from group spam/strangers).
              </p>
            </form>
          </div>
    
          {/* 2. KARTU TELEGRAM */}
          <div className={`p-4 sm:p-5 rounded-xl border flex flex-col justify-between transition-all shadow-sm ${
            tgStatus === "connected"
              ? "bg-white/[0.035] border-sky-400/40 shadow-[0_0_20px_rgba(56,189,248,0.06)]"
              : "bg-white/[0.02] border-white/[0.08] hover:border-white/[0.15]"
          }`}>
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-sky-500/15 border border-sky-400/30 flex items-center justify-center text-sky-400 shadow-md shrink-0">
                <BrandIcon name="telegram" className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-white">Telegram Bot</h4>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase border flex items-center gap-1.5 ${
                    tgStatus === "connected"
                      ? "bg-sky-500/10 text-sky-300 border-sky-400/30"
                      : "bg-white/[0.04] text-slate-400 border-white/10"
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${tgStatus === "connected" ? "bg-sky-400" : "bg-slate-500"}`} />
                    {tgStatus === "connected" ? "Active" : "Not Connected"}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  {tgStatus === "connected" && tgBot
                    ? `@${tgBot.username || "Bot"} (${tgBot.first_name || "Anara"})`
                    : "Link Telegram bot token to send and read messages"}
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between gap-2">
              <button
                onClick={() => setIsTgModalOpen(true)}
                className="px-3 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 text-sky-200 hover:text-white border border-sky-400/30 text-xs font-medium transition-all cursor-pointer"
              >
                {tgStatus === "connected" ? "Change Settings" : "Connect Telegram"}
              </button>
              {tgStatus === "connected" && (
                <span className="text-sky-300 text-xs font-mono">Ready to Use</span>
              )}
            </div>
          </div>
    
          {/* 3. KARTU GOOGLE WORKSPACE */}
          <div className={`p-4 sm:p-5 rounded-xl border flex flex-col justify-between transition-all shadow-sm ${
            googleStatus === "connected"
              ? "bg-white/[0.035] border-rose-400/40 shadow-[0_0_20px_rgba(251,113,133,0.06)]"
              : "bg-white/[0.02] border-white/[0.08] hover:border-white/[0.15]"
          }`}>
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-rose-500/15 border border-rose-400/30 flex items-center justify-center text-rose-300 shadow-md shrink-0">
                <BrandIcon name="google" className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-white">Google Workspace</h4>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase border flex items-center gap-1.5 ${
                    googleStatus === "connected"
                      ? "bg-rose-500/10 text-rose-300 border-rose-400/30"
                      : "bg-white/[0.04] text-slate-400 border-white/10"
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${googleStatus === "connected" ? "bg-rose-400" : "bg-slate-500"}`} />
                    {googleStatus === "connected" ? "Connected" : "Not Linked"}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  {googleStatus === "connected" && googleEmail
                    ? `${googleEmail} (Gmail &amp; Calendar)`
                    : "Reading incoming Gmail emails and Google Calendar schedule"}
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between gap-2">
              {googleStatus === "connected" ? (
                <>
                  <span className="text-rose-300 text-xs font-mono">Gmail &amp; Calendar Active</span>
                  <button
                    onClick={handleGoogleDisconnect}
                    className="px-3 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 hover:text-white border border-rose-500/30 text-xs font-medium transition-all cursor-pointer"
                  >
                    Disconnect
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setIsGoogleModalOpen(true)}
                  className="px-3 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-200 hover:text-white border border-rose-400/30 text-xs font-medium transition-all cursor-pointer"
                >
                  Link Google Account
                </button>
              )}
            </div>
          </div>
    
          {/* 4. KARTU SPOTIFY DESKTOP */}
          <div className="p-4 sm:p-5 rounded-xl bg-white/[0.02] border border-white/[0.08] hover:border-white/[0.15] flex flex-col justify-between shadow-sm">
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-400/30 flex items-center justify-center text-emerald-400 shadow-md shrink-0">
                <BrandIcon name="spotify" className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-white">Spotify Desktop</h4>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase border bg-emerald-500/10 text-emerald-300 border-emerald-400/30 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    Active
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Open native desktop player and control playback via autonomous agent
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between text-xs text-slate-400">
              <span>Direct voice commands:</span>
              <span className="text-emerald-300 font-mono">&quot;Play Music&quot;</span>
            </div>
          </div>
        </div>
      </div>

    {/* ── MODAL POPUP PAIRING QR CODE WHATSAPP ── */}
    {isWaModalOpen && (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-sm p-6 rounded-3xl liquid-glass border border-emerald-400/40 shadow-[0_0_50px_rgba(52,211,153,0.2)] flex flex-col items-center text-center">
        {/* Close Button */}
        <button
          onClick={() => setIsWaModalOpen(false)}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer"
        >
          ✕
        </button>
    
        <div className="w-12 h-12 rounded-2xl bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center text-emerald-400 mb-3 shadow-lg">
          <BrandIcon name="whatsapp" className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-semibold text-white tracking-wide">
          Connect WhatsApp
        </h3>
        <p className="text-xs text-slate-300 mt-1 mb-4 leading-relaxed">
          Open <span className="text-emerald-300 font-semibold">WhatsApp on your phone</span> &gt; Linked Devices &gt; Link a Device, then scan the QR code below:
        </p>
    
        {/* QR Code Container */}
        <div className="p-3.5 bg-white rounded-2xl shadow-2xl border-2 border-emerald-400/50 relative">
          {isWaLoading && !waQrUrl ? (
            <div className="w-52 h-52 flex flex-col items-center justify-center text-slate-800 font-mono text-xs gap-3">
              <span className="w-8 h-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
              <span>Menghubungkan Bridge...</span>
            </div>
          ) : waQrUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={waQrUrl}
              alt="WhatsApp QR Code"
              className="w-52 h-52 object-contain rounded-lg"
            />
          ) : (
            <div className="w-52 h-52 flex flex-col items-center justify-center text-slate-800 font-mono text-xs gap-2 p-2">
              <span>{waStatus === "connected" ? "Successfully Connected" : "Waiting for QR Code..."}</span>
            </div>
          )}
        </div>
    
        <div className="mt-4 flex items-center gap-2 text-[11px] font-mono text-emerald-300">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Modal will close automatically after successful scan</span>
        </div>
      </div>
    </div>
    )}
    
    {/* ── MODAL SETUP TELEGRAM BOT ── */}
    {isTgModalOpen && (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-sm p-6 rounded-3xl liquid-glass border border-sky-400/40 shadow-[0_0_50px_rgba(56,189,248,0.2)] flex flex-col text-left">
        <button
          onClick={() => setIsTgModalOpen(false)}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer"
        >
          ✕
        </button>
    
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-sky-500/15 border border-sky-400/30 flex items-center justify-center text-sky-400">
            <BrandIcon name="telegram" className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white tracking-wide">
              Telegram Settings
            </h3>
            <p className="text-[11px] text-slate-400">Connect your official Telegram bot</p>
          </div>
        </div>
    
        <form onSubmit={handleSaveTelegramConfig} className="space-y-3 mt-2">
          <div>
            <label className="text-[11px] font-mono text-slate-300 block mb-1">
              Telegram Bot Token (from @BotFather)
            </label>
            <input
              type="password"
              placeholder="misal: 123456789:ABCdefGhIJKlmNoPQ..."
              value={tgTokenInput}
              onChange={(e) => setTgTokenInput(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-black/50 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-sky-400 font-mono"
              required
            />
          </div>
    
          <div>
            <label className="text-[11px] font-mono text-slate-300 block mb-1">
              Default Chat ID (Opsional)
            </label>
            <input
              type="text"
              placeholder="e.g. 123456789 or -1001234567"
              value={tgChatIdInput}
              onChange={(e) => setTgChatIdInput(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-black/50 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-sky-400 font-mono"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-[11px] font-mono text-slate-300">
                Admin User IDs (Otorisasi Approval)
              </label>
              <span className="text-[9.5px] font-mono text-sky-300">
                Ketik /status in bot to check ID
              </span>
            </div>
            <input
              type="text"
              placeholder="misal: 7024711852 (pisahkan koma jika banyak)"
              value={tgAdminIdsInput}
              onChange={(e) => setTgAdminIdsInput(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-black/50 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-sky-400 font-mono"
            />
            <p className="text-[10px] text-slate-400 mt-1 leading-relaxed">
              Only user IDs registered here are authorized to press the <b>[Approve Plan]</b> button to execute terminal/file commands on PC.
            </p>
          </div>

          {tgErrorMsg && (
            <div className="p-2.5 rounded-xl bg-rose-500/20 border border-rose-500/40 text-rose-200 text-xs font-mono leading-relaxed">
              ⚠️ {tgErrorMsg}
            </div>
          )}
    
          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsTgModalOpen(false)}
              className="px-3 py-1.5 text-xs text-slate-400 hover:text-white"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={isTgLoading}
              className="px-4 py-1.5 rounded-xl bg-sky-500/20 hover:bg-sky-500/35 border border-sky-400/40 text-xs font-semibold text-white transition-all cursor-pointer"
            >
              {isTgLoading ? "Verifying..." : "Save & Connect"}
            </button>
          </div>
        </form>
      </div>
    </div>
    )}
    
    {/* ── MODAL SETUP GOOGLE WORKSPACE ── */}
    {isGoogleModalOpen && (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-sm p-6 rounded-3xl liquid-glass border border-rose-400/40 shadow-[0_0_50px_rgba(251,113,133,0.2)] flex flex-col text-left">
        <button
          onClick={() => setIsGoogleModalOpen(false)}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer"
        >
          ✕
        </button>
    
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-rose-500/15 border border-rose-400/30 flex items-center justify-center text-rose-300">
            <BrandIcon name="google" className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white tracking-wide">
              Google Workspace
            </h3>
            <p className="text-[11px] text-slate-400">Gmail Inbox &amp; Google Calendar</p>
          </div>
        </div>
    
        <form onSubmit={handleSaveGoogleConfig} className="space-y-3 mt-2">
          <div>
            <label className="text-[11px] font-mono text-slate-300 block mb-1">
              Alamat Email Google
            </label>
            <input
              type="email"
              placeholder="nama@gmail.com"
              value={googleEmailInput}
              onChange={(e) => setGoogleEmailInput(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-black/50 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-rose-400"
              required
            />
          </div>
    
          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsGoogleModalOpen(false)}
              className="px-3 py-1.5 text-xs text-slate-400 hover:text-white"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={isGoogleLoading}
              className="px-4 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/35 border border-rose-400/40 text-xs font-semibold text-white transition-all cursor-pointer"
            >
              {isGoogleLoading ? "Connecting..." : "Link Account"}
            </button>
          </div>
        </form>
      </div>
    </div>
    )}
    </>
  );
}
