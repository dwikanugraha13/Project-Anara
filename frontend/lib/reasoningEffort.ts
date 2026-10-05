/**
 * Project Anara Reasoning Effort Architecture
 * Provides normalized per-model reasoning effort configuration, labels,
 * default capability inference, and local persistence.
 */

export type ReasoningEffortLevel = "off" | "low" | "medium" | "high" | "max" | "ultra" | "budget";

export interface ReasoningEffortConfig {
  label: string;
  shortLabel: string;
  description: string;
  tokenBadge: string;
}

export const REASONING_EFFORT_CONFIG: Record<ReasoningEffortLevel, ReasoningEffortConfig> = {
  off: {
    label: "Off",
    shortLabel: "Off",
    description: "Standard generation without extended thinking",
    tokenBadge: "0 tokens",
  },
  low: {
    label: "Low",
    shortLabel: "Low",
    description: "Fast reasoning for lightweight analysis and triage",
    tokenBadge: "~1K-2K tokens",
  },
  medium: {
    label: "Medium",
    shortLabel: "Med",
    description: "Balanced reasoning for general problem solving",
    tokenBadge: "~4K-8K tokens",
  },
  high: {
    label: "High",
    shortLabel: "High",
    description: "Deep thinking for complex coding and architecture",
    tokenBadge: "~16K-32K tokens",
  },
  budget: {
    label: "Budget",
    shortLabel: "Budget",
    description: "Targeted reasoning budget for precise token limits",
    tokenBadge: "~2K-4K tokens",
  },
  max: {
    label: "Max",
    shortLabel: "Max",
    description: "Exhaustive reasoning budget for hardest algorithmic tasks",
    tokenBadge: "Full context",
  },
  ultra: {
    label: "Ultra",
    shortLabel: "Ultra",
    description: "Extreme reasoning depth & autonomous exhaustive deliberation",
    tokenBadge: "64K+ tokens",
  },
};

export const REASONING_LEVELS: ReasoningEffortLevel[] = ["off", "low", "medium", "high", "budget", "max", "ultra"];

export interface MinimalModelInfo {
  id: string;
  name?: string;
  provider?: string;
  supports_reasoning?: boolean;
  supports_voice?: boolean;
  supports_vision?: boolean;
  supports_video?: boolean;
  supports_text?: boolean;
  modalities?: string[];
  input_modalities?: string[];
  output_modalities?: string[];
  tags?: string[];
  capabilities?: string[] | Record<string, any>;
  supported_parameters?: string[];
  parameters?: string[];
  architecture?: {
    modality?: string;
    instruct_type?: string;
    [key: string]: any;
  };
  supported_reasoning_levels?: string[];
  reasoning_options?: string[];
  reasoning_effort_levels?: string[];
  allowed_effort?: string[];
  [key: string]: any;
}

export interface ModelModalityInfo {
  id: "text" | "image" | "video" | "audio" | "reasoning";
  label: string;
  shortLabel: string;
  title: string;
  className: string;
  dotColor: string;
}

/**
 * Returns supported reasoning levels tailored dynamically per model.
 * E.g. GPT-6 Astra supports up to 'ultra', OpenAI o1/o3 support ['low', 'medium', 'high'].
 */
