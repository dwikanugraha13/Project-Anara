---
category: autonomous-ai-agents
name: agent-model-catalog-and-routing-engineering
description: Use when building model routing, catalogs, or aggregators.
---

# Agent Model Catalog and Routing Engineering

Use this skill when designing, building, or auditing AI agent model discovery, catalog organization, multi-provider routing aggregators (e.g. 9Router, LiteLLM, OpenRouter, and local proxies), and reasoning effort controls across CLI, web, and desktop interfaces.

## Core Architectural Invariants

### 1. Pure Verbatim Router Codenames vs Artificial Translation & Keyword Re-Bucketing
- **Pure Verbatim Codename Extraction:** When integrating custom model routers or AI gateway proxies (e.g. 9Router, LiteLLM, or multi-route endpoints) serving models with routing slugs (`ag/gemini-3.8-flash`, `cl/claude-3-7-sonnet`, `kr/deepseek-r1`, `cx/gpt-5.6-sol`, `yz/custom-model`), preserve the upstream router codename *verbatim* (`ag`, `cl`, `kr`, `cx`, `xkiro`, `yz`). Do not artificially translate raw codenames into expanded labels (e.g. mapping `ag` -> `Antigravity` or `cl` -> `Claudeflare`). Following Anara standard, keep the raw code pure as supplied by the gateway.
- **Strict Isolation from Keyword Re-Bucketing:** Never use model name substring inspection (e.g. searching `gemini`, `claude`, `gpt`) to re-bucket aggregator models into first-party vendor groups. If an obscure or custom provider `yz` serves a model named `yz/gemini-pro`, that model strictly belongs to sub-route `yz` under the proxy. Allowing model name keywords to re-bucket models into `Google` or `Anthropic` causes cross-provider contamination, routes requests to wrong credentials, and breaks routing transparency.
- **Prefix Path Parsing:** Parse route codenames directly from model slug segments:
  - If the slug is prefixed by gateway tags (e.g. `9router/<route>/<model>` or `custom/<route>/<model>`), extract segment index 1 as the raw router codename.
  - If the slug begins directly with a route code (e.g. `<route>/<model>`), extract segment index 0.
  - Automatically cluster any novel, unregistered codenames (e.g. `yz`, `nim`, `together`) into their own route without prior dictionary registration.
- **Fallback to Native Provider:** Only for standalone native providers without routing path segments, fall back cleanly to `model.provider` (Google, OpenAI, Anthropic, DeepSeek, Ollama) without keyword guessing.

### 2. Tier Variant Deduplication & Representative Consolidation
- **Consolidation by Route and Base Slug:** Multi-tier router proxies often expose separate model endpoints for reasoning depth (e.g. `gemini-3.8-flash-low`, `gemini-3.8-flash-medium`, `gemini-3.8-flash-high`, and base `gemini-3.8-flash`). Never dump all suffix variants into the catalog as duplicate rows with identical clean display names.
- **Representative Selection:** Group models by `(route, base_slug)` after stripping tier suffixes (`-low`, `-medium`, `-high`, `-thinking`, `-thought`, `-reasoning`). Select a single representative entry per group using priority ordering: base (no suffix) > high > medium > low > thinking.
- **Tier Count Surface:** Annotate consolidated entries with a compact tier badge (e.g. `4T`, `3T`) indicating that multiple reasoning levels are consolidated into that model entry.

### 3. Decoupled Reasoning Parameter vs Sibling Model Swapping Loop
- **Decoupled Reasoning Control:** Never require users to pick between separate `-low`, `-medium`, or `-high` models in the main catalog. Keep the model selector focused on model identity, and manage reasoning depth via a dedicated, adjacent `ReasoningPill`.
- **Anti-Model-Swapping Pitfall (The Bouncing Sibling Loop):** Do NOT swap or mutate the active model ID when the user clicks a reasoning tier in the pill. Sibling model swapping (`resolveSiblingTierModelId`) triggers catastrophic ping-pong loops: changing effort swaps the model, model selection re-reads saved presets for the new slug (which often default to medium), and immediately forces the reasoning effort back, causing selections like `High` to immediately revert to `Medium` or `Off`. Reasoning effort must be passed as an independent wire parameter (`reasoning_effort: "off" | "low" | "medium" | "high" | "max"`).
- **Prefix-Tolerant Model Resolver (`findModelById`):** When resolving capabilities for the active model from the catalog, never use naive exact match (`models.find(m => m.id === activeId) || models[0]`). If provider/router prefixes differ (`ag/...` vs `9router/ag/...`), exact matching fails and falls back to `models[0]`. If `models[0]` lacks reasoning, auto-clamp effects will falsely detect missing capabilities and forcibly revert the user's choice to Medium or Off. Use prefix-tolerant matching that strips namespace wrappers (`9router/`, `openrouter/`) and base slug comparisons before defaulting.
- **Streamlined Pill Typography (Zero Word Waste):** Display the active effort directly on the pill (`High`, `Medium`, `Low`, `Off`) without redundant prefixes like `Think: High`.
- **Sibling Family Effort State Binding (Base Slug Keying):** When persisting or retrieving reasoning effort per model, always normalize keys to the base slug (`getBaseSlug(modelId)` after stripping `-low`, `-medium`, `-high`, `-thinking`). Keying storage strictly to the current active sibling ID causes state desynchronization when switching (e.g. switching to `Off` lands on `base`, but subsequent switches to `High` save to `base` while the resolver swaps to the sibling `-high`, causing the newly active sibling to read stale defaults and flip the UI pill back).

