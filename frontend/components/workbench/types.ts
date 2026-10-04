import type { MediaSession } from "../dock/AnaraMediaPlayer";
import type { TokenUsagePayload, ToolProgressPayload } from "@/hooks/useWebSocket";
import type { PlanData } from "@/components/hud/types";
import type { InteractiveQuestionData } from "@/components/chat/InteractiveQuestionCard";

export type AssistantStatus = "idle" | "listening" | "thinking" | "speaking";

export interface TranscriptItem {
  speaker: "input" | "output";
  text: string;
  id?: string;
  timestamp?: number | string;
  visualType?: "image" | "weather" | "code" | "system_hud" | "knowledge_card" | "todo_list" | "briefing" | "agent_action" | "document_viewer" | "folder_workspace" | "plan_card" | "interactive_question" | "approval" | "subagent" | "none";
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
  briefingData?: any;
  agentActionData?: any;
  subagentData?: any;
  questionData?: InteractiveQuestionData;
  documentViewerData?: {
    fileName: string;
    fileExt: string;
    fileSizeKb: number;
    totalChars?: number;
    content: string;
    isPdf?: boolean;
  };
  workspaceFolderData?: {
    folderName: string;
    rootPath?: string;
    totalFiles: number;
    files: Array<{
      name: string;
      path: string;
      ext: string;
      size_kb: number;
      is_pdf?: boolean;
      is_image?: boolean;
      is_code?: boolean;
    }>;
  };
  planData?: PlanData;
  images?: Array<{ image_url?: string; url?: string; title?: string; source_domain?: string; sourceDomain?: string; source_url?: string; sourceUrl?: string }>;
  mediaType?: "image" | "hud";
  agentMode?: "plan" | "build";
  modelId?: string;
  durationText?: string;
  thinkingText?: string | null;
  thinkingDuration?: number;
  tokenUsage?: TokenUsagePayload;
  toolsUsed?: string[];
  toolRecordsCount?: number;
  isStreaming?: boolean;
  approvalData?: {
    planId: string;
    toolName: string;
    commandPreview?: string;
    rationale?: string;
    riskLevel?: "low" | "medium" | "high" | "critical";
  };
  interrupted?: boolean;
  isError?: boolean;
  errorDetails?: string;
  retryable?: boolean;
  startTime?: number;
}

export interface AnaraWorkbenchProps {
  status: AssistantStatus;
  connectionStatus: "disconnected" | "connecting" | "connected" | "error";
  transcript: TranscriptItem[];
  liveToolProgress?: ToolProgressPayload | null;
  isMicActive: boolean;
  isMuted: boolean;
  userIntensity: number;
  aiIntensity: number;
  interactionMode?: "voice" | "chat";
  onSetInteractionMode?: (mode: "voice" | "chat") => void;
  onStartSession: () => void;
  onSendText?: (text: string, agentMode?: "plan" | "build") => void;
  onSteer?: (text: string) => void;
  onToggleMute: () => void;
  onInterrupt: () => void;
  onClearTranscript: () => void;
  onTriggerAnimation?: (animName: string, emotion: string) => void;
  micDenied?: boolean;
  activeSpeaker?: string | null;
  speakerRoster?: string[];
  mediaSession?: MediaSession | null;
  mediaControl?: { action: "stop" | "pause" | "resume" | "next" | "prev"; nonce: number } | null;
  onCloseMedia?: () => void;
  activeSessionId?: number | null;
  sessionRefreshKey?: number;
  onSelectSession?: (id: number) => void;
  onNewSession?: () => void;
  onApprovePlan?: (plan: PlanData) => void;
  onRejectPlan?: (plan?: any) => void;
  onSidebarToggle?: (isOpen: boolean) => void;
  sidebarWidth?: number;
  onWidthChange?: (width: number) => void;
  initialSidebarTab?: "history" | "editor";
  activeThinkingText?: string | null;
  onAnswerQuestion?: (questionId: string, answers: any, dismissed?: boolean) => void;
  reasoningEffort?: "off" | "low" | "medium" | "high" | string;
  onSelectReasoningEffort?: (effort: "off" | "low" | "medium" | "high") => void;
  latestTokenUsage?: any;
}
