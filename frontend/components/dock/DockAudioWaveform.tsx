"use client";

import React, { useRef, useEffect } from "react";
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
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | null>(null);
  const intensityRef = useRef(activeIntensity);
  intensityRef.current = activeIntensity;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    const width = 64;
    const height = 20;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    let phase = 0;
    const barCount = 7;
    const barWidth = 3;
    const barGap = 4;

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      phase += 0.12;
      const baseIntensity = intensityRef.current;

      for (let i = 0; i < barCount; i++) {
        const wave = Math.sin(phase + i * 0.7) * 0.5 + 0.5;
        const h = Math.max(
          4,
          Math.min(height - 2, baseIntensity * 28 * wave + (status !== "idle" ? 7 : (Math.sin(phase * 0.6 + i) * 2 + 4)))
        );
        const x = i * (barWidth + barGap) + 4;
        const y = (height - h) / 2;

        const grad = ctx.createLinearGradient(0, y, 0, y + h);
        if (status === "speaking") {
          grad.addColorStop(0, "#38bdf8");
          grad.addColorStop(1, "#06b6d4");
        } else if (status === "listening") {
          grad.addColorStop(0, "#a5b4fc");
          grad.addColorStop(1, "#6366f1");
        } else if (status === "thinking") {
          grad.addColorStop(0, "#fbcfe8");
          grad.addColorStop(1, "#ec4899");
        } else {
          grad.addColorStop(0, "rgba(56, 189, 248, 0.45)");
          grad.addColorStop(1, "rgba(99, 102, 241, 0.25)");
        }

        ctx.fillStyle = grad;
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(x, y, barWidth, h, 1.5);
        } else {
          ctx.rect(x, y, barWidth, h);
        }
        ctx.fill();
      }

      rafRef.current = requestAnimationFrame(render);
    };

    rafRef.current = requestAnimationFrame(render);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [status]);

  return (
    <div className="w-full flex items-center justify-between py-1 px-1">
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex items-center h-6 px-2 bg-gradient-to-r from-cyan-950/40 to-slate-950/60 rounded-lg border border-cyan-400/25 shadow-[0_0_12px_rgba(34,211,238,0.1)]">
          <canvas ref={canvasRef} className="w-16 h-5" style={{ width: 64, height: 20 }} />
        </div>
        <p className="text-xs font-mono font-medium text-slate-300 truncate" suppressHydrationWarning>
          {status === "speaking"
            ? "Anara is speaking..."
            : status === "thinking"
            ? "Anara is thinking..."
            : isMuted
            ? "Microphone Muted"
            : isMicActive
            ? "Listening..."
            : "Voice Assistant Ready"}
        </p>
      </div>
    </div>
  );
}
