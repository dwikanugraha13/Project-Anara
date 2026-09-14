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
  status: "running" | "done" | string;
  summary?: string;
  icon?: string;
}

export interface WebSocketMessage {
  type: "audio_chunk" | "transcript" | "transcript_partial" | "token_usage" | "tool_progress" | "interrupted" | "turn_complete" | "error" | "emotion_update" | "acoustic_emotion" | "brain_sync" | "speaker_identified" | "hud_timer" | "hud_visual" | "media_play" | "media_control" | "proactive_message" | "session_switched" | "session_id_sync" | "agent_action" | "agent_action_start" | "agent_action_complete" | "agent_thinking" | "interactive_question" | "workspace_file_uploaded" | "workspace_folder_imported" | "workspace_file_created";
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
  sessionId?: number;
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
  onSessionIdSync?: (sessionId: number) => void;
  onAgentAction?: (payload: AgentActionPayload) => void;
  onAgentThinking?: (text: string) => void;
  onInteractiveQuestion?: (payload: InteractiveQuestionPayload) => void;
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

              case "transcript_partial":
                if (msg.text && onTranscript) {
                  onTranscript({
                    text: msg.text,
                    speaker: msg.speaker ?? "output",
                    visualType: msg.visualType,
                    isPartial: true,
                    isStreaming: true,
                  });
                }
                break;

              case "transcript":
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


              case "agent_action_start":
              case "agent_action_complete":
                if (onTranscript && msg.action_title) {
                  onTranscript({
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
                if (onAgentThinking) {
                  const thinkingContent = msg.text !== undefined ? msg.text : (msg.data !== undefined ? msg.data : "");
                  onAgentThinking(thinkingContent);
                }
                break;

              case "interactive_question":
                if (onInteractiveQuestion && (msg.questions || (msg as any).data?.questions)) {
                  onInteractiveQuestion({
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
                }
                break;

              case "acoustic_emotion":
                if (onAcousticEmotion && msg.data) {
                  onAcousticEmotion(msg.data);
                }
                break;

              case "speaker_identified":
                onSpeakerIdentified?.(msg.name ?? null, msg.roster ?? []);
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
                if (onTranscript && msg.data) {
                  onTranscript(msg.data, msg.speaker ?? "output");
                }
                break;

              case "hud_visual":
                if (onHudVisual) {
                  onHudVisual({
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
                  onMediaPlay?.({
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
                  onMediaControl?.(msg.action);
                }
                break;

              case "session_id_sync":
                if (msg.sessionId) {
                  onSessionIdSync?.(msg.sessionId);
                }
                break;

              case "tool_progress":
                if (onToolProgress && (msg.tool_name || msg.toolName)) {
                  onToolProgress({
                    toolName: msg.tool_name || msg.toolName || "tool",
                    status: msg.status || "running",
                    summary: msg.summary,
                    icon: msg.icon,
                  });
                }
                break;

              case "token_usage":
                if (onTokenUsage) {
                  onTokenUsage({
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

              case "session_switched":
                onSessionSwitched?.({
                  sessionId: msg.sessionId ?? 0,
                  title: msg.title ?? null,
                  messages: msg.messages ?? [],
                });
                break;

              case "agent_action":
                onAgentAction?.({
                  eventType: msg.eventType ?? "agent_action",
                  toolName: msg.toolName,
                  actionTitle: msg.actionTitle,
                  detail: msg.detail,
                  summary: msg.summary,
                  rawResult: msg.rawResult,
                  icon: msg.icon ?? "⚙️",
                });
                break;

              case "proactive_message":
                onProactive?.({
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
  }, [url, onAudioChunk, onTranscript, onTokenUsage, onToolProgress, onInterrupted, onTurnComplete, onError, onEmotionUpdate, onHudVisual, onMediaPlay, onMediaControl, onProactive, onSessionSwitched, onSessionIdSync, onAgentAction]);

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
