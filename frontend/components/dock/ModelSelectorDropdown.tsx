"use client";

import React, { useState } from "react";
import { formatModelDisplayName } from "@/lib/modelFormat";

export interface AIModelInfo {
  id: string;
  name: string;
  provider: string;
  category: string;
  badge: string;
  description: string;
  icon: string;
  supports_voice: boolean;
  supports_reasoning?: boolean;
  supports_vision?: boolean;
  context_window?: number;
  max_output_tokens?: number;
  is_configured: boolean;
  is_active: boolean;
}

export function isReasoningSupported(model?: AIModelInfo | null): boolean {
  if (!model) return false;
  if (typeof model.supports_reasoning === "boolean") return model.supports_reasoning;
  const lower = (model.id || "").toLowerCase();
  const nameLower = (model.name || "").toLowerCase();
  return (
    lower.includes("thinking") ||
    lower.includes("reasoning") ||
    lower.includes("reasoner") ||
    lower.includes("claude-3-7") ||
    lower.includes("claude-3.7") ||
    lower.includes("o1") ||
    lower.includes("o3") ||
    lower.includes("o4") ||
    lower.includes("deepseek-r1") ||
    lower.includes("r1") ||
    lower.includes("qwq") ||
    lower.includes("gemini-2.5") ||
    lower.includes("gemini-3") ||
    lower.includes("gemini-2.0-flash-thinking") ||
    nameLower.includes("thinking") ||
    nameLower.includes("reasoning")
  );
}

export interface ModelSelectorDropdownProps {
  isOpen: boolean;
  onClose: () => void;
  models: AIModelInfo[];
  activeModelId: string;
  onSelectModel: (id: string) => void;
  interactionMode: "voice" | "chat";
  reasoningEffort?: "off" | "low" | "medium" | "high" | string;
  onSelectReasoningEffort?: (effort: "off" | "low" | "medium" | "high") => void;
}

export default function ModelSelectorDropdown({
  isOpen,
  onClose,
  models,
  activeModelId,
  onSelectModel,
  interactionMode,
  reasoningEffort = "medium",
  onSelectReasoningEffort,
}: ModelSelectorDropdownProps) {
  const [modelSearchQuery, setModelSearchQuery] = useState("");

  if (!isOpen) return null;

  const activeModel = models.find((m) => m.id === activeModelId);
  const activeSupportsReasoning = isReasoningSupported(activeModel);

  const modeFilteredModels = models.filter((m) => {
    if (interactionMode === "voice") {
      return !!m.supports_voice || m.id.toLowerCase().includes("live-preview");
    }
    return true;
  });

  const formatTokens = (tokens?: number) => {
    if (!tokens) return "";
    if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(0)}M`;
    if (tokens >= 1_000) return `${Math.round(tokens / 1_000)}k`;
    return `${tokens}`;
  };

  return (
    <div
      onClick={(e) => e.stopPropagation()}
      className="absolute bottom-9 left-0 z-50 w-72 sm:w-80 p-2 rounded-2xl bg-slate-950/95 border border-white/15 backdrop-blur-2xl shadow-2xl animate-scale-up space-y-2 max-h-[420px] flex flex-col font-mono"
    >
      <div className="px-2 py-1 border-b border-white/10 flex items-center justify-between">
        <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-300">
          {interactionMode === "voice" ? "Live Audio Models" : "AI Text Models"} ({modeFilteredModels.length})
        </span>
        <button
          type="button"
          onClick={onClose}
          className="w-5 h-5 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {interactionMode === "chat" && (
        <div className="px-2.5 py-1.5 border-b border-white/[0.08] flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-1.5">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                activeSupportsReasoning ? "bg-purple-400 shadow-[0_0_6px_#c084fc]" : "bg-slate-600"
              }`}
            />
            <span className="text-[10px] font-mono font-medium text-slate-300">Reasoning</span>
          </div>

          {activeSupportsReasoning ? (
            <div className="flex items-center gap-1 bg-white/[0.04] p-0.5 rounded-lg border border-white/[0.08]">
              {(["off", "low", "medium", "high"] as const).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => onSelectReasoningEffort?.(lvl)}
                  className={`px-2 py-0.5 rounded text-[9.5px] font-mono uppercase transition-all cursor-pointer ${
                    (reasoningEffort || "medium") === lvl
                      ? "bg-purple-500/25 text-purple-200 font-bold border border-purple-400/40 shadow-xs"
                      : "text-slate-400 hover:text-white"
                  }`}
                  title={
                    lvl === "off"
                      ? "Standard generation without extended thinking"
                      : `Extended thinking effort: ${lvl} budget`
                  }
                >
                  {lvl}
                </button>
              ))}
            </div>
          ) : (
            <span className="text-[9px] font-mono text-slate-500 italic">
              Standard · No extended thinking
            </span>
          )}
        </div>
      )}

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
                    <div className="flex items-center justify-between gap-1">
                      <p className="text-xs font-bold truncate">{formatModelDisplayName(m.name || m.id)}</p>
                      {m.context_window && (
                        <span className="text-[9px] font-mono text-slate-400 bg-white/[0.04] px-1 rounded">
                          {formatTokens(m.context_window)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="px-1.5 py-0.5 rounded bg-white/[0.08] text-slate-300 font-mono text-[9px] font-semibold">
                        {capBadge}
                      </span>
                      {isReasoningSupported(m) && (
                        <span className="px-1.5 py-0.5 rounded bg-purple-500/15 border border-purple-400/25 text-purple-300 font-mono text-[9px] font-semibold">
                          REASONING
                        </span>
                      )}
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
