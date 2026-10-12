---
name: agent-platform-and-capability-engineering
description: Use when filtering skills by OS or managing tool telemetry.
---

# Agent Platform and Capability Engineering

Use this skill when designing, auditing, or implementing platform-aware capability filtering, operating system compatibility detection, and non-invasive telemetry accounting for AI coding agents.

## Core Invariants

### 1. Host OS Platform Compatibility Filtering
- **Frontmatter Declarations:** Skills declare target operating systems in frontmatter via `platforms: [macos, linux, windows]` (or singular `platform`). Absent or empty declarations mean the skill is universal and supported across all platforms.
- **Platform Mapping:** Normalize system platforms against runtime values (`sys.platform`):
  ```python
  PLATFORM_MAP = {"macos": "darwin", "linux": "linux", "windows": "win32"}
  ```
- **Offer Surface Filtering:** On all offer surfaces (catalog indexing, prompt manifest generation, autocomplete, slash command listings), strictly filter out skills that are incompatible with the host OS.
- **Why (Failure Mechanism):** Failing to filter by host platform causes platform-incompatible skills (e.g. macOS-only Apple Notes, iMessage, FindMy, or Linux-specific packages on Windows hosts) to leak into the prompt manifest. LLMs eagerly read these and hallucinate OS-specific shell commands, triggering catastrophic runtime failures.
- **Inspection Escape Hatch:** Direct lookups (`get_skill` / `skill_view`) must support an explicit `include_unsupported=True` parameter so administrative tools, code editors, and catalog search engines can still view and modify raw skill files regardless of the host OS.

### 2. Decoupled Telemetry Sidecar (`.usage.json`)
- **Non-Invasive Storage:** Store skill invocation counters and execution statistics in a decoupled sidecar store (`.usage.json` or database ledger) keyed by skill name or slug. Never mutate `SKILL.md` frontmatter to track invocation counts.
- **Why (Failure Mechanism):** Writing usage counts into `SKILL.md` dirties git working trees on bundled repositories, invalidates model prompt caching tokens across consecutive turns, and creates race conditions or zero-byte file truncation during concurrent tool runs.
- **Optimistic Ranking & Fallback:** Read sidecar usage data dynamically during skill indexing (`list_skills`) and overlay counts onto parsed skill objects for UI sorting and ranking. If the sidecar file is absent or corrupted, gracefully fall back to zero without crashing the agent loop.

### 3. Master–Detail Capability Scaffolding
- **Responsive Layout:** Construct capability and tool browsers using a Master–Detail split layout (dense search/filter rail on the left, full documentation/schema view on the right) with a draggable, persisted vertical sash.
- **Dense Item Rows (`CapRow`):** Keep left rail rows compact (`h-8` or `h-11`), displaying title, subtitle/category, invocation count badge (`×211`), and an immediate toggle switch on the right edge.
- **Separation of Dedicated Hubs:** Keep Core Capabilities (`skills`, `tools`, `connectors`, `plugins`) distinct from Workspace Management hubs (`providers`, `messaging`, `scheduled jobs`). Embed each as a full-bleed workspace view rather than stacking nested modals or floating popups.
