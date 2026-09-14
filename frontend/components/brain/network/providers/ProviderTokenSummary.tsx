"use client";

import React, { useState } from "react";

export interface TokenSummaryData {
  overall?: { total_tokens: number; total_prompt: number; total_completion: number; total_requests: number };
  today?: { today_tokens: number; today_requests: number };
  by_provider?: Array<{ provider: string; requests: number; total_tokens: number }>;
  top_models?: Array<{ model_id: string; requests: number; total_tokens: number }>;
}

export interface TokenLogEntry {
  id: number;
  model_id: string;
  provider: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  created_at: string;
}

interface ProviderTokenSummaryProps {
  tokenSummary: TokenSummaryData | null;
  tokenLogs: TokenLogEntry[];
}

export default function ProviderTokenSummary({
  tokenSummary,
  tokenLogs,
}: ProviderTokenSummaryProps) {
  const [showTokenHistory, setShowTokenHistory] = useState(false);

  if (!tokenSummary) return null;

  return (
    <div className="space-y-3">
      {/* ── Token Usage & Credit Tracking Summary Cards (Compact Liquid Glass) ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-3.5 rounded-2xl liquid-glass border border-white/10 space-y-0.5">
          <span className="text-[10px] font-mono font-bold uppercase text-slate-400">Total Token Terpakai</span>
          <p className="text-lg font-bold text-white font-mono">
            {(tokenSummary.overall?.total_tokens || 0).toLocaleString()} <span className="text-xs text-cyan-300 font-normal">tokens</span>
          </p>
          <p className="text-[10px] text-slate-500 font-mono">
            In: {(tokenSummary.overall?.total_prompt || 0).toLocaleString()} · Out: {(tokenSummary.overall?.total_completion || 0).toLocaleString()}
          </p>
        </div>

        <div className="p-3.5 rounded-2xl liquid-glass border border-white/10 space-y-0.5">
          <span className="text-[10px] font-mono font-bold uppercase text-slate-400">Penggunaan Hari Ini</span>
          <p className="text-lg font-bold text-slate-200 font-mono">
            {(tokenSummary.today?.today_tokens || 0).toLocaleString()} <span className="text-xs text-slate-400 font-normal">tokens</span>
          </p>
          <p className="text-[10px] text-slate-500 font-mono">
            {tokenSummary.today?.today_requests || 0} kali permintaan turn
          </p>
        </div>

        <div className="p-3.5 rounded-2xl liquid-glass border border-white/10 flex items-center justify-between">
          <div className="space-y-0.5">
            <span className="text-[10px] font-mono font-bold uppercase text-slate-400">Riwayat Token</span>
            <p className="text-xs text-slate-300 font-mono">
              {tokenLogs.length} transaksi tercatat
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowTokenHistory((v) => !v)}
            className="px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-slate-200 border border-white/15 text-[11px] font-mono font-medium transition-all cursor-pointer flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <span>{showTokenHistory ? "Tutup" : "Lihat Log"}</span>
          </button>
        </div>
      </div>

      {/* ── Tabel Riwayat Token Logs (Accordion) ── */}
      {showTokenHistory && (
        <div className="p-4 rounded-2xl bg-black/40 border border-white/15 space-y-3">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <span className="text-xs font-mono font-bold text-white flex items-center gap-1.5">
              Log Transaksi Pemakaian Token &amp; Kredit
            </span>
            <span className="text-[10px] font-mono text-slate-400">50 interaksi terakhir</span>
          </div>

          {tokenLogs.length === 0 ? (
            <p className="text-xs text-slate-500 font-mono text-center py-4">Belum ada catatan pemakaian token.</p>
          ) : (
            <div className="max-h-[260px] overflow-y-auto custom-scrollbar pr-1">
              <table className="w-full text-left font-mono text-[11px] border-collapse">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 text-[10px] uppercase">
                    <th className="py-1.5 px-2">Waktu</th>
                    <th className="py-1.5 px-2">Model AI</th>
                    <th className="py-1.5 px-2">Provider</th>
                    <th className="py-1.5 px-2 text-right">Prompt</th>
                    <th className="py-1.5 px-2 text-right">Completion</th>
                    <th className="py-1.5 px-2 text-right">Total Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {tokenLogs.map((log) => (
                    <tr key={log.id} className="border-b border-white/5 hover:bg-white/[0.03] transition-colors text-slate-200">
                      <td className="py-1.5 px-2 text-slate-500 text-[10px] whitespace-nowrap">
                        {new Date(log.created_at).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td className="py-1.5 px-2 font-semibold truncate max-w-[140px]" title={log.model_id}>
                        {log.model_id}
                      </td>
                      <td className="py-1.5 px-2">
                        <span className="px-1.5 py-0.5 rounded text-[9px] bg-white/10 text-slate-400 uppercase">
                          {log.provider}
                        </span>
                      </td>
                      <td className="py-1.5 px-2 text-right text-slate-400">{log.prompt_tokens.toLocaleString()}</td>
                      <td className="py-1.5 px-2 text-right text-slate-400">{log.completion_tokens.toLocaleString()}</td>
                      <td className="py-1.5 px-2 text-right font-bold text-cyan-300">{log.total_tokens.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
