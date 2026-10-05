"use client";

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import {
  ReasoningEffortLevel,
  REASONING_EFFORT_CONFIG,
  REASONING_LEVELS,
  getModelSupportedReasoningLevels,
  saveReasoningEffortForModel,
  MinimalModelInfo,
} from "@/lib/reasoningEffort";

export interface ReasoningPillProps {
  modelId?: string;
  model?: MinimalModelInfo | null;
  reasoningEffort?: string;
  onSelectReasoningEffort?: (effort: ReasoningEffortLevel) => void;
  disabled?: boolean;
  modelName?: string;
  supportedLevels?: ReasoningEffortLevel[];
}

export default function ReasoningPill({
  modelId,
  model,
  reasoningEffort = "medium",
  onSelectReasoningEffort,
  disabled = false,
  modelName = "Model",
  supportedLevels,
}: ReasoningPillProps) {
  const [isOpen, setIsOpen] = useState(false);
  const pillRef = useRef<HTMLDivElement>(null);
  const [focusedLevelIndex, setFocusedLevelIndex] = useState<number>(0);

  const targetId = modelId || model?.id || "";

  // Dynamic supported levels per model - Memoized to prevent effect re-render churn
  const availableLevels = useMemo<ReasoningEffortLevel[]>(() => {
    const raw = (
      supportedLevels && supportedLevels.length > 0
        ? supportedLevels
        : getModelSupportedReasoningLevels(model || (modelId ? { id: modelId } : null))
    );
    return raw.filter((lvl) => REASONING_LEVELS.includes(lvl));
  }, [supportedLevels, model, modelId]);

  const shouldRender = !disabled && availableLevels.length > 0;

  // Safe fallback clamping: prefer current, then medium, then low, then first available
  const currentLevel: ReasoningEffortLevel = useMemo(() => {
    if (availableLevels.includes(reasoningEffort as ReasoningEffortLevel)) {
      return reasoningEffort as ReasoningEffortLevel;
    }
    if (availableLevels.includes("medium")) return "medium";
    if (availableLevels.includes("low")) return "low";
    return availableLevels[0] || "off";
  }, [availableLevels, reasoningEffort]);

  const currentConfig = REASONING_EFFORT_CONFIG[currentLevel] || REASONING_EFFORT_CONFIG.medium;
  const isOff = currentLevel === "off";

  // Auto-clamp and sync when model capabilities do not support the previously active effort
  useEffect(() => {
    if (!shouldRender) return;
    if (reasoningEffort && !availableLevels.includes(reasoningEffort as ReasoningEffortLevel)) {
      onSelectReasoningEffort?.(currentLevel);
      if (targetId) {
        saveReasoningEffortForModel(targetId, currentLevel);
      }
    }
  }, [shouldRender, reasoningEffort, availableLevels, currentLevel, onSelectReasoningEffort, targetId]);

  // Synchronize focusedLevelIndex with current active level
  useEffect(() => {
    if (isOpen) {
      const idx = availableLevels.indexOf(currentLevel);
      setFocusedLevelIndex(idx >= 0 ? idx : 0);
    }
  }, [isOpen, currentLevel, availableLevels]);

  const handleSelectLevel = useCallback(
    (level: ReasoningEffortLevel) => {
      const tid = modelId || model?.id;
      if (tid) {
        saveReasoningEffortForModel(tid, level);
      }
      onSelectReasoningEffort?.(level);
      setIsOpen(false);
    },
    [modelId, model?.id, onSelectReasoningEffort]
  );

  // Close on click outside or escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (pillRef.current && !pillRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [isOpen]);

  // Keyboard navigation through reasoning options (ArrowDown, ArrowUp, Enter)
  const handlePopoverKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || availableLevels.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusedLevelIndex((prev) => (prev + 1) % availableLevels.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedLevelIndex((prev) => (prev - 1 + availableLevels.length) % availableLevels.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const level = availableLevels[focusedLevelIndex];
      if (level) {
        handleSelectLevel(level);
      }
    }
  };

  if (!shouldRender) return null;

  return (
    <div
      ref={pillRef}
      data-dropdown-root="true"
      className="relative shrink-0 font-mono"
    >
      {/* Project Anara Minimal Reasoning Effort Pill */}
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        onClick={(e) => {
          e.stopPropagation();
          e.nativeEvent?.stopImmediatePropagation?.();
          setIsOpen((prev) => !prev);
        }}
        title={`Thinking Effort: ${currentConfig.label} (${currentConfig.description})`}
        className={`flex items-center gap-1.5 py-1 px-2.5 rounded-lg border text-[11px] font-medium transition-colors cursor-pointer select-none ${
          isOpen
            ? "bg-white/[0.08] border-white/20 text-white"
            : isOff
            ? "bg-white/[0.02] border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12]"
            : "bg-white/[0.04] hover:bg-white/[0.07] border-white/[0.08] hover:border-white/[0.15] text-zinc-300 hover:text-white"
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full shrink-0 ${
            isOff ? "bg-zinc-600" : "bg-purple-400"
          }`}
        />
        <span className="font-semibold tracking-tight">
          {isOff ? "Off" : currentConfig.shortLabel}
        </span>
        <svg
          className={`w-3 h-3 text-zinc-500 transition-transform shrink-0 ${
            isOpen ? "rotate-180 text-zinc-300" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Reasoning Effort Dropdown Popover */}
      {isOpen && (
        <div
          role="dialog"
          aria-label="Reasoning Effort Budget"
          onClick={(e) => {
            e.stopPropagation();
            e.nativeEvent?.stopImmediatePropagation?.();
          }}
          onKeyDown={handlePopoverKeyDown}
          className="absolute bottom-9 left-0 z-50 w-64 p-1.5 rounded-xl bg-[#090d16]/98 border border-white/[0.08] backdrop-blur-xl shadow-2xl shadow-black/90 animate-scale-up space-y-1 font-mono select-none"
        >
          {/* Header */}
          <div className="px-2 py-1 border-b border-white/[0.06] flex items-center justify-between text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">
            <span>Thinking Budget</span>
            <span className="text-[9px] font-mono text-zinc-400 px-1.5 py-0.5 rounded bg-white/[0.03] border border-white/[0.06] truncate max-w-[100px]">
              {modelName}
            </span>
          </div>

          {/* Dynamic Effort Options List */}
          <div className="space-y-0.5 pt-0.5">
            {availableLevels.map((level, idx) => {
              const cfg = REASONING_EFFORT_CONFIG[level];
              const isSelected = level === currentLevel;
              const isFocused = idx === focusedLevelIndex;

              return (
                <button
                  key={level}
                  type="button"
                  onClick={() => handleSelectLevel(level)}
                  onMouseEnter={() => setFocusedLevelIndex(idx)}
                  className={`w-full flex items-start gap-2 p-1.5 rounded-lg text-left transition-colors cursor-pointer border ${
                    isFocused
                      ? "bg-white/[0.10] border-purple-400/40 text-white"
                      : isSelected
                      ? "bg-white/[0.08] border-white/[0.12] text-white"
                      : "bg-transparent border-transparent hover:bg-white/[0.04] text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  {/* Subtle Radio / Check Indicator */}
                  <div
                    className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 mt-0.5 transition-colors ${
                      isSelected
                        ? "border-purple-400 bg-purple-500/20 text-purple-300"
                        : "border-zinc-700 bg-black/30"
                    }`}
                  >
                    {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />}
                  </div>

                  {/* Text Details */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-1">
                      <span className={`text-xs font-semibold ${isSelected ? "text-white" : "text-zinc-200"}`}>
                        {cfg.label}
                      </span>
                      <span
                        className={`text-[9px] font-mono px-1 py-0.2 rounded border ${
                          isSelected
                            ? "bg-purple-500/10 border-purple-400/30 text-purple-300"
                            : "bg-white/[0.02] border-white/[0.06] text-zinc-500"
                        }`}
                      >
                        {cfg.tokenBadge}
                      </span>
                    </div>
                    <p className="text-[10px] text-zinc-400 leading-tight mt-0.5 font-sans">
                      {cfg.description}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
