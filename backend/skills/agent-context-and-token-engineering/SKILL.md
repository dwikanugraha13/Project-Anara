---
category: autonomous-ai-agents
name: agent-context-and-token-engineering
description: Use when designing prompt assembly and token budgeting.
---

# Agent Context & Token Engineering

Use this skill when designing, implementing, or auditing prompt assembly pipelines, LLM prefix caching boundaries, multi-tokenizer budgeting, and context window compaction algorithms in autonomous AI agent loops.

## Core Architectural Invariants

### 1. 3-Tier Prefix Caching Architecture
- Structure system prompts into three distinct tiers to maximize Anthropic, Gemini, and OpenAI prefix cache hits (>90% target):
  1. **Tier 1 — Stable Prefix:** Static persona identity (`SOUL.md`), operational mode boundaries, and immutable tool guidelines. These must remain byte-identical across all turns.
  2. **Tier 2 — Semi-Static Context:** Registered skills manifest, repository guidelines (`AGENTS.md` / `CLAUDE.md`), and pinned project structure.
  3. **Tier 3 — Volatile Tail:** Dynamic long-term memory updates (`USER.md` / `MEMORY.md`) and working memory / task scratchpad notes.
- **Pitfall:** Placing hyper-volatile components (e.g. scratchpads or live git diffs that mutate every turn) in the middle of the prompt invalidates the cache for all subsequent slots, causing re-tokenization at full non-cached rates on every turn.

### 2. Output Cap vs Context Limit Error Discrimination
- When learning context window limits dynamically from provider error strings (Anara `agent/model_metadata.py` parity):
  - Reject error messages mentioning generation caps (`output limit`, `output tokens`, `completion tokens`) when calculating total context window.
  - Only update context ceilings if the error explicitly references total context, model length (`max_model_len`), or context window limit.
- **Pitfall:** Parsing an error like "max_tokens exceeds model output limit of 4096 tokens" as a context window limit permanently crushes a 1M+ token model down to 4K tokens, triggering premature compaction and aborts.

### 3. Multilingual Token Calibration & Tool Call Accounting
- Count tokens across diverse message shapes, extracting payload data from:
  - OpenAI `tool_calls` arguments and function definitions.
  - Google Gemini `parts` (`function_call` args and `function_response` data).
  - Anthropic content block lists.
- Avoid naive character-length heuristics (`len/3.4`) for non-ASCII text; calibrate token counts for CJK, Cyrillic, and Arabic via dense unicode codepoints or byte estimations.
- **Pitfall:** Omitting tool call arguments leaves the token tracker blind to thousands of tokens of accumulated code and JSON parameters, while naive character heuristics undercount CJK text by up to 73%, causing sudden context overflow crashes.

### 4. Priority-Based Slot Truncation & Critical Slot Immutability
- When context window pressure forces prompt slot truncation:
  - Treat Core Identity, Operational Mode, and Tool Definition schemas as strictly immutable.
  - Prune dispensable context in reverse priority order (e.g. Project Context -> Skills Manifest -> Scratchpad -> Memory).
  - If still over budget, truncate degradable slots with newline-bounded head/tail preservation, never by blind reverse-popping.
- **Pitfall:** Unchecked `.pop()` on prompt slots deletes the Tool Definition slot, leaving the model instructed to call tools that have been wiped from its catalog.

