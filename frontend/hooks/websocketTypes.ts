"use client";

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
  playlistName?: string;
  playlistIndex?: number;
  playlistTotal?: number;
  playlistTracks?: MediaTrack[];
}

export type MediaControlAction = "stop" | "pause" | "resume" | "next" | "prev";

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

export interface ProactivePayload {
  kind: "due_reminder" | "greeting" | "follow_up" | "info";
  text: string;
  todo?: { id?: number; title?: string; due?: string; content?: string } | null;
  project?: { id?: number; name?: string; days?: number } | null;
  todos?: string[] | null;
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
  sessionId?: number;
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
  exit_code?: number;
  duration_ms?: number;
  command?: string;
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

export interface ReconnectBackoffOptions {
  baseDelayMs?: number;
  capMs?: number;
  jitter?: boolean;
}

export const DEFAULT_BASE_DELAY_MS = 500;
export const DEFAULT_CAP_MS = 15000;
export const RECONNECT_STABLE_OPEN_MS = 5000;
export const PING_INTERVAL_MS = 30000;
export const HEARTBEAT_TIMEOUT_MS = 65000;
export const MAX_MESSAGE_QUEUE_SIZE = 100;

/**
 * Exponential reconnect backoff with full jitter (AWS / Anara Desktop standard).
 */
export function reconnectBackoffDelayMs(attempt: number, options: ReconnectBackoffOptions = {}): number {
  const baseDelayMs = options.baseDelayMs ?? DEFAULT_BASE_DELAY_MS;
  const capMs = options.capMs ?? DEFAULT_CAP_MS;
  const exponent = Math.min(Math.max(0, Math.trunc(attempt)), 32);
  const ceiling = Math.min(capMs, baseDelayMs * 2 ** exponent);
  return options.jitter === false ? ceiling : Math.random() * ceiling;
}

export interface UseWebSocketOptions {
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
