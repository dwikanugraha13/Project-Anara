"use client";

import React, { useState } from "react";

export interface AIModelInfo {
  id: string;
  name: string;
  provider: string;
  category: string;
  badge: string;
  description: string;
  icon: string;
  supports_voice: boolean;
  is_configured: boolean;
  is_active: boolean;
}

interface ModelSelectorDropdownProps {
  isOpen: boolean;
  onClose: () => void;
  models: AIModelInfo[];
  activeModelId: string;
  onSelectModel: (id: string) => void;
  interactionMode: "voice" | "chat";
}

export default function ModelSelectorDropdown({
  isOpen,
  onClose,
  models,
  activeModelId,
  onSelectModel,
  interactionMode,
}: ModelSelectorDropdownProps) {
  const [modelSearchQuery, setModelSearchQuery] = useState("");

  if (!isOpen) return null;

  const modeFilteredModels = models.filter((m) => {
    if (interactionMode === "voice") {
      return !!m.supports_voice || m.id.toLowerCase().includes("live-preview");
    }
    return true;
  });

  return (
    <div
      onClick={(e) => e.stopPropagation()}
      className="absolute bottom-9 left-0 z-50 w-72 sm:w-80 p-2 rounded-2xl bg-slate-950/95 border border-white/15 backdrop-blur-2xl shadow-2xl animate-scale-up space-y-2 max-h-[380px] flex flex-col font-mono"
    >
      <div className="px-2 py-1 border-b border-white/10 flex items-center justify-between">
        <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-300">
          {interactionMode === "voice" ? "Model Live Audio" : "Model AI Teks"} ({modeFilteredModels.length})
        </span>
        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 hover:text-white text-xs cursor-pointer px-1"
        >
          ✕
        </button>
      </div>

      <div className="px-1">
        <input
          type="text"
          placeholder={interactionMode === "voice" ? "Search live audio models..." : "Search AI models..."}
          value={modelSearchQuery}
          onChange={(e) => setModelSearchQuery(e.target.value)}
          className="w-full px-2.5 py-1 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-white/30 font-mono"
        />
      </div>

      <div className="space-y-1 overflow-y-auto custom-scrollbar flex-1 pr-1">
        {modeFilteredModels.length === 0 ? (
          <div className="p-3 text-center text-xs text-slate-400">
            {interactionMode === "voice"
              ? "No active live audio model. Configure Gemini API key in Anara Brain."
              : "No text models configured."}
          </div>
        ) : (
          modeFilteredModels
            .filter((m) => {
              const q = modelSearchQuery.toLowerCase().trim();
              if (!q) return true;
              return (
                m.name.toLowerCase().includes(q) ||
                m.id.toLowerCase().includes(q) ||
                (m.badge || "").toLowerCase().includes(q)
              );
            })
            .map((m) => {
              const isSelected = m.id === activeModelId;
              const isLive = !!m.supports_voice || m.id.toLowerCase().includes("live-preview");
              const capBadge = interactionMode === "voice" ? "LIVE" : isLive ? "LIVE" : "CHAT";
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    onSelectModel(m.id);
                    onClose();
                  }}
                  className={`w-full flex items-start p-2 px-2.5 rounded-xl text-left transition-all cursor-pointer border ${
                    isSelected
                      ? "bg-white/15 border-white/25 text-white"
                      : "bg-white/[0.03] border-transparent hover:bg-white/[0.08] hover:border-white/15 text-slate-200"
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-bold truncate">{m.name}</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="px-1.5 py-0.5 rounded bg-white/[0.08] text-slate-300 font-mono text-[9px] font-semibold">
                        {capBadge}
                      </span>
                      <span className="text-[9.5px] text-slate-400 truncate">
                        {m.provider?.toUpperCase()} · {m.badge?.replace(/[^\x20-\x7E]/g, "").trim()}
                      </span>
                    </div>
                  </div>
                </button>
              );
            })
        )}
      </div>
    </div>
  );
}