### 5. Lossless Tool Pruning & Disk Spillover
- Never use unverified regex substitution (e.g. deleting all ` ``` ` fences) to compress tool results.
- Implement structured head/tail windowing snapped to line boundaries.
- Spill oversized tool outputs (>2,000 chars) to disk cache and provide an explicit retrieval pointer with line and byte offsets.
- **Pitfall:** Indiscriminate code-block wiping destroys essential test failure traces and compiler errors, while in-memory truncation without disk spillover leaves the agent with no recovery path.

### 6. Bounded Working Memory Scratchpads & ADR Tail Placement
- Always enforce strict item and character caps on dynamic task scratchpads and episodic architectural decision records (ADRs) injected into prompts (e.g. maximum 15 checklist steps, 8 findings, and 1,500 characters total).
- Working memory and recent decision records must sit strictly in Tier 3 (Volatile Tail), never in Tier 2 semi-static slots.
- **Pitfall:** Injecting unbudgeted task checklists or historical ADR logs into Tier 2 causes prompt expansion without upper bounds and evicts the KV cache across all subsequent prompt slots on every turn.

### 7. Runtime Session & Active Interface Grounding
- LLMs possess zero innate awareness of the physical interface, transport channel, or active database session ID they are executing within.
- In prompt assembly pipelines, always inject explicit runtime metadata into Tier 2 (Semi-Static Context):
  - Active Platform / Transport Channel (`cli`, `web`, `telegram`, `whatsapp`, `discord`)
  - Session Identifier and active user/speaker name
  - Working directory / physical root path
- Customize platform-specific interaction rules (e.g. instructing CLI sessions that they run in a plain terminal and must avoid unrendered HTML, while Web sessions can render markdown and visual components).
- **Pitfall:** Omitting runtime session metadata causes the model to guess its environment based on workspace file names (e.g. hallucinating that it is inside a web code editor because the project folder contains editor files) or embark on aggressive tool-calling sprees (querying databases or running shell commands) trying to discover its own session ID.

### 8. Dynamic Reasoning Effort & Monotonic Ladder Clamping
- When discovering and normalizing user/system requested reasoning effort against a model provider's allowed set (e.g. OpenAI `["low", "medium", "high"]`, Gemini `["off", "low", "medium", "high"]`, frontier Astra/Claude `["off", "low", "medium", "high", "max", "ultra"]`):
  - **Dynamic Protocol Handshake First:** Inspect upstream metadata first (`supported_parameters`, `reasoning_options`, `architecture.modality`, Ollama capabilities) before falling back to model name regex token discovery (`cot`, `thought`, `think`, `ultra`, `qwq`).
  - **Standard Canonical Ladder Membership:** Always verify membership against the canonical multi-tier ladder (`EFFORT_LADDER = ["none", "low", "medium", "high", "max", "ultra"]`) BEFORE querying an alias dictionary (`alias_map.get(clean, "none")`).
  - **Honest Ceilings ("Sama Aja Boong"):** Never expose fake options that exceed an upstream provider's API ceiling (e.g. Gemini API caps thinking budget at ~24K tokens setara `high`, while OpenAI o-series strictly accepts `"low" | "medium" | "high"`). Offering `max` or `ultra` on ceiling-bound models triggers upstream HTTP 400s or silent failures.
  - **Monotonic Step-Down Clamping:** When switching from a higher-tier frontier model (`ultra` / `max`) to a model with a lower ceiling, clamp the active effort level down to the target model's highest supported tier (`"high"`) and update storage immediately.
  - **Reasoning "Off" Semantics:** Explicitly support `off` / `none` (zero CoT, 0 thinking tokens, instant time-to-first-token direct generation, budget preservation).
- **Pitfall:** If standard ladder values (`max`, `high`, `ultra`) are omitted from the alias map and not checked against the ladder first, valid ladder requests not directly in the provider's allowed set fall back to `"none"` (index 0). This causes `"max"` to collapse to `"low"` instead of cleanly stepping down to `"high"`. Exposing fake `max`/`ultra` tiers on models capped at `high` produces deceptive UI and upstream API rejections.

### 9. Session Key Regex Anchoring & Injection Defense
- Always anchor canonical session key validation patterns to string terminators (`re.compile(r"^\d{8}_\d{6}_[a-f0-9]{6}\Z")`).
- **Pitfall:** Unanchored patterns (`^\d{8}_\d{6}_[a-f0-9]{6}`) allow path traversal payloads (`20260927_054512_a3f89b/../../evil`) and SQL injections (`..._AND_1=1`) to pass validation as legitimate session identifiers.

### 10. Hot-Reloading Configuration Discovery & Extension Flexibility
- When loading template configurations from disk without explicit extensions, check both `.yml` and `.yaml` candidates against physical disk existence before applying fallbacks.
- **Pitfall:** Hardcoding `.yaml` extension appending causes valid `.yml` files on disk to fail resolution, falling back to empty defaults.

- Clean Session Workspace Decoupling & CWD Truthfulness (Anara Parity)
- When assembling the environment and workspace context for a new or unattached chat session, never default the active directory or repository snapshot to the host agent's own codebase (e.g. `anara_agent.get_project_repo_root()`).
- In clean sessions where no project folder has been explicitly selected or attached by the user:
  - The working directory must ground truthfully in the User Home directory (`~`, e.g. `C:\Users\<user>`).
  - Suppress live git worktree status probes (`git diff`, `git branch`) and project file snapshots so the agent does not perceive the host repo as its active workspace.
  - Provide a list of recent project workspaces from session history (`Recent Project Workspaces: ...`), instructing the model that when asked about its location, it should state its current home directory and ask if the user wants to switch to one of their project folders or another directory.
- **Mode-Coupling Pitfall in Workspace Scoping:** Never tie workspace attachment to execution mode (e.g. `is_build_mode = mode in ("build", "code")`). If an IDE/code surface defaults to build mode, unattached new sessions will automatically hijack the agent's repository root, creating a discrepancy where conversational home chat stays at `~` but code studio opens in the agent's repo. Workspace attachment MUST strictly require an explicit custom folder flag (`is_custom_folder == True` or attached workspace handle), regardless of whether the session is in plan, build, or conversational mode.
- **Zero-Hardcoding Dynamic User Home Resolution:** Resolve user home dynamically across all operating systems via `os.path.expanduser('~')` (yielding `C:\Users\<user>` on Windows, `/home/<user>` on Linux, `/Users/<user>` on macOS). Never hardcode username strings or drive assumptions into prompts or backend path evaluators.
- **Conversational Workspace Inquiries vs Tool Runaway:** In operational guidelines, explicitly differentiate conversational questions about location/state ("where are you?", "what workspace is active?") from operational tasks. Instruct the model to answer location questions directly in prose from runtime context metadata without invoking filesystem inspection tools (`pwd`, `git status`) or workspace mutation tools (`switch_workspace`). Models given over-zealous "always verify with tools" instructions enter 10+ tool call loops and self-trigger workspace switches when asked casual questions.
