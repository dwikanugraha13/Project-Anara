---
category: autonomous-ai-agents
name: agent-composer-and-approval-engineering
description: Use when building composer queues and approval gates.
---

# Agent Composer, Queueing & Interactive Approval Engineering

Use this skill when designing, building, or auditing AI agent input composers, sequential prompt queues, mid-turn steering protocols, tool run tickers, and interactive human-in-the-loop approval gates.

## Core Architectural Invariants

### 1. Sequential Prompt Queue & Auto-Drain (Anti-Drop Concurrency)
- **Prompt Queueing During Active Execution:** Never disable or freeze the prompt input while the model is executing tools or streaming responses (`if (isBusy) return;` anti-pattern). When the user sends a prompt while busy, enqueue the prompt into an active session queue (`useComposerQueue`). Render a subtle hairline status strip above the composer (`Antrean Turn (N): ...`) with a quick cancel action.
- **Auto-Drain Transition Engine:** Monitor the agent's execution status. When the agent transitions from `busy -> idle`, automatically claim the drain lock and dispatch the next queued prompt with a brief settling timeout (~120ms).
- **Mid-Turn Redirection Protocol:** If the submitted text begins with a steering directive (e.g. `/steer <instruction>`), bypass the queue and dispatch an immediate out-of-band `steer` event to the active session runner to course-correct the running model mid-turn.

### 2. Tool Run Ticker & Single-Line Activity Reel
- **Sliding Reel vs Transcript Vertical Bloat:** In complex agent turns involving multiple tool invocations, rendering large standalone cards for each tool consumes hundreds of vertical pixels. Provide a single-line 24–26px activity reel (`ToolRunTicker`).
- **In-Place Reel Sliding:** Each new tool invocation slides smoothly into the single-line window with an active cyan status pulse, ticking in place while preserving an audit step counter (`N steps`). Full output and diff inspectors remain accessible via click disclosure.

### 3. Conversational Gate Approval (3-Scope: Once / Session / Deny)
- **Granular Approval Scopes:** When sensitive tools (shell commands, file modifications, system reboots) require user consent, present an interactive Liquid Glass approval card (`InteractiveApprovalCard`) offering three distinct scopes:
  - `Approve Once`: Authorizes only the single targeted execution.
  - `Allow for Session`: Grants continuous authorization for that specific tool pattern within the active conversation.
  - `Reject / Cancel`: Halts the execution safely without crashing the agent loop.
- **Contextual Preview & Risk Tiers:** Display a clear risk badge (`low`, `medium`, `high`, `critical`), human-readable rationale, and syntax-highlighted command/payload preview (`$ tool command`).

### 4. In-Place User Prompt Editing & Rerun
- **Hover Action Toolbar:** Render a quiet action toolbar on user message bubbles (`group-hover`) featuring `Copy` and `Edit` (pencil icon).
- **Inline Fluid Editor:** Clicking `Edit` replaces the user bubble in-place with an auto-focused Liquid Glass textarea editor.
- **Keyboard Ergonomics:** Support `Esc` to cancel editing and `Ctrl+Enter` (or `Cmd+Enter`) to save and immediately re-run the conversation from that turn forward without losing context.

### 5. Crash-Survivable In-Flight Turn Journaling & Draft Stashing
- **Storage-Backed Turn Snapshots:** Persist in-flight turn state (`sessionId`, `userPrompt`, `streamingText`, `liveToolProgress`, `activeTools`) into client storage (`sessionStorage`), throttling updates (300–400ms).
- **Live In-Flight Folding:** On session switch or cross-client attachment, fold the journaled state onto restored transcript bubbles (`mergeInFlightWithTranscript`) and display active thinking/tool indicators immediately.
- **Session-Scoped Draft Stashing:** Stash unsent draft text per session ID (`composer_draft_<sessionId>`) upon session change and restore it when returning to that session. Delete the stashed draft strictly upon form submission.
- **Blob Object URL Revocation:** Whenever attachments are removed, submitted, or discarded, immediately call `URL.revokeObjectURL(url)` on all `blob:` URLs to prevent multi-megabyte image leaks in browser V8 heap memory.

### 6. Render Payload Clamping & V8 Heap Protection (`MAX_TOOL_RENDER_CHARS`)
- **Anti-DOM Freeze Truncation:** When tools output large terminal transcripts, log files, or code searches (100KB–500KB+), rendering raw text blocks directly in React DOM freezes the layout thread and triggers V8 Out-Of-Memory (`SIGABRT`) tab crashes. Always clamp inline-rendered payloads to a bounded threshold (`MAX_TOOL_RENDER_CHARS = 20_000`).
- **Omission Annotation with Full-Payload Copy:** When clamping, append an explicit notice: `\n\n… [X characters truncated for render performance — use Copy button for complete output]`. The card's Copy button must access the un-truncated full payload in memory so developers never lose raw diagnostic output.

