import { useState, useCallback, useEffect } from "react";
import { anaraApi } from "@/lib/apiClient";
import type { ChatSession } from "@/components/sidebar/types";

export interface UseAgentSessionOptions {
  sessionType: "chat" | "code";
  storageKey?: string;
  onSessionChange?: (sessionId: number | null) => void;
}

export function useAgentSession({
  sessionType,
  storageKey = sessionType === "code" ? "anara_active_code_session_id" : "anara_active_session_id",
  onSessionChange,
}: UseAgentSessionOptions) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const list = await anaraApi.sessions.list(sessionType);
      if (Array.isArray(list)) {
        setSessions(list);
      }
    } catch (err) {
      console.warn(`[useAgentSession] Error loading ${sessionType} sessions:`, err);
    } finally {
      setSessionsLoading(false);
    }
  }, [sessionType]);

  const selectSession = useCallback(
    (id: number | null) => {
      setActiveSessionId(id);
      if (typeof window !== "undefined") {
        if (id) {
          localStorage.setItem(storageKey, String(id));
        } else {
          localStorage.removeItem(storageKey);
        }
      }
      onSessionChange?.(id);
    },
    [storageKey, onSessionChange]
  );

  const createNewSession = useCallback(
    async (title: string = sessionType === "code" ? "New Project" : "New Chat") => {
      try {
        const res = await anaraApi.sessions.create({
          session_type: sessionType,
          title,
        });
        if (res?.session?.id) {
          const newId = res.session.id;
          selectSession(newId);
          await loadSessions();
          return newId;
        }
      } catch (err) {
        console.warn("[useAgentSession] Error creating session:", err);
      }
      return null;
    },
    [sessionType, selectSession, loadSessions]
  );

  const deleteSession = useCallback(
    async (sessionId: number) => {
      try {
        await anaraApi.sessions.delete(sessionId);
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        if (activeSessionId === sessionId) {
          selectSession(null);
        }
      } catch (err) {
        console.warn("[useAgentSession] Error deleting session:", err);
      }
    },
    [activeSessionId, selectSession]
  );

  // Initialize from storage on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = Number(saved);
        if (!isNaN(parsed) && parsed > 0) {
          setActiveSessionId(parsed);
        }
      }
    }
    loadSessions();
  }, [storageKey, loadSessions]);

  return {
    sessions,
    activeSessionId,
    sessionsLoading,
    selectSession,
    createNewSession,
    deleteSession,
    loadSessions,
    setActiveSessionId,
  };
}
