---
category: autonomous-ai-agents
name: agent-sidebar-and-session-engineering
description: Use when building agent sidebar sessions and filters.
---

# Agent Sidebar, Session History & Filtering Engineering

Use this skill when designing, building, modernizing, or auditing AI agent session history sidebars, session metadata indices, sorting/filtering popovers, and cross-channel chat routing (matching desktop engineering parity with professional agent workspaces).

## Core Architectural Invariants

### 1. Dual Identity: Physical Session vs Logical Route Key
- **`session_id` (Physical Transcript Timeline):** Unique, immutable identifier for a concrete conversation run (e.g. `YYYYMMDD_HHMMSS_<hex>`). Stores actual user/assistant message rows, tool outputs, and token ledgers in SQLite (`sessions` table).
- **`session_key` (Logical Routing Address):** Deterministic address of an inbound channel/thread/user lane (e.g. `agent:main:telegram:dm:7024711852` or `agent:main:cli:local`). The routing address continuously points to the active `session_id`.
- **Reset vs Switch Semantics:**
  - `/new`, `/reset`, or `/clear`: Rotates `session_key` to point to a freshly minted `session_id`, leaving the previous transcript archived in SQLite.
  - `/resume <target>`: Repoints `session_key` to a previous `session_id`.

### 2. Multi-Channel Origin Attribution & Badges
- **Unified Store, Explicit Provenance:** All sessions (Web Studio, CLI, Telegram, WhatsApp, Discord, Code IDE) live side-by-side in the same database. Never partition channels into separate disjoint databases.
- **Visual Origin Badges:** Display subtle, dedicated origin chips in the session row lead slot:
  - **Telegram:** Sky blue badge (`bg-sky-500/15 border-sky-400/30 text-sky-400`) with paper plane glyph.
  - **WhatsApp:** Emerald badge (`bg-emerald-500/15 border-emerald-400/30 text-emerald-400`) with chat bubble glyph.
  - **CLI:** Terminal chip (`bg-emerald-500/15 border-emerald-400/30 text-emerald-400`) with `>_` glyph.
  - **Code Studio:** Violet chip (`bg-violet-500/15 border-violet-400/30 text-violet-400`) with `</>` glyph.
  - **Default / Web:** Glowing or slate status dot.

### 3. Dynamic Session Grouping & Filtering (The "Filter Popover" Pattern)
Rather than fragmenting navigation with rigid top-level tabs that isolate conversations into silos, use a single unified stream driven by a contextual **Filter & View Menu** (`SidebarFilterMenu`):
- **Grouping Models:**
  - `project` (Default): Pinned sessions at top $\to$ Detached/Home chats $\to$ Project folders grouped by workspace directory (`root_path`).
  - `date`: Chronological recency buckets (`Today`, `Yesterday`, `Previous 7 days`, `Older`), preserving pinned sessions at top.
  - `status`: Lifecycle buckets (`Working` / active vs `Done` / idle).
  - `none`: Flat chronological stream without folder dividers.
- **Ordering Controls:**
  - `updated` (Default): Most recently active session first.
  - `created`: Session creation date.
  - `tokens`: Highest token count first (essential for context audit & cost tracking).
  - `status`: Urgency order (sessions requiring input or running tools first).
- **Show Toggles (Metadata Visibility):**
  - `showTokens`: Compact badge showing formatted token count (`formatTokens`: `1.2k`, `18k`, `1.4M`).
  - `showUpdated`: Relative timestamp (`5m ago`, `yesterday`).
  - `showChannel`: Toggle visibility of channel/origin chips.
- **Channel Filters:** Instant filtering by channel (`All`, `Web Studio`, `CLI`, `Telegram`, `WhatsApp`).
- **Project Scope Filters:** Multi-select checkboxes to filter sessions strictly to specific repositories or workspaces.

