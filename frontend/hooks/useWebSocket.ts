"use client";

import { useEffect, useRef, useCallback, useState } from "react";

export type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

// ── Emotion / Gesture types ──────────────────────────────────────────────────
export type EmotionType =
  | "neutral" | "happy" | "angry" | "sad" | "shy"
  | "thinking" | "empathetic" | "curious" | "enthusiastic" | "dance";

export type GestureType =
  | "idle" | "wave" | "talking" | "explaining"
  | "shy_movement" | "angry_pointing" | "think"
  | "joy" | "empathy" | "nod" | "shake" | "salute" | "question" | "sad";

export interface EmotionState {
  emotion: EmotionType;
  gesture: GestureType;
  intensity: number;
}

export interface AcousticEmotionPayload {
  emotion: "sad" | "angry" | "happy" | "neutral";
  confidence: number;
  pitch_hz: number;
  rms: number;
  spectral_centroid_hz: number;
  tone_description: string;
}

export interface WebSocketMessage {
  type: "audio_chunk" | "transcript" | "interrupted" | "turn_complete" | "error" | "emotion_update" | "acoustic_emotion" | "brain_sync" | "speaker_identified" | "hud_timer";
  data?: any;
  event?: string;
  name?: string | null;
  speaker?: "input" | "output";
  intensity?: number;
  sampleRate?: number;
  durationSeconds?: number;
  label?: string;
  emotion?: EmotionType;
  gesture?: GestureType;
  visualType?: "image" | "weather" | "code" | "system_hud" | "knowledge_card" | "todo_list" | "none";
  imageUrl?: string;
  imagePrompt?: string;
  imageTitle?: string;
  sourceDomain?: string;
  sourceUrl?: string;
  weatherData?: any;
  codeData?: any;
  systemHudData?: any;
  knowledgeCardData?: any;
  todoData?: any;
  images?: any[];
  mediaType?: "image" | "hud";
}

export interface TranscriptPayload {
  text: string;
  speaker: "input" | "output";
  visualType?: "image" | "weather" | "code" | "system_hud" | "knowledge_card" | "todo_list" | "none";
  imageUrl?: string;
  imagePrompt?: string;
  imageTitle?: string;
  sourceDomain?: string;
  sourceUrl?: string;
  images?: any[];
  weatherData?: any;
  codeData?: any;
  systemHudData?: any;
  knowledgeCardData?: any;
  todoData?: any;
  mediaType?: "image" | "hud";
}

interface UseWebSocketOptions {
  url: string;
  onAudioChunk?: (audioData: ArrayBuffer, intensity: number, sampleRate: number) => void;
  onTranscript?: (payload: TranscriptPayload | string, speaker?: "input" | "output") => void;
  onInterrupted?: () => void;
  onTurnComplete?: () => void;
  onError?: (message: string) => void;
  onEmotionUpdate?: (state: EmotionState) => void;
  onAcousticEmotion?: (data: AcousticEmotionPayload) => void;
  onSpeakerIdentified?: (name: string | null) => void;
}

