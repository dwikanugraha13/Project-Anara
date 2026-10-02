"use client";

import React from "react";

interface LoadingScreenProps {
  progress?: number;
  title?: string;
  message?: string;
  onCancel?: () => void;
  cancelLabel?: string;
}

export default function LoadingScreen({
  progress,
  title = "Anara",
  message = "Initializing Anara Avatar & Voice Engine...",
  onCancel,
  cancelLabel = "Switch to Chat Mode",
}: LoadingScreenProps) {
  const [dynamicProgress, setDynamicProgress] = React.useState(progress ?? 20);

  React.useEffect(() => {
    if (progress !== undefined) {
      setDynamicProgress(progress);
      return;
    }
    const interval = setInterval(() => {
      setDynamicProgress((prev) => {
        if (prev >= 92) return prev;
        const inc = Math.max(1, Math.round((95 - prev) * 0.12));
        return Math.min(92, prev + inc);
      });
    }, 400);
    return () => clearInterval(interval);
  }, [progress]);

  const clampedProgress = Math.max(0, Math.min(100, dynamicProgress));

  return (
    <div
      role="status"
      aria-label="Loading Anara Interface"
      className="absolute inset-0 flex flex-col items-center justify-center bg-[#030712]/80 backdrop-blur-2xl z-50 notranslate select-none"
      translate="no"
    >
      {/* Background ambient orbs */}
      <div className="absolute top-1/3 left-1/3 w-72 h-72 bg-indigo-500/15 rounded-full blur-[100px] pointer-events-none animate-pulse" />
      <div className="absolute bottom-1/3 right-1/3 w-72 h-72 bg-cyan-500/15 rounded-full blur-[100px] pointer-events-none animate-pulse" />

      {/* Liquid Glass Center Card */}
      <div className="liquid-glass rounded-3xl p-8 max-w-sm w-full mx-4 flex flex-col items-center text-center shadow-2xl border-white/20 relative overflow-hidden bg-[#060913]/90">
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-cyan-400/30 to-transparent pointer-events-none" />

        {/* Animated logo */}
        <div className="relative mb-6">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-cyan-400 flex items-center justify-center shadow-xl shadow-indigo-500/30">
            <span className="text-2xl font-bold text-white tracking-widest font-mono">AN</span>
          </div>
          <div className="absolute -inset-2 rounded-3xl border border-indigo-400/30 animate-pulse pointer-events-none" />
        </div>

        {/* Title */}
        <h1
          className="text-white text-lg font-bold mb-1 tracking-tight"
          suppressHydrationWarning
        >
          {title}
        </h1>
        <p className="text-slate-400 text-xs mb-6 font-normal" suppressHydrationWarning>
          {message}
        </p>

        {/* Liquid Progress bar */}
        <div
          role="progressbar"
          aria-valuenow={clampedProgress}
          aria-valuemin={0}
          aria-valuemax={100}
          className="w-full h-2 bg-white/[0.06] border border-white/10 rounded-full overflow-hidden p-0.5 shadow-inner"
        >
          <div
            className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-cyan-400 rounded-full transition-all duration-300 shadow-[0_0_12px_#818cf8]"
            style={{ width: `${clampedProgress}%` }}
          />
        </div>

        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="mt-6 px-4 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-slate-400 hover:text-white text-xs font-mono transition-colors cursor-pointer"
          >
            {cancelLabel}
          </button>
        )}
      </div>
    </div>
  );
}
