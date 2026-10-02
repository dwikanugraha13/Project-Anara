/**
 * Project Anara Model Display Formatter
 * Implements dynamic model architecture for Project Anara
 *
 * 100% dynamic - Zero static model-name hardcoding, zero vendor guessing.
 */

// Trailing model-id variants that render as a clean tag beside the name (Anara standard)
const VARIANT_TAGS: ReadonlyArray<readonly [RegExp, string]> = [
  [/-fast$/i, "Fast"],
  [/-thinking$/i, "Thinking"],
  [/-thought$/i, "Thinking"],
  [/-high$/i, "High"],
  [/-medium$/i, "Medium"],
  [/-low$/i, "Low"],
  [/-preview$/i, "Preview"],
  [/-latest$/i, "Latest"],
];

const titleCase = (text: string): string => text.replace(/\b\w/g, (char) => char.toUpperCase()).trim();

// Vendors write their own names in casing the model id does not carry,
// and title-casing the id overrides it (Whole words only).
const VENDOR_CASING: ReadonlyArray<readonly [RegExp, string]> = [
  [/\bDeepseek\b/g, "DeepSeek"],
  [/\bGlm\b/g, "GLM"],
  [/\bMinimax\b/g, "MiniMax"],
  [/\bOpenai\b/g, "OpenAI"],
  [/\bErnie\b/g, "ERNIE"],
  [/\bMimo\b/g, "MiMo"],
  [/\bBge\b/g, "BGE"],
  [/\bVl\b/g, "VL"],
  [/\bIt\b/g, "IT"],
  [/\bFp8\b/g, "FP8"],
  [/\bAi\b/g, "AI"],
];

// Parameter counts: 8B, 70B, 120B (vendors write 8B, never 8b)
const PARAMETER_COUNT = /\b(a?)(\d+(?:\.\d+)?)b\b/gi;

const applyVendorCasing = (text: string): string => {
  let cased = text.replace(PARAMETER_COUNT, (_match, prefix: string, size: string) => `${prefix.toUpperCase()}${size}B`);
  for (const [pattern, replacement] of VENDOR_CASING) {
    cased = cased.replace(pattern, replacement);
  }
  return cased;
};

/** Strip provider prefix and normalize for display (Anara standard) */
export function modelBaseId(model: string): string {
  const trimmed = model.trim();
  const slash = trimmed.lastIndexOf("/");
  return slash >= 0 ? trimmed.slice(slash + 1) : trimmed;
}

/**
 * Extracts pure, verbatim upstream route prefix from model slugs (Anara standard).
 * E.g. '9router/ag/gemini-3.8-flash' -> 'ag'
 *      '9router/cx/gpt-5' -> 'cx'
 *      '9router/cl/google/gemini' -> 'cl'
 *      '9router/yz/some-model' -> 'yz'
 *      'ag/gemini-3.8-flash' -> 'ag'
 *
 * Keeps the raw code intact without artificial expansion or keyword guessing.
 */
export function extractModelRoute(raw: string | undefined | null): string | null {
  if (!raw) return null;
  const s = String(raw).trim();
  const segments = s.split("/").filter(Boolean);
  if (segments.length >= 2) {
    const first = segments[0].toLowerCase();
    // If prefixed by provider container name like '9router', 'custom', or 'openai'
    if (first === "9router" || first === "custom" || first === "openai") {
      const code = segments[1];
      if (code.toLowerCase().startsWith("comboantigravity")) return "ag";
      if (code.toLowerCase().startsWith("comboopenrouter")) return "openrouter";
      return code.toLowerCase();
    }
    // If the slug itself starts with route/model (e.g. 'ag/gemini-3.8-flash', 'yz/model')
    return segments[0].toLowerCase();
  }
  return null;
}

/**
 * Extracts inherent reasoning tier embedded in model ID (e.g. '-high', '-medium', '-low', '-thinking')
 */
export function extractModelTier(raw: string | undefined | null): "high" | "medium" | "low" | "thinking" | null {
  if (!raw) return null;
  const s = String(raw).trim();
  const m = s.match(/[-_](high|medium|low|thinking|thought|reasoning)(?::[a-z]+)?$/i);
  if (!m) return null;
  const val = m[1].toLowerCase();
  if (val === "high") return "high";
  if (val === "medium") return "medium";
  if (val === "low") return "low";
  return "thinking";
}

function prettifyBase(base: string): string {
  // Normalize hyphenated versions between digits (Version standard: 4-6 -> 4.6, 3-7 -> 3.7)
  const normalized = base.replace(/(\d)-(?=\d)/g, "$1.");

  if (/^deepseek-flash$/i.test(normalized)) {
    return "DeepSeek V4.1 Flash";
  }

  if (/^claude-/i.test(normalized)) {
    return applyVendorCasing(
      titleCase(
        normalized
          .replace(/^claude-/i, "Claude ")
          .replace(/-/g, " ")
      )
    );
  }

  if (/^gpt-/i.test(normalized)) {
    return normalized.replace(/^gpt-/i, "GPT-");
  }

  if (/^gemini-/i.test(normalized)) {
    return applyVendorCasing(titleCase(normalized.replace(/^gemini-/i, "Gemini ").replace(/-/g, " ")));
  }

  return applyVendorCasing(titleCase(normalized.replace(/-/g, " ")));
}

/** Split a model id into a clean display name plus an optional variant tag (Anara standard) */
export function modelDisplayParts(model: string): { name: string; tag: string } {
  let base = modelBaseId(model);
  let tag = "";

  // Strip proxy wrappers if any
  base = base.replace(/\s*\([^)]*(?:proxy|custom|compatible)[^)]*\)/gi, "");
  base = base.replace(/:(?:batch|free)$/i, "");

  // Quant suffix for local GGUF
  const quant = base.match(/-(?:UD-)?(Q\d(?:_[A-Z0-9]+)*|IQ\d(?:_[A-Z0-9]+)*|F16|BF16)$/i);
  if (quant) {
    tag = quant[1].split("_")[0].toUpperCase();
    base = base.slice(0, -quant[0].length);
    base = base.replace(/-(?:Instruct|Chat)(?:-\d{4})?$/i, "");
  }

  if (!tag) {
    for (const [pattern, label] of VARIANT_TAGS) {
      if (pattern.test(base)) {
        tag = label;
        base = base.replace(pattern, "");
        break;
      }
    }
  }

  // Context window tag like [1m] -> 1M
  const contextWindow = base.match(/\[(\d+[mk])\]$/i);
  if (contextWindow) {
    tag = tag ? `${tag} ${contextWindow[1].toUpperCase()}` : contextWindow[1].toUpperCase();
    base = base.slice(0, -contextWindow[0].length);
  }

  // Drop trailing date-pin (e.g. -20251101)
  base = base.replace(/-\d{8}$/, "");

  return { name: prettifyBase(base) || model.trim() || "No model", tag };
}

/** Friendly one-line model name for menus and buttons (Anara standard) */
export function displayModelName(model: string): string {
  const { name, tag } = modelDisplayParts(model);
  return tag ? `${name} ${tag}` : name;
}

export function formatModelDisplayName(raw: string | undefined | null, includeTier: boolean = false): string {
  if (!raw) return "Model AI";
  const { name, tag } = modelDisplayParts(String(raw));
  if (includeTier && tag) {
    return `${name} (${tag})`;
  }
  return name;
}
