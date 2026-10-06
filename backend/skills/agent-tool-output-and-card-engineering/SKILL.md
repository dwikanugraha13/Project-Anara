---
category: autonomous-ai-agents
name: agent-tool-output-and-card-engineering
description: Use when designing tool output cards, diffs, or subagent UI.
---

# Agent Tool Output and Card Engineering

Use this skill when designing, building, modernizing, or auditing AI agent tool output cards, execution transcripts, file diff viewers, and multi-agent delegation UI in desktop and web workspaces.

## 1. Scaffolding & Disclosure Row Hierarchy

Transcript scaffolding represents the quiet lines around agent responses that indicate what the agent *did* rather than what it *said* (thinking headers, settled tool runs, activity tickers):

- **Header Alignment & Leading Cells:** Every scaffold row (`ScaffoldRow`) shares a fixed leading cell (`grid size-3.5 place-items-center`) so labels, spinners, and icons share a precise left edge.
- **Affordance Caret Placement:** Never use an intrusive leading triangle. Place a subtle disclosure caret to the right of the title text on hover (`group-hover:opacity-80`) with smooth rotation (`rotate-90` when open) inside a `max-w-fit` click container so clicks in empty trailing space do not trigger accidental toggles.
- **Trailing Slot Isolation:** Reserve the right edge of the header row strictly for the live elapsed timer (`ActivityTimerText`) during execution or a completed timestamp (`TimelineTimestamp`). Interactive controls (such as the hover-revealed dismiss `✕` button) layout in flow to avoid colliding with the disclosure caret hit-target.
- **Resting Fade Invariant:** Scaffold text rests at subdued tertiary contrast (`opacity: 0.67` / muted slate) and lifts to `1.0` on hover or focus-visible.
- **Unboxed Prose Canvas Stream:** Prose narrative responses must flow directly on the canvas without card wrappers, heavy borders, or animated perimeter outlines (`streaming-arc-border`). Boxing narrative prose inside card containers creates visual clutter and breaks conversational reading continuity.
- **Stacking Context Pitfall for Activity Tickers:** Never apply opacity or resting fade (`data-conversation-scaffold`) to a container element that wraps an active ticker reel. Opacity opens a CSS stacking context around the transformed element (`translateY`), which breaks `overflow: clip` and causes off-screen activity lines to paint through as stacked ghost artifacts. Apply resting fade strictly to individual line elements, never to the container.

---

## 2. Tool Run Coalescing & Dynamic Reel Tickers

When an agent executes sequential utility tools (reads, searches, directory listings, terminal commands):

- **Run vs. Card Splitting (`splitRunItems`):** Coalesce sequential non-card utility calls into a single summary line ("Explored 3 files, ran 5 commands"). Standalone deliverable cards (file diffs, interactive approvals, user clarifications, subagent delegations) must never be folded into a summary line; they render in sequence where they occurred.
- **Single Utility Execution Aesthetic (Anti-Box Standard):** For lone utility commands (a single `terminal` run, `read_file`, `search_files`, or `glob`), never wrap them in wide, heavy, full-width bordered cards with prominent prompt bars and exit status boxes when collapsed. Render them as **tight, inline scaffold rows with `max-w-fit`** (`» Ran <command>` or `» Read <filename>`) using subdued monospace text (`text-slate-400 hover:text-slate-200`) and a resting opacity of 0.67. Full output blocks stay collapsed until clicked.
- **Dynamic Reel Ticker Motion:** While a multi-tool run or subagent is actively executing, display a single-line animated ticker window (`ToolRunTicker`). As each new action arrives, slide the preceding action up and out of view using CSS translateY reel transitions (`transform: translateY(calc(activeIdx * -20px)); transition: transform 240ms cubic-bezier(0.22, 1, 0.36, 1)`).
- **Tense Shifting:** Live runs narrate in present continuous tense ("Exploring 3 files, running 2 commands"); settled runs narrate in past tense ("Explored 3 files, ran 2 commands").

---

## 3. File Diff & Code Modification Panels

Render file modifications with clean, distraction-free IDE parity:

- **Collapsed Scaffold by Default:** File edit and creation cards must be **collapsed by default** (`isExpanded = false`) as a clean 1-line scaffold bar (`</> filename.tsx +N −M ⌄`). Never blow open a massive 340px raw code table across the chat canvas by default; users expand the diff voluntarily when they want to inspect hunks.
- **File Creation vs. Unified Diff (`+0 -0` Trap):** When an agent creates a new file from scratch (`write_file` / `write_local_file`), there are no git unified diff hunks (`@@`), causing standard diff parsers to report 0 additions and 0 deletions. Never display `+0 -0` for newly created files. Compute the line count from the file content (`content.split('\n').length`) and display `+{lineCount}` with an explicit `Create` or `Write` badge instead of `Edit`.
- **Header Stripping:** Strip git file preambles (`diff --git`, `index`, `--- a/`, `+++ b/`, `/dev/null`) and noisy hunk headers (`@@`) before display. The card title already identifies the target file.
- **Streamlined 3-Column Diff Gutter:** Drop redundant `+` and `-` symbol columns. A 3-column layout (`oldLine`, `newLine`, `code`) with a 2px left border accent (`border-l-2 border-emerald-400 bg-emerald-500/10` for additions, `border-l-2 border-rose-400 bg-rose-500/10` for deletions) saves ~24px of horizontal space and renders code naturally.
- **Diff Statistics Badge:** Display concise additions/deletions counts (`+A −R`) in the header row using mathematical minus (`−` U+2212), not an ASCII hyphen. Omit deletion indicators entirely if `delCount === 0`.
- **Scroll & Containment:** Apply `overscroll-y-auto` so reaching scroll boundaries passes wheel events back to the timeline, and `overscroll-x-contain` to prevent trackpad horizontal overscroll from triggering browser history navigation.
- **Settled Changed Files Rollup:** At the tail of a completed assistant turn, render a consolidated `SettledChangedFilesCard` summarizing all workspace mutations in that turn. Deduplicate by unique file path and sum cumulative additions/deletions. Provide a one-click `Review changes ↗` link to the Git Review panel and individual file links to the editor. Gate this card to render only when the turn is settled (`!isStreaming`), preventing visual clutter during generation.
- **Checkpoint Rollback Affordance:** Provide an inline Revert button when the tool result or session database tracks an atomic checkpoint ID, accompanied by double-confirmation timeout gates.

---

## 4. File Read & Exploration Surfaces

- **Collapsed Scaffold by Default:** For non-modifying file inspection (`read_file`), present a compact 1-line scaffold row (`Read <filename> L1-50 (N lines) ›`) to preserve transcript real estate, expanding on demand into a gutter line number table.
- **Eliminate Loud Badges:** Replace blocky uppercase badges (`READ`, `GREP`, `GLOB`) with calm monospace sentences (`» Read <filename>`, `» Searched "<pattern>"`).
- **Line Range Derivation:** Parse requested offset/limit arguments or scan output line markers (`^(\d+)\|`) to construct precise line badges (`L1-45` or `L12`).
- **Exploration vs. Error Semantics:** Treat `File not found` during discovery as neutral `notice` (quiet informational badge), not destructive red `error`. Autonomous agents routinely probe potential file locations as part of discovery; painting routine non-existent paths in red creates false alarm fatigue.

---

## 5. Terminal & Shell Execution Transcripts

Present command output with clean terminal ergonomics:

- **Monospace Command Prompt:** Render the executed command on a dark background with an accent prompt symbol (`$ ` in neutral slate or amber).
- **Exit Code Pill:** Show an explicit exit status pill (`exit 0` in emerald, `exit N` in amber/rose). Treat non-zero exit codes as `notice` or amber warning if the command yielded readable output (e.g. grep or test diffs), reserving destructive red exclusively for hard process crashes with no output.
- **Split Stream Inspection:** If both stdout and stderr are populated, split them into separate labeled blocks with tiny uppercase tracking labels (`STDOUT`, `STDERR`). Never style `STDERR` in destructive red by default, as standard build tools and package managers routinely route informational messages to stderr.
- **Pinned Auto-Scroll (Tailing):** Monitor scroll position against threshold (`scrollHeight - scrollTop - clientHeight < 32px`). Automatically pin to bottom as output streams, but immediately disengage tailing when the user scrolls upward to inspect earlier logs.
- **Initial Jump Reflow Protection:** Perform initial mount scroll positioning inside a `ResizeObserver` callback or microtask rather than a synchronous layout effect (`useLayoutEffect`) to eliminate reflow storms across transcripts mounting dozens of execution blocks.
- **Dedicated Copy Control:** Provide a copy button positioned in the upper right of the expanded surface that yields the raw unstripped terminal text.

