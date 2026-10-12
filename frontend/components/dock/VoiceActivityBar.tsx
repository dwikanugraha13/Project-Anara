"use client";

import React from "react";

export interface VoiceActivityBarProps {
  status: "idle" | "recording" | "transcribing";
  elapsedSeconds: number;
  level: number;
  onCancel?: () => void;
}

function formatElapsed(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const m = Math.floor(safe / 60);
  const s = safe % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function VoiceLevelBars({ level, active }: { active: boolean; level: number }) {
  const normalized = Math.max(0, Math.min(level, 1));
  const weights = [0.45, 0.75, 1.0, 0.75, 0.45];

  return (
    <div aria-hidden="true" className="flex h-3.5 items-center gap-0.5">
      {weights.map((w, idx) => {
        const height = active ? Math.min(1.0, 0.2 + normalized * w * 1.6) : 0.2;
        return (
          <span
            key={idx}
            className={`w-0.5 rounded-full transition-[height,opacity] duration-75 ease-out ${
              active ? "bg-cyan-400 opacity-90 shadow-[0_0_4px_#22d3ee]" : "bg-slate-500 opacity-40"
            }`}
            style={{ height: `${Math.round(height * 100)}%` }}
          />
        );
      })}
    </div>
  );
}

/**
 * VoiceActivityBar — Live Dictating & Transcribing activity strip (Hermes 1:1 Parity).
 * Rendered above the composer textarea during voice dictation.
 */
export function VoiceActivityBar({
  status,
  elapsedSeconds,
  level,
  onCancel,
}: VoiceActivityBarProps) {
  if (status === "idle") return null;

  const isRecording = status === "recording";
  const title = isRecording ? "Dictating" : "Transcribing";

  return (
    <div
      role="status"
      aria-live="polite"
      className="w-full flex items-center justify-between px-3 py-1.5 mb-1.5 rounded-xl border border-cyan-400/25 bg-[#060B16]/90 backdrop-blur-xl text-xs font-mono shadow-[0_4px_16px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.06)] animate-in fade-in duration-150 select-none"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        {/* Status Indicator Icon (Hermes Blue Circle with White Icon) */}
        <div
          className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
            isRecording
              ? "bg-cyan-500/25 border border-cyan-400/50 text-cyan-200 shadow-[0_0_8px_rgba(34,211,238,0.35)]"
              : "bg-cyan-500/15 border border-cyan-400/30 text-cyan-300"
          }`}
        >
          {isRecording ? (
            <svg className="w-3 h-3 fill-current" viewBox="0 0 24 24">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
          ) : (
            <svg className="w-3 h-3 animate-spin text-cyan-300" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          )}
        </div>

        {/* Text Label & Elapsed Timer */}
        <div className="flex items-center gap-2">
          <span className="font-semibold text-white tracking-tight">{title}</span>
          <span className="text-slate-400 font-mono text-[11px] tabular-nums">
            {formatElapsed(elapsedSeconds)}
          </span>
        </div>
      </div>

      {/* Right Cluster: Live Audio Waveform (Recording) OR Status Dots (Transcribing) + Cancel */}
      <div className="flex items-center gap-2.5 shrink-0">
        {isRecording ? (
          <VoiceLevelBars active={true} level={level} />
        ) : (
          <span className="text-slate-400 tracking-widest text-[11px]">•••</span>
        )}

        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer text-[10px]"
            title="Cancel dictation"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}
