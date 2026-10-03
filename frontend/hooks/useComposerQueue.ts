"use client";

import { useState, useCallback, useEffect, useRef } from "react";

export interface QueuedPromptItem {
  id: string;
  text: string;
  agentMode: "plan" | "build";
  enqueuedAt: number;
}

export interface UseComposerQueueOptions {
  activeSessionId: number | null;
  isBusy: boolean;
  onSend: (text: string, mode: "plan" | "build") => void;
  onSteer?: (steerText: string) => void;
}

/**
 * useComposerQueue.ts — Anara Sequential Prompt Queue & Auto-Drain Hook
 *
 * Implements client-side turn sequencing:
 * 1. Queueing while busy: If user enters a prompt while the model is executing,
 *    it queues seamlessly rather than blocking input.
 * 2. Auto-Drain: Automatically pops and sends the next prompt when the model returns to idle.
 * 3. Steer integration: If user signals a mid-turn redirection, routes directly to onSteer.
 */
export function useComposerQueue({
  activeSessionId,
  isBusy,
  onSend,
  onSteer,
}: UseComposerQueueOptions) {
  const [queueBySession, setQueueBySession] = useState<Record<string, QueuedPromptItem[]>>({});
  const isBusyRef = useRef(isBusy);
  isBusyRef.current = isBusy;

  const currentSessionKey = activeSessionId ? String(activeSessionId) : "global";
  const currentQueue = queueBySession[currentSessionKey] || [];

  const enqueue = useCallback(
    (text: string, agentMode: "plan" | "build" = "build") => {
      const item: QueuedPromptItem = {
        id: `q_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        text: text.trim(),
        agentMode,
        enqueuedAt: Date.now(),
      };
      setQueueBySession((prev) => ({
        ...prev,
        [currentSessionKey]: [...(prev[currentSessionKey] || []), item],
      }));
    },
    [currentSessionKey]
  );

  const removeQueued = useCallback(
    (id: string) => {
      setQueueBySession((prev) => ({
        ...prev,
        [currentSessionKey]: (prev[currentSessionKey] || []).filter((q) => q.id !== id),
      }));
    },
    [currentSessionKey]
  );

  const clearQueue = useCallback(() => {
    setQueueBySession((prev) => ({
      ...prev,
      [currentSessionKey]: [],
    }));
  }, [currentSessionKey]);

  // ── Auto-Drain Engine: fires when model goes from busy -> idle ──
  const prevBusyRef = useRef(isBusy);
  useEffect(() => {
    const wasBusy = prevBusyRef.current;
    prevBusyRef.current = isBusy;

    // Transition: was busy, now idle
    if (wasBusy && !isBusy) {
      const queue = queueBySession[currentSessionKey] || [];
      if (queue.length > 0) {
        const [nextItem, ...remaining] = queue;
        // Schedule next execution on microtask to let UI settle
        setTimeout(() => {
          onSend(nextItem.text, nextItem.agentMode);
          setQueueBySession((prev) => ({
            ...prev,
            [currentSessionKey]: remaining,
          }));
        }, 120);
      }
    }
  }, [isBusy, currentSessionKey, queueBySession, onSend]);

  return {
    queuedItems: currentQueue,
    queuedCount: currentQueue.length,
    enqueue,
    removeQueued,
    clearQueue,
    isQueued: currentQueue.length > 0,
  };
}

export default useComposerQueue;