### 4. Modality Detection & Surface Chips
- **Contract-Driven Capability Introspection:** Detect model modalities (`TXT`, `VISION`, `VIDEO`, `AUDIO`, `THINK`) through structured backend contracts (`supports_vision`, `supports_video`, `supports_audio`, `supports_reasoning`, `modalities: string[]`) and upstream protocol handshakes rather than naive name guessing.
- **Dynamic Upstream Schema Contracts (Dict vs List Capabilities):** Modern OpenAI/vLLM/aggregator proxies declare capabilities as a dictionary (`{"vision": true, "reasoning": true, "tools": true, "audioInput": false}`) rather than a list. Discovery routines must parse dictionary payloads directly (`caps.get("vision")`, `caps.get("image")`, `caps.get("imageInput")`) rather than checking only `isinstance(capabilities, list)` which silently drops upstream capability declarations. Also inspect `input_modalities` alongside `modalities`.
- **Generational Frontier Heuristics vs Version Hardcoding:** Fallback capability heuristics must use dynamic generational family regexes (`gpt-[4-9]`, `claude-[3-9]`, `gemini-[1-9]`, `qwen.*vl`) rather than frozen static version strings (e.g. `gpt-4o|gpt-5`). Frozen version lists immediately break on newer frontier releases (e.g. `gpt-6.1-sol`, `gpt-6-astra`, `gpt-7`), falsely claiming they lack vision or thinking.
- **Anti-"AI Slop" Visual Hygiene (Zero Colored Status Dots & Neon Badges):** Remove colored status dots (cyan, purple, emerald, zinc) from model rows and toolbar pill buttons. A professional engineering workspace relies on clean, high-density monochrome typography (`text-zinc-200`/`text-slate-300`, `border-white/[0.08]`, `bg-white/[0.03]`) and subtle muted micro-badges (`[REASON]`, `[FAST]`, `[IMG]`), avoiding colored glowing dots, neon borders, and emoji icons that create an amateur "AI slop" aesthetic.
- **Compact High-Density Model Popover Geometry:** Constrain model picker dropdowns to compact desktop widths (`w-72 sm:w-80` / `288px–320px`, max-h `400px–420px`) with single-line non-wrapping items (`h-7.5` / `30px`), streamlined search, and zero bloated double-deck filter carousels.
- **Clean Micro-Chips in Single-Row Layout:** Render modality micro-chips horizontally in single-row tabular model items (~32px height) alongside context window metrics (`1M`, `128K`). Expose primary visual indicators (`[IMG] [VID]`) on the active dock button so users know input capabilities before attaching files.

### 5. Ceiling-Aware Honest Reasoning Clamping
- **No False Options ("Sama Aja Boong"):** If an upstream API ceiling restricts reasoning tokens to `High` (e.g. Google Gemini API capping thinking budget at ~24K tokens; OpenAI o-series accepting only `low`, `medium`, `high`), do NOT render `Max` or `Ultra` options in the UI. Rendering unsupported options triggers HTTP 400 errors or deceives users.
- **Monotonic Downward Clamping:** When switching from an `Ultra` frontier model to a lower-ceiling model (e.g. Gemini), automatically clamp the active effort down to the target model's highest supported level (`High`) and synchronize storage immediately, preventing invalid state persistence.

### 6. Two-Tier Hierarchy Architecture (Configured Providers vs Pure Sub-Route Rails)
- **Top Tier (Configured Provider Origins):** Primary catalog navigation must strictly reflect user-configured provider boundaries: Official Providers (e.g. `Google AI Studio`, `OpenAI Codex`, `Anthropic Claude` authenticated via native keys or OAuth) versus Custom Aggregator Endpoints (e.g. `9Router Proxy`, `OpenRouter`, `Ollama` connected via custom base URLs). Never scatter models from a custom aggregator into arbitrary vendor buckets at the top level; selecting `9Router Proxy` must isolate all models routed through that proxy, while selecting `Google AI Studio` must isolate official first-party models without aggregator routing contamination.
- **Secondary Tier (Pure Sub-Route Filter Rails):** Within multi-route aggregators (e.g. 9Router serving `ag/`, `cl/`, `kr/`, `cx/`, `yz/`), surface a secondary sub-route filter rail (`Route: [all] [cl] [xkiro] [kr] [ag] [yz] ...`) derived dynamically from prefix segments. Keep the labels strictly verbatim to match the router's exact codename. Hide this rail when a native, non-aggregator provider is selected.
- **Unified All-Providers Sticky Sectioning:** When viewing `All Providers`, group models by provider origin with sticky section headers (`GOOGLE AI STUDIO (10)`, `9ROUTER PROXY (758)`), replicating Anara Desktop `model-picker.tsx` (`<CommandGroup heading={<ProviderHeading />} />`) for structured multi-account browsing.

