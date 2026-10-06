---
category: autonomous-ai-agents
name: agent-desktop-operations-and-governance
description: Use when building agent command centers, cron, or MCP.
---

# Agent Desktop Operations, Governance & Extension Engineering

Use this skill when designing, building, or auditing AI agent administrative command centers, OS-level quick-entry capture, wall-clock cron schedulers, Model Context Protocol (MCP) subprocess security, universal session routing, and cross-session artifact libraries.

## Core Architectural Invariants

### 1. Unified Command Center & Selective Store Slices
- **Four-Pillar Operational Layout:** Structure the agent administrative command center into four distinct domains:
  1. *Sessions:* Paginated session search, pin/unpin, JSON/Markdown export, and delete confirmations.
  2. *System:* Gateway status, multiplexer restart, version info, and multi-file live log tailing (`agent`, `gateway`, `errors`) with level filters (`ALL`, `INFO`, `WARNING`, `ERROR`).
  3. *Usage:* 7/30/90-day token analytics, stacked input/output daily bar chart, and top model/skill distribution.
  4. *Maintenance:* Diagnostic controls for Doctor checks, Security Audits, Backups, Debug Share links, Curator daemon toggles, and Memory resets.
- **Selective Store Subscriptions (Token Streaming Shield):** Active model streaming updates conversation stores on every token. Never subscribe inactive command center tabs to global session stores. Use selector slices (e.g. `useStoreSelector($sessions, s => (section === 'sessions' ? s : EMPTY_SESSIONS))`) so streaming tokens do not trigger costly re-renders in System, Usage, or Maintenance panels.

### 2. Quick Entry Mini-Composer & Zero-Loss Prompt State Machine
- **Zero-Gateway Transparent Shell:** Implement OS-level quick prompt entry as a dedicated frameless transparent window (`?win=quick`) carrying NO direct gateway connection. The primary window pushes connectivity state (`connected`, `sessions`) via main-process IPC, and submissions relay through the primary window's submission pipeline.
- **Zero-Loss State Machine (`quickComposerReducer`):** Protect user prompts with strict reducer invariants:
  - *Empty Submit Guard:* Strip empty strings; pressing Enter on blank input must never dismiss or submit.
  - *Offline Guard:* Disable submission and preserve text buffer when the backend gateway is disconnected.
  - *Timeout Disambiguation:* If an IPC relay times out, mark state as `submit-unknown` rather than dropping the text, preventing accidental double-submits while preserving the draft.
  - *Orphaned Failure Restoration:* If a relayed submission fails after the quick window was dismissed, restore `orphanedFailure.text` upon the next summon so user prompts are never lost.

### 3. Wall-Clock 5-Field Cron Scheduling & Trust Enforcement
- **Wall-Clock Anchoring vs Interval Seconds Flattening:** Store 5-field cron expressions explicitly (`cron_expr TEXT`) across database schemas and task runners. Never flatten a standard cron expression (e.g. `"0 9 * * *"`) into a static interval (e.g. `86400s`) or calculate next-run from task creation time. Evaluate next-run timestamps using `croniter.croniter(cron_expr, now).get_next(datetime)` anchored to local wall-clock time so jobs fire at the exact expected hour across restarts.
- **Trust-Level Policy Gate:** Pass all scheduled runs through a strict trust policy:
  - *Supervised:* Mutating tools pause and request human approval (`waiting_approval`) via messaging channels (Telegram/WhatsApp).
  - *Semi-Autonomous:* Auto-approves read-only tools; pauses on mutating tools.
  - *Full-Autonomous:* Auto-approves benign mutations, but `ask`-tier and dangerous patterns (`rm -rf`, `.env`, `.git`) are NEVER auto-approved.
- **Circuit Breaker:** Apply exponential backoff penalty on consecutive task execution errors (5m, 10m, 20m, 40m, max 1h); automatically pause tasks after 5 consecutive failures.
- **Atomic Kanban Claiming:** Use conditional atomic SQL updates (`UPDATE autonomous_tasks SET status = 'running' WHERE id = ? AND status IN ('idle', 'failed') AND next_run <= ?`) to eliminate concurrent run race conditions.

### 4. Model Context Protocol (MCP) Subprocess Isolation & Security
- **Headless Process Hardening (Windows `CREATE_NO_WINDOW`):** Spawn stdio-based MCP servers with `creationflags = 0x08000000` (`CREATE_NO_WINDOW`) to prevent console windows from repeatedly flashing on the host desktop.
- **Concurrent Stderr Drainage:** Attach an asynchronous background reader task to the child process `stderr` pipe (`_drain_stderr`). Without active stderr consumption, subprocesses emitting diagnostic logs will fill the operating system's 64KB pipe buffer and deadlock the entire JSON-RPC channel.
- **Strict Environment Whitelisting:** Subprocesses must never blindly inherit host process environment variables. Whitelist strictly required system keys (`PATH`, `USER`, `TEMP`, `SYSTEMROOT`, `PYTHONPATH`, `NODE_PATH`) and user-declared extras, preventing unintended leakage of agent auth tokens, API keys, or cloud credentials.
- **Regex Secret Scrubbing:** Scrub tool responses and error messages against regex patterns for provider keys (`sk-ant-*`, `AIza*`, `sk-*`, `ghp_*`) before exposing tool outputs to LLM prompt context or telemetry logs.
- **Dynamic Tool Registry Bridge:** Automatically namespace discovered MCP tools into the central tool registry as `mcp_{server}_{tool}`, inferring read-only vs mutating risk levels from JSON schema properties.

