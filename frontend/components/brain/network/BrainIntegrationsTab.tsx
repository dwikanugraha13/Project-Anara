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
  const [contacts, setContacts] = useState<Array<{ id: number; name: string; phone_number: string; platform: string }>>([]);
  const [newContactName, setNewContactName] = useState("");
  const [newContactPhone, setNewContactPhone] = useState("");
  const [isAddContactOpen, setIsAddContactOpen] = useState(false);

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

  const fetchContacts = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/contacts`);
      if (res.ok) {
        const data = await res.json();
        setContacts(data || []);
      }
    } catch {}
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
    if (!confirm("Apakah Anda yakin ingin memutuskan sambungan WhatsApp? Sesi akan dihapus.")) return;
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

  const handleSaveContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContactName.trim() || !newContactPhone.trim()) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/contacts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newContactName, phone_number: newContactPhone, platform: "whatsapp" }),
      });
      if (res.ok) {
        setNewContactName("");
        setNewContactPhone("");
        setIsAddContactOpen(false);
        fetchContacts();
      }
    } catch (err) {
      console.error("Save contact error:", err);
    }
  };

  const handleDeleteContact = async (id: number) => {
    if (!confirm("Hapus kontak ini?")) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/integrations/contacts/${id}`, { method: "DELETE" });
      if (res.ok) {
        setContacts((prev) => prev.filter((c) => c.id !== id));
      }
    } catch (err) {
      console.error("Delete contact error:", err);
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
          setTgErrorMsg(data.message || "Token tidak valid menurut Telegram Bot API.");
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        setTgErrorMsg(errData.detail || "Gagal menghubungi server backend.");
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
    fetchContacts();
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
        } else if (isAddContactOpen) {
          setIsAddContactOpen(false);
          e.stopPropagation();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isWaModalOpen, isTgModalOpen, isGoogleModalOpen, isAddContactOpen]);

  return (
    <>
      <div className="space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 sm:p-5 rounded-2xl liquid-glass border border-white/10">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <h3 className="text-xs sm:text-sm font-semibold text-white tracking-wide">
                Integrasi Layanan &amp; Media
              </h3>
            </div>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Hubungkan WhatsApp, Telegram, Google Workspace, atau Spotify untuk sinkronisasi pesan dan kontrol media secara langsung.
            </p>
          </div>
        </div>
    
        {/* Grid Kartu Integrasi */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 1. KARTU WHATSAPP */}
          <div className={`p-5 rounded-2xl border transition-all flex flex-col justify-between ${
            waStatus === "connected"
              ? "liquid-glass border-emerald-400/40 shadow-[0_0_25px_rgba(52,211,153,0.1)]"
              : "liquid-glass-subtle hover:border-white/20"
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
                      {waStatus === "connected" && waUser ? "Terhubung" : waStatus === "connecting" && waUser ? "Menghubungkan..." : "Belum Aktif"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {waStatus === "connected" && waUser
                      ? `${waUser.name || "Akun"} (+${waUser.phone})`
                      : "Scan QR code untuk membaca &amp; mengirim pesan"}
                  </p>
                </div>
              </div>
            </div>
    
            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between gap-2">
              {waStatus === "connected" ? (
                <>
                  <button
                    onClick={fetchWhatsAppStatus}
                    className="px-3 py-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] text-slate-300 hover:text-white text-xs font-medium transition-all cursor-pointer"
                  >
                    Cek Status
                  </button>
                  <button
                    onClick={handleWhatsAppLogout}
                    disabled={isWaLoading}
                    className="px-3 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 hover:text-white border border-rose-500/30 text-xs font-medium transition-all cursor-pointer"
                  >
                    Putuskan Sambungan
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
                  Hubungkan WhatsApp (Scan QR)
                </button>
              )}
            </div>

            {/* Whitelist Nomor WhatsApp */}
            <form onSubmit={handleSaveWhatsAppConfig} className="mt-3 pt-3 border-t border-white/10 space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-mono text-slate-300">
                  Nomor Terotorisasi (Whitelist)
                </label>
                {isWaConfigSaved && (
                  <span className="text-[10px] font-mono text-emerald-300 animate-fade-in">
                    ✓ Tersimpan
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="misal: 6281234567890 (kosongkan jika terima semua)"
                  value={waAllowedNumbersInput}
                  onChange={(e) => setWaAllowedNumbersInput(e.target.value)}
                  className="flex-1 px-3 py-1.5 rounded-xl bg-black/40 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-emerald-400 font-mono"
                />
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-200 border border-emerald-400/40 text-xs font-mono font-semibold transition-all cursor-pointer shrink-0"
                >
                  Simpan
                </button>
              </div>
              <p className="text-[10px] text-slate-400 leading-relaxed">
                Hanya nomor di atas yang direspons Anara (aman dari spam grup/orang asing).
              </p>
            </form>
          </div>
    
          {/* 2. KARTU TELEGRAM */}
          <div className={`p-5 rounded-2xl border flex flex-col justify-between transition-all ${
            tgStatus === "connected"
              ? "liquid-glass border-sky-400/40 shadow-[0_0_25px_rgba(56,189,248,0.1)]"
              : "liquid-glass-subtle hover:border-white/20"
          }`}>
            <div className="flex items-start gap-3.5">
              <div className="w-11 h-11 rounded-2xl bg-sky-500/15 border border-sky-400/30 flex items-center justify-center text-sky-400 shadow-md shrink-0">
                <BrandIcon name="telegram" className="w-6 h-6" />
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
                    {tgStatus === "connected" ? "Aktif" : "Belum Terhubung"}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  {tgStatus === "connected" && tgBot
                    ? `@${tgBot.username || "Bot"} (${tgBot.first_name || "Anara"})`
                    : "Tautkan bot token Telegram untuk kirim &amp; baca pesan"}
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between gap-2">
              <button
                onClick={() => setIsTgModalOpen(true)}
                className="px-3 py-1.5 rounded-xl bg-sky-500/15 hover:bg-sky-500/25 text-sky-200 hover:text-white border border-sky-400/30 text-xs font-medium transition-all cursor-pointer"
              >
                {tgStatus === "connected" ? "Ubah Pengaturan" : "Hubungkan Telegram"}
              </button>
              {tgStatus === "connected" && (
                <span className="text-sky-300 text-xs font-mono">Siap Digunakan</span>
              )}
            </div>
          </div>
    
          {/* 3. KARTU GOOGLE WORKSPACE */}
          <div className={`p-5 rounded-2xl border flex flex-col justify-between transition-all ${
            googleStatus === "connected"
              ? "liquid-glass border-rose-400/40 shadow-[0_0_25px_rgba(251,113,133,0.1)]"
              : "liquid-glass-subtle hover:border-white/20"
          }`}>
            <div className="flex items-start gap-3.5">
              <div className="w-11 h-11 rounded-2xl bg-rose-500/15 border border-rose-400/30 flex items-center justify-center text-rose-300 shadow-md shrink-0">
                <BrandIcon name="google" className="w-6 h-6" />
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
                    {googleStatus === "connected" ? "Terhubung" : "Belum Ditautkan"}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  {googleStatus === "connected" && googleEmail
                    ? `${googleEmail} (Gmail &amp; Calendar)`
                    : "Membaca email Gmail masuk &amp; jadwal Google Calendar"}
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between gap-2">
              {googleStatus === "connected" ? (
                <>
                  <span className="text-rose-300 text-xs font-mono">Gmail &amp; Calendar Aktif</span>
                  <button
                    onClick={handleGoogleDisconnect}
                    className="px-3 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 hover:text-white border border-rose-500/30 text-xs font-medium transition-all cursor-pointer"
                  >
                    Putuskan
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setIsGoogleModalOpen(true)}
                  className="px-3 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-200 hover:text-white border border-rose-400/30 text-xs font-medium transition-all cursor-pointer"
                >
                  Tautkan Akun Google
                </button>
              )}
            </div>
          </div>
    
          {/* 4. KARTU SPOTIFY DESKTOP */}
          <div className="p-5 rounded-2xl liquid-glass-subtle border border-white/10 hover:border-white/20 flex flex-col justify-between">
            <div className="flex items-start gap-3.5">
              <div className="w-11 h-11 rounded-2xl bg-emerald-500/15 border border-emerald-400/30 flex items-center justify-center text-emerald-400 shadow-md shrink-0">
                <BrandIcon name="spotify" className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-white">Spotify Desktop</h4>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase border bg-emerald-500/10 text-emerald-300 border-emerald-400/30 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    Aktif
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Buka aplikasi &amp; putar lagu langsung di desktop laptop Anda
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between text-xs text-slate-400">
              <span>Perintah suara langsung:</span>
              <span className="text-emerald-300 font-mono">&quot;Buka Spotify&quot;</span>
            </div>
          </div>
        </div>
    
    
    
        {/* ── BUKU KONTAK WHATSAPP (CONTACTS BOOK) ── */}
        <div className="p-5 rounded-2xl liquid-glass border border-white/10 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-semibold text-white tracking-wide flex items-center gap-2">
                <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                <span>Buku Kontak WhatsApp</span>
              </h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Daftar nama panggilan dan nomor telepon agar Anara dapat mengirim pesan ke kontak Anda secara langsung.
              </p>
            </div>
            <button
              onClick={() => setIsAddContactOpen((v) => !v)}
              className="px-3 py-1.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-200 hover:text-white border border-emerald-400/30 text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5"
            >
              <span>+</span> Tambah Kontak
            </button>
          </div>
    
          {/* Form Tambah Kontak */}
          {isAddContactOpen && (
            <form onSubmit={handleSaveContact} className="p-4 rounded-xl bg-black/40 border border-emerald-400/30 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-mono text-slate-400 block mb-1">Nama Panggilan</label>
                  <input
                    type="text"
                    placeholder="misal: Budi / Ibu / Kantor"
                    value={newContactName}
                    onChange={(e) => setNewContactName(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-black/50 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-emerald-400"
                    required
                  />
                </div>
                <div>
                  <label className="text-[11px] font-mono text-slate-400 block mb-1">Nomor WhatsApp</label>
                  <input
                    type="text"
                    placeholder="misal: 08123456789 atau 628123456789"
                    value={newContactPhone}
                    onChange={(e) => setNewContactPhone(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-black/50 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-emerald-400"
                    required
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddContactOpen(false)}
                  className="px-3 py-1 text-xs text-slate-400 hover:text-white"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-emerald-500/30 hover:bg-emerald-500/50 border border-emerald-400 text-xs font-bold text-white shadow-md cursor-pointer"
                >
                  Simpan Kontak
                </button>
              </div>
            </form>
          )}
    
          {/* List Kontak */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 max-h-[220px] overflow-y-auto pr-1 custom-scrollbar">
            {contacts.length === 0 ? (
              <div className="col-span-full py-6 text-center text-xs text-slate-500 italic">
                Belum ada kontak tersimpan. Tambahkan kontak di atas atau ucapkan: &quot;Anara, catat kontak Budi nomornya 0812...&quot;
              </div>
            ) : (
              contacts.map((c) => (
                <div key={c.id} className="p-2.5 px-3 rounded-xl bg-black/30 border border-white/10 flex items-center justify-between gap-2 group hover:border-emerald-400/40 transition-colors">
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-white truncate">{c.name}</p>
                    <p className="text-[10px] font-mono text-emerald-300/80 truncate">+{c.phone_number}</p>
                  </div>
                  <button
                    onClick={() => handleDeleteContact(c.id)}
                    className="w-6 h-6 rounded flex items-center justify-center text-slate-500 hover:text-rose-300 hover:bg-rose-500/20 transition-all opacity-0 group-hover:opacity-100 cursor-pointer"
                    title="Hapus kontak"
                  >
                    ✕
                  </button>
                </div>
              ))
            )}
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
          Hubungkan WhatsApp
        </h3>
        <p className="text-xs text-slate-300 mt-1 mb-4 leading-relaxed">
          Buka <span className="text-emerald-300 font-semibold">WhatsApp di HP</span> &gt; Perangkat Tertaut &gt; Tautkan Perangkat, lalu scan kode QR di bawah ini:
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
              <span>{waStatus === "connected" ? "Berhasil Terhubung" : "Menunggu QR Code..."}</span>
            </div>
          )}
        </div>
    
        <div className="mt-4 flex items-center gap-2 text-[11px] font-mono text-emerald-300">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Modal akan tertutup otomatis setelah scan berhasil</span>
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
              Pengaturan Telegram
            </h3>
            <p className="text-[11px] text-slate-400">Hubungkan bot Telegram resmi Anda</p>
          </div>
        </div>
    
        <form onSubmit={handleSaveTelegramConfig} className="space-y-3 mt-2">
          <div>
            <label className="text-[11px] font-mono text-slate-300 block mb-1">
              Telegram Bot Token (dari @BotFather)
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
              placeholder="misal: 123456789 atau -1001234567"
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
                Ketik /status di bot untuk cek ID
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
              Hanya ID pengguna yang terdaftar di sini yang berhak menekan tombol <b>[Setujui Rencana]</b> untuk eksekusi perintah terminal/file di PC.
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
              {isTgLoading ? "Memverifikasi..." : "Simpan & Hubungkan"}
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
              {isGoogleLoading ? "Menghubungkan..." : "Tautkan Akun"}
            </button>
          </div>
        </form>
      </div>
    </div>
    )}
    </>
  );
}
