"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BriefingData, HudDismissButton } from "./types";

export interface HudBriefingCardProps {
  briefingData: BriefingData;
  onDismiss?: () => void;
  onToggleTodo?: (index: number, completed: boolean) => void;
  onSelectProject?: (projectName: string) => void;
}

// ── Pure SVG Weather Glyph Selector ─────────────────────────────────────────
function WeatherConditionIcon({ condition }: { condition?: string }) {
  const c = (condition || "").toLowerCase();

  if (c.includes("rain") || c.includes("drizzle") || c.includes("shower")) {
    return (
      <svg className="w-5 h-5 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 00-9.78 2.096A4.001 4.001 0 003 15z"
        />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 19v2m4-2v2m4-2v2" />
      </svg>
    );
  }

  if (c.includes("thunder") || c.includes("storm") || c.includes("lightning")) {
    return (
      <svg className="w-5 h-5 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M13 10V3L4 14h7v7l9-11h-7z"
        />
      </svg>
    );
  }

  if (c.includes("snow") || c.includes("blizzard") || c.includes("sleet")) {
    return (
      <svg className="w-5 h-5 text-sky-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M12 2v20m10-10H2m17.071-7.071l-14.142 14.142m0-14.142l14.142 14.142"
        />
      </svg>
    );
  }

  if (c.includes("cloud") || c.includes("overcast")) {
    return (
      <svg className="w-5 h-5 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 00-9.78 2.096A4.001 4.001 0 003 15z"
        />
      </svg>
    );
  }

  if (c.includes("fog") || c.includes("mist") || c.includes("haze")) {
    return (
      <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 8h16M4 12h16M4 16h16" />
      </svg>
    );
  }

  // Default: Sunny / Clear
  return (
    <svg className="w-5 h-5 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
      />
    </svg>
  );
}