export function useWebSocket({
  url,
  onAudioChunk,
  onTranscript,
  onInterrupted,
  onTurnComplete,
  onError,
  onEmotionUpdate,
  onAcousticEmotion,
  onSpeakerIdentified,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isIntentionalClose = useRef(false);
  const retryCountRef = useRef(0);
  const MAX_RETRY_DELAY_MS = 10000;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    setStatus("connecting");
    isIntentionalClose.current = false;

    try {
      console.log(`[WebSocket] Connecting to ${url} ...`);
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        retryCountRef.current = 0;
        setStatus("connected");
        console.log("[WebSocket] Connected to", url);
      };

      ws.onmessage = (event) => {
        if (typeof event.data === "string") {
          try {
            const msg: WebSocketMessage = JSON.parse(event.data);

            switch (msg.type) {
              case "audio_chunk":
                if (msg.data && onAudioChunk) {
                  try {
                    const binary = atob(msg.data);
                    const buffer = new ArrayBuffer(binary.length);
                    const view = new Uint8Array(buffer);
                    for (let i = 0; i < binary.length; i++) {
                      view[i] = binary.charCodeAt(i);
                    }
                    onAudioChunk(buffer, msg.intensity ?? 0, msg.sampleRate ?? 24000);
                  } catch (decodeErr) {
                    console.error("[WS] Audio decode error:", decodeErr);
                  }
                }
                break;

              case "transcript":
                console.log(`[WS] transcript received: speaker="${msg.speaker}" visualType="${msg.visualType}" data="${msg.data?.substring(0, 60)}" image="${msg.imageUrl ? 'yes' : 'no'}"`);
                if (msg.data && onTranscript) {
                  onTranscript({
                    text: msg.data,
                    speaker: msg.speaker ?? "output",
                    visualType: msg.visualType,
                    imageUrl: msg.imageUrl,
                    imagePrompt: msg.imagePrompt,
                    imageTitle: msg.imageTitle,
                    sourceDomain: msg.sourceDomain,
                    sourceUrl: msg.sourceUrl,
                    weatherData: msg.weatherData,
                    codeData: msg.codeData,
                    systemHudData: msg.systemHudData,
                    knowledgeCardData: msg.knowledgeCardData,
                    todoData: msg.todoData,
                    images: msg.images,
                    mediaType: msg.mediaType,
                  });
                }
                break;


              case "interrupted":
                onInterrupted?.();
                break;

              case "turn_complete":
                onTurnComplete?.();
                break;

              case "emotion_update":
                if (onEmotionUpdate && msg.emotion && msg.gesture) {
                  onEmotionUpdate({
                    emotion: msg.emotion,
                    gesture: msg.gesture,
                    intensity: msg.intensity ?? 0.7,
                  });
                  console.log(`[Emotion] ${msg.emotion} | ${msg.gesture} (${msg.intensity})`);
                }
                break;

              case "acoustic_emotion":
                if (onAcousticEmotion && msg.data) {
                  onAcousticEmotion(msg.data);
                  console.log(`[Acoustic Tone SER] Emotion: ${msg.data.emotion} (${msg.data.tone_description})`);
                }
                break;

              case "speaker_identified":
                console.log(`[WS] speaker_identified: ${msg.name}`);
                onSpeakerIdentified?.(msg.name ?? null);
                if (typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "speaker_identified", name: msg.name } }));
                }
                break;

              case "hud_timer":
                if (typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("anara-hud-timer", { detail: { durationSeconds: msg.durationSeconds, label: msg.label } }));
                }
                if (onTranscript && msg.data) {
                  onTranscript(msg.data, msg.speaker ?? "output");
                }
                break;

              case "brain_sync":
                if (typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: msg }));
                }
                console.log(`[Brain Sync] Received SQLite live mutation: ${msg.event}`, msg.data);
                break;

              case "error":
                onError?.(msg.data ?? "Unknown server error");
                break;
            }
          } catch (e) {
            console.error("[WebSocket] JSON parse error:", e);
          }
        }
      };

      ws.onerror = () => {
        const msg = `Cannot connect to backend at ${url}. Make sure the FastAPI server is running (python main.py).`;
        console.warn("[WebSocket] Connection error —", msg);
        setStatus("error");
      };

      ws.onclose = (event) => {
        setStatus("disconnected");
        wsRef.current = null;

        if (!isIntentionalClose.current) {
          const delay = Math.min(2000 * Math.pow(1.5, retryCountRef.current), MAX_RETRY_DELAY_MS);
          retryCountRef.current += 1;
          console.log(`[WebSocket] Disconnected (code ${event.code}). Retrying in ${(delay / 1000).toFixed(1)}s... (attempt ${retryCountRef.current})`);
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else {
          retryCountRef.current = 0;
        }
      };

      wsRef.current = ws;
    } catch (e) {
      console.error("[WebSocket] Failed to connect:", e);
      setStatus("error");
    }
  }, [url, onAudioChunk, onTranscript, onInterrupted, onTurnComplete, onError, onEmotionUpdate]);

  const disconnect = useCallback(() => {
    isIntentionalClose.current = true;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("disconnected");
  }, []);

  const sendBinary = useCallback((data: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  const sendJSON = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const sendInterrupt = useCallback(() => {
    sendJSON({ type: "interrupt" });
  }, [sendJSON]);

  const sendText = useCallback((text: string) => {
    sendJSON({ type: "text_input", text });
  }, [sendJSON]);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { status, connect, disconnect, sendBinary, sendJSON, sendInterrupt, sendText };
}
