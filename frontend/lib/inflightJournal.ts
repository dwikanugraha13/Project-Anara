/**
 * inflightJournal.ts — Crash-Survivable In-Flight Turn Journal for Project Anara.
 *
 * Persists running turn state (user prompt, live streaming text, tool execution cards)
 * to client storage during active generation. If the client refreshes, switches tabs,
 * or attaches from another device/channel (e.g. Telegram to Web Studio), the journal
 * immediately folds the in-flight progress onto the transcript so the user sees live
 * work instantly without waiting for backend turn completion.
 */

import type { TranscriptItem } from "@/components/workbench/AnaraWorkbench";
import type { ToolProgressPayload } from "@/hooks/useWebSocket";

const JOURNAL_PREFIX = "anara_inflight_journal_";
const MAX_JOURNAL_AGE_MS = 10 * 60 * 1000; // 10 minutes

export interface InFlightSnapshot {
  sessionId: number | string;
  status: "thinking" | "speaking" | "idle";
  userPrompt?: string;
  streamingText?: string;
  liveToolProgress?: ToolProgressPayload | null;
  activeTools: string[];
  updatedAt: number;
}

function getStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

export function saveInFlightSnapshot(
  sessionId: number | string | null | undefined,
  snapshot: Partial<InFlightSnapshot>
): void {
  if (!sessionId) return;
  const storage = getStorage();
  if (!storage) return;

  const key = `${JOURNAL_PREFIX}${sessionId}`;
  try {
    const existing = getInFlightSnapshot(sessionId);
    const updated: InFlightSnapshot = {
      sessionId,
      status: snapshot.status || existing?.status || "thinking",
      userPrompt: snapshot.userPrompt !== undefined ? snapshot.userPrompt : existing?.userPrompt,
      streamingText: snapshot.streamingText !== undefined ? snapshot.streamingText : existing?.streamingText,
      liveToolProgress: snapshot.liveToolProgress !== undefined ? snapshot.liveToolProgress : existing?.liveToolProgress,
      activeTools: snapshot.activeTools || existing?.activeTools || [],
      updatedAt: Date.now(),
    };
    storage.setItem(key, JSON.stringify(updated));
  } catch {
    // Best-effort storage — failures must never break the execution path
  }
}

export function getInFlightSnapshot(
  sessionId: number | string | null | undefined
): InFlightSnapshot | null {
  if (!sessionId) return null;
  const storage = getStorage();
  if (!storage) return null;

  const key = `${JOURNAL_PREFIX}${sessionId}`;
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const parsed: InFlightSnapshot = JSON.parse(raw);
    if (Date.now() - parsed.updatedAt > MAX_JOURNAL_AGE_MS) {
      storage.removeItem(key);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearInFlightSnapshot(sessionId: number | string | null | undefined): void {
  if (!sessionId) return;
  const storage = getStorage();
  if (!storage) return;
  try {
    storage.removeItem(`${JOURNAL_PREFIX}${sessionId}`);
  } catch {}
}

/**
 * Folds the active in-flight journal snapshot onto restored transcript bubbles.
 * Guarantees that if a turn is running, the in-flight prompt and thinking/tool bubble
 * appear smoothly at the bottom of the timeline.
 */
export function mergeInFlightWithTranscript(
  baseTranscript: TranscriptItem[],
  snapshot: InFlightSnapshot | null
): TranscriptItem[] {
  if (!snapshot) return baseTranscript;

  const result = [...baseTranscript];
  const lastItem = result[result.length - 1];

  // 1. If user prompt is journaled and not yet present in restored transcript tail
  if (snapshot.userPrompt && (!lastItem || lastItem.speaker !== "input" || lastItem.text !== snapshot.userPrompt)) {
    const alreadyPresent = result.some(
      (item) => item.speaker === "input" && item.text?.trim() === snapshot.userPrompt?.trim()
    );
    if (!alreadyPresent) {
      result.push({
        speaker: "input",
        text: snapshot.userPrompt,
      });
    }
  }

  // 2. If turn is still actively thinking/streaming, ensure active output placeholder exists
  const hasRunningOutput = result.length > 0 && result[result.length - 1].speaker === "output" && !result[result.length - 1].text;
  if (!hasRunningOutput && snapshot.status === "thinking") {
    result.push({
      speaker: "output",
      text: snapshot.streamingText || "",
      isStreaming: true,
      toolsUsed: snapshot.activeTools.length > 0 ? snapshot.activeTools : undefined,
    });
  }

  return result;
}