---

## 6. Grep & Codebase Search Results

- **Grouped File Cards:** Cluster search hits by relative file path with hit counts (`(N matches across M files)`).
- **Hairline Dividers:** In expanded search bodies, separate files with 1px hairline dividers (`border-t border-white/[0.06]`) rather than heavy nested cards-in-cards.
- **Match Substring Highlighting:** Highlight the searched query pattern within matched lines using `<mark>` or subtle accent backgrounds.
- **Jump-to-Line Navigation:** Ensure clicking a search hit passes the exact 1-based `line_number` to the editor handler (`onOpenFile(file, filename, hit.line_number)`), scrolling the editor canvas directly to the target line.

---

## 7. Subagent Delegation Card & Fan-Out Architecture

When an orchestrator delegates missions to autonomous worker subagents:

- **Compact Footprint (Anti-Sprawl):** Never dump full child message histories into the parent chat timeline. A fan-out of 5 children must occupy a compact card stack (~10 lines total).
- **Child Row Structure (`DelegateRowView` / `SubagentCard`):**
  - **Leading Glyph:** Smooth breathing spinner while live (`running`/`queued`), subtle checkmark when completed, destructive red alert on failure/timeout, and parked neutral dot when dispatched in background without active streaming.
  - **Metadata:** Specific task goal on the left, model badge, settled duration, and trailing agent icon.
  - **Live Elapsed Timer:** Display real-time seconds ticking at the trailing edge.
- **Activity Ticker Reel (`TICKER_DEPTH=6`):** Render a single-line ticker beneath the child goal showing the worker's latest relayed step ("Reading config.py", "Ran pytest"). Buffer to the last 6 actions with smooth sliding/fade animation.
- **WebSocket Event Bridge:** Subagent managers running background tasks must register an active listener with the platform WebSocket broadcaster (`subagent_manager.register_listener(broadcast_agent_event)`). Without an explicit bridge, background child lifecycle events (`subagent_task_started`, `subagent_progress`, `subagent_task_completed`, `subagent_task_failed`) remain trapped in memory and cannot update the UI.
- **In-Place Accordion Expansion (Anti-Modal Standard):** Never kick the user into an invasive full-screen modal inspector on task click. Expand child execution traces directly beneath the row as an in-place accordion drawer, displaying tool execution sequences (`Terminal`, `Read`, `Patch`) and key findings in flow.

---

## 8. Scroll Anchoring, Viewport Pinning & Chat Timeline Ergonomics

- **Observer-Driven Auto-Tailing (`ResizeObserver`):** Relying solely on passive React state dependencies (`[transcript.length, lastItemLen]`) fails when tool accordions expand/collapse or Shiki syntax highlighting completes post-mount. Attach a `ResizeObserver` to the inner content wrapper to immediately synchronize `scrollTop = scrollHeight` whenever content height changes while the user is pinned to the bottom.
- **Text Selection Guard:** Check `window.getSelection()?.toString()`. If the user is actively selecting text to copy while an answer is streaming, auto-scroll must pause immediately. Forcing `scrollTop = scrollHeight` during mouse text selection violently cancels the user's selection range.
- **Unread Counter Invariant:** Only increment the unread messages counter when actual new message entities arrive (`transcript.length` increases). Never increment on streaming token or character deltas (`lastItemLen`), which causes a single 80-token response to falsely show "80 messages" on the scroll pill.
- **Container Isolation (`overscroll-contain`):** Apply `overscroll-contain` on the root chat scroller to prevent scroll chaining to the outer application window. Apply `overscroll-x-contain overscroll-y-auto` on code diffs and terminal outputs to isolate horizontal trackpad swipes from browser back/forward navigation.
- **Unobtrusive Jump-to-Bottom Positioning:** Never center a floating scroll button in the horizontal middle of the chat canvas (`left-1/2 -translate-x-1/2`), where it hovers directly over active code and text. Position it as a compact pill (`↓ N messages` or `↓ Latest`) at the bottom center or bottom right, only appearing when the user has genuinely scrolled far up (`distanceToBottom > 150px`).
- **Streaming Caret Beam vs Blocky Cursors:** Avoid chunky block cursors (`w-2 h-4` with heavy glow) that look like trapped artifact elements at the end of paragraphs. Use a sleek vertical beam (`w-[2px] h-[1.15em] bg-white/80 animate-pulse ml-0.5 align-text-bottom`), and ensure the streaming flag is cleanly cleared upon turn completion so the caret unmounts cleanly.

