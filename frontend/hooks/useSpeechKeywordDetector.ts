"use client";

/**
 * useSpeechKeywordDetector.ts
 *
 * Uses the browser's built-in Web Speech API (SpeechRecognition) to detect
 * keyword commands (like "nari dong", "hibur gw") in near real-time (~300ms),
 * BEFORE Gemini Live API has a chance to process and respond.
 *
 * This runs as a PARALLEL listener alongside Gemini — it does NOT replace
 * the existing microphone stream. When a keyword is detected, it fires
 * onKeywordDetected() so the caller can immediately block Gemini and trigger
 * the appropriate action.
 */

import { useRef, useCallback, useEffect } from "react";
import { isDanceKeyword } from "@/lib/danceDetector";

// ── Types ─────────────────────────────────────────────────────────────────────

export type KeywordType = "dance";

export interface KeywordEvent {
  type: KeywordType;
  transcript: string;
}

interface UseSpeechKeywordDetectorOptions {
  enabled?: boolean;
  lang?: string;
  onKeywordDetected?: (event: KeywordEvent) => void;
  onSpeechTranscript?: (transcript: string, isFinal: boolean) => void;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useSpeechKeywordDetector({
  enabled = true,
  lang = "id-ID",
  onKeywordDetected,
  onSpeechTranscript,
}: UseSpeechKeywordDetectorOptions = {}) {
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const isRunningRef = useRef(false);
  const callbackRef = useRef(onKeywordDetected);
  const onSpeechTranscriptRef = useRef(onSpeechTranscript);
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep callback ref fresh without restarting recognition
  useEffect(() => {
    callbackRef.current = onKeywordDetected;
    onSpeechTranscriptRef.current = onSpeechTranscript;
  }, [onKeywordDetected, onSpeechTranscript]);

  const stop = useCallback(() => {
    isRunningRef.current = false;
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
    try {
      recognitionRef.current?.abort();
    } catch {
      // ignore
    }
  }, []);

  const start = useCallback(() => {
    if (typeof window === "undefined") return;

  const SpeechRecognitionCtor: new () => SpeechRecognition =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;

    if (!SpeechRecognitionCtor) {
      console.warn("[KeywordDetector] Web Speech API not supported in this browser.");
      return;
    }

    if (isRunningRef.current) return;
    isRunningRef.current = true;

    const recognition: SpeechRecognition = new SpeechRecognitionCtor();
    recognitionRef.current = recognition;

    recognition.lang = lang;
    recognition.continuous = true;    // keep listening without stopping
    recognition.interimResults = true; // fire on partial results for speed
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let currentSegment = "";
      let isFinalResult = false;
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0]?.transcript || "";
        if (result.isFinal) isFinalResult = true;
        if (transcript.trim()) {
          currentSegment = currentSegment ? `${currentSegment} ${transcript.trim()}` : transcript.trim();
        }
      }

      if (currentSegment.trim()) {
        onSpeechTranscriptRef.current?.(currentSegment.trim(), isFinalResult);

        if (isDanceKeyword(currentSegment)) {
          console.log(
            `[KeywordDetector] 🎯 DANCE keyword detected (${isFinalResult ? "final" : "interim"}): "${currentSegment}"`
          );
          callbackRef.current?.({ type: "dance", transcript: currentSegment });
        }
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "no-speech" || event.error === "audio-capture") {
        scheduleRestart();
        return;
      }
      if (event.error === "aborted" || event.error === "not-allowed") {
        isRunningRef.current = false;
        return;
      }
      console.warn("[KeywordDetector] SpeechRecognition error:", event.error);
      scheduleRestart();
    };

    recognition.onend = () => {
      // Auto-restart to keep continuous listening
      if (isRunningRef.current) {
        scheduleRestart();
      }
    };

    try {
      recognition.start();
      console.log("[KeywordDetector] ✅ Web Speech API keyword detector started");
    } catch (e) {
      console.warn("[KeywordDetector] Failed to start:", e);
    }
  }, [lang]);

  function scheduleRestart() {
    if (!isRunningRef.current) return;
    if (restartTimerRef.current) return;
    restartTimerRef.current = setTimeout(() => {
      restartTimerRef.current = null;
      if (isRunningRef.current) {
        try {
          recognitionRef.current?.start();
        } catch {
          // If start() fails (already running), just wait for onend
        }
      }
    }, 300);
  }

  // Auto-start when enabled
  useEffect(() => {
    if (enabled) {
      start();
    } else {
      stop();
    }
    return () => stop();
  }, [enabled, start, stop]);

  return { start, stop };
}
