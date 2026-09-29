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
      phase += 0.15;
      const baseIntensity = intensityRef.current;

      for (let i = 0; i < barCount; i++) {
        const wave = Math.sin(phase + i * 0.8) * 0.5 + 0.5;
        const h = Math.max(
          3,
          Math.min(height - 2, baseIntensity * 28 * wave + (status !== "idle" ? 5 : 2))
        );
        const x = i * (barWidth + barGap) + 4;
        const y = (height - h) / 2;

        ctx.fillStyle =
          status === "speaking"
            ? "#22d3ee"
            : status === "listening"
            ? "#818cf8"
            : "#475569";

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
        <div className="flex items-center h-5 px-1.5 bg-black/50 rounded-lg border border-cyan-400/20">
          <canvas ref={canvasRef} className="w-16 h-5" style={{ width: 64, height: 20 }} />
        </div>
        <p className="text-xs font-mono font-medium text-slate-300 truncate" suppressHydrationWarning>
          {status === "speaking"
            ? "AI Speaking..."
            : status === "thinking"
            ? "AI Thinking..."
            : isMuted
            ? "Microphone Muted"
            : isMicActive
            ? "Listening to speech..."
            : "Microphone Ready (Click Voice to Speak)"}
        </p>
      </div>
    </div>
  );
}
