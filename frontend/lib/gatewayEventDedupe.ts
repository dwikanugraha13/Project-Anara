"use client";

/**
 * gatewayEventDedupe.ts — Anara Cross-Socket Event Deduplication Engine
 *
 * Prevents duplicated events, duplicate transcript tokens, and stuttering during
 * rapid network reconnects, dual-pane session views, or multi-socket fan-outs.
 * Uses an LRU cache with a sliding time window (30 seconds).
 */

export const DUPLICATE_WINDOW_MS = 30_000;
const SEQS_PER_SESSION_MAX = 2048;
const SESSIONS_MAX = 256;

interface SessionSeen {
  seen: Map<string | number, number>;
}

export interface GatewayEventDedupe {
  admit(sessionId: string | number | undefined, eventKey: string | number | undefined, now?: number): boolean;
  clear(sessionId?: string | number): void;
}

export function createGatewayEventDedupe(): GatewayEventDedupe {
  const sessions = new Map<string, SessionSeen>();

  const touch = (key: string): SessionSeen => {
    let entry = sessions.get(key);
    if (entry) {
      sessions.delete(key);
    } else {
      entry = { seen: new Map() };
    }
    sessions.set(key, entry);

    while (sessions.size > SESSIONS_MAX) {
      const oldest = sessions.keys().next().value;
      if (oldest === undefined) break;
      sessions.delete(oldest);
    }

    return entry;
  };

  return {
    admit(sessionId, eventKey, now = Date.now()) {
      if (eventKey === undefined || eventKey === null) {
        return true;
      }

      const sKey = sessionId ? String(sessionId) : "global";
      const entry = touch(sKey);
      const firstSeenAt = entry.seen.get(eventKey);

      if (firstSeenAt !== undefined && now - firstSeenAt < DUPLICATE_WINDOW_MS) {
        return false;
      }

      entry.seen.delete(eventKey);
      entry.seen.set(eventKey, now);

      while (entry.seen.size > SEQS_PER_SESSION_MAX) {
        const oldest = entry.seen.keys().next().value;
        if (oldest === undefined) break;
        entry.seen.delete(oldest);
      }

      return true;
    },

    clear(sessionId) {
      if (sessionId) {
        sessions.delete(String(sessionId));
      } else {
        sessions.clear();
      }
    },
  };
}

export default createGatewayEventDedupe;