---

## 9. Monolithic UI Decomposition & Barrel Routing

When UI tool cards grow beyond 1,000 lines of code:

- **Sub-Component Decomposition:** Split monoliths into single-responsibility sub-modules (`ThinkingCard`, `TerminalTranscript`, `ReadFileView`, `GrepResultView`, `GlobResultView`, `AgentActionCard`, `ToolRunGroupCard`, `TodoChecklistCard`, `SubagentCard`, `SettledChangedFilesCard`, `toolCardUtils.ts`).
- **Thin Barrel Re-export:** Maintain the original component file as a lightweight router/barrel re-exporting all sub-components and utilities, ensuring zero breakage for existing timeline consumers.

---

## 10. Interactive Clarification & Questionnaire Cards (`clarify` / `AskUserQuestion`)

- **Cognitive Tools vs. Safety Permission Gates:** Clarification cards (`InteractiveQuestionCard` / `ClarifyToolPending`) are NOT permission gates. Safety approval gates (`manual`, `smart`, `off`) govern whether mutating actions may execute. Clarification cards are cognitive interaction tools driven 100% by dynamic model reasoning (question text, multi-choice options, recommended flags, descriptions).
- **Mode-Agnostic Availability:** Clarification tools are available across all autonomy and approval modes (`plan`, `auto`, `smart`, `off`). No runtime filter should block their availability based on approval policy.
- **Low-Stakes vs. High-Stakes Heuristic:** In autonomous/build modes (`auto`, `smart`, `off`), models operate under a "prefer deciding low-stakes questions yourself" heuristic (e.g. creating standard boilerplate files directly using sensible defaults). In plan mode, the threshold is deliberately lowered to clarify requirements upfront before proposing a plan. In any mode, genuinely high-stakes, under-specified, or mutually exclusive architectural choices should prompt the model to call `clarify`.
- **Staging & Keyboard Ergonomics:** Support numeric keys (1–9) for instant selection, Enter to advance/submit, Escape to dismiss, and automatically append an "Other (type your answer)" option in the UI for open-ended customization.

---

## 11. Interactive Approval Action Cards (Safety Permission Gate)

When user consent is required before running dangerous shell commands or workspace mutations:

- **Approval Mode Semantics & UI Palettes:**
  - **Plan (`amber-400` / `#fbbf24`):** Deliberate brainstorming and verification gatekeeper. Autonomously inspects and reads codebase files, but pauses to prompt for explicit confirmation before writing/modifying workspace files or executing mutating shell commands.
  - **Auto (`sky-400` / `#38bdf8`, Default):** Adaptive autonomous engineering. Routine workspace file creation and editing executes immediately without prompting, while shell commands are continuously guarded by auxiliary safety evaluation.
  - **Off (`rose-400` / `#fb7185`):** Unrestricted autonomy (YOLO). Bypasses interactive prompts for shell executions and file modifications, but hardline floor commands (e.g. `rm /`, `mkfs`, fork bombs) remain blocked permanently.
