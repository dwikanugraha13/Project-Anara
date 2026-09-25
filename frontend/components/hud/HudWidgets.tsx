"use client";

import React, { useState } from "react";
import AgentToolCard from "../chat/AgentToolCard";
import {
  WeatherData,
  CodeData,
  SystemHudData,
  KnowledgeCardData,
  TodoData,
  AgentActionData,
  HudDismissButton,
} from "./types";

export function HudWeatherCard({
  weatherData,
  onDismiss,
}: {
  weatherData: WeatherData;
  onDismiss?: () => void;
}) {
  const isRain = weatherData.condition.toLowerCase().includes("hujan");
  return (
    <div className="mt-2.5 rounded-2xl overflow-hidden border border-cyan-400/40 bg-slate-950/80 backdrop-blur-xl p-4 sm:p-5 shadow-[0_0_30px_rgba(34,211,238,0.2)] text-white select-none font-sans">
      <div className="flex items-center justify-between pb-2.5 border-b border-cyan-400/20 text-[11px] font-mono text-cyan-300">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_#22d3ee]" />
          <span className="font-bold tracking-widest uppercase">Anara Atmosphere</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="px-2.5 py-1 rounded-md bg-cyan-500/15 border border-cyan-400/30 text-cyan-300 text-[10px] font-bold uppercase tracking-wider">Live WIB</span>
          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      <div className="flex items-center justify-between py-4 px-1">
        <div>
          <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wider font-mono">{weatherData.city}</h4>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-4xl sm:text-5xl font-extrabold text-white font-mono tracking-tight drop-shadow">
              {weatherData.temp_c}°
            </span>
            <span className="text-base font-semibold text-cyan-300">C</span>
          </div>
          <p className="text-sm font-medium text-cyan-200 mt-1">{weatherData.condition}</p>
        </div>

        <div className="flex flex-col items-end gap-2">
          <div className="w-14 h-14 rounded-2xl bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center text-3xl shadow-[0_0_15px_rgba(34,211,238,0.3)]">
            {isRain ? "🌧️" : weatherData.temp_c > 30 ? "☀️" : "⛅"}
          </div>
          <div className="flex items-center gap-2.5 text-[11px] font-mono text-slate-300">
            <span>💧 {weatherData.humidity}%</span>
            <span>💨 {weatherData.wind_kmh} km/j</span>
          </div>
        </div>
      </div>

      {weatherData.forecast && weatherData.forecast.length > 0 && (
        <div className="grid grid-cols-2 gap-2.5 pt-2.5 border-t border-white/10 text-[11px] font-mono">
          {weatherData.forecast.map((fc, idx) => (
            <div key={idx} className="flex items-center justify-between p-2 px-3 rounded-xl bg-black/40 border border-cyan-400/20">
              <span className="text-slate-400">{fc.day}</span>
              <span className="text-white font-bold">{fc.temp_c}°C • {fc.condition}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function HudCodeCard({
  codeData,
  onDismiss,
}: {
  codeData: CodeData;
  onDismiss?: () => void;
}) {
  const [copiedCode, setCopiedCode] = useState(false);

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  return (
    <div className="mt-2.5 rounded-2xl overflow-hidden border border-indigo-400/40 bg-slate-950/90 shadow-[0_0_30px_rgba(129,140,248,0.2)] text-white select-text font-sans">
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/90 border-b border-indigo-400/20 text-[11px] font-mono">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
          </div>
          <span className="text-indigo-300 font-bold uppercase tracking-widest truncate max-w-[240px]">
            {codeData.title || "Terminal Kode"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-md bg-indigo-500/30 text-indigo-200 border border-indigo-400/30 font-bold uppercase text-[10px]">
            {codeData.language || "CODE"}
          </span>
          <button
            onClick={() => handleCopyCode(codeData.code)}
            className="px-2.5 py-1 rounded-md bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition-colors cursor-pointer text-[10px] font-mono"
          >
            {copiedCode ? "✓ Tersalin" : "Salin"}
          </button>
          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      <div className="p-4 font-mono text-[13px] leading-relaxed overflow-x-auto max-h-[300px] bg-black/50 text-cyan-200">
        <pre className="whitespace-pre">{codeData.code}</pre>
      </div>

      {codeData.explanation && (
        <div className="px-4 py-2.5 bg-slate-900/60 border-t border-white/5 text-xs text-slate-400 leading-relaxed">
          {codeData.explanation}
        </div>
      )}
    </div>
  );
}

export function HudSystemCard({
  systemHudData,
  onDismiss,
}: {
  systemHudData: SystemHudData;
  onDismiss?: () => void;
}) {
  return (
    <div className="mt-2.5 rounded-2xl overflow-hidden border border-cyan-400/50 bg-slate-950/85 backdrop-blur-xl p-4 sm:p-5 shadow-[0_0_30px_rgba(34,211,238,0.25)] text-white select-none font-sans">
      <div className="flex items-center justify-between pb-2.5 border-b border-cyan-400/20 text-[11px] font-mono text-cyan-300">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]" />
          <span className="font-bold tracking-widest uppercase">Anara Core Telemetry</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-400/40 text-[10px] font-bold">
            {systemHudData.core_status || "ONLINE"}
          </span>
          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-4 text-[11px] font-mono">
        <div className="p-2.5 rounded-xl bg-black/40 border border-cyan-400/20 flex flex-col">
          <span className="text-slate-400">AI MODEL</span>
          <span className="text-white font-bold mt-1 truncate">{systemHudData.ai_model || "Gemini Live"}</span>
        </div>
        <div className="p-2.5 rounded-xl bg-black/40 border border-cyan-400/20 flex flex-col">
          <span className="text-slate-400">KEY POOL</span>
          <span className="text-cyan-300 font-bold mt-1">{systemHudData.active_keys} Active Accounts</span>
        </div>
        <div className="p-2.5 rounded-xl bg-black/40 border border-cyan-400/20 flex flex-col">
          <span className="text-slate-400">MEMORY NODES</span>
          <span className="text-purple-300 font-bold mt-1">{systemHudData.memory_nodes} Fakta SQLite</span>
        </div>
        <div className="p-2.5 rounded-xl bg-black/40 border border-cyan-400/20 flex flex-col">
          <span className="text-slate-400">LATENSI VAD</span>
          <span className="text-emerald-300 font-bold mt-1">{systemHudData.latency_ms}ms • {systemHudData.uptime}</span>
        </div>
      </div>
    </div>
  );
}

export function HudKnowledgeCard({
  knowledgeCardData,
  onDismiss,
}: {
  knowledgeCardData: KnowledgeCardData;
  onDismiss?: () => void;
}) {
  const kSteps: string[] =
    knowledgeCardData.steps && knowledgeCardData.steps.length > 0
      ? knowledgeCardData.steps
      : (knowledgeCardData.specs || []).map((sp) => sp.value);
  const kIngredients: string[] = knowledgeCardData.ingredients || [];

  return (
    <div className="mt-2.5 rounded-2xl overflow-hidden border border-cyan-400/40 bg-slate-950/85 backdrop-blur-xl shadow-[0_0_30px_rgba(34,211,238,0.2)] text-white select-none font-sans">
      <div className="flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-indigo-950/80 via-slate-900/80 to-cyan-950/80 border-b border-cyan-400/25 text-[11px] font-mono">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse shadow-[0_0_6px_#818cf8] shrink-0" />
          <span className="text-indigo-300 font-bold uppercase tracking-widest truncate">
            {knowledgeCardData.category || "Pengetahuan"}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {knowledgeCardData.badge && (
            <span className="px-2.5 py-1 rounded-md bg-cyan-500/15 text-cyan-300 border border-cyan-400/30 text-[10px] font-bold uppercase tracking-wider">
              {knowledgeCardData.badge}
            </span>
          )}
          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      <div className="px-4 sm:px-5 py-3.5 max-h-[52vh] overflow-y-auto [scrollbar-width:thin] [scrollbar-color:rgba(34,211,238,0.3)_transparent]">
        <h4 className="text-lg font-bold text-white tracking-wide leading-snug">
          {knowledgeCardData.title}
        </h4>
        {knowledgeCardData.summary && (
          <p className="text-xs text-slate-400 mt-1 leading-relaxed line-clamp-2">
            {knowledgeCardData.summary}
          </p>
        )}

        {kIngredients.length > 0 && (
          <div className="mt-3.5">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-cyan-400/80 mb-2">
              Bahan-Bahan
            </p>
            <div className="flex flex-wrap gap-1.5">
              {kIngredients.map((ing, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg bg-cyan-500/10 border border-cyan-400/25 text-cyan-100 text-xs leading-snug font-mono"
                >
                  {ing}
                </span>
              ))}
            </div>
          </div>
        )}

        {kSteps.length > 0 && (
          <div className="mt-3.5">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-indigo-300/80 mb-2">
              {kIngredients.length > 0 ? "Langkah Memasak" : "Langkah-Langkah"}
            </p>
            <div className="space-y-1.5">
              {kSteps.map((step, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2.5 py-2 px-3 rounded-xl bg-black/40 border border-cyan-400/15"
                >
                  <span className="w-5 h-5 rounded-full bg-indigo-500/25 border border-indigo-400/40 text-indigo-200 text-[11px] font-mono font-bold flex items-center justify-center shrink-0 mt-px">
                    {idx + 1}
                  </span>
                  <p className="text-sm text-slate-100 leading-snug flex-1">
                    {step}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function HudTodoListCard({
  todoData,
  onDismiss,
}: {
  todoData: TodoData;
  onDismiss?: () => void;
}) {
  return (
    <div className="w-full select-text">
      <AgentToolCard todoData={todoData} onDismiss={onDismiss} />
    </div>
  );
}

export function HudAgentActionCard({
  agentActionData,
  onOpenFile,
  onDismiss,
}: {
  agentActionData: AgentActionData;
  onOpenFile?: (filePath: string) => void;
  onDismiss?: () => void;
}) {
  return (
    <div className="w-full select-text">
      <AgentToolCard action={agentActionData} onOpenFile={onOpenFile} onDismiss={onDismiss} />
    </div>
  );
}

export function HudWhatsAppQrCard({
  imageUrl,
  onDismiss,
}: {
  imageUrl?: string;
  onDismiss?: () => void;
}) {
  return (
    <div className="mt-2.5 rounded-2xl overflow-hidden border border-emerald-400/50 bg-slate-950/95 backdrop-blur-2xl shadow-[0_0_40px_rgba(52,211,153,0.35)] text-white select-none max-w-sm mx-auto font-sans">
      <div className="flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-emerald-950/90 via-slate-900/90 to-teal-950/90 border-b border-emerald-400/30 text-[11px] font-mono">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
          <span className="text-emerald-300 font-bold uppercase tracking-widest truncate">
            WHATSAPP WEB • TAUTKAN AKUN
          </span>
        </div>
        <HudDismissButton onDismiss={onDismiss} />
      </div>

      <div className="p-5 flex flex-col items-center text-center">
        <p className="text-xs text-slate-300 mb-3.5 leading-relaxed">
          Open <span className="text-emerald-300 font-semibold">WhatsApp on your phone</span> &gt; Linked Devices &gt; Link a Device, then scan this QR:
        </p>

        <div className="p-3 bg-white rounded-2xl shadow-2xl border-2 border-emerald-400/40 relative group">
          {imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imageUrl}
              alt="WhatsApp QR Code"
              className="w-48 h-48 object-contain rounded-lg"
            />
          ) : (
            <div className="w-48 h-48 flex flex-col items-center justify-center text-slate-800 font-mono text-xs gap-2">
              <span className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
              <span>Menyiapkan QR...</span>
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center gap-2 text-[10px] font-mono text-slate-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
          <span>QR will close automatically after connected</span>
        </div>
      </div>
    </div>
  );
}

export function HudWhatsAppChatCard({
  knowledgeCardData,
  onDismiss,
}: {
  knowledgeCardData: KnowledgeCardData;
  onDismiss?: () => void;
}) {
  const steps = knowledgeCardData.steps || [];
  return (
    <div className="mt-2.5 rounded-2xl overflow-hidden border border-emerald-400/40 bg-slate-950/90 backdrop-blur-xl shadow-[0_0_35px_rgba(52,211,153,0.25)] text-white select-none font-sans">
      <div className="flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-emerald-950/90 via-slate-900/90 to-cyan-950/90 border-b border-emerald-400/30 text-[11px] font-mono">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
          <span className="text-emerald-300 font-bold uppercase tracking-widest truncate">
            WHATSAPP INBOX • PESAN TERBARU
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {knowledgeCardData.badge && (
            <span className="px-2.5 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-400/35 text-[10px] font-bold font-mono">
              {knowledgeCardData.badge}
            </span>
          )}
          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      <div className="p-4 sm:p-5">
        <h4 className="text-base font-bold text-white tracking-wide leading-snug">
          {knowledgeCardData.title}
        </h4>

        <div className="mt-3 space-y-2 max-h-[220px] overflow-y-auto pr-1 custom-scrollbar">
          {steps.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-4">No unread messages.</p>
          ) : (
            steps.map((msgItem, idx) => (
              <div
                key={idx}
                className="p-2.5 px-3 rounded-xl bg-black/40 border border-emerald-400/20 text-xs text-slate-100 leading-relaxed flex items-start gap-2"
              >
                <span className="text-emerald-400 mt-0.5">💬</span>
                <p className="flex-1">{msgItem.replace(/^💬\s*/, "")}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
