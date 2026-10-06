# Session State Management

Rules for multi-view apps where several UI surfaces (Desktop chat, Code Studio IDE, etc.) share one backend session store.

## Deferred Session Creation (Anara Pattern)

"New Chat" must NEVER immediately create a database session. Sessions accumulate with empty titles ("New Chat", "New Project") when created eagerly on button click — users who click New Chat then navigate away leave orphan rows.

**The correct flow:**
1. **"New Chat" click** → clear all UI state (`transcript`, `workspaceTree`, `gitStatus`), set `activeSessionId = null`, remove localStorage key. No WebSocket message, no API call.
2. **First message send** → include `session_type` ("chat" or "code") in the `text_input` WS payload. The backend's `ensure_session()` auto-creates the session when `activeSessionId` is null.
3. **Backend responds with `session_id_sync`** → frontend receives the new session ID and sets it as active. Sidebar refresh picks up the new session.
4. **Auto-title** → after the first turn completes, backend calls `maybe_auto_title_session()` which uses the LLM to generate a meaningful title from the conversation content.

**Backend `ensure_session()` must accept `session_type` parameter** — without it, sessions created from Code Studio default to "chat" instead of "code". The `text_input` handler reads `session_type` from the incoming WS data and passes it through.

**Sidebar safety net: `message_count > 0` filter** — when listing sessions, filter out any with `message_count === 0`. This mirrors Anara's `min_messages=1` API parameter and catches any edge cases where empty sessions leak through.

**Pitfall: dead `isNewSessionPendingRef` pattern.** When migrating from eager to deferred creation, remove the `isNewSessionPendingRef` flag that was set before sending `new_session` WS message. It becomes permanently `false` dead code that adds confusion to the session-switched handler.

**Pitfall: auto-create on mount.** Remove any `useEffect` that creates a session via API when the session list is empty on page load. With deferred creation, an empty session list means the user hasn't chatted yet — leave `activeSessionId = null` and let the first message trigger creation.

## Eager-Clear on Session Switch

When switching sessions, null out ALL view-specific state BEFORE setting the new `activeSessionId`. Otherwise the previous session's data remains visually rendered until the async re-fetch completes — causing stale workspace trees, phantom file explorers, and ghost transcripts.

**Pattern (React):**
```tsx
const handleSelectSession = (id: number) => {
  // Clear FIRST — prevents stale flash
  setWorkspaceTree(null);
  setGitStatus(null);
  setTranscript([]);
  // THEN switch
  setActiveSessionId(id);
  localStorage.setItem("active_session_id", String(id));
  sendJSON({ type: "switch_session", sessionId: id });
};
```

Apply the same eager-clear in `handleNewSession` (which now just clears state without any WS send).

## Unified Session Pointer

- Use ONE `localStorage` key for the active session (e.g. `active_session_id`), never per-view keys (`_code_session_id` vs `_chat_session_id`). Per-view keys cause session amnesia when navigating between views.
- On mount, read `?session_id=` from URL search params first, then fall back to the shared localStorage key.

## Universal Session List (No Frontend Filtering)

- Never filter session list API calls by `session_type` on the frontend — all sessions must be visible and resumable from any view. The view is a "lens" over the same session, not a silo.
- Backend can still accept an optional `session_type` query param for other consumers, but the sidebar session list must fetch without it.

## Cross-View Resume Links

Navigation links between views must carry `?session_id=${activeSessionId}` so the target view resumes the same conversation:
```tsx
// Code Studio → Desktop
<Link href={activeSessionId ? `/?session_id=${activeSessionId}` : "/"} />
// Desktop → Code Studio  
window.open(activeSessionId ? `/code?session_id=${activeSessionId}` : "/code", "_blank");
```