- **Workspace File Writes vs. Command Gates (Anti-Approval Fatigue):**
  - Standard project file operations (`write_file`, `patch` creating `index.html` or editing code files in project workspace) are core coding capabilities and are **not gated by interactive approval prompts** under Auto mode. Gating routine project file creations causes severe approval fatigue.
  - Write approval gates are strictly reserved for:
    1. **Plan Mode Verification:** Deliberate human-in-the-loop review of proposed workspace mutations during planning/brainstorming phases.
    2. **Protected Agent Instructions:** Changes to `SOUL.md`, `SYSTEM.md`, `.cursorrules`, or `SKILL.md`.
    3. **Remote Execution & System Vectors:** Modifications to `~/.ssh/config`, system daemon configs (`/etc/`), or repository state (`.git/`).
- **Dual Hotkey Ergonomics:** Support `Enter` for instant "Approve Once" and `Esc` for "Reject", displaying subtle hotkey pills (`[↵]`, `[Esc]`) on the button labels.
- **Input Boundary Guard:** Always verify whether the active focus is currently inside an `input`, `textarea`, or contenteditable element before triggering approval hotkeys. Never intercept Enter/Escape while the user is typing in a text field.
- **Focus Origin Restoration:** Capture `document.activeElement` when the approval gate mounts. Upon recording a decision (approve or reject), immediately restore focus to that element (e.g. the active code editor tab or terminal pane) so keyboard users do not lose their workflow context.

---

## 12. In-Place Message Edit & Optimistic History Truncation

When users edit an earlier prompt in the conversation timeline:

- **Optimistic History Slicing over Input Copying:** Never simply copy the edited text down into the composer dock while leaving the old prompt and subsequent turns intact. Appending a modified prompt at the bottom of the timeline pollutes the agent's context window with contradictory instructions.
- **Atomic Rewind & Resubmit:** Slice the transcript state array optimistically from the target index forward (`transcript.slice(0, index)`), update the prompt text in-place, and immediately trigger the runner turn from that exact point.
- **Backend History Pruning:** Send the target turn ID to the gateway so conversations from that index downward are pruned from persistent storage before new inference begins.

---

## 13. Composer Attachment Pipeline & Vision Prompt Fallback

- **Zero-Drop Screenshot Submissions:** If a user pastes or drops a screenshot and hits Send without typing prompt text, never drop the submission or fail on `if (!text.trim()) return`. Automatically inject an analysis prompt (`"Tolong analisa dan periksa screenshot gambar terlampir ini."` or localized equivalent) so the vision-capable model processes the image seamlessly.
- **Legible Thumbnail Sizing:** Thumbnail previews for pasted image chips must be at least 28–32px with rounded borders and specular drop shadows (`w-7 h-7 rounded-md object-cover`). Micro 16px thumbnails prevent users from verifying screenshot contents before sending.
- **Inline Audio & Voice Bubble Playback:** When an assistant response yields an audio artifact or recorded speech directive (`MEDIA:...`), parse the directive into a dedicated inline player bubble (`AnaraVoiceBubble`) with play/pause, live elapsed scrubber, and playback speed cycle (`1.0x` $\to$ `2.0x`) rather than dumping raw media paths into markdown.

---

## 14. Terminal PTY Screen Clear (`Ctrl+L`) & Browser Address Bar Protection

- **Browser URL Bar Interception:** In web-based terminal emulators (xterm.js), always intercept `Ctrl+L` inside `attachCustomKeyEventHandler`. Invoke `term.clear()` and send the form-feed escape character (`\x0c`) to the PTY WebSocket while calling `event.preventDefault()`. Without this explicit handler, browsers intercept `Ctrl+L` to focus the browser's address bar.

---

## 15. Critical Context Window Budget Alerts & Telemetry

- **Elevated Warning at Critical Thresholds (>=90%):** Do not rely solely on neutral text ratios. When token usage reaches >=90% of model context capacity, pulse an alert icon (`AlertTriangle animate-pulse`), tint the meter in bold rose, and display an explicit tooltip warning that auto-compaction will trigger on subsequent turns.
- **Transparent Popover Compaction Banners (>=85%):** In the detailed context usage breakdown, render a warning banner when token usage crosses 85%, informing the user that older conversational history will be compacted into semantic memory to preserve context integrity.

---

## 16. Professional Neutral Typography & Crisp White Prose (The Zero-Cyan Text Rule)

Professional coding agent interfaces demand high readability, calm aesthetics, and visual discipline:

- **Solid Neutral White/Slate Prose:** Narrative prose, paragraphs, list items, bold text, and headings must render in crisp neutral white or light slate (`text-slate-100`, `text-white`, `text-slate-200`). Never tint regular explanatory prose, paragraphs, or headings in cyan, teal, or colored hues (`text-cyan-200/300`).
- **Eliminate Streaming Rainbow Gradients:** Never apply animated colored gradients (e.g. cyan/violet flowing gradients with `-webkit-text-fill-color: transparent`) to assistant text during streaming. It distorts typography, degrades contrast, and causes severe eye fatigue. Streaming text must be solid crisp neutral white (`text-slate-100` / `#f1f5f9`).
- **Zero Raw Emojis & Neon Status Dots:** Forbid raw decorative emojis (`⚡`, `🧠`, `🚀`) on toolbar pills, agent action headers, and subagent cards. Use solid Phosphor / Codicon vector glyphs. Forbid neon status dots (cyan or purple dots) on resting control pills; use clean monospace typography.
- **Neutral Inline Code Chips:** Inline code snippets (`...`) must use neutral styling (`text-slate-100 font-mono bg-white/[0.06] border border-white/[0.08] px-1.5 py-0.5 rounded-[0.25rem]`). Never color code chips in bright neon cyan (`text-cyan-300`).
- **Selective Git Diff Color Preservation:** Semantic diff accents are strictly reserved for git modifications: additions must be emerald/green (`border-l-2 border-emerald-400 bg-emerald-500/10 text-emerald-300`), and deletions must be rose/red (`border-l-2 border-rose-400 bg-rose-500/10 text-rose-300`). Hunk separators (`@@ ... @@`) must remain quiet neutral slate (`bg-white/[0.03] text-slate-400 border-white/[0.06]`).
- **Scaffold Row & Label Quietness:** Keep tool scaffold labels ("Thinking", "Exploring files", file names, command text) in neutral slate (`text-slate-400 hover:text-slate-200`). Cyan is reserved exclusively for the active running animation glyph (e.g. `bg-cyan-400 animate-ping` pulse) while a tool or subagent is currently executing; once settled, all labels and glyphs settle into neutral white/slate.
- **Affordance Link Icons (`↗`):** Navigation affordances and link icons must hover to clean neutral white (`hover:text-white`), not cyan.

---

## 17. Procedural Web Audio Cues (Zero-Asset Auditory Feedback)

- **Zero-Asset Web Audio Synthesis:** Implement auditory cues using native Web Audio API procedural oscillator synthesis rather than loading external `.mp3` or `.wav` files. This eliminates network dependencies, 404 missing asset errors, and yields zero playback latency.
- **Harmonic Task Completion Chime:** When an agent finishes a long turn (`onTurnComplete`), play a warm, comforting 2-note ascending harmonic chime (e.g. E4 at 329.63 Hz gliding to C5 at 523.25 Hz with a sub-bass C4 fundamental and smooth exponential decay over 0.7s).
- **Attention Alert Ding:** When user consent or intervention is required (action approval, clarify question), play a soft, non-intrusive ascending fourth (G5 at 783.99 Hz to C6 at 1046.5 Hz). Never sound harsh buzzers or shrill alarms.
- **Persistent Mute & Volume Governance:** Provide a master mute toggle stored in persistent storage (`localStorage.getItem("anara_sound_muted")`) and safe audio context auto-resumption on user interaction.

---

## 18. In-Pane Git Diff Viewer in Review Workspace

- **In-Situ Git Diff Inspection:** When a modified or untracked file is clicked in a Git Review panel, render an inline unified diff viewer directly inside the review pane beneath the file list. Never kick the user out of the review context to a full editor tab that lacks repository diff context.
- **Unified Diff Rendering with Line Anchoring:** Fetch diff against `HEAD` (or staged index) via backend workspace endpoints (`/api/agent/git/file-diff?path=...`) and display unified diff lines with clear addition (`+`), deletion (`-`), and hunk (`@@`) styling.
- **Clean Collapse & Dismiss Affordance:** Provide a quick dismiss button (`✕`) in the diff viewer header so users can collapse the preview and return to navigating the file tree seamlessly.
