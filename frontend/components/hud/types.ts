export interface WeatherData {
  city: string;
  temp_c: number;
  condition: string;
  humidity: number;
  wind_kmh: number;
  uv_index?: number;
  forecast?: Array<{ day: string; temp_c: number; condition: string }>;
}

export interface CodeData {
  language: string;
  title: string;
  code: string;
  explanation?: string;
}

export interface SystemHudData {
  core_status: string;
  ai_model: string;
  active_keys: number;
  memory_nodes: number;
  latency_ms: number;
  uptime: string;
}

export interface KnowledgeCardData {
  title: string;
  category?: string;
  badge?: string;
  summary: string;
  specs?: Array<{ label: string; value: string }>;
  steps?: string[];
  ingredients?: string[];
}

export interface BriefingData {
  date_str: string;
  time_str: string;
  greeting?: string;
  speaker?: string;
  weather?: {
    city?: string;
    temp_c?: number;
    condition?: string;
    humidity?: number;
    wind_kmh?: number;
    advice?: string;
  } | null;
  todos?: Array<{ title: string; content?: string | null; due?: string | null }>;
  projects?: Array<{ name: string; goal?: string | null; tech?: string | null }>;
}

export interface TodoData {
  items: Array<{
    id?: number;
    title: string;
    content?: string;
    category?: string;
    is_completed?: number | boolean;
    due_date?: string;
  }>;
}

export interface AgentActionData {
  eventType?: "agent_action_start" | "agent_action_complete" | string;
  toolName?: string;
  actionTitle?: string;
  detail?: string;
  summary?: string;
  rawResult?: string;
  icon?: string;
  filePath?: string;
  filename?: string;
  content?: string;
  sizeKb?: number;
  checkpointId?: string;
  added?: number;
  deleted?: number;
}

export interface DocumentViewerData {
  fileName: string;
  fileExt: string;
  fileSizeKb: number;
  totalChars?: number;
  content: string;
  isPdf?: boolean;
  downloadUrl?: string;
}

export interface WorkspaceFolderData {
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
}

export interface PlanData {
  title: string;
  summary?: string;
  steps: Array<string | {
    id?: string | number;
    title?: string;
    description?: string;
    status?: "pending" | "in_progress" | "completed";
  }>;
  tech_stack?: string[];
  techStack?: string[];
  estimated_effort?: string;
  estimatedEffort?: string;
  filesToModify?: string[];
  estimatedScope?: string;
  planStatus?: "pending" | "approved" | "executing" | "completed";
}

export interface ImageItem {
  image_url?: string;
  url?: string;
  title?: string;
  source_domain?: string;
  sourceDomain?: string;
  source_url?: string;
  sourceUrl?: string;
  prompt?: string;
}

export interface AnaraHUDProps {
  visualType?: "image" | "weather" | "code" | "system_hud" | "knowledge_card" | "todo_list" | "briefing" | "agent_action" | "whatsapp_qr" | "whatsapp_chat" | "document_viewer" | "folder_workspace" | "plan_card" | "none";
  imageUrl?: string;
  imageTitle?: string;
  sourceDomain?: string;
  sourceUrl?: string;
  imagePrompt?: string;
  images?: ImageItem[];
  weatherData?: WeatherData;
  codeData?: CodeData;
  systemHudData?: SystemHudData;
  knowledgeCardData?: KnowledgeCardData;
  todoData?: TodoData;
  briefingData?: BriefingData;
  agentActionData?: AgentActionData;
  documentViewerData?: DocumentViewerData;
  workspaceFolderData?: WorkspaceFolderData;
  planData?: PlanData;
  compact?: boolean;
  onOpenLightbox?: (data: { url: string; title: string; sourceDomain?: string; sourceUrl?: string; prompt?: string }) => void;
  onOpenFile?: (filePath: string) => void;
  onApprovePlan?: (plan: PlanData) => void;
  onRejectPlan?: () => void;
  onDismiss?: () => void;
}

// Re-export HudDismissButton from its dedicated component file
export { HudDismissButton } from "./HudDismissButton";
