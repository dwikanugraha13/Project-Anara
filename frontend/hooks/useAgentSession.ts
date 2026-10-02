import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { anaraApi } from "@/lib/apiClient";
import type { ChatSession } from "@/components/sidebar/types";

export interface UseAgentSessionOptions {
  sessionType: "chat" | "code";
  storageKey?: string;
  storageKeySessionKey?: string;
  onSessionChange?: (sessionId: number | null, sessionKey?: string | null) => void;
}

export function useAgentSession({
  sessionType,
  storageKey = sessionType === "code" ? "anara_active_code_session_id" : "anara_active_session_id",
  storageKeySessionKey = `${storageKey}_key`,
  onSessionChange,
}: UseAgentSessionOptions) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [activeSessionKey, setActiveSessionKey] = useState<string | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const isMountedRef = useRef(true);
  const brainSyncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (brainSyncTimerRef.current) {
        clearTimeout(brainSyncTimerRef.current);
        brainSyncTimerRef.current = null;
      }
    };
  }, []);

  const activeSession = useMemo(() => {
    if (activeSessionId !== null) {
      const match = sessions.find((s) => s.id === activeSessionId);
      if (match) return match;
    }
    if (activeSessionKey !== null) {
      const match = sessions.find((s) => s.session_key === activeSessionKey);
      if (match) return match;
    }
    return null;
  }, [sessions, activeSessionId, activeSessionKey]);

  // Load sessions from API
  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const list = await anaraApi.sessions.list(sessionType);
      if (isMountedRef.current && Array.isArray(list)) {
        setSessions(list);

        // Auto-reconcile dual-identity mapping if one ID is set but the other isn't
        if (activeSessionId !== null && activeSessionKey === null) {
          const match = list.find((s: ChatSession) => s.id === activeSessionId);
          if (match?.session_key) {
            setActiveSessionKey(match.session_key);
            if (typeof window !== "undefined") {
              try {
                localStorage.setItem(storageKeySessionKey, match.session_key);
              } catch {}
            }
          }
        } else if (activeSessionKey !== null && activeSessionId === null) {
          const match = list.find((s: ChatSession) => s.session_key === activeSessionKey);
          if (match?.id) {
            setActiveSessionId(match.id);
            if (typeof window !== "undefined") {
              try {
                localStorage.setItem(storageKey, String(match.id));
              } catch {}
            }
          }
        }
      }
    } catch (err) {
      console.warn(`[useAgentSession] Error loading ${sessionType} sessions:`, err);
    } finally {
      if (isMountedRef.current) {
        setSessionsLoading(false);
      }
    }
  }, [sessionType, activeSessionId, activeSessionKey, storageKey, storageKeySessionKey]);

  // Select session supporting both numeric SQLite ID and canonical string session_key
  const selectSession = useCallback(
    async (idOrKey: number | string | null) => {
      if (idOrKey === null) {
        setActiveSessionId(null);
        setActiveSessionKey(null);
        if (typeof window !== "undefined") {
          try {
            localStorage.removeItem(storageKey);
            localStorage.removeItem(storageKeySessionKey);
          } catch {}
        }
        onSessionChange?.(null, null);
        return;
      }

      let targetId: number | null = null;
      let targetKey: string | null = null;

      if (typeof idOrKey === "number") {
        targetId = idOrKey;
        const matched = sessions.find((s) => s.id === idOrKey);
        targetKey = matched?.session_key ?? null;
      } else if (typeof idOrKey === "string") {
        const trimmed = idOrKey.trim();
        if (/^\d+$/.test(trimmed)) {
          targetId = Number(trimmed);
          const matched = sessions.find((s) => s.id === targetId);
          targetKey = matched?.session_key ?? null;
        } else {
          // Canonical collision-free session_key
          targetKey = trimmed;
          const matched = sessions.find((s) => s.session_key === trimmed);
          if (matched) {
            targetId = matched.id;
          } else {
            // Not in local cache: resolve asynchronously from backend
            try {
              const res = await anaraApi.sessions.get(trimmed);
              if (res?.session?.id) {
                targetId = res.session.id;
                if (!sessions.some((s) => s.id === targetId)) {
                  setSessions((prev) => [res.session, ...prev]);
                }
              }
            } catch (resolveErr) {
              console.warn(`[useAgentSession] Failed to resolve session key "${trimmed}":`, resolveErr);
            }
          }
        }
      }

      setActiveSessionId(targetId);
      setActiveSessionKey(targetKey);

      if (typeof window !== "undefined") {
        try {
          if (targetId !== null) {
            localStorage.setItem(storageKey, String(targetId));
          } else {
            localStorage.removeItem(storageKey);
          }
          if (targetKey !== null) {
            localStorage.setItem(storageKeySessionKey, targetKey);
          } else {
            localStorage.removeItem(storageKeySessionKey);
          }
        } catch {}
      }

      onSessionChange?.(targetId, targetKey);
    },
    [sessions, storageKey, storageKeySessionKey, onSessionChange]
  );

  // Optimistic create session with rollback on failure
  const createNewSession = useCallback(
    async (title: string = sessionType === "code" ? "New Project" : "New Chat") => {
      // 1. Optimistic placeholder session
      const tempId = -Date.now();
      const tempKey = `temp_${Date.now()}`;
      const nowIso = new Date().toISOString();
      const optimisticSession: ChatSession = {
        id: tempId,
        session_key: tempKey,
        title,
        speaker_name: null,
        session_type: sessionType,
        message_count: 0,
        is_archived: 0,
        is_pinned: 0,
        created_at: nowIso,
        updated_at: nowIso,
      };

      setSessions((prev) => [optimisticSession, ...prev]);

      try {
        const res = await anaraApi.sessions.create({
          session_type: sessionType,
          title,
        });

        if (res?.session?.id) {
          const realSession: ChatSession = res.session;
          if (isMountedRef.current) {
            // Replace optimistic session with confirmed server session
            setSessions((prev) =>
              prev.map((s) => (s.id === tempId ? realSession : s))
            );
          }
          await selectSession(realSession.id);

          // Dispatch event to Anara event bus
          if (typeof window !== "undefined") {
            window.dispatchEvent(
              new CustomEvent("anara-brain-sync", {
                detail: {
                  event: "session_created",
                  session: realSession,
                  sessionId: realSession.id,
                  sessionKey: realSession.session_key,
                },
              })
            );
          }

          return realSession.id;
        } else {
          throw new Error("Invalid session creation response");
        }
      } catch (err) {
        console.warn("[useAgentSession] Error creating session, rolling back:", err);
        if (isMountedRef.current) {
          // Rollback optimistic addition
          setSessions((prev) => prev.filter((s) => s.id !== tempId));
        }
        return null;
      }
    },
    [sessionType, selectSession]
  );

  // Optimistic update session with rollback on failure
  const updateSession = useCallback(
    async (idOrKey: number | string, patch: Partial<ChatSession>) => {
      const prevSessions = [...sessions];

      // Optimistic update
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === idOrKey || s.session_key === idOrKey) {
            return { ...s, ...patch, updated_at: new Date().toISOString() };
          }
          return s;
        })
      );

      try {
        await anaraApi.sessions.update(idOrKey, patch as Record<string, unknown>);

        // Dispatch update to event bus
        if (typeof window !== "undefined") {
          window.dispatchEvent(
            new CustomEvent("anara-brain-sync", {
              detail: {
                event: "session_updated",
                idOrKey,
                patch,
              },
            })
          );
        }
        return true;
      } catch (err) {
        console.warn("[useAgentSession] Error updating session, rolling back:", err);
        if (isMountedRef.current) {
          setSessions(prevSessions);
        }
        return false;
      }
    },
    [sessions]
  );

  // Optimistic delete session with rollback on failure
  const deleteSession = useCallback(
    async (sessionIdOrKey: number | string) => {
      const prevSessions = [...sessions];
      const prevActiveId = activeSessionId;
      const prevActiveKey = activeSessionKey;

      const sessionToDelete = sessions.find(
        (s) => s.id === sessionIdOrKey || s.session_key === sessionIdOrKey
      );
      const numericId = sessionToDelete?.id ?? (typeof sessionIdOrKey === "number" ? sessionIdOrKey : null);

      // Optimistic removal
      setSessions((prev) =>
        prev.filter((s) => s.id !== sessionIdOrKey && s.session_key !== sessionIdOrKey)
      );

      // If active session was deleted, switch to next available or null
      if (
        activeSessionId === sessionIdOrKey ||
        activeSessionKey === sessionIdOrKey ||
        (numericId !== null && activeSessionId === numericId)
      ) {
        const remaining = prevSessions.filter(
          (s) => s.id !== sessionIdOrKey && s.session_key !== sessionIdOrKey
        );
        const nextSession = remaining[0] ?? null;
        await selectSession(nextSession ? nextSession.id : null);
      }

      try {
        await anaraApi.sessions.delete(sessionIdOrKey);

        if (typeof window !== "undefined") {
          window.dispatchEvent(
            new CustomEvent("anara-brain-sync", {
              detail: {
                event: "session_deleted",
                sessionId: numericId,
                sessionKey: sessionToDelete?.session_key,
              },
            })
          );
        }
        return true;
      } catch (err) {
        console.warn("[useAgentSession] Error deleting session, rolling back:", err);
        if (isMountedRef.current) {
          setSessions(prevSessions);
          setActiveSessionId(prevActiveId);
          setActiveSessionKey(prevActiveKey);
        }
        return false;
      }
    },
    [sessions, activeSessionId, activeSessionKey, selectSession]
  );

  // Anara event bus integration (anara-brain-sync) with burst coalescing
  useEffect(() => {
    if (typeof window === "undefined") return;

    const handleBrainSync = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (!detail) return;
      const { event } = detail;

      // Remote or local session sync events
      if (
        event === "session_created" ||
        event === "session_updated" ||
        event === "session_deleted" ||
        event === "session_workspace_updated" ||
        event === "conversation_logged" ||
        event === "conversation_deleted" ||
        event === "batch"
      ) {
        // Coalesce rapid event bursts into a single trailing refresh (Anara standard: 300ms)
        if (brainSyncTimerRef.current) clearTimeout(brainSyncTimerRef.current);
        brainSyncTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            loadSessions();
          }
          brainSyncTimerRef.current = null;
        }, event === "conversation_logged" ? 1000 : 300);
      } else if (event === "session_id_sync" || event === "session_switched") {
        const sid = detail.sessionId;
        const skey = detail.sessionKey;
        if (sid && sid > 0 && sid !== activeSessionId) {
          setActiveSessionId(sid);
          if (skey) setActiveSessionKey(skey);
          onSessionChange?.(sid, skey || null);
        }
      }
    };

    window.addEventListener("anara-brain-sync", handleBrainSync);
    return () => {
      window.removeEventListener("anara-brain-sync", handleBrainSync);
      if (brainSyncTimerRef.current) {
        clearTimeout(brainSyncTimerRef.current);
        brainSyncTimerRef.current = null;
      }
    };
  }, [loadSessions, activeSessionId, onSessionChange]);

  // Initialize from storage on mount (handling both numeric id and canonical session_key)
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const savedId = localStorage.getItem(storageKey);
        const savedKey = localStorage.getItem(storageKeySessionKey);

        let resolvedId: number | null = null;
        let resolvedKey: string | null = null;

        if (savedId) {
          const parsed = Number(savedId);
          if (!isNaN(parsed) && parsed > 0) {
            resolvedId = parsed;
          } else if (typeof savedId === "string" && savedId.trim()) {
            resolvedKey = savedId.trim();
          }
        }

        if (savedKey && !resolvedKey) {
          resolvedKey = savedKey.trim();
        }

        if (resolvedId !== null) {
          setActiveSessionId(resolvedId);
        }
        if (resolvedKey !== null) {
          setActiveSessionKey(resolvedKey);
        }

        if (resolvedId !== null || resolvedKey !== null) {
          onSessionChange?.(resolvedId, resolvedKey);
        }
      } catch {}
    }
    loadSessions();
  }, [storageKey, storageKeySessionKey, loadSessions, onSessionChange]);

  return {
    sessions,
    activeSessionId,
    activeSessionKey,
    activeSession,
    sessionsLoading,
    selectSession,
    createNewSession,
    updateSession,
    deleteSession,
    loadSessions,
    setActiveSessionId,
    setActiveSessionKey,
  };
}