### 4. Layout Placement & Hierarchy: The SESSIONS Header Rule
- **Visual Hierarchy Order (Top to Bottom):**
  1. Primary Top Actions: `New session` (`Ctrl+N`), quick access action pills (`Capabilities`, `Artifacts`).
  2. Search Field: `Search sessions...` input.
  3. `PINNED` Section: All pinned chats (`is_pinned === 1`), with drag-to-pin and drag-to-unpin drop targets.
  4. **`SESSIONS` Section Header Bar:** Placed **BELOW** the search bar and **BELOW** pinned chats, immediately above the unpinned/recent session list.
  5. Content: SESSIONS label (uppercase monospace tracking with bullet dot) and a single Filter button (`ListFilter` icon) anchored with the `SidebarFilterMenu` popover. Strictly avoid adding a secondary `+` creation button in this header bar when a primary `+ New session` button already exists above the search field — redundant duplicate creation affordances within 100px create visual clutter and confuse users.
  6. Unpinned Session List: Categorized accordion folders with preview count caps (`SESSION_PREVIEW_COUNT = 3`) and "Show all N sessions" expandable rows.
- **Pitfall:** Never place the `SESSIONS` header bar at the very top above the action bar or search box. Doing so breaks grouping proximity and disconnects controls from the list they filter.

### 5. Hydration-Safe Filter State Persistence
- Store all sidebar view preferences in client storage (`localStorage`) using typed keys (`anara.sidebar.grouping`, `anara.sidebar.ordering`, `anara.sidebar.showTokens`, `anara.sidebar.showUpdated`, `anara.sidebar.showChannel`, `anara.sidebar.channelFilter`, `anara.sidebar.showArchived`, `anara.sidebar.projectFilter`).
- Provide an eager SSR-safe initialization function (`loadSidebarFilterState()`) and a partial updater (`saveSidebarFilterState()`).
- Always support a one-click **"Reset to defaults"** action to rescue users from over-filtered empty states.

### 6. Popover Containment, Positioning & Inline Accordion Invariant
- **The React Portal Body Displacement Trap:** When building filter popovers inside narrow, scrollable sidebars (`w-60` to `w-72` with `overflow-y: auto`), never wrap the menu in `createPortal(..., document.body)` with manual `getBoundingClientRect()` coordinate state. If `coords` is initially `null` or uncalculated on the initial render frame, falling back to `absolute right-0 top-full` on `document.body` drops the element at 100% of the document height (the very bottom of the entire page), creating a giant dark blank slab that obscures the screen and breaks scrolling.
- **Direct Container Relative Anchoring:** When the popover width (`w-56` or `w-60` / 224–240px) comfortably fits inside the sidebar width (260px), anchor the popover directly inside `<div className="relative">` on the filter trigger button with `absolute right-0 top-full mt-1.5 z-50`. It aligns with the button, requires zero viewport math, and never gets misplaced on screen resize or scroll.
- **Inline Submenu Accordions vs Cascading Horizontal Flyouts:** In sidebars bounded by `overflow-x: hidden`, desktop-style cascading flyouts (`left-full top-0`) will either be clipped off horizontally or require escape portals that glitch. Instead, design all submenus (Grouping, Ordering, Show Badges, Channel Filters) as **smooth in-place accordions** (clicking a category smoothly reveals its choices directly below it with checkmarks). Everything stays 100% inside the bounded popover.
- **Max-Height Bounds & Scroll Hygiene:** Always constrain popover height (`max-h-[460px] overflow-y-auto [scrollbar-width:thin]`) so large lists or expanded accordions never extend off the bottom of the screen. Wire outside-click (`mousedown`) and `Escape` listeners to close the popover smoothly.

### 7. IDE First-Class Activity Bar Rail vs Cramped Header Dropdowns
- **The Nested Header Dropdown Anti-Pattern:** When embedding session selection in multi-pane IDEs (with File Explorer, Code Editor, Terminal, and Agent Console), never cram the session selector into a small dropdown inside the top navigation bar or squeezed atop the file explorer tree. In narrow or split-pane configurations, title truncation turns session names into unreadable ellipses, popovers overflow horizontally into adjacent editor panes, and redundant controls proliferate (e.g. duplicate `+ New` buttons competing with sidebar actions).
- **First-Class Activity Bar Rail Integration:**
  1. Elevate sessions to a primary tab on the vertical activity bar rail alongside `Explorer` (Folder icon) and `Source Control` (Git icon).
  2. Clicking the Sessions icon toggles the left sidebar pane directly into the full-fidelity `SessionHistoryList` view.
  3. Clicking File Explorer toggles back to `WorkspaceTreeView`.
