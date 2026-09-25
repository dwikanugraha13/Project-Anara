"use client";

import React from "react";

export function HudDismissButton({ onDismiss }: { onDismiss?: () => void }) {
  if (!onDismiss) return null;
  return (
    <button
      type="button"
      aria-label="Close HUD projection"
      title="Close (Esc)"
      onClick={(e) => {
        e.stopPropagation();
        onDismiss();
      }}
      className="w-7 h-7 rounded-full bg-black/60 hover:bg-rose-500/70 border border-white/20 hover:border-rose-300 text-slate-300 hover:text-white flex items-center justify-center backdrop-blur-md transition-all shadow-lg active:scale-90 shrink-0 cursor-pointer"
    >
      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  );
}

export default HudDismissButton;
