"use client";

import React from "react";
import { BriefingData, HudDismissButton } from "./types";

interface HudBriefingCardProps {
  briefingData: BriefingData;
  onDismiss?: () => void;
}

export default function HudBriefingCard({
  briefingData,
  onDismiss,
}: HudBriefingCardProps) {
  const w = briefingData.weather;
  const todos = briefingData.todos ?? [];
  const projects = briefingData.projects ?? [];
  const isRain = (w?.condition || "").toLowerCase().includes("hujan");

  return (
    <div className="mt-2.5 rounded-2xl overflow-hidden border border-cyan-400/40 bg-slate-950/90 backdrop-blur-xl shadow-[0_0_34px_rgba(34,211,238,0.24)] text-white select-none">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-indigo-950/85 via-slate-900/85 to-cyan-950/85 border-b border-cyan-400/25 text-[11px] font-mono">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_#22d3ee] shrink-0" />
          <span className="text-cyan-300 font-bold uppercase tracking-widest truncate">
            Briefing Harian
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="px-2.5 py-1 rounded-md bg-cyan-500/15 text-cyan-300 border border-cyan-400/30 text-[10px] font-bold tabular-nums">
            {briefingData.time_str} WIB
          </span>
          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      <div className="px-4 sm:px-5 py-4 max-h-[56vh] overflow-y-auto [scrollbar-width:thin] [scrollbar-color:rgba(34,211,238,0.3)_transparent] font-sans">
        {/* Greeting + date */}
        <h4 className="text-lg font-bold text-white tracking-wide leading-snug">
          {briefingData.greeting}
          {briefingData.speaker ? `, ${briefingData.speaker}` : ""}
        </h4>
        <p className="text-xs text-slate-400 mt-1">{briefingData.date_str}</p>

        {/* Weather strip */}
        {w && (
          <div className="mt-4 flex items-center gap-4 p-3 px-4 rounded-xl bg-black/40 border border-cyan-400/20">
            <div className="w-12 h-12 rounded-xl bg-cyan-500/15 border border-cyan-400/35 flex items-center justify-center text-2xl shrink-0">
              {isRain ? "🌧️" : (w.temp_c ?? 0) > 30 ? "☀️" : "⛅"}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-1.5">
                {w.temp_c !== undefined && w.temp_c !== null && (
                  <span className="text-2xl font-extrabold font-mono text-white tabular-nums">
                    {w.temp_c}°
                  </span>
                )}
                <span className="text-sm text-cyan-200 font-medium truncate">{w.condition}</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5 truncate">
                {w.city}
                {w.humidity ? ` · 💧 ${w.humidity}%` : ""}
                {w.wind_kmh ? ` · 💨 ${w.wind_kmh} km/j` : ""}
              </p>
            </div>
          </div>
        )}
        {w?.advice && (
          <p className="text-[11px] text-cyan-300/80 mt-2 leading-relaxed">💡 {w.advice}</p>
        )}

        {/* To-dos */}
        <div className="mt-4">
          <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-indigo-300/80 mb-2">
            Today's Tasks {todos.length > 0 && `(${todos.length})`}
          </p>
          {todos.length === 0 ? (
            <p className="text-xs text-slate-500 italic py-1">
              No pending tasks — your day is clear.
            </p>
          ) : (
            <div className="space-y-1.5">
              {todos.map((t, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2.5 py-2 px-3 rounded-xl bg-black/40 border border-cyan-400/15"
                >
                  <span className="w-5 h-5 rounded-full bg-indigo-500/25 border border-indigo-400/40 text-indigo-200 text-[11px] font-mono font-bold flex items-center justify-center shrink-0 mt-px">
                    {idx + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-100 leading-snug">{t.title}</p>
                    {t.content && (
                      <p className="text-[11px] text-slate-500 truncate mt-0.5">{t.content}</p>
                    )}
                  </div>
                  {t.due && (
                    <span className="px-2 py-0.5 rounded-md bg-amber-500/15 border border-amber-400/30 text-amber-300 text-[10px] font-mono shrink-0">
                      {t.due}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Active projects */}
        {projects.length > 0 && (
          <div className="mt-4">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-cyan-400/80 mb-2">
              Active Projects
            </p>
            <div className="flex flex-wrap gap-1.5">
              {projects.map((p, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg bg-cyan-500/10 border border-cyan-400/25 text-cyan-100 text-xs leading-snug"
                  title={p.goal || undefined}
                >
                  {p.name}
                  {p.tech && <span className="text-cyan-400/60"> · {p.tech}</span>}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