### 7. Multi-Step Turn Run Summary & Metric Synthesis
- **Grammatical Turn Synthesis:** Rather than leaving dozens of scattered individual tool pills in the chat, synthesize finished multi-tool runs into a single grammatical clause row: `Edited 2 files · Ran 3 commands · Explored 4 files (2.4s) · 1,420 tokens`.
- **Integrated Execution Metrics:** Pair the synthesized summary with precise elapsed duration, active model name, and token usage counts in a compact, single-line Liquid Glass hairline container (`RunSummaryCard`).

### 8. Cross-Socket Gateway Event Deduplication (LRU Sliding Window Anti-Stutter)
- **Multi-Socket Fan-Out Duplicate Floods:** When client apps hold multiple sockets to an agent gateway (e.g. secondary background socket alongside primary during reconnect, or split dual panes), the backend joins every socket to that chat's transport fan-out. Every incoming event (`message.delta`, `message.interim`, `tool_progress`) arrives twice within milliseconds.
- **LRU Sequence Deduplication Window (30s):** Place an LRU sequence deduplicator (`createGatewayEventDedupe`) at the gateway ingress before events reach state stores. Enforce a 30-second sliding time window (`DUPLICATE_WINDOW_MS = 30_000`), bounded by max sequences per session (`2048`) and max sessions (`256`).
- **Keying & Dropping Contract:** Key events by `(session_id, seq)` or event ID. If an incoming frame has been seen within the duplicate window, `admit` returns `false` and drops the frame immediately. Events without sequence numbers pass unconditionally.
- **Pitfall:** Omitting client-side sequence deduplication causes streaming token text to double-print and interim messages to seal duplicate chat bubbles upon rapid reconnects or multi-pane views.

### 9. Active Turn Liveness Watchdog & Active Keepalive Probing
- **Silent Half-Open TCP Disconnects:** Long-running model generations often produce silence intervals exceeding 30-40 seconds. Reverse proxies, NAT firewalls, and tunnels frequently drop idle TCP connections silently without emitting FIN packets.
- **Dynamic Watchdog Arming (45s-65s):** Whenever the agent enters an active turn (`thinking`, `running tool`, `transcript_partial`), arm a client-side liveness watchdog timer. Reset the timer on any inbound socket frame.
- **Active Keepalive Probe:** If no inbound frame arrives within the timeout window, dispatch an active ping frame (`{"type": "ping", "watchdog": true, "timestamp": Date.now()}`) to probe backend liveness and wake the connection.
- **Clean Disarming:** Disarm and clear the watchdog timer immediately upon receiving terminal turn events (`turn_complete`, `interrupted`) to prevent spurious pings during natural idle periods.
- **Pitfall:** Relying solely on passive ping intervals without active turn watchdogging leaves users waiting indefinitely when upstream LLM connections drop silently mid-turn.

### 10. Canonical Approval Taxonomy & Composer Dock Controls Cluster
- **Canonical Three-Tier Taxonomy (Plan / Auto / Off):**
  - `plan` (formerly *Manual*, Warm Amber `amber-400`/`amber-500/10`): Intercepts all mutating workspace actions and system commands (`mutating` and `ask` risk tiers) to enforce a two-phase workflow. The agent explores and reads codebase files autonomously, formulates a structured execution plan, and pauses for human sign-off before modifying any files or running mutating shell commands.
  - `auto` (formerly *Smart*, Sky Blue `sky-400`/`sky-500/10`, Default): Full autonomous engineering with continuous AI safety evaluation. Routine coding tools (reading files, AST search, workspace file writes/edits, running test suites and compilers) execute autonomously without confirmation prompts. The agent loop pauses strictly for high-risk / destructive actions (`ask` tier: mass file wipes `rm -rf`, git history rewrites, database drops, system registry tampering).
  - `off` (Bypass Permissions / YOLO, Rose Red `rose-400`/`rose-500/10`): Fully autonomous execution without human approval prompts, except for hardline sandbox security violations (system root destruction, unrecoverable database erasure) which are permanently blocked by security sentinels.
