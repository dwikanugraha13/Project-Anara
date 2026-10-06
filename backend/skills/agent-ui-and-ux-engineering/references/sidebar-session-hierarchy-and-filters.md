# Sidebar Session Hierarchy, Dynamic Grouping, and Filter Menu Architecture

Use this reference when building or auditing sidebar session history navigation, cross-platform origin badges, dynamic grouping, token metrics, and filter popovers for AI agent IDEs.

## 1. Unified Stream vs Rigid Partitioned Tabs

- **Anti-Silo Invariant:** Never segregate sessions into rigid, isolated navigation tabs (e.g. `[CLI] | [Telegram] | [Studio]`). Forcing users to toggle tabs breaks conversational continuity and prevents rapid context switching across local and omnichannel workflows.
- **Unified Workspace Hierarchy with Origin Badges:**
  - Display all sessions within a single unified sidebar stream organized primarily by workspace directory (`cwd` / git repository root).
  - Distinguish session provenance via inline, low-noise origin badges (e.g. Telegram paper plane, WhatsApp chat bubble, CLI terminal prompt `>_`, Studio code brackets `</>`).
  - When sessions originate from or hand off between channels, render the origin badge quietly without dominating the session title.

---

## 2. Sidebar Section Header Anatomy

The sessions container begins with a compact, high-density section header row:

```text
• SESSIONS                                [ + ] [ ⫸ Filter ]
─────────────────────────────────────────────────────────────
[ Search sessions...                                       ]
```

- **Section Label:** Monospace, uppercase, tracked label (`text-[11px] font-semibold tracking-wider uppercase font-mono text-slate-400`).
- **Quick Action (`+`):** New session shortcut button with tooltip and `Ctrl+N` keybinding.
- **Filter Trigger Button:** A minimal icon button (`ListFilter` / sliders icon).
  - Resting state: `text-slate-400 hover:text-white hover:bg-white/[0.08]`.
  - Active filter state: Displays a luminous accent dot (`size-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#22d3ee]`) whenever grouping, ordering, channel filters, or project scopes deviate from system defaults.

---

## 3. Filter Popover Menu Architecture (`SidebarFilterMenu`)

A floating Liquid Glass popover anchored to the filter button with outside-click and `Escape` dismissal:

### Surface Styling (Liquid Glass Obsidian)
- Palette: Deep dark cosmic obsidian (`bg-[#080c14]/95`, `border border-white/[0.08]`, `backdrop-blur-xl`, `shadow-2xl shadow-black/80`).
- Typography: Clean slate text (`text-slate-200`, `text-[12px] font-sans`).
- Active Indicators: Neutral silver/white checkmarks (`✓` in `text-zinc-200`) on active radio items and checkboxes — **strictly zero raw emojis or colored neon checkmarks**.
- Submenus: Cascading hover/click submenus with chevron indicators (`›`) and debounce exit delays (~200ms) to prevent accidental closure during mouse travel.

### Menu Structure
1. **Grouping (Radio Group):**
   - **Workspace / Project** *(Default)*: Pinned sessions sticky at top, Home (`NO_PROJECT_ID` / unattached sessions), and Projects grouped by workspace root path.
   - **Updated / Date**: Chronological buckets (`Today`, `Yesterday`, `Previous 7 days`, `Older`), keeping pinned sessions sticky at top.
   - **Status**: Lifecycle buckets (`Working` vs `Done`).
   - **None**: Flat continuous list without category dividers.
2. **Ordering (Radio Group):**
   - **Last updated** *(Default)*: Sorted by `updated_at || created_at` desc.
   - **Date created**: Sorted by `created_at` desc.
   - **Total tokens**: Descending leaderboard of context consumption.
   - **Status urgency**: Ranked by urgency (`needs-input` > `working` > `unread` > `draft` > `idle`).
3. **Show Toggles (Checkboxes):**
   - **Tokens**: Toggles visibility of the token count badge in session rows.
   - **Updated**: Toggles relative timestamp (`now`, `5m`, `2h`, `yesterday`).
   - **Channel**: Toggles platform origin badge.
4. **Filters:**
   - **Channel**: Radio selector (`All`, `Web Studio`, `CLI`, `Telegram`, `WhatsApp`).
   - **Project**: Multi-select project checkboxes allowing users to isolate specific codebases.
   - **Archived**: Toggles display of archived sessions.
5. **Quick Actions (Footer):**
   - **Expand all / Collapse all**: Batch toggles open/closed state of all group accordions.
   - **Reset to defaults**: Restores default grouping (`project`), ordering (`updated`), and clears all filters.

---

## 4. Token Metric Representation (`formatTokens`)

When `showTokens` is enabled, render a compact, monospace badge in the session row:

```typescript
export function formatTokens(tokens?: number | null): string {
  if (tokens === undefined || tokens === null || Number.isNaN(tokens)) return "0";
  const num = Math.max(0, Math.round(tokens));
  if (num < 1000) return `${num}`;
  if (num < 10_000) {
    const val = (num / 1000).toFixed(1).replace(/\.0$/, "");
    return `${val}k`;
  }
  if (num < 1_000_000) return `${Math.round(num / 1000)}k`;
  if (num < 10_000_000) {
    const val = (num / 1_000_000).toFixed(1).replace(/\.0$/, "");
    return `${val}M`;
  }
  return `${Math.round(num / 1_000_000)}M`;
}
```

- **Badge Styling:** `text-[10px] font-mono text-cyan-400/80 bg-cyan-500/10 px-1.5 py-0.5 rounded border border-cyan-500/20 tabular-nums shrink-0`.
- **Database Calculation:** Backend `get_sessions` queries should resolve tokens from token usage logs (`token_usage_logs.total_tokens`) or estimate from conversation characters (`(LENGTH(user_text) + LENGTH(assistant_text)) / 4`) so tokens are populated across all sessions.

---

## 5. Local Storage Persistence & Hydration Safety

- **Storage Keys:** Namespace all filter keys (e.g. `anara.sidebar.grouping`, `anara.sidebar.ordering`, `anara.sidebar.showTokens`, `anara.sidebar.channelFilter`).
- **Hydration Guard:** On Next.js / SSR frameworks, evaluate `typeof window !== "undefined"` and load defaults during initial server render, re-syncing from `localStorage` inside `useEffect` to prevent React hydration mismatch errors (`Text content does not match server-rendered HTML`).
