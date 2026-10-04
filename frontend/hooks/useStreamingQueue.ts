/**
 * Adaptive streaming delta queue — coalesces incoming deltas and flushes
 * to React state at ~30fps with adaptive floor scaling.
 * 
 * Pattern: Delta Queue (ref-based coalescing) → Adaptive Timer Flush → State Update
 * 
 * This prevents high-frequency WebSocket messages (30-100+ tokens/sec from fast LLMs)
 * from each triggering an individual React state update + full markdown re-parse.
 */
import { useCallback, useEffect, useRef } from "react";

const FLUSH_MS = 33;        // ~30fps baseline
const MAX_FLUSH_MS = 250;   // never slower than ~4 updates/sec

export function useStreamingQueue(
  onFlush: (accumulatedText: string) => void
) {
  const accumulatedRef = useRef("");
  const flushHandleRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastFlushAtRef = useRef(0);
  const lastFlushCostRef = useRef(0);
  const activeRef = useRef(false);

  const flush = useCallback(() => {
    flushHandleRef.current = null;
    const start = performance.now();
    lastFlushAtRef.current = start;
    onFlush(accumulatedRef.current);
    lastFlushCostRef.current = performance.now() - start;
  }, [onFlush]);

  const scheduleFlush = useCallback(() => {
    if (flushHandleRef.current !== null) return; // already scheduled

    const sinceLast = performance.now() - lastFlushAtRef.current;
    // Adaptive floor: scales to 3x measured flush cost to keep thread ~75% idle
    const adaptiveFloor = Math.min(
      Math.max(FLUSH_MS, lastFlushCostRef.current * 3),
      MAX_FLUSH_MS
    );

    flushHandleRef.current = setTimeout(
      flush,
      Math.max(0, adaptiveFloor - sinceLast)
    );
  }, [flush]);

  const appendDelta = useCallback((delta: string) => {
    accumulatedRef.current += delta;
    activeRef.current = true;
    scheduleFlush();
  }, [scheduleFlush]);

  const setAccumulated = useCallback((text: string) => {
    // For fallback: set the full accumulated text directly (when only msg.text is available)
    accumulatedRef.current = text;
    activeRef.current = true;
    scheduleFlush();
  }, [scheduleFlush]);

  const reset = useCallback(() => {
    accumulatedRef.current = "";
    activeRef.current = false;
    if (flushHandleRef.current !== null) {
      clearTimeout(flushHandleRef.current);
      flushHandleRef.current = null;
    }
  }, []);

  const flushNow = useCallback(() => {
    if (flushHandleRef.current !== null) {
      clearTimeout(flushHandleRef.current);
      flushHandleRef.current = null;
    }
    if (activeRef.current) {
      flush();
      activeRef.current = false;
    }
  }, [flush]);

  // Flush on visibility change (tab comes back to foreground)
  useEffect(() => {
    const handler = () => {
      if (document.visibilityState === "visible" && flushHandleRef.current !== null) {
        clearTimeout(flushHandleRef.current);
        flushHandleRef.current = null;
        flush();
      }
    };
    document.addEventListener("visibilitychange", handler);
    return () => document.removeEventListener("visibilitychange", handler);
  }, [flush]);

  // Cleanup on unmount
  useEffect(() => () => {
    if (flushHandleRef.current !== null) clearTimeout(flushHandleRef.current);
  }, []);

  return { appendDelta, setAccumulated, reset, flushNow };
}
