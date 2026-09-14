"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BACKEND_URL, AnimationProfile, FALLBACK_ANIMATIONS, animationLabel } from "../types";

interface BrainAnimationsTabProps {
  onTriggerAnimation?: (animName: string, emotion: string) => void;
}

export default function BrainAnimationsTab({
  onTriggerAnimation,
}: BrainAnimationsTabProps) {
  const [animations, setAnimations] = useState<AnimationProfile[]>(FALLBACK_ANIMATIONS);

  const fetchAnimations = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/animations`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setAnimations(data);
        }
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchAnimations();
  }, [fetchAnimations]);

  return (
    <div className="space-y-5 font-sans select-text">
      <div className="p-5 rounded-2xl liquid-glass-subtle text-xs text-slate-300">
        <span className="text-emerald-300 font-semibold uppercase tracking-wider text-[11px]">
          Pustaka Gestur 3D &amp; Ekspresi
        </span>
        <p className="mt-1.5 leading-relaxed text-slate-400">
          Daftar gerakan skeletal dan morph target ekspresi wajah yang terdaftar di database untuk mendukung respons visual interaktif.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {animations.map((a) => (
          <div
            key={a.id}
            className="p-4 px-5 rounded-2xl liquid-glass-subtle hover:border-cyan-400/40 transition-all flex items-center justify-between gap-3"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h4 className="text-sm font-bold text-white truncate">{animationLabel(a.name)}</h4>
                <span className="text-[10px] text-cyan-300 bg-cyan-400/10 border border-cyan-400/20 px-2 py-0.5 rounded-md">
                  {a.gesture}
                </span>
                <span className="text-[10px] text-purple-300 bg-purple-400/10 border border-purple-400/20 px-2 py-0.5 rounded-md">
                  {a.emotion}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed line-clamp-2">
                {a.description || `Animasi ${a.category} dengan intensitas ${(a.intensity * 100).toFixed(0)}% selama ${a.duration_sec.toFixed(1)} detik`}
              </p>
              {a.keywords && a.keywords.length > 0 && (
                <p className="text-[10px] text-slate-500 mt-1.5 truncate">
                  Trigger: {a.keywords.slice(0, 6).join(", ")}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => onTriggerAnimation?.(a.gesture || a.name, a.emotion)}
              className="px-3.5 py-2 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/30 border border-cyan-400/35 text-cyan-200 text-xs font-semibold transition-all cursor-pointer shrink-0 flex items-center gap-1.5"
            >
              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
              <span>Uji</span>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
