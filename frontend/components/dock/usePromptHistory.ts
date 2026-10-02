import { useRef, useEffect, useCallback } from "react";

const STORAGE_KEY = "anara:prompt-history";
const MAX_HISTORY = 50;

export interface UsePromptHistoryReturn {
  pushHistory: (prompt: string) => void;
  navigateHistory: (direction: "up" | "down", currentDraft: string) => string | null;
  resetHistoryIndex: () => void;
}

/**
 * Prompt history ring buffer (Anara input history standard).
 * Persists history in sessionStorage and supports ArrowUp/ArrowDown REPL navigation.
 */
export function usePromptHistory(): UsePromptHistoryReturn {
  const historyRef = useRef<string[]>([]);
  const indexRef = useRef<number>(-1);
  const draftSnapshotRef = useRef<string>("");

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          historyRef.current = parsed.filter((item) => typeof item === "string");
        }
      }
    } catch {}
  }, []);

  const pushHistory = useCallback((prompt: string) => {
    const trimmed = prompt.trim();
    if (!trimmed) return;

    if (historyRef.current[0] !== trimmed) {
      historyRef.current.unshift(trimmed);
      if (historyRef.current.length > MAX_HISTORY) {
        historyRef.current.pop();
      }
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(historyRef.current.slice(0, MAX_HISTORY)));
      } catch {}
    }

    indexRef.current = -1;
    draftSnapshotRef.current = "";
  }, []);

  const navigateHistory = useCallback(
    (direction: "up" | "down", currentDraft: string): string | null => {
      const history = historyRef.current;
      if (history.length === 0) return null;

      if (direction === "up") {
        if (indexRef.current === -1) {
          draftSnapshotRef.current = currentDraft;
          indexRef.current = 0;
          return history[0];
        } else if (indexRef.current < history.length - 1) {
          indexRef.current += 1;
          return history[indexRef.current];
        }
      } else if (direction === "down") {
        if (indexRef.current > 0) {
          indexRef.current -= 1;
          return history[indexRef.current];
        } else if (indexRef.current === 0) {
          indexRef.current = -1;
          return draftSnapshotRef.current;
        }
      }

      return null;
    },
    []
  );

  const resetHistoryIndex = useCallback(() => {
    indexRef.current = -1;
    draftSnapshotRef.current = "";
  }, []);

  return {
    pushHistory,
    navigateHistory,
    resetHistoryIndex,
  };
}
