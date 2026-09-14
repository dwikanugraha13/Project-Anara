"use client";

import React, { useState } from "react";
import { BrandIcon } from "../../types";

interface ProviderDetailViewProps {
  selectedProvider: any;
  onBack: () => void;
  activeAiModelId: string;
  onSelectModel: (modelId: string) => void;
  handleHideModel: (modelId: string, provider: string) => void;
  handleUnhideModel: (modelId: string, provider: string) => void;
  handleRestoreAllHidden: (provider: string) => void;
  handleDeleteCustomProvider: (providerId: number, name: string) => void;
  handleToggleCustomProvider: (providerId: number, e?: React.MouseEvent) => void;
  handleDisconnectProvider: (providerId: string) => void;
  handleOAuthLogin: (providerId: string) => void;
  handleAddAccount: (providerId: string) => void;
  handleToggleAccount: (providerId: string, accountId: number) => void;
  handleDeleteAccount: (providerId: string, accountId: number, label: string) => void;
  providerLabelInputs: Record<string, string>;
  setProviderLabelInputs: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  providerKeyInputs: Record<string, string>;
  setProviderKeyInputs: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  isConnectingProvider: string | null;
  hiddenModelsByProvider: Record<string, string[]>;
}

export default function ProviderDetailView({
  selectedProvider,
  onBack,
  activeAiModelId,
  onSelectModel,
  handleHideModel,
  handleUnhideModel,
  handleRestoreAllHidden,
  handleDeleteCustomProvider,
  handleToggleCustomProvider,
  handleDisconnectProvider,
  handleOAuthLogin,
  handleAddAccount,
  handleToggleAccount,
  handleDeleteAccount,
  providerLabelInputs,
  setProviderLabelInputs,
  providerKeyInputs,
  setProviderKeyInputs,
  isConnectingProvider,
  hiddenModelsByProvider,
}: ProviderDetailViewProps) {
  const [providerDetailTab, setProviderDetailTab] = useState<"accounts" | "models" | "endpoint">("accounts");
  const [detailModelSearch, setDetailModelSearch] = useState("");
  const [detailCategoryFilter, setDetailCategoryFilter] = useState("all");
  const [detailOnlyEnabled, setDetailOnlyEnabled] = useState(false);

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Top Navigation & Breadcrumb */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-2xl liquid-glass border border-white/10 shadow-md">
        <button
          type="button"
          onClick={onBack}
          className="px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-200 hover:text-white border border-white/15 text-xs font-mono font-medium transition-all cursor-pointer flex items-center gap-2 group shadow-sm w-fit"
        >
        <span className="text-cyan-400 group-hover:-translate-x-1 transition-transform font-bold text-sm">←</span>
        <span>Kembali ke Daftar Provider</span>
      </button>
        
      <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
        <span className="text-slate-500">Providers</span>
        <span className="text-slate-600">/</span>
        <span className="text-cyan-300 font-bold">{selectedProvider.name}</span>
        <span className="text-slate-600">/</span>
        <span className="px-2 py-0.5 rounded-md text-[10px] bg-white/5 border border-white/10 text-slate-400">
          {selectedProvider.is_custom ? "Custom Provider" : "Official / OAuth"}
        </span>
      </div>
    </div>
        
    {/* Big Provider Banner Card */}
    <div className="p-6 rounded-3xl liquid-glass border border-white/15 shadow-xl relative overflow-hidden">
      <div className={`absolute -right-10 -top-10 w-60 h-60 rounded-full blur-3xl pointer-events-none opacity-20 ${
        selectedProvider.id === "codex" ? "bg-emerald-500" : selectedProvider.id === "gemini" ? "bg-cyan-500" : "bg-purple-500"
      }`} />
        
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 relative z-10">
        <div className="flex items-center gap-4 min-w-0">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 border shadow-lg ${
            selectedProvider.id === "codex"
              ? "bg-emerald-500/20 border-emerald-400/40 text-emerald-300 shadow-emerald-950/40"
              : selectedProvider.id === "gemini"
              ? "bg-cyan-500/20 border-cyan-400/40 text-cyan-300 shadow-cyan-950/40"
              : "bg-white/10 border-white/20 text-white shadow-black/40"
          }`}>
            <BrandIcon name={selectedProvider.id} className="w-8 h-8" />
          </div>
        
          <div className="min-w-0">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h3 className="text-lg font-bold text-white tracking-wide">{selectedProvider.name}</h3>
              {selectedProvider.is_connected ? (
                <span className="px-2.5 py-0.5 rounded-lg text-xs font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-400/30 uppercase flex items-center gap-1.5 shadow-sm">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  {selectedProvider.accounts?.length || 0} Akun Terhubung · {selectedProvider.models?.length || 0} Model
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded-lg text-xs font-mono text-slate-400 bg-white/5 border border-white/10 uppercase">
                  Belum Terhubung
                </span>
              )}
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
                {selectedProvider.badge}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed max-w-2xl">
              {selectedProvider.description}
            </p>
          </div>
        </div>
        
        {/* Action Buttons */}
        <div className="flex items-center gap-2 shrink-0">
          {selectedProvider.is_custom && selectedProvider.custom_data ? (
            <button
              type="button"
              onClick={() => handleDeleteCustomProvider(selectedProvider.custom_data.id, selectedProvider.name)}
              className="px-3.5 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/30 text-rose-300 hover:text-rose-100 border border-rose-400/30 text-xs font-mono font-medium transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
            >
              <span>Hapus Provider</span>
            </button>
          ) : selectedProvider.is_connected ? (
            <button
              type="button"
              onClick={() => handleDisconnectProvider(selectedProvider.id)}
              className="px-3.5 py-1.5 rounded-xl bg-white/5 hover:bg-rose-500/20 text-slate-400 hover:text-rose-200 border border-white/10 text-xs font-mono transition-all cursor-pointer"
            >
              Putuskan Sambungan
            </button>
          ) : null}
        </div>
      </div>
    </div>
        
    {/* Segmented Control Navigation Tabs */}
    <div className="flex items-center gap-2 p-1.5 rounded-2xl liquid-glass border border-white/10 font-mono text-xs shadow-md">
      <button
        type="button"
        onClick={() => setProviderDetailTab("accounts")}
        className={`py-2 px-4 rounded-xl font-medium border transition-colors duration-150 ease-out cursor-pointer flex items-center gap-2 select-none ${
          providerDetailTab === "accounts"
            ? "bg-cyan-500/20 text-cyan-200 border-cyan-400/40 shadow-sm"
            : "border-transparent text-slate-400 hover:text-white hover:bg-white/[0.04]"
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
        </svg>
        <span>Akun &amp; Pool Kunci</span>
        <span className="px-2 py-0.2 rounded-full bg-white/10 text-[11px]">
          {selectedProvider.accounts?.length || 0}
        </span>
      </button>
        
      <button
        type="button"
        onClick={() => setProviderDetailTab("models")}
        className={`py-2 px-4 rounded-xl font-medium border transition-colors duration-150 ease-out cursor-pointer flex items-center gap-2 select-none ${
          providerDetailTab === "models"
            ? "bg-cyan-500/20 text-cyan-200 border-cyan-400/40 shadow-sm"
            : "border-transparent text-slate-400 hover:text-white hover:bg-white/[0.04]"
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
        <span>Katalog Model AI</span>
        <span className="px-2 py-0.2 rounded-full bg-white/10 text-[11px]">
          {selectedProvider.models?.length || 0}
        </span>
      </button>
        
      {selectedProvider.is_custom && (
        <button
          type="button"
          onClick={() => setProviderDetailTab("endpoint")}
          className={`py-2 px-4 rounded-xl font-medium border transition-colors duration-150 ease-out cursor-pointer flex items-center gap-2 select-none ${
            providerDetailTab === "endpoint"
              ? "bg-cyan-500/20 text-cyan-200 border-cyan-400/40 shadow-sm"
              : "border-transparent text-slate-400 hover:text-white hover:bg-white/[0.04]"
          }`}
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span>Endpoint &amp; Konfigurasi</span>
        </button>
      )}
    </div>
        
    {/* Full-view Body Sections */}
    <div className="p-6 rounded-3xl liquid-glass border border-white/15 shadow-xl space-y-4">
      {/* TAB 1: AKUN & KONEKSI */}
      {providerDetailTab === "accounts" && (
        <div className="space-y-4">
          {/* If Codex OAuth */}
          {(selectedProvider.auth_type === "oauth_or_key" || selectedProvider.id === "codex") && (
            <div className="p-5 rounded-2xl bg-gradient-to-r from-emerald-500/10 via-teal-500/10 to-cyan-500/10 border border-emerald-500/30 space-y-3 shadow-md">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <BrandIcon name="openai" className="w-5 h-5 text-emerald-400" />
                  <span className="text-sm font-bold text-white">Login Cepat Akun OpenAI (OAuth PKCE)</span>
                </div>
                <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-400/30 font-semibold">
                  Resmi Codex CLI
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed max-w-2xl">
                Login langsung dengan akun ChatGPT/OpenAI Anda via popup otentikasi resmi. <strong>Tanpa perlu API key berbayar</strong> dan tanpa kartu kredit terpisah.
              </p>
              <button
                type="button"
                onClick={() => handleOAuthLogin(selectedProvider.id)}
                disabled={isConnectingProvider === selectedProvider.id}
                className="w-full sm:w-auto py-2.5 px-6 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold font-mono transition-all cursor-pointer shadow-lg shadow-emerald-950/50 flex items-center justify-center gap-2 border border-emerald-400/40 disabled:opacity-50"
              >
                <BrandIcon name="openai" className="w-4 h-4 text-white" />
                <span>{isConnectingProvider === selectedProvider.id ? "Menghubungkan OAuth..." : "Login dengan Akun OpenAI (OAuth PKCE)"}</span>
              </button>
            </div>
          )}
        
          {(selectedProvider.auth_type === "oauth_or_key" || selectedProvider.id === "codex") && (
            <div className="relative flex py-1 items-center">
              <div className="flex-grow border-t border-white/10" />
              <span className="flex-shrink mx-3 text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                atau masukkan API Key / Access Token manual
              </span>
              <div className="flex-grow border-t border-white/10" />
            </div>
          )}
        
          {/* Input Form Tambah Akun */}
          <div className="p-4 rounded-2xl bg-black/40 border border-white/10 space-y-3">
            <span className="text-[10px] font-mono font-bold uppercase text-slate-400 block">
              {selectedProvider.is_connected ? "+ Tambah Akun ke Pool (Auto-Rotate)" : "Hubungkan Akun / Kunci API"}
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <input
                type="text"
                placeholder="Label Akun (mis: Utama / Backup)"
                value={providerLabelInputs[selectedProvider.id] ?? ""}
                onChange={(e) => setProviderLabelInputs((prev) => ({ ...prev, [selectedProvider.id]: e.target.value }))}
                className="sm:col-span-1 px-3.5 py-2 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-400 font-mono"
              />
              <input
                type="password"
                placeholder={selectedProvider.key_placeholder || "Masukkan API Key / Token..."}
                value={providerKeyInputs[selectedProvider.id] ?? ""}
                onChange={(e) => setProviderKeyInputs((prev) => ({ ...prev, [selectedProvider.id]: e.target.value }))}
                className="sm:col-span-2 px-3.5 py-2 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-400 font-mono"
              />
            </div>
            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={() => handleAddAccount(selectedProvider.id)}
                disabled={isConnectingProvider === selectedProvider.id || !(providerKeyInputs[selectedProvider.id] || "").trim()}
                className="px-5 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/35 border border-cyan-400/40 text-xs font-semibold text-white transition-all cursor-pointer disabled:opacity-40 flex items-center gap-1.5 shadow-sm"
              >
                <span>+</span> {isConnectingProvider === selectedProvider.id ? "Menyimpan..." : "Simpan & Hubungkan"}
              </button>
            </div>
          </div>
        
          {/* DAFTAR AKUN DENGAN TOGGLE ON/OFF PER AKUN */}
          <div className="space-y-2.5">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 block">
              Daftar Akun Terhubung ({selectedProvider.accounts?.length || 0}):
            </span>
            {(!selectedProvider.accounts || selectedProvider.accounts.length === 0) ? (
              <div className="p-6 rounded-2xl bg-black/30 border border-white/5 text-center text-xs font-mono text-slate-500">
                Belum ada akun yang terdaftar untuk provider ini.
              </div>
            ) : (
              <div className="space-y-2">
                {selectedProvider.accounts.map((acc: any) => {
                  const isEnabled = acc.is_enabled !== 0;
                  return (
                    <div
                      key={acc.id}
                      className={`p-3.5 rounded-2xl border transition-all flex items-center justify-between gap-3 ${
                        isEnabled
                          ? "bg-black/40 border-white/15 hover:border-white/25 shadow-sm"
                          : "bg-black/20 border-white/5 opacity-50"
                      }`}
                    >
                      <div className="flex items-center gap-3 truncate min-w-0 flex-1">
                        <div className="w-8 h-8 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-cyan-400 shrink-0">
                          🔑
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-bold text-white truncate font-mono">
                              {acc.account_label}
                            </span>
                            {isEnabled ? (
                              <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-400/30 font-semibold">
                                Aktif
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-slate-700/50 text-slate-400 border border-slate-600/30">
                                Nonaktif
                              </span>
                            )}
                            {acc.status === "cooldown" && (
                              <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-amber-500/15 text-amber-300 border border-amber-400/30">
                                Cooldown
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono block truncate mt-0.5">
                            {acc.masked_key} · {acc.requests_count || 0} reqs
                          </span>
                        </div>
                      </div>
        
                      {/* Right Actions: On/Off Switch & Delete */}
                      <div className="flex items-center gap-3 shrink-0">
                        {/* Account Toggle Switch */}
                        <div
                          onClick={() => handleToggleAccount(selectedProvider.id, acc.id)}
                          className={`w-10 h-5 rounded-full p-0.5 transition-colors cursor-pointer shrink-0 ${
                            isEnabled ? "bg-emerald-500" : "bg-slate-700/60"
                          }`}
                          title={isEnabled ? "Klik untuk menonaktifkan akun ini" : "Klik untuk mengaktifkan akun ini"}
                        >
                          <div
                            className={`w-4 h-4 rounded-full bg-white transition-transform shadow-sm ${
                              isEnabled ? "translate-x-5" : "translate-x-0"
                            }`}
                          />
                        </div>
        
                        <button
                          type="button"
                          onClick={() => handleDeleteAccount(selectedProvider.id, acc.id, acc.account_label)}
                          className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/25 text-rose-300 hover:text-rose-100 transition-colors cursor-pointer text-xs"
                          title="Hapus akun ini"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        
          {/* Portal link footer */}
          {selectedProvider.signup_url && (
            <div className="pt-3 border-t border-white/10 flex items-center justify-between text-xs font-mono">
              <span className="text-slate-500 text-[11px]">Portal Resmi:</span>
              <a
                href={selectedProvider.signup_url}
                target="_blank"
                rel="noreferrer"
                className="text-cyan-300 hover:text-white underline text-[11px]"
              >
                {selectedProvider.signup_label}
              </a>
            </div>
          )}
        </div>
      )}
        
      {/* TAB 2: KATALOG MODEL */}
      {providerDetailTab === "models" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-mono uppercase text-slate-400 font-bold">
              Katalog Model AI ({selectedProvider.models?.length || 0})
            </span>
            <input
              type="text"
              placeholder="Filter model..."
              value={detailModelSearch}
              onChange={(e) => setDetailModelSearch(e.target.value)}
              className="w-48 px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-400 font-mono"
            />
          </div>
        
          {(!selectedProvider.models || selectedProvider.models.length === 0) ? (
            <div className="p-8 rounded-2xl bg-black/30 text-center text-xs text-slate-500 font-mono">
              Belum ada model aktif. Silakan hubungkan akun di tab Akun &amp; Koneksi.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[480px] overflow-y-auto custom-scrollbar pr-1">
              {selectedProvider.models
                .filter((m: any) =>
                  !detailModelSearch ||
                  m.name.toLowerCase().includes(detailModelSearch.toLowerCase()) ||
                  m.id.toLowerCase().includes(detailModelSearch.toLowerCase()) ||
                  (m.badge || "").toLowerCase().includes(detailModelSearch.toLowerCase())
                )
                .map((m: any) => (
                  <div
                    key={m.id}
                    className="flex items-center justify-between p-3 rounded-2xl text-xs bg-black/40 border border-white/5 hover:bg-white/[0.04] text-slate-200 group"
                  >
                    <div className="flex items-center gap-2.5 truncate flex-1 min-w-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
                      <div className="min-w-0">
                        <p className="font-medium truncate text-white">{m.name}</p>
                        <p className="text-[10px] text-slate-500 font-mono truncate">{m.id}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
                        {m.badge}
                      </span>
                      <button
                        onClick={() => handleHideModel(m.id, selectedProvider.id)}
                        className="text-slate-500 hover:text-rose-400 p-1 rounded hover:bg-rose-500/10 transition-colors cursor-pointer"
                        title="Sembunyikan model ini"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          )}
        
          {/* Disabled / Hidden Models Section (9Router-style below available models) */}
          {hiddenModelsByProvider[selectedProvider.id] && hiddenModelsByProvider[selectedProvider.id].length > 0 && (
            <div className="pt-4 border-t border-white/10 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono text-slate-400 font-bold tracking-wide">
                  Disabled models ({hiddenModelsByProvider[selectedProvider.id].length}):
                </span>
                <button
                  type="button"
                  onClick={() => handleRestoreAllHidden(selectedProvider.id)}
                  className="text-[10px] text-cyan-400 hover:text-cyan-200 font-mono font-bold cursor-pointer transition-colors"
                >
                  Pulihkan Semua
                </button>
              </div>
        
              <div className="flex flex-wrap gap-2">
                {hiddenModelsByProvider[selectedProvider.id].map((mId) => (
                  <button
                    key={mId}
                    type="button"
                    onClick={() => handleUnhideModel(mId, selectedProvider.id)}
                    className="px-3 py-1.5 rounded-xl bg-black/40 hover:bg-black/60 border border-white/10 hover:border-cyan-400/40 text-xs font-mono text-slate-400 hover:text-white transition-all cursor-pointer flex items-center gap-1.5 shadow-sm group"
                    title={`Aktifkan kembali model ${mId}`}
                  >
                    <span className="text-cyan-400 font-bold group-hover:scale-110 transition-transform">+</span>
                    <span>{mId}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
        
      {/* TAB 3: ENDPOINT (KHUSUS CUSTOM PROVIDER) */}
      {providerDetailTab === "endpoint" && selectedProvider.is_custom && selectedProvider.custom_data && (
        <div className="space-y-4 font-mono text-xs">
          <div className="p-5 rounded-2xl bg-black/40 border border-white/10 space-y-3">
            <div>
              <span className="text-[10px] uppercase text-slate-500 block">Base URL</span>
              <span className="text-white font-semibold text-sm">{selectedProvider.custom_data.base_url}</span>
            </div>
            <div>
              <span className="text-[10px] uppercase text-slate-500 block">Prefix</span>
              <span className="text-cyan-300 font-semibold">{selectedProvider.custom_data.prefix}</span>
            </div>
            <div>
              <span className="text-[10px] uppercase text-slate-500 block">API Type</span>
              <span className="text-slate-300 font-semibold">{selectedProvider.custom_data.api_type}</span>
            </div>
            {selectedProvider.custom_data.default_model && (
              <div>
                <span className="text-[10px] uppercase text-slate-500 block">Default Model</span>
                <span className="text-slate-300">{selectedProvider.custom_data.default_model}</span>
              </div>
            )}
          </div>
        
          <div className="pt-2 flex justify-end">
            <button
              type="button"
              onClick={() => handleDeleteCustomProvider(selectedProvider.custom_data.id, selectedProvider.name)}
              className="px-4 py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/30 text-rose-300 hover:text-rose-100 border border-rose-400/30 text-xs font-mono font-medium transition-all cursor-pointer flex items-center gap-1.5"
            >
              <span>Hapus Custom Provider Ini</span>
            </button>
          </div>
        </div>
      )}
    </div>
  </div>
);
}