### 5. Universal Session Router & Intent Taxonomy
- **Single Entry Point (`openSession`):** Route all session open triggers (Sidebar, Command Palette, Notifications, Switcher, Deep Links, Artifacts) through a centralized router.
- **Intent Taxonomy:**
  - `in-place`: Focuses existing tile/main if already visible; otherwise routes main.
  - `stack`: Reuses an open empty draft tab before stacking a new tab.
  - `tab` (Ctrl/Cmd-click): Opens beside current session without overwriting main.
  - `window` (Shift+Ctrl/Cmd-click): Delegates to a new desktop window if supported.
- **Draft Tab Conservation:** If the user opens a session while looking at an untouched blank draft, reuse the blank draft rather than spawning an extra tab.
- **Read Receipt Invariant:** Always mark session read (`markSessionRead`) before checking if the session is already on-screen, ensuring unread badges clear reliably.

### 6. Cross-Session Artifacts Gallery vs Code Studio Separation
- **Strict Separation of Concerns:** In workbench sidebar navigation, never conflate the Code Studio workstation (`/code`) with the Artifacts Gallery (`/artifacts`):
  - *Code Studio (`/code`):* Interactive code editor, file explorer, git staging review, and terminal workstation.
  - *Artifacts Gallery (`/artifacts`):* A searchable library and gallery of all documents, images, diagrams, and files produced across all conversation sessions with filter tabs (`All`, `Images`, `Files`, `Code`), copy actions, and 1-click links back to the origin session.
  - *Capabilities (`/capabilities` / Brain):* Extensible skills catalog, tool permissions, multi-provider API keys, and omnichannel gateways.

### 7. Direct Import vs Dynamic Bundling for Interactive Root Modals
- **Zero-Latency Modal Shells:** In Next.js client component trees, root interactive modal overlays (Command Palette, Artifacts Gallery, Brain Control Center) must use direct module imports (`import ArtifactsGalleryModal from "../artifacts/ArtifactsGalleryModal"`) rather than bare `dynamic(() => import(...), { ssr: false })` without `<Suspense>`. Dynamic chunk splitting on root modals introduces runtime network round-trips upon user button clicks, risking hydration mismatches and unclickable UI buttons when connection latency fluctuates.

### 8. Large Paste Protection in Composers (>3,000 Chars)
- **Automatic Attachment Conversion:** Pasting more than 3,000 characters of plain text or code into a chat composer must automatically convert the pasted string into a clean `.txt` file attachment badge (`pasted_text_<stamp>.txt`) instead of inserting it raw into the textarea DOM. Pasting massive multi-kilobyte text blocks directly into a React-controlled textarea locks up the main V8 thread, causes long frame drops during input composition, and overflows the visual dock.

### 9. Unified Sidebar Session Management, Filter Menus & Cross-Channel Badging
- **Unified Storage with Platform Origin Attribution:** Maintain a unified SQLite session storage table where all sessions (Web, Desktop, CLI, Telegram, WhatsApp) coexist. Stamp each session with its immutable origin (`channel` / `source`) and query aggregate token counts (`total_tokens`). Avoid segregating sessions into isolated database partitions or hard-siloed navigation tabs.
- **Unified Stream with Inline Origin Badges:** Display sessions in a single coherent list with semantic origin badges (Telegram paper-plane, CLI prompt `>_`, Code Studio brackets `</>`, WhatsApp bubble) and unread/activity dots, eliminating mode-switch friction when continuing tasks across surfaces.
- **Sidebar View & Filter Control Popover (`SidebarFilterMenu`):** Anchor a compact filter/slider button (`ListFilter`) in the sidebar section header (`SESSIONS`) next to the New Session (`+`) action. Clicking reveals a dark Liquid Glass popover menu offering:
  - *Grouping:* `Project` (workspace folder hierarchy with synthetic `Home` bucket), `Updated` (temporal date buckets: Today, Yesterday, Previous 7 days, Older), `Status` (Working vs Finished), or `None` (flat unpartitioned list).
  - *Ordering:* `Updated` (recency), `Created` (chronological), `Tokens` (context size leaderboard), or `Status` (urgency).
  - *Show Toggles:* Granular switches for `Tokens` (compact `k`/`m` badges), `Updated` relative timestamps, and `Channel` origin badges.
  - *Filters:* Channel filter (`All`, `Web Studio`, `Telegram`, `WhatsApp`, `CLI`), Project multi-select, and Archived visibility toggle.
  - *Batch Actions:* `Expand all`, `Collapse all`, and `Reset to defaults`.
- **Global Leaderboards & Temporal Suppression:** Persist grouping, ordering, and filter preferences in client storage. When sorting by `tokens` or `cost`, automatically suppress date/temporal dividers so the list functions as an unpolluted global leaderboard rather than claiming a costly historical session occurred "Today".