- **Scope Boundaries & Prevention of Approval Fatigue (Files vs Terminal Commands):**
  - In `auto` mode, standard workspace file operations (`write_file`, `patch`, `edit_file`) MUST run autonomously without gating. Tying file creation to approval prompts in `auto` mode triggers severe "approval fatigue" and destroys the autonomous agent workflow. File changes in code workspaces are easily reversible via version control checkpoints.
  - Conversely, terminal commands (`terminal`, `bash`, `cmd`) have uncontained side effects outside git trees and must be guarded by dynamic risk evaluation.
  - In `plan` mode, both file modifications and mutating terminal commands are held until the user approves the proposed plan.
- **Client-Side State Normalization & Mode Forwarding:**
  - Both frontend dispatchers (`HomePageClient`, `CodePageClient`) and backend routers must normalize modes using `normalizeApprovalMode()`.
  - Never pass hardcoded fallbacks (`onSend(text, mode || "build")`). If the user submits a prompt in `plan` mode, hardcoding `"build"` overrides their setting and forces autonomous execution.
  - Stored modes in client storage (`localStorage.getItem("anara_approval_mode")`) and backend configuration (`config.yaml` under `approvals.mode`) must strictly normalize to the canonical trio `plan`, `auto`, or `off`.
- **Inner Loop Single-Token Purity (Anti-Tuple Clutter):**
  - Normalize approval modes strictly at the ingress boundaries (API endpoints, CLI argument parsing, WebSocket consumer).
  - The inner execution loops (`agent_loops.py`, `runner.py`, `approval_guard.py`) must evaluate single canonical literals (`mode == "auto"`, `mode == "plan"`, `mode == "off"`).
  - Avoid defensive multi-alias tuples in core loop checks (`if mode in ("auto", "smart"): ... elif mode in ("plan", "manual"): ...`) — internal fragmentation causes maintenance rot, divergent logic paths, and telemetry confusion.
- **Scope Gating & Fatigue Prevention (Files vs Terminal Commands):**
  - In `auto` mode, standard workspace file modifications (`write_file`, `patch`, `edit_file`) MUST run autonomously without interactive confirmation cards. Gating file writes in `auto` mode causes severe developer approval fatigue. Code edits remain protected by VCS history and git worktree checkpoints.
  - Interactive approval prompts are strictly reserved for uncontained commands (destructive shell operations, irreversible filesystem wipes, system tampering).
  - In `plan` mode, both file modifications and mutating shell commands are withheld until the proposed execution plan receives human sign-off.
- **Composer Dock Integration (Anti-Statusbar Clutter & Anti-"AI Slop" Typography):**
  - Do NOT place approval mode selectors in a separate, screen-hogging bottom statusbar that inflates dead space and creates vertical bloat.
  - Mount a dedicated `ApprovalModePill` directly inside the composer dock's controls cluster alongside Model and Reasoning selectors (`[ + ] ... [ Model ▾ ] [ High ▾ ] [ Auto ▾ ] [ Send ]`).
  - **Anti-"AI Slop" Visual Hygiene & Popover Minimalism:**
    - **Resting Dock Controls:** Strictly avoid raw emojis, colored glowing status dots (cyan/purple/zinc), and neon-tinted container backgrounds on resting toolbar pill buttons. Professional developer workbenches rely on clean, neutral monochrome typography (`bg-white/[0.03] border-white/[0.08] text-zinc-300 hover:text-white font-mono`). Avoid decorative icons (shields, lightning bolts, sparkles) on resting dock buttons.
    - **Popover Menu Hygiene:** In the expanded approval mode popover, eliminate decorative mode icons (shields, sparkles, lightning bolts) and loud yellow/green header tags. Present clean, left-aligned typography (bold title + clear description) with a quiet, neutral silver/white checkmark (`text-zinc-200`) on the active item, and a neutral header badge (`text-slate-300 bg-white/[0.05] border-white/[0.08]`).
  - The popover anchors cleanly directly above the pill (`absolute bottom-9 left-0 z-50 w-72`), opening upon click and closing on outside click / escape.
  - This keeps all prompt dispatch parameters unified at the point of entry and frees the bottom viewport completely.
- **Backward-Compatible Alias Handshake:**
  - Runtime routers and command hubs must seamlessly normalize legacy tokens (`manual -> plan`, `smart -> auto`) across configuration files (`config.yaml`), CLI commands (`/approvals [plan|auto|off]`), and REST endpoints (`/api/approvals/mode`), guaranteeing zero breaking changes across existing automation scripts.
