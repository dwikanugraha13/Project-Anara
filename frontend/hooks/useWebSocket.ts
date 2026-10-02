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

export interface TokenUsagePayload {
  modelId?: string;
  model_id?: string;
  provider?: string;
  promptTokens: number;
  prompt_tokens?: number;
  completionTokens: number;
  completion_tokens?: number;
  totalTokens: number;
  total_tokens?: number;
  contextLimit: number;
  context_limit?: number;
  contextRemaining: number;
  context_remaining?: number;
  source?: "actual" | "estimated";
  tools_used?: string[];
  toolsUsed?: string[];
}

export interface ToolProgressPayload {
  toolName: string;
  status: "running" | "done" | "error" | string;
  summary?: string;
  icon?: string;
  detail?: string;
  rawResult?: string;
  raw_result?: string;
}

export interface WebSocketMessage {
  type: "audio_chunk" | "transcript" | "transcript_partial" | "token_usage" | "tool_progress" | "plan_pending" | "need_approval" | "interrupted" | "turn_complete" | "error" | "emotion_update" | "acoustic_emotion" | "brain_sync" | "speaker_identified" | "hud_timer" | "hud_visual" | "media_play" | "media_control" | "proactive_message" | "session_switched" | "session_id_sync" | "agent_action" | "agent_action_start" | "agent_action_complete" | "agent_thinking" | "interactive_question" | "workspace_file_uploaded" | "workspace_folder_imported" | "workspace_file_created";
  data?: any;
  event?: string;
  name?: string | null;
  speaker?: "input" | "output";
  intensity?: number;
  sampleRate?: number;
  durationSeconds?: number;
  label?: string;
  alarmKind?: "timer" | "alarm";
  soundVariant?: "gentle" | "urgent" | "notify";
  targetTime?: string | null;
  kind?: "music" | "video";
  videoId?: string;
  title?: string;
  channel?: string;
  thumbnail?: string;
  duration?: string;
  queue?: MediaTrack[];
  playlistName?: string;
  playlistIndex?: number;
  question_id?: string;
  questions?: InteractiveQuestionItem[];
  playlistTotal?: number;
  playlistTracks?: MediaTrack[];
  action?: "stop" | "pause" | "resume" | "next" | "prev";
  todo?: { id?: number; title?: string; due?: string; content?: string } | null;
  project?: { id?: number; name?: string; days?: number } | null;
  todos?: string[] | null;
  roster?: string[] | null;
  previous?: string | null;
  sessionId?: number | string;
  session_id?: number | string;
  sessionKey?: string;
  session_key?: string;
  session_type?: "chat" | "code";
  sessionType?: "chat" | "code";
  messages?: SessionMessage[];
  eventType?: string;
  toolName?: string;
  tool_name?: string;
  actionTitle?: string;
  action_title?: string;
  detail?: string;
  summary?: string;
  rawResult?: string;
  raw_result?: string;
  file_path?: string;
  filename?: string;
  content?: string;
  size_kb?: number;
  checkpoint_id?: string;
  added?: number;
  deleted?: number;
  icon?: string;
  emotion?: EmotionType;
  gesture?: GestureType;
  visualType?: "image" | "weather" | "code" | "system_hud" | "knowledge_card" | "todo_list" | "briefing" | "agent_action" | "document_viewer" | "folder_workspace" | "plan_card" | "none";
  imageUrl?: string;
  imagePrompt?: string;
  imageTitle?: string;
  sourceDomain?: string;
  sourceUrl?: string;
  weatherData?: any;
  codeData?: any;
  systemHudData?: any;
  knowledgeCardData?: any;
  briefingData?: any;
  todoData?: any;
  agentActionData?: any;
  documentViewerData?: any;
  workspaceFolderData?: any;
  planData?: any;
  images?: any[];
  mediaType?: "image" | "hud";
  text?: string;
  delta?: string;
  isPartial?: boolean;
  is_final?: boolean;
  agent_mode?: "plan" | "build";
  agentMode?: "plan" | "build";
  model?: string;
  model_id?: string;
  modelId?: string;
  duration_text?: string;
  durationText?: string;
  token_usage?: TokenUsagePayload;
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
  contextLimit?: number;
  contextRemaining?: number;
  provider?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  context_limit?: number;
  context_remaining?: number;
  source?: "actual" | "estimated";
  tools_used?: string[];
  toolsUsed?: string[];
  status?: string;
}

