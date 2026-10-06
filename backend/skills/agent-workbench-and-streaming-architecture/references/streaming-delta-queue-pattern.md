# Adaptive Streaming Delta Queue — Implementation Pattern

## Architecture

```
WebSocket transcript_partial → appendDelta(delta) → ref accumulator → adaptive setTimeout → flush → setState → render
```

## Hook Shape (`useStreamingQueue`)

```typescript
const FLUSH_MS = 33;        // ~30fps baseline
const MAX_FLUSH_MS = 250;   // never slower than ~4 updates/sec

function useStreamingQueue(onFlush: (text: string) => void) {
  const accumulatedRef = useRef('');
  const flushHandleRef = useRef<number | null>(null);
  const lastFlushCostRef = useRef(0);

  const flush = useCallback(() => {
    flushHandleRef.current = null;
    const start = performance.now();
    onFlush(accumulatedRef.current);
    lastFlushCostRef.current = performance.now() - start;
  }, [flush]);

  const scheduleFlush = useCallback(() => {
    if (flushHandleRef.current !== null) return;
    const adaptiveFloor = Math.min(
      Math.max(FLUSH_MS, lastFlushCostRef.current * 3),
      MAX_FLUSH_MS
    );
    flushHandleRef.current = window.setTimeout(flush, adaptiveFloor);
  }, [flush]);

  return {
    appendDelta: (d: string) => { accumulatedRef.current += d; scheduleFlush(); },
    setAccumulated: (t: string) => { accumulatedRef.current = t; scheduleFlush(); },
    reset: () => { accumulatedRef.current = ''; clearTimeout(flushHandleRef.current!); },
    flushNow: () => { clearTimeout(flushHandleRef.current!); flush(); },
  };
}
```

## Integration in Page Client

In the `handleTranscript` callback, add a fast-path BEFORE the main `setTranscript`:

```typescript
// Streaming fast-path: bypass full setTranscript machinery
if (isPartial && payloadIsStreaming && speaker === 'output' && !visualType) {
  if (delta) streamAppendDelta(delta);
  else streamSetAccumulated(text);
  return;
}

// Final message: flush pending queue
if (!isPartial && !payloadIsStreaming) {
  streamFlushNow();
  streamReset();
}
```

The flush callback finds the last output item in the current turn and updates it in-place.

## Incremental Block Cache Shape

Two maps:
- `exactCache: Map<string, BlockToken[]>` (128 entries, LRU eviction)
- `appendCache: {blocks, text}[]` (4 entries, FIFO)

On parse:
1. Check exact cache → return same array identity
2. Check if text starts with any appendCache entry's text → reuse settled blocks, re-lex only suffix
3. Fall through to full parse

After parse, update both caches.

## Key Pitfall: Timer vs requestAnimationFrame

Use `setTimeout`, never `requestAnimationFrame`. Chromium suspends rAF for hidden/minimized/background windows and Electron renderers. A timer guarantees delivery. The adaptive floor (3× cost) provides the same frame-budget awareness that rAF would.