- **Persistent Statusbar Control & Bi-Directional Synchronization:**
  - Expose an interactive statusbar button with a dynamic mode icon (e.g. Zap glyph) and active mode label (`Plan`, `Auto`, `Off`).
  - Clicking opens a Liquid Glass popover menu displaying the 3 tiers with clear, human-centric descriptions ("Analyze codebase and plan before executing actions", "Automatically assess actions and ask when needed", "Run without approval prompts") and an active checkmark.
  - Changes must persist bi-directionally across client storage (`localStorage`) and backend configuration (`config.yaml` under `approvals.mode`) via dedicated REST endpoints (`/api/approvals/mode`), ensuring immediate enforcement across all channels without restarting the daemon.
- **Frontend Input Mode Override Trap (`mode || "build"` Anti-Pattern):** In UI chat input docks and composer wrappers, never pass a hardcoded fallback (`onSend(text, mode || "build")`). When the user sends a routine prompt without an explicit mode override, passing `"build"` overrides the user's manual/plan approval setting, forcing the backend runner into autonomous execution and bypassing human approval gates. Always let the mode resolve from the active approval mode (`activeApproval === "manual" ? "plan" : "build"`) and pass `approval_mode` explicitly in the WebSocket payload (`text_input`).
- **Cross-Port API Rewrites & Direct Backend Resolution:** In Next.js/React architectures, bare `fetch("/api/approvals/mode")` calls route to the frontend port (e.g. 3000), which returns 404 if Next.js does not configure `rewrites()`. Always configure Next.js `rewrites()` for `/api/:path*` to the backend port, and have client statusbar components resolve the backend URL explicitly via `getBackendUrl()` to prevent silent 404 drops that leave approval mode unsynchronized.
- **Static File Exclusions from Verification Stop-Gates:** Static markup and styling files (`.html`, `.htm`, `.css`, `.scss`, `.json`, `.yaml`) must be excluded from automated verification stop-gates. Enforcing project test suite execution on static file edits or within ephemeral workspaces lacking test runners causes agents to hallucinate robotic verification reports and attempt failing `pytest` commands.
- **Pitfall:** Hardcoding approval prompts or tying approval solely to binary plan modes prevents users from toggling autonomy levels on the fly, either overwhelming them with confirmations for safe reads or blocking hands-free autonomous workflows.

## Diagnostic Audit Checklist

1. **Prompt Queue & Auto-Drain:** When the user enters a prompt while the model is busy, does it queue smoothly rather than getting dropped or blocked, auto-draining sequentially upon return to idle?
2. **Mid-Turn Steering:** Does submitting with `/steer` dispatch an immediate out-of-band redirection event to course-correct the running model without aborting the turn?
3. **Tool Run Ticker:** Do sequential tool executions slide in-place inside a single-line 24-26px activity reel rather than stacking vertically and blowing out transcript height?
4. **Granular Gate Approvals:** Does the approval card offer 3 explicit scopes (Approve Once, Allow for Session, Reject) with risk badges and command payload previews?
5. **In-Place Prompt Editing:** Can the user edit earlier prompts in-place with `Ctrl+Enter` re-run and `Esc` cancel without losing conversation context?
6. **In-Flight Turn Journaling:** Does switching sessions during active generation fold in-flight execution state from storage without displaying a blank frozen screen?
7. **Draft Stashing & Memory Safety:** Are uncommitted drafts preserved across session switching, and are preview blob URLs immediately revoked upon submission or removal?
8. **Render Payload Clamping:** Are large tool stdout and diff payloads clamped at 20,000 characters with an omission note to prevent DOM freezing, while preserving full clipboard copy?
9. **Turn Run Summary:** Are multi-step tool executions synthesized into a single grammatical summary line with duration, model, and token metrics?
10. **Gateway Event Deduplication:** Are incoming socket events filtered through an LRU sequence deduplicator with a 30s sliding window to prevent stuttering and duplicate bubbles?
11. **Active Turn Liveness Watchdog:** Is the WebSocket protected by an activity watchdog (45s–65s) armed during active generation and disarmed on turn completion?
12. **Canonical Approval Policy Matrix:** Does the statusbar and composer dock provide a selector to switch between Plan (Amber), Auto (Sky Blue), and Off (Rose Red) modes, persisting across backend config.yaml and localStorage with immediate enforcement across runtime tool interceptors?
13. **Scope Gating & Fatigue Prevention:** Does `auto` mode execute workspace file writes autonomously without prompts while reserving gating for destructive terminal commands? Does client prompt dispatch normalize approval modes without hardcoded `"build"` overrides?