export function getModelSupportedReasoningLevels(model?: MinimalModelInfo | null): ReasoningEffortLevel[] {
  if (!model) return [];
  if (!isReasoningSupported(model)) return [];

  // Normalize upstream declarations (OpenRouter / Ollama / vLLM / GitHub Models / Anara backend)
  const rawLevels =
    model.supported_reasoning_levels ||
    model.reasoning_options ||
    model.reasoning_effort_levels ||
    model.allowed_effort;

  if (Array.isArray(rawLevels) && rawLevels.length > 0) {
    const mapped: ReasoningEffortLevel[] = [];
    for (const lvl of rawLevels) {
      const s = String(lvl).toLowerCase().trim();
      if (s === "none" || s === "off" || s === "0" || s === "disabled" || s === "false") {
        mapped.push("off");
      } else if (s === "low" || s === "minimal" || s === "min") {
        mapped.push("low");
      } else if (s === "medium" || s === "med" || s === "default" || s === "standard") {
        mapped.push("medium");
      } else if (s === "high" || s === "deep") {
        mapped.push("high");
      } else if (s === "budget" || s === "target") {
        mapped.push("budget");
      } else if (s === "max" || s === "maximum" || s === "xhigh") {
        mapped.push("max");
      } else if (s === "ultra" || s === "extreme") {
        mapped.push("ultra");
      }
    }
    const unique = Array.from(new Set(mapped)).filter((lvl): lvl is ReasoningEffortLevel =>
      REASONING_LEVELS.includes(lvl)
    );
    if (unique.length > 0) return unique;
  }

  const mid = (model.id || "").toLowerCase();
  const name = (model.name || "").toLowerCase();

  // Astra / Frontier ultra reasoning
  if (mid.includes("astra") || mid.includes("ultra") || mid.includes("gpt-6") || name.includes("astra")) {
    return ["off", "low", "medium", "high", "max", "ultra"];
  }

  // OpenAI o1, o3, o4 native (OpenAI wire only accepts low, medium, high)
  if (/(?:^|[-_./\s])(o[134]|o[134]-mini)(?:[-_./\s]|$)/i.test(mid)) {
    return ["low", "medium", "high"];
  }

  // DeepSeek R1 native
  if (mid.includes("r1") || mid.includes("deepseek-reasoner")) {
    return ["off", "high", "max"];
  }

  // Google Gemini & Perplexity Sonar officially top out at High
  if (mid.includes("gemini") || mid.includes("sonar") || name.includes("gemini")) {
    return ["off", "low", "medium", "high"];
  }

  // Anthropic Claude 3.7+ / Extended thinking with explicit budget
  if (mid.includes("claude-3-7") || mid.includes("claude-3.7") || mid.includes("claude") || name.includes("claude")) {
    return ["off", "low", "medium", "high", "budget", "max"];
  }

  // Extended ultra-tier reasoning models
  if (mid.includes("opus-4") || mid.includes("sonnet-4") || mid.includes("ultra")) {
    return ["off", "low", "medium", "high", "budget", "max", "ultra"];
  }

  // Default reasoning tiers (general reasoning models)
  return ["off", "low", "medium", "high", "max"];
}

/**
 * Extracts normalized modalities (Text, Vision, Video, Audio, Reasoning) for any model.
 */
export function getModelModalities(model?: MinimalModelInfo | null): ModelModalityInfo[] {
  if (!model) return [];
  const mid = (model.id || "").toLowerCase();
  const modalities: ModelModalityInfo[] = [];

  const allMods = [
    ...(Array.isArray(model.modalities) ? model.modalities : []),
    ...(Array.isArray(model.input_modalities) ? model.input_modalities : []),
    ...(Array.isArray(model.output_modalities) ? model.output_modalities : []),
  ].map((m) => String(m).toLowerCase());

  // 1. Text is universal
  modalities.push({
    id: "text",
    label: "Text",
    shortLabel: "TXT",
    title: "Text input & code synthesis",
    className: "text-zinc-400 bg-white/[0.03] border-white/[0.08]",
    dotColor: "bg-zinc-400",
  });

  // 2. Vision / Image
  const hasVision =
    model.supports_vision ||
    allMods.includes("image") ||
    allMods.includes("vision") ||
    /(\bvision\b|-vl\b|\bllava\b|\bpixtral\b|\bmultimodal\b|\bgpt-4o\b|\bgpt-4-turbo\b|\bgpt-5\b|\bclaude-(?:sonnet|opus|haiku|[3-9])\b|\bgemini-|\bqwen(?:2\.5)?-vl\b|\bmimo-v)/i.test(mid);

  if (hasVision) {
    modalities.push({
      id: "image",
      label: "Vision",
      shortLabel: "VISION",
      title: "Multimodal image & document perception",
      className: "text-emerald-400 bg-emerald-500/[0.08] border-emerald-500/25",
      dotColor: "bg-emerald-400",
    });
  }

  // 3. Video
  const hasVideo =
    model.supports_video ||
    allMods.includes("video") ||
    /(\bgemini-(?:1\.5|2\.[0-9]|2\.5|3\.[0-9]|flash|pro)\b|\bqwen2(?:.5)?-vl\b|\bvideo\b|\bgpt-4o\b|\bgpt-5\b|\bclaude-(?:sonnet|opus)-[4-9]\b)/i.test(mid);

  if (hasVideo) {
    modalities.push({
      id: "video",
      label: "Video",
      shortLabel: "VIDEO",
      title: "Video temporal analysis & frame comprehension",
      className: "text-amber-400 bg-amber-500/[0.08] border-amber-500/25",
      dotColor: "bg-amber-400",
    });
  }

  // 4. Voice / Audio
  const hasVoice =
    model.supports_voice ||
    allMods.includes("audio") ||
    allMods.includes("voice") ||
    /(\baudio\b|\bvoice\b|\brealtime\b|\blive-preview\b|\bflash-live\b)/i.test(mid);

  if (hasVoice) {
    modalities.push({
      id: "audio",
      label: "Voice",
      shortLabel: "AUDIO",
      title: "Realtime bidirectional audio & voice conversation",
      className: "text-sky-400 bg-sky-500/[0.08] border-sky-500/25",
      dotColor: "bg-sky-400",
    });
  }

  // 5. Reasoning / Thinking
  if (isReasoningSupported(model)) {
    modalities.push({
      id: "reasoning",
      label: "Thinking",
      shortLabel: "THINK",
      title: "Extended chain-of-thought & deep reasoning",
      className: "text-purple-400 bg-purple-500/[0.08] border-purple-500/25",
      dotColor: "bg-purple-400",
    });
  }

  return modalities;
}

