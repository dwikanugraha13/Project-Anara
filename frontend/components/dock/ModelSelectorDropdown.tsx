"use client";

import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";
import {
  formatModelDisplayName,
  extractModelRoute,
  extractModelTier,
} from "@/lib/modelFormat";
import {
  isReasoningSupported,
  getModelModalities,
  ReasoningEffortLevel,
} from "@/lib/reasoningEffort";
export { isReasoningSupported };

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
  supports_video?: boolean;
  modalities?: string[];
  supported_reasoning_levels?: string[];
  context_window?: number;
  max_output_tokens?: number;
  is_configured: boolean;
  is_active: boolean;
}

export interface ModelSelectorDropdownProps {
  isOpen: boolean;
  onClose: () => void;
  models: AIModelInfo[];
  activeModelId: string;
  onSelectModel: (id: string) => void;
  interactionMode: "voice" | "chat";
  reasoningEffort?: "off" | "low" | "medium" | "high" | "max" | "ultra" | "budget" | string;
  onSelectReasoningEffort?: (effort: ReasoningEffortLevel) => void;
}

/**
 * Curated static fallback catalog (Hermes Desktop / Claude Code resilience standard).
 * Guaranteed fallback if backend model endpoint is down, slow, or returning empty.
 */
export const DEFAULT_CURATED_MODELS: AIModelInfo[] = [
  {
    id: "9router/ag/gemini-3.8-flash-high",
    name: "Gemini 3.8 Flash (High)",
    provider: "gemini",
    category: "multimodal",
    badge: "Fast",
    description: "Ultra-fast multimodal reasoning engine with 1M context",
    icon: "gemini",
    supports_voice: true,
    supports_reasoning: true,
    supports_vision: true,
    supports_video: true,
    modalities: ["text", "image", "video", "audio", "reasoning"],
    context_window: 1000000,
    is_configured: true,
    is_active: true,
  },
  {
    id: "anthropic/claude-3-7-sonnet",
    name: "Claude 3.7 Sonnet",
    provider: "anthropic",
    category: "reasoning",
    badge: "Pro",
    description: "Hybrid architecture with dynamic extended thinking budget",
    icon: "anthropic",
    supports_voice: false,
    supports_reasoning: true,
    supports_vision: true,
    modalities: ["text", "image", "reasoning"],
    context_window: 200000,
    is_configured: true,
    is_active: true,
  },
  {
    id: "openai/gpt-4o",
    name: "GPT-4o Official",
    provider: "openai",
    category: "general",
    badge: "Pro",
    description: "Flagship high-intelligence multimodal Omni foundation",
    icon: "openai",
    supports_voice: true,
    supports_reasoning: false,
    supports_vision: true,
    modalities: ["text", "image", "audio"],
    context_window: 128000,
    is_configured: true,
    is_active: true,
  },
  {
    id: "openai/o3-mini",
    name: "o3-mini Reasoning",
    provider: "openai",
    category: "reasoning",
    badge: "Reasoning",
    description: "Specialized STEM, coding, and mathematical reasoning",
    icon: "openai",
    supports_voice: false,
    supports_reasoning: true,
    supports_vision: false,
    modalities: ["text", "reasoning"],
    context_window: 200000,
    is_configured: true,
    is_active: true,
  },
  {
    id: "deepseek/deepseek-r1",
    name: "DeepSeek R1 Official",
    provider: "deepseek",
    category: "reasoning",
    badge: "Reasoning",
    description: "Open-weights frontier reasoning & mathematical solver",
    icon: "deepseek",
    supports_voice: false,
    supports_reasoning: true,
    supports_vision: false,
    modalities: ["text", "reasoning"],
    context_window: 64000,
    is_configured: true,
    is_active: true,
  },
  {
    id: "groq/llama-3.3-70b-versatile",
    name: "Llama 3.3 70B (Groq LPU)",
    provider: "groq",
    category: "fast",
    badge: "Fast",
    description: "Sub-second LPU inference acceleration",
    icon: "groq",
    supports_voice: false,
    supports_reasoning: false,
    supports_vision: false,
    modalities: ["text"],
    context_window: 128000,
    is_configured: true,
    is_active: true,
  },
  {
    id: "ollama/qwen2.5-coder:7b",
    name: "Qwen 2.5 Coder 7B (Local)",
    provider: "ollama",
    category: "local",
    badge: "Fast",
    description: "Air-gapped on-device code generation",
    icon: "ollama",
    supports_voice: false,
    supports_reasoning: false,
    supports_vision: false,
    modalities: ["text"],
    context_window: 32000,
    is_configured: true,
    is_active: true,
  },
];

