"use client";

import { useRef, useCallback, useState, useEffect } from "react";

/**
 * Hook for playing PCM16 audio chunks from the AI in real-time.
 * Uses Web Audio API to queue and play audio buffers sequentially.
 * Handles browser autoplay policy by queuing chunks until first user gesture.
 */
export function useAudioPlayer() {
  const audioContextRef = useRef<AudioContext | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const isPlayingRef = useRef(false);
  const nextPlayTimeRef = useRef(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const analyserDataRef = useRef<Float32Array | null>(null);
  const activeSourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const stopTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Autoplay policy handling
  const hasInteractionRef = useRef(false);
  const pendingQueueRef = useRef<{ buffer: ArrayBuffer; sampleRate: number }[]>([]);

  // Jitter buffer lead-time (150ms) ensures incoming network chunks arrive before current chunk finishes
  const JITTER_LEAD_TIME = 0.15;

  // Internal: get or create AudioContext
  const getCtx = useCallback((): AudioContext => {
    if (!audioContextRef.current || audioContextRef.current.state === "closed") {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.4;
      analyser.connect(ctx.destination);
      analyserRef.current = analyser;
      analyserDataRef.current = new Float32Array(analyser.fftSize);
      audioContextRef.current = ctx;
    }
    return audioContextRef.current;
  }, []);

  // Internal: decode and schedule one PCM16 chunk
  const scheduleChunk = useCallback(
    async (pcm16Buffer: ArrayBuffer, sampleRate: number) => {
      try {
        const ctx = getCtx();
        if (ctx.state === "suspended") await ctx.resume();

        const sampleCount = Math.floor(pcm16Buffer.byteLength / 2);
        if (sampleCount === 0) return;
        const pcm16 = new Int16Array(pcm16Buffer, 0, sampleCount);
        const float32 = new Float32Array(sampleCount);
        for (let i = 0; i < pcm16.length; i++) {
          float32[i] = pcm16[i] / 32768.0;
        }

        const audioBuffer = ctx.createBuffer(1, float32.length, sampleRate);
        audioBuffer.getChannelData(0).set(float32);

        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(analyserRef.current ?? ctx.destination);

        const now = ctx.currentTime;
        let startTime: number;

        // If starting from idle or if the previous buffer already expired, buffer slightly ahead
        if (nextPlayTimeRef.current < now + 0.005) {
          startTime = now + JITTER_LEAD_TIME;
        } else {
          // Seamless contiguous playback
          startTime = nextPlayTimeRef.current;
        }

        source.start(startTime);
        nextPlayTimeRef.current = startTime + audioBuffer.duration;
        activeSourcesRef.current.add(source);

        // Cancel any pending stop timeout since new audio is streaming in
        if (stopTimeoutRef.current) {
          clearTimeout(stopTimeoutRef.current);
          stopTimeoutRef.current = null;
        }

        if (!isPlayingRef.current) {
          isPlayingRef.current = true;
          setIsPlaying(true);
        }

        source.onended = () => {
          activeSourcesRef.current.delete(source);
          try {
            source.disconnect();
          } catch {}

          // Only mark playback finished if no upcoming chunks are scheduled
          if (ctx.currentTime >= nextPlayTimeRef.current - 0.02) {
            if (stopTimeoutRef.current) clearTimeout(stopTimeoutRef.current);
            // 120ms debounce prevents flickering between rapid consecutive chunks
            stopTimeoutRef.current = setTimeout(() => {
              if (activeSourcesRef.current.size === 0 && ctx.currentTime >= nextPlayTimeRef.current - 0.01) {
                isPlayingRef.current = false;
                setIsPlaying(false);
              }
              stopTimeoutRef.current = null;
            }, 120);
          }
        };
      } catch (e) {
        console.error("[AudioPlayer] scheduleChunk error:", e);
      }
    },
    [getCtx]
  );

  // Unlock AudioContext on first user gesture, then drain pending queue
  useEffect(() => {
    const unlock = async () => {
      if (hasInteractionRef.current) return;
      hasInteractionRef.current = true;

      const ctx = getCtx();
      if (ctx.state === "suspended") {
        await ctx.resume();
        console.log("[AudioPlayer] Unlocked by user gesture");
      }

      // Drain chunks queued before interaction
      const queued = pendingQueueRef.current.splice(0);
      for (const { buffer, sampleRate } of queued) {
        await scheduleChunk(buffer, sampleRate);
      }
    };

    window.addEventListener("click", unlock, { once: true });
    window.addEventListener("keydown", unlock, { once: true });
    window.addEventListener("touchstart", unlock, { once: true });
    return () => {
      window.removeEventListener("click", unlock);
      window.removeEventListener("keydown", unlock);
      window.removeEventListener("touchstart", unlock);
    };
  }, [getCtx, scheduleChunk]);

  /** Public: play a PCM16 buffer. Queues if AudioContext not yet unlocked. */
  const playAudioChunk = useCallback(
    async (pcm16Buffer: ArrayBuffer, sampleRate = 24000) => {
      const ctx = getCtx();
      if ((ctx.state as string) === "suspended") {
        try {
          await ctx.resume();
        } catch {
          // browser autoplay blocked until gesture
        }
      }

      if ((ctx.state as string) === "running") {
        hasInteractionRef.current = true;
        // Drain any pending queue first
        const queued = pendingQueueRef.current.splice(0);
        for (const q of queued) {
          await scheduleChunk(q.buffer, q.sampleRate);
        }
        await scheduleChunk(pcm16Buffer, sampleRate);
        return;
      }

      if (!hasInteractionRef.current) {
        if (pendingQueueRef.current.length < 50) {
          pendingQueueRef.current.push({ buffer: pcm16Buffer, sampleRate });
        }
        return;
      }
      await scheduleChunk(pcm16Buffer, sampleRate);
    },
    [getCtx, scheduleChunk]
  );

  /** RMS intensity of current playback for lip-sync (0–1) */
  const getIntensity = useCallback((): number => {
    if (!isPlayingRef.current) return 0;
    const analyser = analyserRef.current;
    const data = analyserDataRef.current;
    if (!analyser || !data) return 0;
    analyser.getFloatTimeDomainData(data as Float32Array<ArrayBuffer>);
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
    return Math.sqrt(sum / data.length);
  }, []);

  /** Immediately stop and discard all queued/playing audio */
  const stopAudio = useCallback(() => {
    if (stopTimeoutRef.current) {
      clearTimeout(stopTimeoutRef.current);
      stopTimeoutRef.current = null;
    }

    // Stop all actively playing / scheduled Web Audio sources
    activeSourcesRef.current.forEach((src) => {
      try {
        src.stop();
        src.disconnect();
      } catch {
        // already stopped
      }
    });
    activeSourcesRef.current.clear();

    const ctx = audioContextRef.current;
    if (ctx && ctx.state !== "closed") {
      nextPlayTimeRef.current = ctx.currentTime;
    } else {
      nextPlayTimeRef.current = 0;
    }

    pendingQueueRef.current = [];
    isPlayingRef.current = false;
    setIsPlaying(false);
  }, []);

  /** Force-unlock AudioContext immediately (call from a real user gesture) */
  const forceUnlock = useCallback(async () => {
    hasInteractionRef.current = true;
    try {
      const ctx = getCtx();
      if (ctx.state === "suspended") {
        await ctx.resume();
        console.log("[AudioPlayer] Force-unlocked and resumed AudioContext via user interaction");
      }
      // Drain any queued chunks
      const queued = pendingQueueRef.current.splice(0);
      for (const { buffer, sampleRate } of queued) {
        await scheduleChunk(buffer, sampleRate);
      }
    } catch (e) {
      console.warn("[AudioPlayer] forceUnlock error:", e);
    }
  }, [getCtx, scheduleChunk]);

  return { isPlaying, playAudioChunk, getIntensity, stopAudio, forceUnlock };
}