export interface TranscriptPayload {
  text: string;
  delta?: string;
  speaker: "input" | "output";
  visualType?: "image" | "weather" | "code" | "system_hud" | "knowledge_card" | "todo_list" | "briefing" | "agent_action" | "document_viewer" | "folder_workspace" | "plan_card" | "none";
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
  briefingData?: any;
  todoData?: any;
  agentActionData?: any;
  documentViewerData?: any;
  workspaceFolderData?: any;
  planData?: any;
  mediaType?: "image" | "hud";
  isPartial?: boolean;
  agentMode?: "plan" | "build";
  modelId?: string;
  durationText?: string;
  tokenUsage?: TokenUsagePayload;
  toolsUsed?: string[];
  isStreaming?: boolean;
}

export interface HudVisualPayload {
  text: string;
  visualType: "image" | "weather" | "code" | "system_hud" | "knowledge_card" | "todo_list" | "briefing" | "agent_action" | "document_viewer" | "folder_workspace" | "plan_card" | "none";
  imageUrl?: string;
  imageTitle?: string;
  sourceDomain?: string;
  sourceUrl?: string;
  images?: any[];
  knowledgeCardData?: any;
  briefingData?: any;
  planData?: any;
  mediaType?: "image" | "hud";
}

/** A single playable YouTube track/video resolved by the backend Media Engine. */
export interface MediaTrack {
  videoId?: string;
  video_id?: string;
  title?: string;
  channel?: string;
  thumbnail?: string;
  duration?: string;
}

export interface MediaPlayPayload {
  kind: "music" | "video";
  videoId: string;
  title: string;
  channel?: string;
  thumbnail?: string;
  duration?: string;
  queue?: MediaTrack[];
  /** Present when the track is part of a saved playlist session. */
  playlistName?: string;
  playlistIndex?: number;
  playlistTotal?: number;
  playlistTracks?: MediaTrack[];
}

export type MediaControlAction = "stop" | "pause" | "resume" | "next" | "prev";

/** One stored dialogue turn returned when a chat session is reopened. */
export interface SessionMessage {
  id: number;
  speaker_name?: string | null;
  user_text?: string | null;
  ai_text?: string | null;
  media_type?: string | null;
  media_url?: string | null;
  visual_data?: any;
  created_at?: string;
}

export interface SessionSwitchedPayload {
  sessionId: number;
  sessionKey?: string | null;
  session_key?: string | null;
  sessionType?: "chat" | "code";
  session_type?: "chat" | "code";
  title?: string | null;
  messages: SessionMessage[];
}

export interface AgentActionPayload {
  eventType: "agent_action_start" | "agent_action_complete" | string;
  toolName?: string;
  actionTitle?: string;
  detail?: string;
  summary?: string;
  rawResult?: string;
  icon?: string;
}

/** Anara taking initiative: due reminder, contextual greeting, project follow-up. */
export interface ProactivePayload {
  kind: "due_reminder" | "greeting" | "follow_up" | "info";
  text: string;
  todo?: { id?: number; title?: string; due?: string; content?: string } | null;
  project?: { id?: number; name?: string; days?: number } | null;
  todos?: string[] | null;
}

export interface InteractiveQuestionItem {
  header: string;
  question: string;
  multiple?: boolean;
  options: Array<{
    label: string;
    description: string;
  }>;
}

export interface InteractiveQuestionPayload {
  question_id: string;
  questions: InteractiveQuestionItem[];
}

// ── Reconnect Backoff & Liveness Constants (Anara Desktop / Anara CLI standards) ──
export interface ReconnectBackoffOptions {
  baseDelayMs?: number;
  capMs?: number;
  jitter?: boolean;
}

const DEFAULT_BASE_DELAY_MS = 500;
const DEFAULT_CAP_MS = 15000;
const RECONNECT_STABLE_OPEN_MS = 5000;
const PING_INTERVAL_MS = 30000;
const HEARTBEAT_TIMEOUT_MS = 65000;
const MAX_MESSAGE_QUEUE_SIZE = 100;