export const CANONICAL_PROVIDER_ORDER = [
  "openai",
  "codex",
  "anthropic",
  "gemini",
  "google",
  "deepseek",
  "groq",
  "ollama",
  "local",
  "llamacpp",
  "9router",
  "openrouter",
  "xai",
  "custom",
];

export const PROVIDER_LABEL_MAP: Record<string, string> = {
  openai: "OpenAI Official",
  codex: "OpenAI Codex",
  anthropic: "Anthropic Claude",
  gemini: "Google AI Studio",
  google: "Google AI Studio",
  deepseek: "DeepSeek Official",
  groq: "Groq Cloud",
  ollama: "Ollama (Local)",
  local: "Local (llama.cpp)",
  llamacpp: "Local (llama.cpp)",
  "9router": "9Router Proxy",
  openrouter: "OpenRouter",
  xai: "xAI Grok",
  custom: "Custom Gateway",
};

export function getProviderDisplayName(providerKey: string | undefined | null): string {
  if (!providerKey) return "Custom Gateway";
  const k = providerKey.toLowerCase().trim();
  return PROVIDER_LABEL_MAP[k] || (k.length <= 4 ? k.toUpperCase() : k.charAt(0).toUpperCase() + k.slice(1));
}

/**
 * Evaluates whether a model qualifies for tier badges (Reasoning, Fast, Vision, Pro)
 */
export function getModelTierBadges(model: AIModelInfo): {
  isReasoning: boolean;
  isFast: boolean;
  isVision: boolean;
  isPro: boolean;
} {
  const mid = (model.id || "").toLowerCase();
  const name = (model.name || "").toLowerCase();
  const badgeLower = (model.badge || "").toLowerCase();

  const isReasoning =
    isReasoningSupported(model) ||
    Boolean(extractModelTier(model.id)) ||
    badgeLower === "reasoning" ||
    mid.includes("reason") ||
    mid.includes("think") ||
    mid.includes("r1") ||
    mid.includes("o1") ||
    mid.includes("o3") ||
    mid.includes("o4");

  const isFast =
    badgeLower === "fast" ||
    mid.includes("flash") ||
    mid.includes("fast") ||
    mid.includes("haiku") ||
    mid.includes("mini") ||
    name.includes("flash") ||
    name.includes("mini") ||
    model.provider?.toLowerCase() === "groq";

  const isVision =
    Boolean(model.supports_vision) ||
    (Array.isArray(model.modalities) && model.modalities.includes("image")) ||
    mid.includes("vision") ||
    mid.includes("-vl") ||
    mid.includes("4o") ||
    name.includes("vision");

  const isPro =
    badgeLower === "pro" ||
    mid.includes("pro") ||
    mid.includes("opus") ||
    mid.includes("sonnet") ||
    mid.includes("gpt-4") ||
    mid.includes("gpt-5") ||
    mid.includes("astra") ||
    mid.includes("ultra") ||
    name.includes("pro");

  return { isReasoning, isFast, isVision, isPro };
}

