# Anara Model Normalization Architecture Reference

Extracted from Anara Agent desktop and CLI implementations (`apps/desktop/src/lib/model-status-label.ts` and `hermes_cli/auth_model_picker.py`).

## 1. Core Functions

```typescript
// Trailing model-id variants that render as a clean tag beside the name
export const VARIANT_TAGS: ReadonlyArray<readonly [RegExp, string]> = [
  [/-fast$/i, 'Fast'],
  [/-thinking$/i, 'Thinking'],
  [/-thought$/i, 'Thinking'],
  [/-high$/i, 'High'],
  [/-medium$/i, 'Medium'],
  [/-low$/i, 'Low'],
  [/-preview$/i, 'Preview'],
  [/-latest$/i, 'Latest']
];

export const titleCase = (text: string): string =>
  text.replace(/\b\w/g, char => char.toUpperCase()).trim();

// Vendors write their own names in casing the model id does not carry
export const VENDOR_CASING: ReadonlyArray<readonly [RegExp, string]> = [
  [/\bDeepseek\b/g, 'DeepSeek'],
  [/\bGlm\b/g, 'GLM'],
  [/\bMinimax\b/g, 'MiniMax'],
  [/\bOpenai\b/g, 'OpenAI'],
  [/\bErnie\b/g, 'ERNIE'],
  [/\bMimo\b/g, 'MiMo'],
  [/\bBge\b/g, 'BGE'],
  [/\bVl\b/g, 'VL'],
  [/\bIt\b/g, 'IT'],
  [/\bFp8\b/g, 'FP8'],
  [/\bAi\b/g, 'AI']
];

export const PARAMETER_COUNT = /\b(a?)(\d+(?:\.\d+)?)b\b/gi;

export const applyVendorCasing = (text: string): string => {
  let cased = text.replace(PARAMETER_COUNT, (_match, prefix: string, size: string) => `${prefix.toUpperCase()}${size}B`);
  for (const [pattern, replacement] of VENDOR_CASING) {
    cased = cased.replace(pattern, replacement);
  }
  return cased;
};

export function modelBaseId(model: string): string {
  const trimmed = model.trim();
  const slash = trimmed.lastIndexOf('/');
  return slash >= 0 ? trimmed.slice(slash + 1) : trimmed;
}

export function prettifyBase(base: string): string {
  // Normalize hyphenated versions between digits (e.g. 4-6 -> 4.6, 3-7 -> 3.7)
  const normalized = base.replace(/(\d)-(?=\d)/g, '$1.');

  if (/^deepseek-flash$/i.test(normalized)) {
    return 'DeepSeek V4.1 Flash';
  }

  if (/^claude-/i.test(normalized)) {
    return applyVendorCasing(
      titleCase(
        normalized
          .replace(/^claude-/i, 'Claude ')
          .replace(/-/g, ' ')
      )
    );
  }

  if (/^gpt-/i.test(normalized)) {
    return normalized.replace(/^gpt-/i, 'GPT-');
  }

  if (/^gemini-/i.test(normalized)) {
    return applyVendorCasing(titleCase(normalized.replace(/^gemini-/i, 'Gemini ').replace(/-/g, ' ')));
  }

  return applyVendorCasing(titleCase(normalized.replace(/-/g, ' ')));
}

export function modelDisplayParts(model: string): { name: string; tag: string } {
  let base = modelBaseId(model);
  let tag = '';

  base = base.replace(/\s*\([^)]*(?:proxy|custom|compatible)[^)]*\)/gi, '');
  base = base.replace(/:(?:batch|free)$/i, '');

  const quant = base.match(/-(?:UD-)?(Q\d(?:_[A-Z0-9]+)*|IQ\d(?:_[A-Z0-9]+)*|F16|BF16)$/i);
  if (quant) {
    tag = quant[1].split('_')[0].toUpperCase();
    base = base.slice(0, -quant[0].length);
    base = base.replace(/-(?:Instruct|Chat)(?:-\d{4})?$/i, '');
  }

  if (!tag) {
    for (const [pattern, label] of VARIANT_TAGS) {
      if (pattern.test(base)) {
        tag = label;
        base = base.replace(pattern, '');
        break;
      }
    }
  }

  const contextWindow = base.match(/\[(\d+[mk])\]$/i);
  if (contextWindow) {
    tag = tag ? `${tag} ${contextWindow[1].toUpperCase()}` : contextWindow[1].toUpperCase();
    base = base.slice(0, -contextWindow[0].length);
  }

  base = base.replace(/-\d{8}$/, '');
  return { name: prettifyBase(base) || model.trim() || 'No model', tag };
}

export function displayModelName(model: string): string {
  const { name, tag } = modelDisplayParts(model);
  return tag ? `${name} ${tag}` : name;
}
```

## 2. Key Takeaways
1. **Never parse by family regex trees**: Do not write `mClaude`, `mGemini`, `mDeepSeek` branches with hardcoded sub-match rules.
2. **Version dots (`(\d)-(?=\d)`)**: Hyphen-to-dot normalization is universally applied to any digit pair.
3. **Tagged Variants**: Reasoning tiers, speed variants, and preview tags are cleanly extracted into `tag` rather than mangling the root model name.