- **Zero-Friction Switching:** Users manage, search, filter, and pin sessions in a dedicated, full-height sidebar pane without popovers, viewport clipping, or horizontal collision with editor splitters.
- **Top Header De-Cluttering Invariant:** When sessions live in the activity bar and project/git metadata already resides in the file tree header, strip redundant project badges (`Project · branch`), session selector pills, and secondary `+ New` buttons from the top window header. Keep the top header strictly dedicated to global workspace mode switchers (e.g. `[Sessions | Code | Bots]`) and layout pane toggles.

### 8. Narrow Resizable Dock Popovers: Container-Bound (`fillContainer`) Invariant
- **The Child-Pill Anchor Overflow Trap:** In resizable agent console sidebars that can be dragged down to narrow widths (< 380px), floating popovers (Model Selector, Reasoning Level, Approval Mode) anchored to small child trigger buttons (`w-16` to `w-28`) fail catastrophically:
  - If anchored `left-0`: The popover (typically 280–320px wide) spills past the right viewport boundary, clipping search fields and action buttons.
  - If anchored `right-0`: The popover bleeds leftward over the resizable splitter, occluding the code editor and terminal.
- **The Container-Bound (`fillContainer`) Solution:**
  1. Pass a boolean flag (`fillContainer={isNarrowPanel}`) down to dock popovers.
  2. Inside the root dock container (`relative w-full`), render the popover anchored to the container itself using `absolute bottom-full mb-1.5 inset-x-0 w-full` instead of anchoring to the small button.
  3. **Guaranteed Bounding:** The popover's left edge aligns exactly with the dock's left boundary (x = 0), and its right edge aligns with the dock's right boundary (x = 100%). It never crosses into adjacent editor panes and never clips at the viewport edge.
  4. **Max-Height Clamping:** Clamp popover height (`max-h-[300px]` with internal overflow scrolling) so the agent chat timeline above remains visible and accessible while choosing models or modes.

### 9. Full-Bleed Pane Layout vs Global Top Header Banding (The Empty Header Gap Trap)
- **The Global Top Header Banding Trap:** When global workspace mode switchers (e.g. `[SESSIONS | CODE | BOTS]`) sit in a standalone full-width `<header>` element (`h-[38px] w-screen`) above a multi-pane IDE, and secondary clutter (session pills, project badges, redundant New buttons) is stripped away, the top header band across the middle pane (Code Editor) and right pane (Agent Console) degenerates into a massive, empty, dark horizontal strip. The editor tabs and the agent chat timeline below are needlessly pushed down by 38px, wasting critical vertical screen real estate.
- **Full-Bleed Panes with Sidebar-Nested Navigation:**
  1. Remove the standalone full-width top header row from the layout root (use `flex flex-row` instead of `flex flex-col` on `<main>`).
  2. Nest the global workspace tabs (`SegmentedStudioTabs`) directly at the top of the Left Sidebar (Pane 1) at `h-[38px]`, mirroring the sidebar header pattern used on the primary chat page.
  3. Allow the Center Editor (Pane 2) and Right Agent Console (Pane 3) to run **full-bleed to the top of the viewport (`y = 0`)**.
  4. **Resulting Geometry:** Zero wasted horizontal header space; the editor's multi-file tab bar (`IdeTabBar`) sits flush at the very top edge of the window, and the agent chat timeline gains full vertical height from top to dock without an awkward 38px gap.
- **Redundant Agent Console Header Elimination:** In resizable agent console panels where model selector, reasoning level, and approval mode already live snugly in the bottom dock, an upper static header bar displaying the model name and title (e.g. `AGENT CONSOLE · Gemini 3.8 Flash`) is redundant chrome that costs 36px of vertical height. Eliminate it so chat transcripts scroll cleanly from the top boundary.