/**
 * Determines whether a model supports extended reasoning / thinking tokens.
 * Dynamically handshakes with model declarations, parameters, modalities, and tags.
 */
export function isReasoningSupported(model?: MinimalModelInfo | null): boolean {
  if (!model) return false;
  const mid = (model.id || "").toLowerCase();

  // Pure bidirectional live WebAudio streaming models do not support extended reasoning tokens
  if (
    mid.includes("live-preview") ||
    mid.includes("flash-live") ||
    mid.includes("-live-") ||
    mid.includes("realtime")
  ) {
    return false;
  }

  // 1. Explicit boolean flag from backend discovery/registry
  if (typeof model.supports_reasoning === "boolean") {
    return model.supports_reasoning;
  }

  // 2. Direct upstream level/option declarations (OpenRouter, LM Studio, vLLM, GitHub Models)
  const explicitLevels =
    model.supported_reasoning_levels ||
    model.reasoning_options ||
    model.reasoning_effort_levels ||
    model.allowed_effort;
  if (Array.isArray(explicitLevels) && explicitLevels.length > 0) {
    return true;
  }

  // 3. Upstream parameter declarations (e.g. reasoning_effort, thinking, include_reasoning)
  const supportedParams = model.supported_parameters || model.parameters;
  if (Array.isArray(supportedParams)) {
    const pSet = new Set(supportedParams.map((p) => String(p).toLowerCase()));
    if (
      pSet.has("reasoning") ||
      pSet.has("include_reasoning") ||
      pSet.has("reasoning_effort") ||
      pSet.has("thinking") ||
      pSet.has("effort")
    ) {
      return true;
    }
  }

  // 4. Upstream modalities array / set
  const allModalities = [
    ...(Array.isArray(model.modalities) ? model.modalities : []),
    ...(Array.isArray(model.output_modalities) ? model.output_modalities : []),
    ...(Array.isArray(model.input_modalities) ? model.input_modalities : []),
  ].map((m) => String(m).toLowerCase());

  if (allModalities.includes("reasoning") || allModalities.includes("thinking")) {
    return true;
  }

  // 5. Upstream architecture instruct_type (e.g. OpenRouter "thinking", "reasoning", "cot")
  if (model.architecture) {
    const instructType = String(model.architecture.instruct_type || "").toLowerCase();
    const archMod = String(model.architecture.modality || "").toLowerCase();
    if (
      instructType.includes("thinking") ||
      instructType.includes("reasoning") ||
      instructType.includes("cot") ||
      archMod.includes("reasoning")
    ) {
      return true;
    }
  }

  // 6. Upstream tags / capabilities array or record
  if (Array.isArray(model.tags)) {
    const tagSet = new Set(model.tags.map((t) => String(t).toLowerCase()));
    if (
      tagSet.has("thinking") ||
      tagSet.has("reasoning") ||
      tagSet.has("cot") ||
      tagSet.has("deepseek-reasoner")
    ) {
      return true;
    }
  }
  if (Array.isArray(model.capabilities)) {
    const capSet = new Set(model.capabilities.map((c) => String(c).toLowerCase()));
    if (capSet.has("thinking") || capSet.has("reasoning") || capSet.has("cot")) {
      return true;
    }
  } else if (model.capabilities && typeof model.capabilities === "object") {
    if (model.capabilities.thinking || model.capabilities.reasoning) {
      return true;
    }
  }

  // 7. Heuristic fallback based on model ID & name
  const nameLower = (model.name || "").toLowerCase();
  const hasReasoningToken =
    /(?:^|[-_./\s])(o[134]|r1|qwq)(?:[-_./\s]|$)/i.test(mid) ||
    /(?:^|[-_./\s])(o[134]|r1|qwq)(?:[-_./\s]|$)/i.test(nameLower);

  return (
    hasReasoningToken ||
    mid.includes("thinking") ||
    mid.includes("reasoning") ||
    mid.includes("reasoner") ||
    mid.includes("claude-3-7") ||
    mid.includes("claude-3.7") ||
    mid.includes("claude-sonnet-4") ||
    mid.includes("claude-opus-4") ||
    mid.includes("claude-4") ||
    mid.includes("deepseek-r1") ||
    mid.includes("gemini-3.") ||
    mid.includes("gemini-2.5") ||
    mid.includes("gpt-5") ||
    nameLower.includes("thinking") ||
    nameLower.includes("reasoning")
  );
}