export default function ModelSelectorDropdown({
  isOpen,
  onClose,
  models,
  activeModelId,
  onSelectModel,
  interactionMode,
  reasoningEffort,
  onSelectReasoningEffort,
}: ModelSelectorDropdownProps) {
  const [modelSearchQuery, setModelSearchQuery] = useState("");
  const [selectedProviderKey, setSelectedProviderKey] = useState<string>("All");
  const [selectedRouteKey, setSelectedRouteKey] = useState<string>("All");
  const [focusedIndex, setFocusedIndex] = useState<number>(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listContainerRef = useRef<HTMLDivElement>(null);

  // Fallback to static curated catalog if models list is empty or undefined
  const effectiveModels = useMemo(() => {
    if (Array.isArray(models) && models.length > 0) {
      return models;
    }
    return DEFAULT_CURATED_MODELS;
  }, [models]);

  const isUsingFallback = !models || models.length === 0;

  const modeFilteredModels = useMemo(() => {
    return effectiveModels.filter((m: AIModelInfo) => {
      if (interactionMode === "voice") {
        return !!m.supports_voice || m.id.toLowerCase().includes("live-preview");
      }
      return true;
    });
  }, [effectiveModels, interactionMode]);

  /**
   * Deduplicate tier variants: models sharing the same base slug (after stripping
   * -low/-medium/-high/-thinking suffixes) are consolidated into a single entry.
   */
  const deduplicatedModels = useMemo(() => {
    const tierPriority: Record<string, number> = {
      "": 0,
      high: 1,
      thinking: 2,
      medium: 3,
      low: 4,
      thought: 5,
      reasoning: 6,
    };

    const baseGroups = new Map<string, { model: AIModelInfo; tier: string; priority: number; siblings: string[] }>();

    for (const m of modeFilteredModels) {
      const tier = extractModelTier(m.id);
      const tierKey = tier || "";
      const baseSlug = tier
        ? m.id.replace(/[-_](low|medium|high|thinking|thought|reasoning)(?::[a-z]+)?$/i, "")
        : m.id;

      const priority = tierPriority[tierKey] ?? 99;

      if (!baseGroups.has(baseSlug)) {
        baseGroups.set(baseSlug, { model: m, tier: tierKey, priority, siblings: [m.id] });
      } else {
        const existing = baseGroups.get(baseSlug)!;
        existing.siblings.push(m.id);
        if (priority < existing.priority) {
          existing.model = m;
          existing.tier = tierKey;
          existing.priority = priority;
        }
      }
    }

    return Array.from(baseGroups.values()).map((g) => ({
      ...g.model,
      _siblingCount: g.siblings.length,
      _siblings: g.siblings,
    }));
  }, [modeFilteredModels]);

  /**
   * Provider Groups ordered canonically according to Hermes standards
   */
  const providerGroups = useMemo(() => {
    const counts: Record<string, { label: string; count: number; order: number }> = {};
    for (const m of deduplicatedModels) {
      const pKey = (m.provider || "custom").toLowerCase();
      if (!counts[pKey]) {
        const orderIdx = CANONICAL_PROVIDER_ORDER.indexOf(pKey);
        counts[pKey] = {
          label: getProviderDisplayName(pKey),
          count: 0,
          order: orderIdx >= 0 ? orderIdx : 999,
        };
      }
      counts[pKey].count += 1;
    }

    const sorted = Object.entries(counts).sort((a, b) => {
      if (a[1].order !== b[1].order) return a[1].order - b[1].order;
      return b[1].count - a[1].count;
    });

    return [
      { key: "All", label: "All Providers", count: deduplicatedModels.length },
      ...sorted.map(([key, info]) => ({ key, label: info.label, count: info.count })),
    ];
  }, [deduplicatedModels]);

  // Sub-Routes within selected provider (e.g. Antigravity, Claudeflare, Xkiro within 9Router)
  const availableRoutes = useMemo(() => {
    const relevantModels = selectedProviderKey === "All"
      ? deduplicatedModels
      : deduplicatedModels.filter((m) => (m.provider || "custom").toLowerCase() === selectedProviderKey.toLowerCase());

    const routeCounts: Record<string, { label: string; count: number }> = {};
    for (const m of relevantModels) {
      const rLabel = extractModelRoute(m.id);
      if (rLabel) {
        if (!routeCounts[rLabel]) {
          routeCounts[rLabel] = { label: rLabel, count: 0 };
        }
        routeCounts[rLabel].count += 1;
      }
    }
    const sorted = Object.entries(routeCounts).sort((a, b) => b[1].count - a[1].count);
    if (sorted.length <= 1) return [];
    return [
      { key: "All", label: "All Routes", count: relevantModels.length },
      ...sorted.map(([key, info]) => ({ key, label: info.label, count: info.count })),
    ];
  }, [deduplicatedModels, selectedProviderKey]);

  // Filter models by search query, provider chip, and route chip
  const displayedModels = useMemo(() => {
    const q = modelSearchQuery.toLowerCase().trim();
    return deduplicatedModels.filter((m: AIModelInfo) => {
      // 1. Provider filter
      if (selectedProviderKey !== "All") {
        const pKey = (m.provider || "custom").toLowerCase();
        if (pKey !== selectedProviderKey.toLowerCase()) return false;
      }
      // 2. Sub-route filter
      if (selectedRouteKey !== "All") {
        const rLabel = extractModelRoute(m.id);
        if (rLabel !== selectedRouteKey) return false;
      }
      // 3. Search filter
      if (!q) return true;
      const siblings = (m as any)._siblings as string[] | undefined;
      return (
        m.name.toLowerCase().includes(q) ||
        m.id.toLowerCase().includes(q) ||
        (m.badge || "").toLowerCase().includes(q) ||
        (m.provider || "").toLowerCase().includes(q) ||
        (siblings && siblings.some((s: string) => s.toLowerCase().includes(q)))
      );
    });
  }, [deduplicatedModels, selectedProviderKey, selectedRouteKey, modelSearchQuery]);

  /**
   * Group displayed models by provider preserving provider headers even during search
   * (Hermes Desktop CommandGroup parity)
   */
  const groupedSections = useMemo(() => {
    const map = new Map<string, AIModelInfo[]>();

    for (const m of displayedModels) {
      const pKey = (m.provider || "custom").toLowerCase();
      const pLabel = getProviderDisplayName(pKey);
      if (!map.has(pLabel)) map.set(pLabel, []);
      map.get(pLabel)!.push(m);
    }

    // Sort sections according to canonical provider order
    return Array.from(map.entries())
      .sort((a, b) => {
        const orderA = CANONICAL_PROVIDER_ORDER.findIndex((k) => PROVIDER_LABEL_MAP[k] === a[0]);
        const orderB = CANONICAL_PROVIDER_ORDER.findIndex((k) => PROVIDER_LABEL_MAP[k] === b[0]);
        return (orderA >= 0 ? orderA : 999) - (orderB >= 0 ? orderB : 999);
      })
      .map(([title, items]) => ({
        title,
        models: items,
      }));
  }, [displayedModels]);

  // Auto-focus search input when opened and initialize focused index
  useEffect(() => {
    if (isOpen) {
      setModelSearchQuery("");
      setFocusedIndex(0);
      const timer = setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Synchronize focusedIndex with activeModelId initially
  useEffect(() => {
    if (isOpen && displayedModels.length > 0) {
      const activeIdx = displayedModels.findIndex(
        (m) => m.id === activeModelId || ((m as any)._siblings && (m as any)._siblings.includes(activeModelId))
      );
      if (activeIdx >= 0) {
        setFocusedIndex(activeIdx);
      }
    }
  }, [isOpen, activeModelId, displayedModels]);

  // Click outside and Escape key dismissal
  useEffect(() => {
    if (!isOpen) return;

    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as Node | null;
      if (containerRef.current && !containerRef.current.contains(target)) {
        onClose();
      }
    };

    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };

    document.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("keydown", handleGlobalKeyDown, true);
    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("keydown", handleGlobalKeyDown, true);
    };
  }, [isOpen, onClose]);

  // Select model handler with tier variant resolution
  const handleSelect = useCallback(
    (m: AIModelInfo) => {
      onSelectModel(m.id);
      const inherentTier = extractModelTier(m.id);
      if (inherentTier && onSelectReasoningEffort) {
        onSelectReasoningEffort(
          inherentTier === "thinking" ? "high" : (inherentTier as ReasoningEffortLevel)
        );
      }
      onClose();
    },
    [onSelectModel, onSelectReasoningEffort, onClose]
  );

  // Keyboard navigation through list (ArrowDown, ArrowUp, Enter, Home, End)
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (displayedModels.length === 0) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setFocusedIndex((prev) => (prev + 1) % displayedModels.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setFocusedIndex((prev) => (prev - 1 + displayedModels.length) % displayedModels.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (displayedModels[focusedIndex]) {
          handleSelect(displayedModels[focusedIndex]);
        }
      } else if (e.key === "Home") {
        e.preventDefault();
        setFocusedIndex(0);
      } else if (e.key === "End") {
        e.preventDefault();
        setFocusedIndex(displayedModels.length - 1);
      }
    },
    [displayedModels, focusedIndex, handleSelect]
  );

  // Scroll active item into view smoothly
  useEffect(() => {
    if (!isOpen || !listContainerRef.current) return;
    const activeEl = listContainerRef.current.querySelector<HTMLElement>(`[data-model-idx="${focusedIndex}"]`);
    if (activeEl) {
      activeEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [focusedIndex, isOpen]);

  if (!isOpen) return null;

  const formatTokens = (tokens?: number) => {
    if (!tokens) return "";
    if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(tokens >= 10_000_000 ? 0 : 1)}M`;
    if (tokens >= 1_000) return `${Math.round(tokens / 1_000)}K`;
    return `${tokens}`;
  };

  return (
    <div
      ref={containerRef}
      data-dropdown-root="true"
      role="dialog"
      aria-label="Model Selector Dropdown"
      onClick={(e) => {
        e.stopPropagation();
        e.nativeEvent?.stopImmediatePropagation?.();
      }}
      onKeyDown={handleKeyDown}
      className="absolute bottom-9 left-0 z-50 w-84 sm:w-[460px] p-2.5 rounded-2xl bg-[#090d16]/98 border border-white/[0.08] backdrop-blur-2xl shadow-2xl shadow-black/95 animate-scale-up flex flex-col font-mono select-none max-h-[500px]"
    >
      {/* 1. Header: Clean Title + Esc Hint + Close Button */}
      <div className="px-1.5 pb-2 border-b border-white/[0.06] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0 shadow-[0_0_6px_rgba(34,211,238,0.6)]" />
          <span className="text-[11px] font-mono font-semibold uppercase tracking-wider text-zinc-200">
            {interactionMode === "voice" ? "Live Audio Engines" : "AI Execution Engines"}
          </span>
          <span className="text-[9.5px] font-mono text-zinc-500 bg-white/[0.04] px-1.5 py-0.2 rounded border border-white/[0.06]">
            {displayedModels.length}
          </span>
          {isUsingFallback && (
            <span
              title="Using curated standby catalog while backend model stream initializes"
              className="text-[8px] font-mono font-semibold uppercase text-amber-400 bg-amber-500/[0.08] border border-amber-500/20 px-1 py-0.2 rounded"
            >
              Standby
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <kbd className="hidden sm:inline-block text-[8.5px] font-mono px-1.5 py-0.5 rounded bg-white/[0.03] border border-white/[0.06] text-zinc-500">
            ESC
          </kbd>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close model picker"
            title="Close model picker (Esc)"
            className="w-5 h-5 rounded-md flex items-center justify-center text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.06] transition-colors cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* 2. Keyboard-Ready Search Input */}
      <div className="relative pt-2 px-0.5">
        <svg
          className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-[17px] pointer-events-none"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          ref={searchInputRef}
          type="text"
          placeholder={interactionMode === "voice" ? "Search live audio models..." : "Search by name, provider, or tier (↑↓ Enter)..."}
          value={modelSearchQuery}
          onChange={(e) => {
            setModelSearchQuery(e.target.value);
            setFocusedIndex(0);
          }}
          className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-cyan-400/40 font-mono transition-colors"
        />
      </div>

      {/* 3. Canonical Provider Filter Chips */}
      {providerGroups.length > 1 && (
        <div className="flex items-center gap-1 overflow-x-auto custom-scrollbar py-1 px-0.5 shrink-0 border-b border-white/[0.04]">
          {providerGroups.map((pg) => {
            const isFilterActive = selectedProviderKey === pg.key;
            return (
              <button
                key={pg.key}
                type="button"
                onClick={() => {
                  setSelectedProviderKey(pg.key);
                  setSelectedRouteKey("All");
                  setFocusedIndex(0);
                }}
                className={`px-2 py-0.5 rounded-lg text-[10px] font-mono whitespace-nowrap transition-colors border cursor-pointer ${
                  isFilterActive
                    ? "bg-white/[0.12] text-white border-white/[0.22] font-semibold shadow-sm"
                    : "bg-transparent text-zinc-400 hover:text-zinc-200 border-transparent hover:bg-white/[0.04]"
                }`}
              >
                {pg.label} <span className="opacity-50 text-[8.5px] ml-0.5">{pg.count}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* 4. Sub-Route Filter Chips */}
      {availableRoutes.length > 1 && (
        <div className="flex items-center gap-1 overflow-x-auto custom-scrollbar py-1 px-0.5 shrink-0 bg-white/[0.015] rounded-lg mt-0.5">
          <span className="text-[8.5px] font-mono text-zinc-500 uppercase tracking-wider pl-1 shrink-0">
            Route:
          </span>
          {availableRoutes.map((rg) => {
            const isFilterActive = selectedRouteKey === rg.key;
            return (
              <button
                key={rg.key}
                type="button"
                onClick={() => {
                  setSelectedRouteKey(rg.key);
                  setFocusedIndex(0);
                }}
                className={`px-1.5 py-0.2 rounded-md text-[9.5px] font-mono whitespace-nowrap transition-colors border cursor-pointer ${
                  isFilterActive
                    ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40 font-semibold"
                    : "bg-transparent text-zinc-400 hover:text-zinc-200 border-transparent hover:bg-white/[0.04]"
                }`}
              >
                {rg.label} <span className="opacity-50 text-[8px] ml-0.5">{rg.count}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* 5. Tabular Model Catalog List with Keyboard Focus and Section Dividers */}
      <div
        ref={listContainerRef}
        role="listbox"
        aria-label="Models list"
        className="mt-1 space-y-0.5 overflow-y-auto custom-scrollbar flex-1 pr-1"
      >
        {displayedModels.length === 0 ? (
          <div className="py-8 text-center text-xs text-zinc-500 font-mono">
            {interactionMode === "voice"
              ? "No live audio models match your criteria."
              : "No matching models found. Press Esc to dismiss."}
          </div>
        ) : (
          groupedSections.map((sec, secIdx) => (
            <div key={sec.title || `sec-${secIdx}`} className="space-y-0.5">
              {/* Provider Heading (Always preserved, Claude Code / Hermes standard) */}
              <div className="sticky top-0 z-10 text-[9.5px] font-mono font-semibold uppercase tracking-wider text-zinc-400 px-2 py-1 bg-[#090d16]/95 backdrop-blur-sm border-b border-white/[0.04] flex items-center justify-between">
                <span>{sec.title}</span>
                <span className="text-[8.5px] text-zinc-500">{sec.models.length}</span>
              </div>

              {sec.models.map((m) => {
                const globalIndex = displayedModels.findIndex((item) => item.id === m.id);
                const isFocused = globalIndex === focusedIndex;
                const siblingCount = (m as any)._siblingCount as number | undefined;
                const siblings = (m as any)._siblings as string[] | undefined;
                const isSelected = m.id === activeModelId || (siblings && siblings.includes(activeModelId));
                const displayName = formatModelDisplayName(m.name || m.id);
                const inherentTier = extractModelTier(m.id);
                const routeName = extractModelRoute(m.id) || m.provider?.toLowerCase();
                const modalities = getModelModalities(m);
                const { isReasoning, isFast, isVision, isPro } = getModelTierBadges(m);

                return (
                  <button
                    key={m.id}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    data-model-idx={globalIndex}
                    onClick={() => handleSelect(m)}
                    onMouseEnter={() => setFocusedIndex(globalIndex)}
                    title={`${displayName} (${m.id})\nProvider: ${getProviderDisplayName(m.provider)}\nRoute: ${routeName}\nTier: ${inherentTier || "Standard"}\nModalities: ${modalities.map((x) => x.label).join(", ")}`}
                    className={`w-full h-8 px-2 rounded-lg flex items-center justify-between text-left transition-colors cursor-pointer border ${
                      isFocused
                        ? "bg-white/[0.10] border-cyan-400/40 text-white"
                        : isSelected
                        ? "bg-white/[0.06] border-white/[0.14] text-white shadow-sm"
                        : "bg-transparent border-transparent hover:bg-white/[0.04] hover:border-white/[0.07] text-zinc-300 hover:text-white"
                    }`}
                  >
                    {/* Left: Indicator + Clean Model Name + Tiers + Route */}
                    <div className="flex items-center gap-1.5 min-w-0 flex-1 pr-2">
                      <span
                        className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                          isSelected
                            ? "bg-cyan-400 ring-2 ring-cyan-400/20 shadow-[0_0_6px_rgba(34,211,238,0.8)]"
                            : isFocused
                            ? "bg-zinc-400"
                            : "bg-transparent"
                        }`}
                      />
                      <span className={`text-[11.5px] truncate ${isSelected ? "text-white font-semibold" : "text-zinc-200"}`}>
                        {displayName}
                      </span>

                      {/* Tier Badges (Reasoning, Fast, Vision, Pro - Hermes Standard) */}
                      <div className="flex items-center gap-0.5 shrink-0">
                        {isReasoning && (
                          <span
                            title="Reasoning / Deep Thinking"
                            className="text-[7.5px] font-mono font-medium px-1 py-0.2 rounded border text-purple-300 bg-purple-500/[0.12] border-purple-400/30"
                          >
                            REASON
                          </span>
                        )}
                        {isFast && !isReasoning && (
                          <span
                            title="Fast LPU / Low-latency inference"
                            className="text-[7.5px] font-mono font-medium px-1 py-0.2 rounded border text-cyan-300 bg-cyan-500/[0.12] border-cyan-400/30"
                          >
                            FAST
                          </span>
                        )}
                        {isPro && (
                          <span
                            title="Flagship / Pro Tier"
                            className="text-[7.5px] font-mono font-medium px-1 py-0.2 rounded border text-amber-300 bg-amber-500/[0.12] border-amber-400/30"
                          >
                            PRO
                          </span>
                        )}
                        {siblingCount && siblingCount > 1 && (
                          <span
                            title={`${siblingCount} tier variants consolidated (controlled via Think pill):\n${siblings?.join("\n")}`}
                            className="text-[7.5px] font-mono font-semibold px-1 py-0.2 rounded border bg-white/[0.05] text-zinc-400 border-white/[0.10]"
                          >
                            {siblingCount} Tiers
                          </span>
                        )}
                      </div>

                      <span className="text-[9px] font-mono text-zinc-500 shrink-0 hidden sm:inline-block">
                        {routeName}
                      </span>
                    </div>

                    {/* Right: Modality Chips + Context Size + Checkmark */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      {/* Modality micro-tags */}
                      <div className="flex items-center gap-0.5">
                        {isVision && (
                          <span
                            title="Vision capable"
                            className="text-[7.5px] font-mono font-medium px-1 py-0.2 rounded border text-emerald-400 bg-emerald-500/[0.06] border-emerald-500/20"
                          >
                            IMG
                          </span>
                        )}
                        {modalities.some((m) => m.id === "video") && (
                          <span
                            title="Video capable"
                            className="text-[7.5px] font-mono font-medium px-1 py-0.2 rounded border text-amber-400 bg-amber-500/[0.06] border-amber-500/20"
                          >
                            VID
                          </span>
                        )}
                        {modalities.some((m) => m.id === "audio") && (
                          <span
                            title="Voice capable"
                            className="text-[7.5px] font-mono font-medium px-1 py-0.2 rounded border text-sky-400 bg-sky-500/[0.06] border-sky-500/20"
                          >
                            AUD
                          </span>
                        )}
                      </div>

                      {/* Context tokens length */}
                      {m.context_window ? (
                        <span className="text-[9px] font-mono text-zinc-400 w-7 text-right shrink-0">
                          {formatTokens(m.context_window)}
                        </span>
                      ) : (
                        <span className="w-7 shrink-0" />
                      )}

                      {/* Active Checkmark */}
                      <div className="w-3.5 h-3.5 flex items-center justify-center shrink-0">
                        {isSelected && (
                          <svg className="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