### 7. Zero Static Hardcoding: Anara Universal Normalization Pipeline
- **Eliminate Hardcoded Model Catalogs & Family if-elses:** Never write static model dictionaries, hardcoded model lists, or sprawling family `if-else` / `switch` blocks (`mClaude`, `mGemini`, `mGpt`, `mDeepSeek`). New frontier, open-weights, and router models appear daily across hundreds of vendors. Static matching is brittle, immediately goes stale, drops minor releases, and creates false classifications.
- **Anara 5-Stage Universal Normalization Standard:**
  1. **Base Extraction (`modelBaseId`):** Strip proxy wrappers (`(9Router Proxy)`) and path prefixes via `model.slice(model.lastIndexOf('/') + 1)`.
  2. **Variant & Metadata Tag Slicing:** Extract variant suffixes (`-fast`, `-thinking`, `-thought`, `-high`, `-medium`, `-low`, `-preview`, `-latest`) into `tag` metadata (`VARIANT_TAGS`) instead of letting them corrupt the base name. Slice local quant suffixes (`Q4_K_M`, `BF16`), context windows (`[1m]` -> `1M`), and snapshot date-pins (`-20251101`).
  3. **Universal Version Dotting:** Normalize hyphenated digit versions (`(\d)-(?=\d)`) to dots (`$1.`). This turns `claude-opus-4-6` into `Opus 4.6`, `claude-3-7-sonnet` into `3.7 Sonnet`, and novel models like `future-ai-9-1` into `Future AI 9.1` without mangling parameter scales (`70b`, `32b`).
  4. **Dynamic Title-Casing:** Convert hyphens to spaces and apply functional word-level title casing (`titleCase`).
  5. **Whole-Word Vendor & Parameter Token Casing (`applyVendorCasing`):** Apply single-pass regex replacement for brand casing on whole words (`DeepSeek`, `GLM`, `MiniMax`, `OpenAI`, `ERNIE`, `MiMo`, `BGE`, `VL`, `IT`, `FP8`, `AI`) and format parameter scales via `\b(a?)(\d+(?:\.\d+)?)b\b` -> `${prefix.toUpperCase()}${size}B` (`8B`, `70B`, `120B`).
- **Reference Implementation:** See `references/anara-model-status-normalization.md` for the complete standalone TypeScript source implementation extracted from `apps/desktop/src/lib/model-status-label.ts`.

### 8. "Off" / "None" Reasoning Semantics & Multi-Provider Wire Protocol
- **Anara Standard Effort Ladder:** Include `none` (rendered as `Off` in the UI) at the base of the effort ladder (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`). Reasoning is enabled unless explicitly turned `off`.
- **Provider Wire Dispatches for "Off":**
  - **Google Gemini:** Emit `thinking_config: {"thinking_budget": 0}`. Simply omitting thinking config or passing `includeThoughts: false` only hides thoughts from the response; Gemini still reasons internally and charges thought tokens against `max_output_tokens`. A budget of `0` is strictly required to disable reasoning on Gemini 2.5 and 3+.
  - **Anthropic Claude:** Omit the `thinking` block or send `{"thinking": {"type": "disabled"}}`.
  - **OpenAI / Codex:** Omit `reasoning_effort` or emit `{"reasoning": {"effort": "none"}}`.
  - **Router Multi-Tier Endpoints (e.g. 9Router):** Sibling resolver swaps the model endpoint back to the root base slug without reasoning suffix (e.g. `ag/gemini-3.8-flash-high` -> `ag/gemini-3.8-flash`).

### 9. Runtime System Prompt Grounding Parity for Reasoning Effort
- **Thread Active Effort to Prompt Assembler:** When the user changes reasoning effort in the UI dock (e.g. setting it to `Off`), that state must flow through the WebSocket/API request directly into `PromptAssembler.assemble(..., reasoning_effort=...)`.
- **Grounding Block Injection (`[ACTIVE MODEL & RUNTIME GROUNDING]`):** The prompt assembler must inject both the resolved clean model name and the exact reasoning tier (`tier_display`):
  - When `reasoning_effort` is `"off"` or `"none"`, display explicitly: `Off (Thinking Disabled / Standard Generation)`.
  - Explicitly instruct the model: *"If Reasoning Level is 'Off', you must accurately state that thinking is disabled / turned off. Never claim to be running on Standard or Medium when thinking is Off."*
- **Pitfall (State Hallucination):** If `reasoning_effort` is omitted from prompt assembly, the prompt assembler inspects only the model slug. For a base model slug without tier suffixes (like `ag/gemini-3.8-flash`), the assembler defaults to `Standard`, causing the agent to hallucinate that thinking is active at "Standard/Medium" even though thinking was turned Off at the wire level.