/**
 * Returns the default effort level for a given model.
 */
export function getDefaultEffortForModel(modelId: string): ReasoningEffortLevel {
  const lower = (modelId || "").toLowerCase();
  if (lower.includes("-high") || lower.includes("deepseek-r1") || lower.includes("o1") || lower.includes("o3")) {
    return "high";
  }
  if (lower.includes("-low")) {
    return "low";
  }
  if (lower.includes("-medium")) {
    return "medium";
  }
  return "medium";
}

export const TIER_SUFFIX_REGEX = /[-_:](low|medium|high|ultra|max|budget|thinking|thought|reasoning)(?::[a-z0-9_-]+)?$/i;

export function getBaseSlug(id: string): string {
  return id.replace(TIER_SUFFIX_REGEX, "");
}

/**
 * Retrieves the saved reasoning effort for a specific model from localStorage.
 */
export function getSavedReasoningEffortForModel(modelId: string): ReasoningEffortLevel {
  if (typeof window === "undefined" || !modelId) return "medium";
  try {
    const stored = localStorage.getItem("anara_model_reasoning_efforts");
    if (stored) {
      const map = JSON.parse(stored);
      if (map) {
        const base = getBaseSlug(modelId);
        if (map[modelId] && REASONING_LEVELS.includes(map[modelId])) {
          return map[modelId];
        }
        if (map[base] && REASONING_LEVELS.includes(map[base])) {
          return map[base];
        }
      }
    }
  } catch {}
  return getDefaultEffortForModel(modelId);
}

/**
 * Persists the reasoning effort for a specific model to localStorage.
 */
export function saveReasoningEffortForModel(modelId: string, level: ReasoningEffortLevel): void {
  if (typeof window === "undefined" || !modelId) return;
  try {
    const stored = localStorage.getItem("anara_model_reasoning_efforts");
    const map = stored ? JSON.parse(stored) : {};
    const base = getBaseSlug(modelId);
    map[modelId] = level;
    map[base] = level;
    localStorage.setItem("anara_model_reasoning_efforts", JSON.stringify(map));
    // Also save legacy single key for backwards compatibility
    localStorage.setItem("anara_reasoning_effort", level);
  } catch {}
}

/**
 * Prefix-tolerant model resolver that locates a model in a list even if
 * provider prefixes differ (e.g. 'ag/gemini-3.8-flash-high' vs '9router/ag/gemini-3.8-flash-high').
 */
export function findModelById(models: MinimalModelInfo[], targetId: string): MinimalModelInfo | undefined {
  if (!targetId || !models || models.length === 0) return undefined;
  const tLower = targetId.toLowerCase().trim();

  // 1. Direct ID match
  const direct = models.find((m) => m.id.toLowerCase() === tLower);
  if (direct) return direct;

  // 2. Prefix-tolerant match (strip leading namespace like '9router/' or 'openrouter/')
  const tClean = targetId.replace(/^[a-z0-9_-]+\//i, "").toLowerCase();
  const cleanMatch = models.find((m) => {
    const mLower = m.id.toLowerCase();
    const mClean = mLower.replace(/^[a-z0-9_-]+\//i, "").toLowerCase();
    return (
      mLower === tClean ||
      mClean === tLower ||
      mClean === tClean ||
      mLower.endsWith("/" + tLower) ||
      tLower.endsWith("/" + mLower)
    );
  });
  if (cleanMatch) return cleanMatch;

  // 3. Fallback to base slug match (e.g. without -high / -medium suffix)
  const tBase = getBaseSlug(targetId).toLowerCase();
  return models.find((m) => getBaseSlug(m.id).toLowerCase() === tBase);
}

/**
 * Resolves a sibling model ID when the active model belongs to a provider that
 * encodes reasoning levels into model slugs. (Deprecated: model is preserved decoupled from effort level).
 */
export function resolveSiblingTierModelId(
  activeModelId: string,
  _targetEffort: ReasoningEffortLevel,
  _allModels: MinimalModelInfo[]
): string {
  return activeModelId;
}