/**
 * Exponential reconnect backoff with full jitter (AWS / Anara Desktop standard).
 * Spreads retries evenly across [0, ceiling) to prevent fleet reconnect stampedes.
 */
export function reconnectBackoffDelayMs(attempt: number, options: ReconnectBackoffOptions = {}): number {
  const baseDelayMs = options.baseDelayMs ?? DEFAULT_BASE_DELAY_MS;
  const capMs = options.capMs ?? DEFAULT_CAP_MS;
  const exponent = Math.min(Math.max(0, Math.trunc(attempt)), 32);
  const ceiling = Math.min(capMs, baseDelayMs * 2 ** exponent);
  return options.jitter === false ? ceiling : Math.random() * ceiling;
}

interface UseWebSocketOptions {
  url: string;
  onAudioChunk?: (audioData: ArrayBuffer, intensity: number, sampleRate: number) => void;
  onTranscript?: (payload: TranscriptPayload | string, speaker?: "input" | "output") => void;
  onTokenUsage?: (payload: TokenUsagePayload) => void;
  onToolProgress?: (payload: ToolProgressPayload) => void;
  onInterrupted?: () => void;
  onTurnComplete?: () => void;
  onError?: (message: string) => void;
  onEmotionUpdate?: (state: EmotionState) => void;
  onAcousticEmotion?: (data: AcousticEmotionPayload) => void;
  onSpeakerIdentified?: (name: string | null, roster?: string[]) => void;
  onHudVisual?: (payload: HudVisualPayload) => void;
  onMediaPlay?: (payload: MediaPlayPayload) => void;
  onMediaControl?: (action: MediaControlAction) => void;
  onProactive?: (payload: ProactivePayload) => void;
  onSessionSwitched?: (payload: SessionSwitchedPayload) => void;
  onSessionIdSync?: (sessionId: number, sessionKey?: string) => void;
  onAgentAction?: (payload: AgentActionPayload) => void;
  onAgentThinking?: (text: string) => void;
  onInteractiveQuestion?: (payload: InteractiveQuestionPayload) => void;
  onPlanPending?: (payload: any) => void;
}