### 10. Capabilities Console & Master–Detail Governance (Skills, Toolsets, Connectors, Plugins)
- **Four-Pillar Capabilities Hub:** Structure agent capability management into four cohesive domains rather than flat unpartitioned card grids:
  1. *Skills:* Left rail with dense list of skills (`CapRow`), usage counter (`×501`), direct toggle switches, and catalog search; Right pane with YAML frontmatter metadata table, formatted Markdown viewer for `SKILL.md`, and a docked bottom editor drawer (`DetailPane`) for in-place authoring.
  2. *Tools (Two-Tier Toolsets):* Left rail groups atomic tools into high-level cohesive Toolsets (e.g. File Operations, Terminal & Processes, Web Search) with aggregate call counters (`×236k`) and category toggle switches; Right pane displays member tool chips with individual call counters (`×13.1k`), expandable parameter JSON schemas, and configuration status.
  3. *Connectors:* Unified catalog of MCP and SaaS integrations (Airtable, Notion, Slack, GitHub, Postgres, etc.) with transport types (`stdio`, `http`), auth badges (`oauth`, `api_key`), configuration dialogs, and local MCP server status / reconnect controls.
  4. *Plugins:* Modular extension packages with semantic version pills (`v1.2.0`), category/author badges, descriptions, and toggle switches persisted to configuration.
- **Master–Detail Layout Primitives (`MasterDetail`):**
  - *Draggable Vertical Sash:* Column seam between left list and right detail features a pointer-capture resize sash with boundary clamping (`min 200px`, `max 450px`), double-click reset to default, and `localStorage` persistence.
  - *Dense Row Optimization (`CapRow`):* Rows keep uniform height (`h-8` single line or `h-11` with subtitle) with `content-visibility: auto` to prevent browser reflow lag on 80+ item catalogs.
  - *Direct Switch Invariant:* Toggle switches sit directly on list rows; toggling an item on/off must never require selecting the item into the detail pane first.

### 11. Code Studio Full-Bleed Geometry & Activity Bar Rail Navigation
- **Full-Bleed Vertical Alignment:** Top header bars over the center editor and right agent console must be eliminated or consolidated. Center code editors and right conversation streams must extend flush to the top of the viewport (`y = 0`) to maximize vertical code and narrative area.
- **First-Class Activity Bar Sessions Toggle:** Chat and workspace session switching belongs as a first-class icon button on the primary vertical Activity Bar rail (swapping the sidebar pane to `SessionHistoryList`) rather than cramped header popovers that clip against window bounds or splitter seams.
- **Container-Bounded Popovers:** In narrow panel layouts (<450px), popovers (model selector, approval modes, reasoning levels) must lock to container width (`inset-x-0 w-full`) or use snug inline-flex triggers, preventing popovers from overflowing splitters into editor or terminal panes.

## Diagnostic Audit Checklist

1. **Selective Store Slices:** Are Command Center system and analytics tabs protected from token streaming re-renders using slice selectors?
2. **Zero-Loss Quick Entry:** Does the quick entry capture window preserve unsubmitted prompts across blur, offline status, and relay timeouts?
3. **Wall-Clock Cron:** Are 5-field cron schedules evaluated via `croniter` against local wall-clock time rather than flattened into static seconds intervals?
4. **Autonomous Trust Policies:** Are mutating and `ask`-tier actions blocked from auto-approval during autonomous cron runs, requiring human approval?
5. **Circuit Breaker:** Does the task runner pause autonomous jobs after 5 consecutive failures with exponential backoff penalties?
6. **MCP Subprocess Hardening:** Do stdio MCP servers spawn with `CREATE_NO_WINDOW`, concurrent stderr drain, strict env whitelisting, and regex secret scrubbing?
7. **Session Intent Routing:** Does clicking a session with Ctrl/Cmd or Shift open it in a side pane or new window rather than overwriting main?
8. **Draft Tab Reuse:** Does opening an existing session replace open untouched blank drafts?
9. **Artifacts vs Code Partitioning:** Is the Artifacts Gallery decoupled from Code Studio, indexing cross-session visual media and documents?
10. **Direct Modal Import:** Are root modal overlays imported synchronously to eliminate chunk download delays and unclickable button states?
11. **Large Paste Protection:** Does pasting >3,000 characters of text convert to a file attachment badge rather than freezing the textarea DOM?
12. **Unified Sidebar Filtering & Badging:** Are sessions unified in a single stream with origin channel badges and configurable Grouping (Project/Date/Status/None), Ordering (Updated/Created/Tokens/Status), and Channel filters via a header filter menu?
13. **Master–Detail Capabilities Hub:** Are Skills, Tools, Connectors, and Plugins structured as a Master–Detail split view with draggable vertical sash, dense `CapRow` toggles, YAML frontmatter inspector, and full Markdown viewer?
14. **Code Studio Full-Bleed & Rail Navigation:** Are editor and chat panes flush to the top of the viewport, with sessions managed via an Activity Bar rail icon rather than overflowing header popovers?