export default function HudBriefingCard({
  briefingData,
  onDismiss,
  onToggleTodo,
  onSelectProject,
}: HudBriefingCardProps) {
  const w = briefingData.weather;
  const todos = briefingData.todos ?? [];
  const projects = briefingData.projects ?? [];

  // Local optimistic state for interactive todos
  const [completedTodos, setCompletedTodos] = useState<Record<number, boolean>>({});

  // Keyboard shortcut: Escape to dismiss
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onDismiss?.();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onDismiss]);

  const handleToggle = useCallback(
    (idx: number) => {
      const nextVal = !completedTodos[idx];
      setCompletedTodos((prev) => ({ ...prev, [idx]: nextVal }));
      onToggleTodo?.(idx, nextVal);
    },
    [completedTodos, onToggleTodo]
  );

  const completedCount = todos.filter((_, idx) => !!completedTodos[idx]).length;

  return (
    <div
      role="region"
      aria-label="Executive Briefing HUD"
      className="mt-2.5 w-full rounded-2xl overflow-hidden border border-white/[0.08] bg-[#060913]/90 backdrop-blur-xl shadow-[0_16px_40px_rgba(0,0,0,0.65),inset_0_1px_0_0_rgba(255,255,255,0.08)] text-slate-100 select-none transition-all duration-200"
    >
      {/* ── Liquid Glass Specular Header ─────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.08] bg-white/[0.02] text-[11px] font-mono">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="relative flex h-2 w-2 shrink-0">
            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400/90 shadow-[0_0_6px_rgba(34,211,238,0.4)]" />
          </span>
          <span className="text-slate-200 font-semibold uppercase tracking-wider truncate text-[10.5px]">
            EXECUTIVE BRIEFING
          </span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="px-2 py-0.5 rounded-md bg-white/[0.04] text-slate-300 border border-white/[0.08] text-[10px] font-mono tabular-nums">
            {briefingData.time_str}
          </span>
          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      {/* ── Card Content Body ───────────────────────────────────── */}
      <div className="p-4 sm:p-5 max-h-[60vh] overflow-y-auto custom-scrollbar font-sans space-y-4">
        {/* Greeting + Date Strip */}
        <div className="space-y-1">
          <h4 className="text-base sm:text-lg font-bold text-white tracking-tight leading-snug">
            {briefingData.greeting}
            {briefingData.speaker ? `, ${briefingData.speaker}` : ""}
          </h4>
          <p className="text-xs text-slate-400 font-mono flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span>{briefingData.date_str}</span>
          </p>
        </div>

        {/* ── Clean Weather Condition Strip (Anti Box-in-Box) ─────── */}
        {w && (
          <div className="rounded-xl bg-white/[0.025] hover:bg-white/[0.04] border border-white/[0.08] p-3 transition-colors">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center shrink-0">
                  <WeatherConditionIcon condition={w.condition} />
                </div>
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2">
                    {w.temp_c !== undefined && w.temp_c !== null && (
                      <span className="text-xl font-bold font-mono text-white tabular-nums">
                        {w.temp_c}°C
                      </span>
                    )}
                    <span className="text-xs text-slate-300 font-medium truncate">
                      {w.condition}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 font-mono truncate">
                    {w.city || "Local Environment"}
                  </p>
                </div>
              </div>

              {/* Weather Telemetry Chips */}
              <div className="flex flex-col items-end gap-1 text-[10.5px] font-mono text-slate-400 shrink-0">
                {w.humidity !== undefined && (
                  <span className="flex items-center gap-1">
                    <svg className="w-3 h-3 text-cyan-400/80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                    </svg>
                    <span>{w.humidity}% humidity</span>
                  </span>
                )}
                {w.wind_kmh !== undefined && (
                  <span className="flex items-center gap-1">
                    <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                    </svg>
                    <span>{w.wind_kmh} km/h wind</span>
                  </span>
                )}
              </div>
            </div>

            {w.advice && (
              <div className="mt-2.5 pt-2 border-t border-white/[0.06] flex items-start gap-1.5 text-[11px] text-slate-300 font-mono">
                <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="leading-relaxed">{w.advice}</span>
              </div>
            )}
          </div>
        )}

        {/* ── Today's Tasks Section (Interactive Flat Rows) ───────── */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[10.5px] font-mono text-slate-400">
            <span className="font-semibold uppercase tracking-wider">
              Today&apos;s Tasks {todos.length > 0 && `(${todos.length})`}
            </span>
            {todos.length > 0 && (
              <span className="tabular-nums">
                {completedCount} of {todos.length} done
              </span>
            )}
          </div>

          {todos.length === 0 ? (
            <p className="text-xs text-slate-500 italic py-1 font-mono">
              No pending tasks — your schedule is clear.
            </p>
          ) : (
            <div className="space-y-1.5">
              {todos.map((t, idx) => {
                const isDone = !!completedTodos[idx];

                return (
                  <div
                    key={idx}
                    role="checkbox"
                    aria-checked={isDone}
                    tabIndex={0}
                    onClick={() => handleToggle(idx)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleToggle(idx);
                      }
                    }}
                    className={`group flex items-start gap-2.5 p-2.5 rounded-xl border transition-all cursor-pointer select-none ${
                      isDone
                        ? "bg-white/[0.015] hover:bg-white/[0.03] border-white/[0.04]"
                        : "bg-white/[0.02] hover:bg-white/[0.05] border-white/[0.06] hover:border-white/[0.12]"
                    }`}
                  >
                    {/* SVG Checkbox Glyph */}
                    <div className="mt-0.5 shrink-0">
                      {isDone ? (
                        <div className="w-4 h-4 rounded-md bg-emerald-500/20 border border-emerald-400/50 flex items-center justify-center text-emerald-300">
                          <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                      ) : (
                        <div className="w-4 h-4 rounded-md border border-white/20 bg-white/5 group-hover:border-white/40 transition-colors" />
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-xs font-medium leading-snug break-words ${
                          isDone ? "line-through text-slate-500" : "text-slate-200 group-hover:text-white"
                        }`}
                      >
                        {t.title}
                      </p>
                      {t.content && (
                        <p className="text-[11px] text-slate-400/90 mt-0.5 leading-relaxed font-sans">
                          {t.content}
                        </p>
                      )}
                    </div>

                    {t.due && (
                      <span className="px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/[0.08] text-slate-400 text-[10px] font-mono shrink-0 flex items-center gap-1">
                        <svg className="w-3 h-3 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>{t.due}</span>
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── Active Projects Section (Clean Liquid Glass Badges) ──── */}
        {projects.length > 0 && (
          <div className="space-y-2 pt-1 border-t border-white/[0.08]">
            <p className="text-[10.5px] font-mono font-semibold uppercase tracking-wider text-slate-400">
              Active Projects ({projects.length})
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {projects.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => onSelectProject?.(p.name)}
                  className="group flex flex-col text-left p-2.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.05] border border-white/[0.06] hover:border-white/[0.12] transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400/50"
                >
                  <div className="flex items-center justify-between gap-2 w-full">
                    <div className="flex items-center gap-2 min-w-0">
                      <svg
                        className="w-3.5 h-3.5 text-slate-400 group-hover:text-cyan-300 transition-colors shrink-0"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                        />
                      </svg>
                      <span className="text-xs font-medium text-slate-200 group-hover:text-white truncate">
                        {p.name}
                      </span>
                    </div>

                    {p.tech && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-slate-400 border border-white/[0.06] shrink-0">
                        {p.tech}
                      </span>
                    )}
                  </div>

                  {p.goal && (
                    <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                      {p.goal}
                    </p>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Micro Action Responsiveness Footer ───────────────────── */}
        <div className="pt-2 border-t border-white/[0.08] flex items-center justify-between text-[11px] font-mono text-slate-400">
          <span className="text-[10px]">
            Press <kbd className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/[0.1] text-slate-300">Esc</kbd> to dismiss
          </span>
          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              className="px-3 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border border-white/[0.08] text-xs font-medium cursor-pointer transition-all active:scale-95"
            >
              Acknowledge
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

