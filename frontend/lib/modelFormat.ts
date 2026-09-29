/**
 * Project Anara Model Display Formatter
 * Transforms raw provider slugs & router paths into clean, human-readable studio model badges.
 * E.g. '9router/ag/gemini-3.8-flash-high' -> 'Gemini 3.8 Flash'
 *      'anthropic/claude-3-7-sonnet' -> 'Claude 3.7 Sonnet'
 *      'openai/gpt-4o' -> 'GPT-4o'
 */

function extractEffortSuffix(raw: string): string {
  const lower = raw.toLowerCase();
  if (lower.endsWith("-high") || lower.includes("-high-") || lower.includes("-high/")) return " (High)";
  if (lower.endsWith("-medium") || lower.includes("-medium-") || lower.includes("-medium/")) return " (Medium)";
  if (lower.endsWith("-low") || lower.includes("-low-") || lower.includes("-low/")) return " (Low)";
  if (lower.endsWith("-thinking") || lower.includes("-thinking-") || lower.includes("-thinking/")) return " (Thinking)";
  return "";
}

export function formatModelDisplayName(raw: string | undefined | null): string {
  if (!raw) return "Model AI";
  const lower = raw.toLowerCase();
  const effortSuffix = extractEffortSuffix(raw);

  // Gemini family
  if (lower.includes("gemini-3.8-flash")) return `Gemini 3.8 Flash${effortSuffix}`;
  if (lower.includes("gemini-3.5-flash")) return `Gemini 3.5 Flash${effortSuffix}`;
  if (lower.includes("gemini-2.5-flash")) return `Gemini 2.5 Flash${effortSuffix}`;
  if (lower.includes("gemini-2.5-pro")) return `Gemini 2.5 Pro${effortSuffix}`;
  if (lower.includes("gemini-3.1-flash-live")) return "Gemini 3.1 Live";
  if (lower.includes("gemini-2.0-flash")) return `Gemini 2.0 Flash${effortSuffix}`;
  if (lower.includes("gemini-1.5-pro")) return "Gemini 1.5 Pro";
  if (lower.includes("gemini-1.5-flash")) return "Gemini 1.5 Flash";

  // Anthropic Claude family
  if (lower.includes("claude-3-7-sonnet")) return `Claude 3.7 Sonnet${effortSuffix}`;
  if (lower.includes("claude-3-5-sonnet")) return `Claude 3.5 Sonnet${effortSuffix}`;
  if (lower.includes("claude-3-5-haiku")) return "Claude 3.5 Haiku";
  if (lower.includes("claude-3-opus")) return "Claude 3 Opus";

  // OpenAI family
  if (lower.includes("gpt-4o-mini")) return "GPT-4o Mini";
  if (lower.includes("gpt-4o")) return "GPT-4o";
  if (lower.includes("gpt-4.5")) return "GPT-4.5 Preview";
  if (lower.includes("o1-mini")) return "OpenAI o1-mini";
  if (lower.includes("o1-preview") || lower.includes("o1")) return `OpenAI o1${effortSuffix}`;
  if (lower.includes("o3-mini")) return `OpenAI o3-mini${effortSuffix}`;

  // DeepSeek family
  if (lower.includes("deepseek-r1")) return "DeepSeek R1";
  if (lower.includes("deepseek-v3") || lower.includes("deepseek-chat")) return "DeepSeek V3";

  // Meta Llama family
  if (lower.includes("llama-3.3-70b")) return "Llama 3.3 70B";
  if (lower.includes("llama-3.1-405b")) return "Llama 3.1 405B";
  if (lower.includes("llama-3.1-70b")) return "Llama 3.1 70B";
  if (lower.includes("llama-3.1-8b")) return "Llama 3.1 8B";

  // Qwen family
  if (lower.includes("qwen-2.5-coder")) return "Qwen 2.5 Coder";
  if (lower.includes("qwen-2.5-72b")) return "Qwen 2.5 72B";

  // Mistral family
  if (lower.includes("mistral-large")) return "Mistral Large";
  if (lower.includes("codestral")) return "Codestral";

  // Generic fallback: strip route prefixes
  const clean = raw.split("/").pop() || raw;
  return clean
    .split(/[-_.]/)
    .map((w) => (w.length <= 3 ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}
