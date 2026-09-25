import React from "react";
import type { AssistantStatus } from "./BottomDock";

export interface DockAudioWaveformProps {
  status: AssistantStatus;
  activeIntensity: number;
  isMicActive: boolean;
  isMuted: boolean;
}

export function DockAudioWaveform({
  status,
  activeIntensity,
  isMicActive,
  isMuted,
}: DockAudioWaveformProps) {
  return (
    <div className="w-full flex items-center justify-between py-1 px-1">
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex items-center gap-1 h-5 shrink-0 px-2 py-0.5 bg-black/40 rounded-lg border border-cyan-400/20">
          {[...Array(6)].map((_, i) => {
            const barHeight = Math.max(
              3,
              Math.min(18, activeIntensity * 30 * (1 + (i % 3) * 0.4) + (status !== "idle" ? 6 : 3))
            );
            return (
              <span
                key={i}
                className={`w-1 rounded-full transition-all duration-75 ${
                  status === "speaking"
                    ? "bg-cyan-400 shadow-[0_0_6px_#22d3ee]"
                    : status === "listening"
                    ? "bg-indigo-400 shadow-[0_0_6px_#818cf8]"
                    : "bg-slate-600"
                }`}
                style={{ height: `${barHeight}px` }}
              />
            );
          })}
        </div>
        <p className="text-xs font-mono font-medium text-slate-300 truncate" suppressHydrationWarning>
          {status === "speaking"
            ? "AI Speaking..."
            : status === "thinking"
            ? "AI Thinking..."
            : isMuted
            ? "Mikrofon Dibisukan"
            : isMicActive
            ? "Mendengarkan suara Anda..."
            : "Microphone Ready (Click Voice to Speak)"}
        </p>
      </div>
    </div>
  );
}