export function useWebSocket({
  url,
  onAudioChunk,
  onTranscript,
  onTokenUsage,
  onToolProgress,
  onInterrupted,
  onTurnComplete,
  onError,
  onEmotionUpdate,
  onAcousticEmotion,
  onSpeakerIdentified,
  onHudVisual,
  onMediaPlay,
  onMediaControl,
  onProactive,
  onSessionSwitched,
  onSessionIdSync,
  onAgentAction,
  onAgentThinking,
  onInteractiveQuestion,
  onPlanPending,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const connectTimeRef = useRef<number>(0);
  const lastActivityRef = useRef<number>(Date.now());
  const unansweredPingsRef = useRef<number>(0);
  const messageQueueRef = useRef<(string | ArrayBuffer)[]>([]);
  const isIntentionalClose = useRef(false);
  const retryCountRef = useRef(0);

  const callbacksRef = useRef({
    onAudioChunk,
    onTranscript,
    onTokenUsage,
    onToolProgress,
    onInterrupted,
    onTurnComplete,
    onError,
    onEmotionUpdate,
    onAcousticEmotion,
    onSpeakerIdentified,
    onHudVisual,
    onMediaPlay,
    onMediaControl,
    onProactive,
    onSessionSwitched,
    onSessionIdSync,
    onAgentAction,
    onAgentThinking,
    onInteractiveQuestion,
    onPlanPending,
  });

  useEffect(() => {
    callbacksRef.current = {
      onAudioChunk,
      onTranscript,
      onTokenUsage,
      onToolProgress,
      onInterrupted,
      onTurnComplete,
      onError,
      onEmotionUpdate,
      onAcousticEmotion,
      onSpeakerIdentified,
      onHudVisual,
      onMediaPlay,
      onMediaControl,
      onProactive,
      onSessionSwitched,
      onSessionIdSync,
      onAgentAction,
      onAgentThinking,
      onInteractiveQuestion,
      onPlanPending,
    };
  });

  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    // Clear any pending reconnect attempts to avoid racing duplicate sockets
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    setStatus("connecting");
    isIntentionalClose.current = false;

    try {
      console.log(`[WebSocket] Connecting to ${url} ...`);
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        if (wsRef.current !== ws) return;
        connectTimeRef.current = Date.now();
        lastActivityRef.current = Date.now();
        unansweredPingsRef.current = 0;
        setStatus("connected");
        console.log("[WebSocket] Connected to", url);

        // Safe message delivery queue drain
        while (messageQueueRef.current.length > 0 && ws.readyState === WebSocket.OPEN) {
          const queued = messageQueueRef.current.shift();
          if (!queued) break;
          try {
            ws.send(queued);
          } catch (err) {
            console.warn("[WebSocket] Error draining queued message, requeueing:", err);
            messageQueueRef.current.unshift(queued);
            break;
          }
        }

        // Heartbeat ping (every 30s) + liveness watchdog (Cloudflare / reverse-proxy keepalive)
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            const now = Date.now();
            // Liveness check: force-close dead/zombie sockets if silent past timeout
            if (unansweredPingsRef.current >= 2 || now - lastActivityRef.current > HEARTBEAT_TIMEOUT_MS) {
              console.warn(
                `[WebSocket] Heartbeat timeout: server silent for ${((now - lastActivityRef.current) / 1000).toFixed(1)}s (unanswered pings: ${unansweredPingsRef.current}). Force-closing zombie socket.`
              );
              try {
                ws.close(4000, "Heartbeat timeout");
              } catch {}
              return;
            }

            unansweredPingsRef.current += 1;
            try {
              ws.send(JSON.stringify({ type: "ping", timestamp: now }));
            } catch (err) {
              console.warn("[WebSocket] Ping heartbeat failed to send:", err);
            }
          }
        }, PING_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        if (wsRef.current !== ws) return;
        lastActivityRef.current = Date.now();
        unansweredPingsRef.current = 0;
        const cb = callbacksRef.current;

        // Direct raw binary ArrayBuffer audio chunk
        if (event.data instanceof ArrayBuffer) {
          cb.onAudioChunk?.(event.data, 0, 24000);
          return;
        }

        if (typeof event.data === "string") {
          try {
            const msg: WebSocketMessage = JSON.parse(event.data);

            // Handle transport keepalive
            if ((msg as any).type === "ping") {
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "pong", timestamp: Date.now() }));
              }
              return;
            }
            if ((msg as any).type === "pong") {
              return;
            }

            switch (msg.type) {
              case "audio_chunk":
                if (msg.data && cb.onAudioChunk) {
                  try {
                    const binary = atob(msg.data);
                    const buffer = new ArrayBuffer(binary.length);
                    const view = new Uint8Array(buffer);
                    for (let i = 0; i < binary.length; i++) {
                      view[i] = binary.charCodeAt(i);
                    }
                    cb.onAudioChunk(buffer, msg.intensity ?? 0, msg.sampleRate ?? 24000);
                  } catch (decodeErr) {
                    console.error("[WS] Audio decode error:", decodeErr);
                  }
                }
                break;

              case "transcript_partial": {
                // Zero-dropped chunks: support delta, text, or data without falsy-dropping empty strings
                const chunkText =
                  msg.text !== undefined
                    ? msg.text
                    : msg.delta !== undefined
                    ? msg.delta
                    : typeof msg.data === "string"
                    ? msg.data
                    : "";
                const delta = msg.delta !== undefined ? msg.delta : typeof msg.data === "string" ? msg.data : undefined;
                if (cb.onTranscript && (chunkText !== undefined || delta !== undefined)) {
                  cb.onTranscript({
                    text: chunkText,
                    delta,
                    speaker: msg.speaker ?? "output",
                    visualType: msg.visualType,
                    isPartial: true,
                    isStreaming: true,
                  });
                }
                break;
              }

              case "transcript": {
                const finalData = msg.data !== undefined ? msg.data : msg.text !== undefined ? msg.text : "";
                if (cb.onTranscript) {
                  cb.onTranscript({
                    text: typeof finalData === "string" ? finalData : JSON.stringify(finalData),
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
                    briefingData: msg.briefingData,
                    todoData: msg.todoData,
                    images: msg.images,
                    mediaType: msg.mediaType,
                    planData: msg.planData,
                    agentMode: msg.agent_mode || msg.agentMode,
                    modelId: msg.model || msg.model_id || msg.modelId,
                    durationText: msg.duration_text || msg.durationText,
                    isStreaming: false,
                    toolsUsed: msg.tools_used || msg.toolsUsed || msg.token_usage?.tools_used || msg.token_usage?.toolsUsed,
                    tokenUsage: msg.token_usage ? {
                      modelId: msg.token_usage.modelId || msg.token_usage.model_id,
                      provider: msg.token_usage.provider,
                      promptTokens: Number(msg.token_usage.promptTokens ?? msg.token_usage.prompt_tokens ?? 0),
                      completionTokens: Number(msg.token_usage.completionTokens ?? msg.token_usage.completion_tokens ?? 0),
                      totalTokens: Number(msg.token_usage.totalTokens ?? msg.token_usage.total_tokens ?? 0),
                      contextLimit: Number(msg.token_usage.contextLimit ?? msg.token_usage.context_limit ?? 0),
                      contextRemaining: Number(msg.token_usage.contextRemaining ?? msg.token_usage.context_remaining ?? 0),
                      source: msg.token_usage.source === "actual" ? "actual" : "estimated",
                      toolsUsed: msg.token_usage.tools_used || msg.token_usage.toolsUsed || msg.tools_used || msg.toolsUsed || [],
                    } : undefined,
                  });
                }
                break;
              }

              case "agent_action_start":
              case "agent_action_complete":
                if (cb.onTranscript && msg.action_title) {
                  cb.onTranscript({
                    text: "",
                    speaker: "output",
                    visualType: "agent_action",
                    agentActionData: {
                      eventType: msg.type,
                      toolName: msg.tool_name,
                      actionTitle: msg.action_title,
                      detail: msg.detail,
                      summary: msg.summary,
                      rawResult: msg.raw_result,
                      icon: msg.icon || "file",
                      filePath: msg.file_path,
                      filename: msg.filename,
                      content: msg.content,
                      sizeKb: msg.size_kb,
                      checkpointId: msg.checkpoint_id,
                      added: msg.added,
                      deleted: msg.deleted,
                    },
                  });
                }
                if (msg.type === "agent_action_complete" && msg.tool_name === "write_local_file" && typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("anara-brain-sync", {
                    detail: { event: "workspace_file_created", file: { path: msg.file_path, name: msg.filename, content: msg.content, size_kb: msg.size_kb } }
                  }));
                }
                break;

              case "agent_thinking":
                if (cb.onAgentThinking) {
                  const thinkingContent = msg.text !== undefined ? msg.text : (msg.data !== undefined ? msg.data : "");
                  cb.onAgentThinking(thinkingContent);
                }
                break;

              case "interactive_question":
                if (cb.onInteractiveQuestion && (msg.questions || (msg as any).data?.questions)) {
                  cb.onInteractiveQuestion({
                    question_id: msg.question_id || (msg as any).questionId || (msg as any).data?.question_id,
                    questions: msg.questions || (msg as any).data?.questions,
                  });
                }
                break;

              case "workspace_file_uploaded":
              case "workspace_folder_imported":
              case "workspace_file_created":
                if (typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: msg }));
                }
                break;

              case "interrupted":
                cb.onInterrupted?.();
                break;

              case "turn_complete":
                cb.onTurnComplete?.();
                break;

              case "emotion_update":
                if (cb.onEmotionUpdate && msg.emotion && msg.gesture) {
                  cb.onEmotionUpdate({
                    emotion: msg.emotion,
                    gesture: msg.gesture,
                    intensity: msg.intensity ?? 0.7,
                  });
                }
                break;

              case "acoustic_emotion":
                if (cb.onAcousticEmotion && msg.data) {
                  cb.onAcousticEmotion(msg.data);
                }
                break;

              case "speaker_identified":
                cb.onSpeakerIdentified?.(msg.name ?? null, msg.roster ?? []);
                if (typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "speaker_identified", name: msg.name } }));
                }
                break;

              case "hud_timer":
                if (typeof window !== "undefined") {
                  window.dispatchEvent(
                    new CustomEvent("anara-hud-timer", {
                      detail: {
                        durationSeconds: msg.durationSeconds,
                        label: msg.label,
                        alarmKind: msg.alarmKind ?? "timer",
                        soundVariant: msg.soundVariant ?? "urgent",
                        targetTime: msg.targetTime ?? null,
                      },
                    })
                  );
                }
                if (cb.onTranscript && msg.data) {
                  cb.onTranscript(msg.data, msg.speaker ?? "output");
                }
                break;

              case "hud_visual":
                if (cb.onHudVisual) {
                  cb.onHudVisual({
                    text: msg.data ?? "",
                    visualType: msg.visualType ?? "none",
                    imageUrl: msg.imageUrl,
                    imageTitle: msg.imageTitle,
                    sourceDomain: msg.sourceDomain,
                    sourceUrl: msg.sourceUrl,
                    images: msg.images,
                    knowledgeCardData: msg.knowledgeCardData,
                    briefingData: msg.briefingData,
                    mediaType: msg.mediaType,
                    planData: msg.planData,
                  });
                }
                break;

              case "media_play":
                if (msg.videoId) {
                  console.log(`[Media] play ${msg.kind}: "${msg.title}" (${msg.videoId})`);
                  cb.onMediaPlay?.({
                    kind: msg.kind ?? "music",
                    videoId: msg.videoId,
                    title: msg.title ?? "Media",
                    channel: msg.channel,
                    thumbnail: msg.thumbnail,
                    duration: msg.duration,
                    queue: msg.queue ?? [],
                    playlistName: msg.playlistName,
                    playlistIndex: msg.playlistIndex,
                    playlistTotal: msg.playlistTotal,
                    playlistTracks: msg.playlistTracks ?? [],
                  });
                }
                break;

              case "media_control":
                if (msg.action) {
                  cb.onMediaControl?.(msg.action);
                }
                break;

              case "session_id_sync": {
                // Dual-identity session synchronization: supports SQLite id and canonical session_key
                const rawSid = msg.sessionId ?? (msg as any).session_id ?? (msg as any).id;
                const numSid = typeof rawSid === "number" ? rawSid : rawSid && !isNaN(Number(rawSid)) ? Number(rawSid) : 0;
                const rawSkey =
                  msg.sessionKey ??
                  msg.session_key ??
                  (msg as any).sessionKey ??
                  (msg as any).session_key ??
                  (typeof rawSid === "string" && isNaN(Number(rawSid)) ? rawSid : undefined);

                if (numSid > 0) {
                  cb.onSessionIdSync?.(numSid, rawSkey);
                  if (typeof window !== "undefined") {
                    window.dispatchEvent(
                      new CustomEvent("anara-brain-sync", {
                        detail: { event: "session_id_sync", sessionId: numSid, sessionKey: rawSkey },
                      })
                    );
                  }
                }
                break;
              }

              case "tool_progress": {
                const toolName =
                  msg.tool_name ||
                  msg.toolName ||
                  (msg.data && (msg.data.tool_name || msg.data.toolName)) ||
                  (typeof msg.data === "string" ? msg.data : "tool");
                const status = msg.status || (msg.data && msg.data.status) || "running";
                const summary = msg.summary || (msg.data && msg.data.summary) || msg.detail || (msg.data && msg.data.detail);
                const icon = msg.icon || (msg.data && msg.data.icon);
                const detail = msg.detail || (msg.data && msg.data.detail);
                const rawResult = msg.raw_result || msg.rawResult || (msg.data && (msg.data.raw_result || msg.data.rawResult));

                if (cb.onToolProgress) {
                  cb.onToolProgress({
                    toolName,
                    status,
                    summary,
                    icon,
                    detail,
                    rawResult,
                  });
                }
                break;
              }

              case "token_usage":
                if (cb.onTokenUsage) {
                  cb.onTokenUsage({
                    modelId: msg.model_id || msg.modelId,
                    provider: msg.provider,
                    promptTokens: Number(msg.prompt_tokens ?? msg.promptTokens ?? 0),
                    completionTokens: Number(msg.completion_tokens ?? msg.completionTokens ?? 0),
                    totalTokens: Number(msg.total_tokens ?? msg.totalTokens ?? 0),
                    contextLimit: Number(msg.context_limit ?? msg.contextLimit ?? 0),
                    contextRemaining: Number(msg.context_remaining ?? msg.contextRemaining ?? 0),
                    source: msg.source === "actual" ? "actual" : "estimated",
                    toolsUsed: msg.tools_used || msg.toolsUsed || [],
                  });
                }
                break;

              case "session_switched": {
                // Dual-identity session synchronization: supports SQLite id, canonical session_key, and session_type
                const rawSid = msg.sessionId ?? (msg as any).session_id ?? (msg as any).id ?? 0;
                const numSid = typeof rawSid === "number" ? rawSid : rawSid && !isNaN(Number(rawSid)) ? Number(rawSid) : 0;
                const rawSkey =
                  msg.sessionKey ??
                  msg.session_key ??
                  (msg as any).sessionKey ??
                  (msg as any).session_key ??
                  (typeof rawSid === "string" && isNaN(Number(rawSid)) ? rawSid : null);
                const stype = (msg as any).sessionType ?? (msg as any).session_type ?? "chat";

                const switchedPayload: SessionSwitchedPayload = {
                  sessionId: numSid,
                  sessionKey: rawSkey,
                  session_key: rawSkey,
                  sessionType: stype,
                  session_type: stype,
                  title: msg.title ?? null,
                  messages: msg.messages ?? [],
                };

                cb.onSessionSwitched?.(switchedPayload);

                if (typeof window !== "undefined" && numSid > 0) {
                  window.dispatchEvent(
                    new CustomEvent("anara-brain-sync", {
                      detail: { event: "session_switched", sessionId: numSid, sessionKey: rawSkey, sessionType: stype },
                    })
                  );
                }
                break;
              }

              case "agent_action":
                cb.onAgentAction?.({
                  eventType: msg.eventType ?? "agent_action",
                  toolName: msg.toolName,
                  actionTitle: msg.actionTitle,
                  detail: msg.detail,
                  summary: msg.summary,
                  rawResult: msg.rawResult,
                  icon: msg.icon ?? "tool",
                });
                break;

              case "proactive_message":
                cb.onProactive?.({
                  kind: (msg.kind as ProactivePayload["kind"]) ?? "info",
                  text: msg.data ?? "",
                  todo: msg.todo ?? null,
                  project: msg.project ?? null,
                  todos: msg.todos ?? null,
                });
                break;

              case "brain_sync":
                if (typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: msg }));
                }
                break;

              case "plan_pending":
              case "need_approval":
                cb.onPlanPending?.(msg);
                break;

              case "error":
                cb.onError?.(msg.data ?? "Unknown server error");
                break;
            }
          } catch (e) {
            // Robust JSON parsing: handle newline-delimited chunks if server flushed multiple frames
            if (typeof event.data === "string" && event.data.includes("\n")) {
              const lines = event.data.split("\n");
              for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed) {
                  try {
                    const parsedLine = JSON.parse(trimmed);
                    // Process line with keepalive and event dispatch
                    if ((parsedLine as any).type === "ping") {
                      if (ws.readyState === WebSocket.OPEN) {
                        try {
                          ws.send(JSON.stringify({ type: "pong", timestamp: Date.now() }));
                        } catch {}
                      }
                      continue;
                    }
                    if ((parsedLine as any).type === "pong") continue;
                    // For brevity, dispatch through cb or internal handler
                    if (parsedLine.type === "transcript_partial" && (parsedLine.text !== undefined || parsedLine.delta !== undefined)) {
                      callbacksRef.current.onTranscript?.({
                        text: parsedLine.text || parsedLine.delta || "",
                        delta: parsedLine.delta,
                        speaker: parsedLine.speaker ?? "output",
                        visualType: parsedLine.visualType,
                        isPartial: true,
                        isStreaming: true,
                      });
                    } else if (parsedLine.type === "tool_progress" && callbacksRef.current.onToolProgress) {
                      callbacksRef.current.onToolProgress({
                        toolName: parsedLine.tool_name || parsedLine.toolName || "tool",
                        status: parsedLine.status || "running",
                        summary: parsedLine.summary,
                        icon: parsedLine.icon,
                      });
                    }
                  } catch {}
                }
              }
              return;
            }
            console.error("[WebSocket] JSON parse error:", e);
          }
        }
      };

      ws.onerror = () => {
        if (wsRef.current !== ws) return;
        const msg = `Cannot connect to backend at ${url}. Make sure the FastAPI server is running.`;
        console.warn("[WebSocket] Connection error —", msg);
        setStatus("error");
      };

      ws.onclose = (event) => {
        if (wsRef.current !== ws) return;
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }
        setStatus("disconnected");
        wsRef.current = null;

        if (!isIntentionalClose.current) {
          // Reset ladder if connection was open and stable for >= 5s (Anara Desktop standard)
          const isStable = connectTimeRef.current > 0 && Date.now() - connectTimeRef.current >= RECONNECT_STABLE_OPEN_MS;
          if (isStable) {
            retryCountRef.current = 0;
          }
          connectTimeRef.current = 0;

          // Exponential backoff with full jitter (AWS / Anara standard)
          const delay = reconnectBackoffDelayMs(retryCountRef.current, {
            baseDelayMs: DEFAULT_BASE_DELAY_MS,
            capMs: DEFAULT_CAP_MS,
            jitter: true,
          });
          retryCountRef.current += 1;
          console.log(
            `[WebSocket] Disconnected (code ${event.code}). Retrying in ${(delay / 1000).toFixed(1)}s... (attempt ${retryCountRef.current})`
          );
          reconnectTimeoutRef.current = setTimeout(() => {
            connectRef.current();
          }, delay);
        } else {
          retryCountRef.current = 0;
          connectTimeRef.current = 0;
        }
      };

      wsRef.current = ws;
    } catch (e) {
      console.error("[WebSocket] Failed to connect:", e);
      setStatus("error");
    }
  }, [url]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const disconnect = useCallback(() => {
    isIntentionalClose.current = true;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (wsRef.current) {
      // Null out event listeners to prevent zombie callbacks or reconnects
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      try {
        wsRef.current.close(1000, "Normal closure");
      } catch {}
      wsRef.current = null;
    }
    setStatus("disconnected");
  }, []);

  const enqueueMessage = (item: string | ArrayBuffer) => {
    if (messageQueueRef.current.length >= MAX_MESSAGE_QUEUE_SIZE) {
      messageQueueRef.current.shift(); // Evict oldest frame (FIFO)
    }
    messageQueueRef.current.push(item);
  };

  const sendBinary = useCallback((data: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(data);
      } catch (err) {
        console.warn("[WebSocket] sendBinary failed, buffering chunk:", err);
        enqueueMessage(data);
      }
    } else {
      enqueueMessage(data);
    }
  }, []);

  const sendJSON = useCallback((data: object) => {
    const str = JSON.stringify(data);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(str);
      } catch (err) {
        console.warn("[WebSocket] sendJSON failed, buffering message:", err);
        enqueueMessage(str);
      }
    } else {
      enqueueMessage(str);
    }
  }, []);

  const sendInterrupt = useCallback(() => {
    sendJSON({ type: "interrupt" });
  }, [sendJSON]);

  const sendText = useCallback((text: string) => {
    sendJSON({ type: "text_input", text });
  }, [sendJSON]);

  // Mid-Turn Steering Protocol (Anara Native Protocol Parity)
  const sendSteer = useCallback((message: string) => {
    sendJSON({ type: "steer", message });
  }, [sendJSON]);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
      messageQueueRef.current = [];
    };
  }, [connect, disconnect]);

  return { status, connect, disconnect, sendBinary, sendJSON, sendInterrupt, sendText, sendSteer };
}
