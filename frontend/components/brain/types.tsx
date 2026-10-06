"use client";

import { getBackendUrl } from "@/lib/apiClient";

export const BACKEND_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  (typeof window !== "undefined" ? getBackendUrl() : "http://localhost:8000")
).replace(/\/+$/, "");

export interface Memory {
  id: number;
  speaker_name: string;
  key: string;
  value: string;
  category: string;
  created_at: string;
  updated_at: string;
}

export interface Note {
  id: number;
  title: string;
  content: string;
  category: string;
  is_completed: number;
  due_date?: string;
  speaker_name?: string;
  created_at: string;
}

export interface Project {
  id: number;
  name: string;
  tech_stack?: string;
  goal?: string;
  status: string;
  notes?: string;
  speaker_name?: string;
  created_at: string;
  updated_at: string;
}

export interface Speaker {
  id: number;
  name: string;
  sample_count: number;
  has_voice_embedding?: number | boolean;
  memory_count: number;
  last_seen: string;
  created_at?: string;
}

export interface Conversation {
  id: number;
  speaker_name: string;
  user_text: string;
  ai_text: string;
  media_type?: string;
  media_url?: string;
  visual_data?: any;
  created_at: string;
}

export interface BrainStats {
  speakers_count: number;
  memories_count: number;
  notes_count: number;
  completed_todos: number;
  conversations_count: number;
  animations_count: number;
  db_size_bytes: number;
  db_path: string;
}

export interface Telemetry {
  core_status: string;
  ai_model: string;
  key_pool_total: number;
  active_key_preview: string;
  memory_nodes: number;
  notes_count: number;
  conversations_logged: number;
  db_size_kb: number;
}

export interface AnimationProfile {
  id: number;
  name: string;
  category: string;
  emotion: string;
  gesture: string;
  intensity: number;
  duration_sec: number;
  keywords: string[];
  description: string;
}

export interface AgentSkill {
  id: number;
  name: string;
  category: string;
  description: string;
  trigger_keywords: string[];
  procedure_steps: string[];
  usage_count: number;
  is_active: boolean;
  learned_from_experience: boolean;
  created_at: string;
}

export interface AgentSkillV2 {
  slug: string;
  name: string;
  category: string;
  description: string;
  trigger_keywords: string[];
  status: "active" | "disabled" | "pending" | "rejected";
  enabled?: boolean;
  usage_count?: number;
  learned_from_experience: boolean;
  created_at?: string;
  body?: string;
  file_path?: string;
  required_environment_variables?: string[];
  required_credential_files?: string[];
}

export interface FileMemorySnapshot {
  soul: string;
  user: string;
  memory: string;
}

export interface AutonomousTaskInfo {
  id: string;
  name: string;
  prompt: string;
  trigger_type: string;
  interval_seconds: number;
  trust_level: "supervised" | "semi_autonomous" | "full_autonomous";
  target_channel: string;
  target_channel_id?: string;
  is_active: number | boolean;
  status: "idle" | "running" | "waiting_approval" | "paused" | "failed";
  pending_plan_id?: string;
  last_run?: string;
  next_run?: string;
}

export interface ToolItem {
  name: string;
  description: string;
  category: string;
  icon: string;
  is_read_only: boolean;
  mode_label: string;
  parameters: any;
}

export interface SubagentTask {
  task_id: string;
  title: string;
  status: string;
  progress_percent: number;
  steps_log: string[];
  result?: string;
  created_at: number;
}

export interface ProviderAccount {
  id: number;
  provider: string;
  account_label: string;
  masked_key: string;
  status: string;
  requests_count: number;
  is_enabled?: number;
}

export interface ModelItem {
  id: string;
  name: string;
  category: string;
  badge: string;
  description: string;
  icon: string;
  is_active: boolean;
}

export interface ProviderItem {
  id: string;
  name: string;
  badge: string;
  icon: string;
  description: string;
  auth_type: string;
  signup_url: string;
  signup_label: string;
  key_placeholder: string;
  help_text: string;
  is_connected: boolean;
  models_count: number;
  accounts_count?: number;
  accounts?: ProviderAccount[];
  models: ModelItem[];
  credit_info?: {
    total_credits?: number;
    total_usage?: number;
    remaining?: number;
  } | null;
  is_custom?: boolean;
  custom_data?: any;
}

export interface TokenSummary {
  grand_total_tokens: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_requests: number;
  by_provider: Array<{
    provider: string;
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    request_count: number;
  }>;
  by_model: Array<{
    model_id: string;
    provider: string;
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    request_count: number;
  }>;
}

export interface ContactItem {
  id: number;
  name: string;
  phone_number: string;
  platform: string;
  notes?: string;
  updated_at?: string;
}

export interface IntegrationMessage {
  id: string;
  chat_id?: string;
  sender_name: string;
  sender_phone?: string;
  sender_username?: string;
  message_text: string;
  timestamp: string;
  is_outgoing: boolean;
  is_read?: boolean;
}

export interface WhatsAppStatus {
  status: "connected" | "disconnected" | "pairing" | "qr_ready" | "initializing";
  has_qr: boolean;
  user?: { id: string; name: string; phone: string } | null;
  recent_messages_count: number;
  unread_count: number;
}

export interface TelegramStatus {
  status: "connected" | "not_configured" | "error";
  bot_username?: string;
  bot_name?: string;
  chat_id?: string;
  is_polling?: boolean;
  recent_messages_count: number;
}

export interface GoogleStatus {
  status: "connected" | "not_configured" | "needs_auth" | "error";
  email?: string;
  scopes?: string[];
  unread_emails_count: number;
  upcoming_events_count: number;
}

export type BrainTabId =
  | "soul"
  | "skills"
  | "tools"
  | "connectors"
  | "plugins"
  | "providers"
  | "integrations";

export type BrainPillar = "persona" | "workers" | "ai" | "system";

export interface AnaraBrainProps {
  isOpen: boolean;
  onClose: () => void;
  onTriggerAnimation?: (animName: string, emotion: string) => void;
  activeSpeaker?: string | null;
}

// Re-export shared UI components from dedicated UI layer
export { BrandIcon, CategoryIcon } from "@/components/ui/BrandIcons";
export { LiquidGlassSelect } from "@/components/ui/LiquidGlassSelect";
export type { LiquidGlassSelectProps, SelectOption } from "@/components/ui/LiquidGlassSelect";
