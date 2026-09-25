"use client";

import React, { useState, useEffect, useRef } from "react";

export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

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
  | "memories"
  | "speakers"
  | "tools"
  | "projects"
  | "todos"
  | "providers"
  | "integrations"
  | "conversations"
  | "animations";

export type BrainPillar = "persona" | "workers" | "ai" | "system";

export interface AnaraBrainProps {
  isOpen: boolean;
  onClose: () => void;
  onTriggerAnimation?: (animName: string, emotion: string) => void;
  activeSpeaker?: string | null;
}

export const FALLBACK_ANIMATIONS: AnimationProfile[] = [
  { id: -1, name: "dance", category: "dance", emotion: "dance", gesture: "dance", intensity: 1.0, duration_sec: 9.0, keywords: ["nari"], description: "Full rhythm Latin dance animation with beat music sync" },
  { id: -2, name: "salute", category: "gesture", emotion: "happy", gesture: "salute", intensity: 0.85, duration_sec: 3.0, keywords: ["hormat"], description: "Professional assistant standing salute gesture" },
  { id: -3, name: "greeting", category: "gesture", emotion: "happy", gesture: "wave", intensity: 0.8, duration_sec: 3.0, keywords: ["hai"], description: "Waving right hand with friendly smile" },
  { id: -4, name: "laughing", category: "emotion", emotion: "happy", gesture: "joy", intensity: 0.9, duration_sec: 3.5, keywords: ["tertawa"], description: "Ekspresi tertawa riang dan gestur gembira" },
  { id: -5, name: "shy", category: "emotion", emotion: "shy", gesture: "shy_movement", intensity: 0.7, duration_sec: 3.0, keywords: ["malu"], description: "Sweet blushing gesture when receiving compliments" },
  { id: -6, name: "thinking", category: "emotion", emotion: "thinking", gesture: "think", intensity: 0.75, duration_sec: 4.0, keywords: ["thinking"], description: "Hand on chin analyzing context" },
  { id: -7, name: "angry", category: "emotion", emotion: "angry", gesture: "angry_pointing", intensity: 0.9, duration_sec: 3.5, keywords: ["angry"], description: "Pointing firmly with furrowed brows" },
  { id: -8, name: "crying", category: "emotion", emotion: "sad", gesture: "sad", intensity: 0.8, duration_sec: 4.0, keywords: ["sad"], description: "Head down with teary eyes" },
  { id: -9, name: "explaining", category: "gesture", emotion: "curious", gesture: "explaining", intensity: 0.75, duration_sec: 4.0, keywords: ["explain"], description: "Open hand gesture when presenting data" },
];

export const ANIMATION_LABELS: Record<string, string> = {
  dance: "Tarian Rumba 3D",
  salute: "Hormat Sopan",
  greeting: "Melambaikan Tangan",
  wave: "Melambaikan Tangan",
  laughing: "Tertawa Ceria",
  laugh: "Tertawa Ceria",
  shy: "Tersipu Malu",
  thinking: "Berpikir Mendalam",
  think: "Berpikir Mendalam",
  angry: "Ekspresi Tegas / Marah",
  crying: "Ekspresi Simpati / Sedih",
  sad: "Ekspresi Simpati / Sedih",
  explaining: "Penjelasan Terbuka",
  talking: "Natural Talking",
  question: "Sikap Penasaran",
  nod: "Nodding in Agreement",
  empathy: "Empathy & Comfort Gesture",
  agree: "Nodding in Agreement",
  disagree: "Menggeleng Tenang",
};

export function animationLabel(name: string): string {
  return ANIMATION_LABELS[name] || (name.charAt(0).toUpperCase() + name.slice(1));
}

export const CALIBRATION_WORKLET_CODE = `
class CalibrationRecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = new Float32Array(4096);
    this._idx = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const samples = input[0];
    for (let i = 0; i < samples.length; i++) {
      this._buf[this._idx++] = samples[i];
      if (this._idx >= this._buf.length) {
        const copy = this._buf.slice();
        this.port.postMessage(copy, [copy.buffer]);
        this._idx = 0;
      }
    }
    return true;
  }
}

registerProcessor('calibration-recorder', CalibrationRecorderProcessor);
`;

export function BrandIcon({ name, className = "w-5 h-5" }: { name: string; className?: string }) {
  const n = (name || "").toLowerCase();
  if (n === "gemini" || n.includes("google")) {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" />
      </svg>
    );
  }
  if (n === "anthropic" || n.includes("claude")) {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M13.8 2.2L12 7.5L10.2 2.2C10.1 1.9 9.8 1.7 9.5 1.8C9.2 1.9 9 2.2 9.1 2.5L11 8.2L5.3 6.3C5 6.2 4.7 6.4 4.6 6.7C4.5 7 4.7 7.3 5 7.4L10.7 9.3L5.4 11.1C5.1 11.2 4.9 11.5 5 11.8C5.1 12.1 5.4 12.3 5.7 12.2L11.4 10.3L9.5 16C9.4 16.3 9.6 16.6 9.9 16.7C10.2 16.8 10.5 16.6 10.6 16.3L12.4 11L14.2 16.3C14.3 16.6 14.6 16.8 14.9 16.7C15.2 16.6 15.4 16.3 15.3 16L13.4 10.3L19.1 12.2C19.4 12.3 19.7 12.1 19.8 11.8C19.9 11.5 19.7 11.2 19.4 11.1L13.7 9.3L19.4 7.4C19.7 7.3 19.9 7 19.8 6.7C19.7 6.4 19.4 6.2 19.1 6.3L13.4 8.2L15.3 2.5C15.4 2.2 15.2 1.9 14.9 1.8C14.6 1.7 14.3 1.9 14.2 2.2H13.8Z" />
      </svg>
    );
  }
  if (n === "openai" || n === "codex") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 8.784a4.474 4.474 0 0 1 2.37-1.996V12.7a.76.76 0 0 0 .385.672l5.834 3.37-2.02 1.168a.076.076 0 0 1-.067.005L3.998 15.13a4.504 4.504 0 0 1-1.658-6.346zm16.597 3.846l-5.834-3.37 2.02-1.168a.076.076 0 0 1 .067-.005l4.844 2.795a4.504 4.504 0 0 1 1.658 6.346 4.47 4.47 0 0 1-2.37 1.996V13.3a.76.76 0 0 0-.385-.67zm2.015-3.018l-.142-.085-4.783-2.759a.771.771 0 0 0-.78 0L9.404 10.14V7.808a.08.08 0 0 1 .033-.062l4.84-2.795a4.5 4.5 0 0 1 6.677 4.659zM11.999 13.5l-2.828-1.633L12 10.234l2.828 1.633L12 13.5z"/>
      </svg>
    );
  }
  if (n === "whatsapp" || n.includes("wa")) {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91C2.13 13.66 2.59 15.36 3.45 16.86L2.05 22L7.3 20.62C8.75 21.41 10.38 21.83 12.04 21.83C17.5 21.83 21.95 17.38 21.95 11.92C21.95 9.27 20.92 6.78 19.05 4.91C17.18 3.03 14.69 2 12.04 2M12.05 3.67C14.25 3.67 16.31 4.53 17.87 6.09C19.42 7.65 20.28 9.72 20.28 11.92C20.28 16.46 16.58 20.15 12.04 20.15C10.56 20.15 9.11 19.76 7.85 19L7.55 18.83L4.43 19.65L5.26 16.61L5.06 16.29C4.24 15 3.8 13.47 3.8 11.91C3.81 7.37 7.5 3.67 12.05 3.67M9.53 7.03C9.36 7.03 9.08 7.09 8.84 7.35C8.6 7.61 7.92 8.25 7.92 9.55C7.92 10.85 8.87 12.11 9 12.28C9.13 12.45 10.87 15.14 13.53 16.29C14.16 16.57 14.66 16.73 15.04 16.85C15.68 17.06 16.26 17.03 16.72 16.96C17.24 16.88 18.31 16.31 18.53 15.67C18.76 15.03 18.76 14.49 18.69 14.37C18.62 14.26 18.45 14.19 18.19 14.07C17.93 13.94 16.66 13.31 16.42 13.22C16.18 13.14 16.01 13.1 15.84 13.35C15.67 13.61 15.18 14.19 15.03 14.36C14.88 14.53 14.73 14.55 14.47 14.42C14.21 14.3 13.38 14.03 12.39 13.15C11.62 12.46 11.1 11.61 10.95 11.35C10.8 11.09 10.93 10.95 11.06 10.82C11.18 10.7 11.33 10.51 11.47 10.34C11.61 10.17 11.66 10.04 11.75 9.87C11.84 9.7 11.79 9.55 11.73 9.42C11.67 9.3 11.18 8.1 10.97 7.62C10.77 7.14 10.57 7.21 10.42 7.2C10.28 7.2 10.11 7.2 9.94 7.2L9.53 7.03Z" />
      </svg>
    );
  }
  if (n === "telegram" || n.includes("tg")) {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.37.74-.56 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
      </svg>
    );
  }
  if (n === "google" || n.includes("gmail") || n.includes("workspace")) {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    );
  }
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
    </svg>
  );
}

export function CategoryIcon({ category, className = "w-4 h-4" }: { category: string; className?: string }) {
  const cat = (category || "").toLowerCase();
  if (cat === "coding" || cat === "code") {
    return (
      <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
      </svg>
    );
  }
  if (cat === "document" || cat === "doc" || cat === "pdf") {
    return (
      <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    );
  }
  if (cat === "research" || cat === "search" || cat === "web") {
    return (
      <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" strokeWidth={1.8} />
        <line x1="2" y1="12" x2="22" y2="12" strokeWidth={1.8} />
        <path strokeWidth={1.8} d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    );
  }
  if (cat === "communication" || cat === "chat" || cat === "msg") {
    return (
      <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    );
  }
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  );
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface LiquidGlassSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  className?: string;
}

export function LiquidGlassSelect({ value, onChange, options, className = "" }: LiquidGlassSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectedOption = options.find((opt) => opt.value === value) || options[0];

  return (
    <div ref={dropdownRef} className={`relative z-50 inline-block font-sans ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between gap-2.5 px-4 py-2 rounded-2xl liquid-glass-subtle hover:border-cyan-400/40 hover:shadow-[0_4px_20px_rgba(34,211,238,0.15)] transition-all duration-300 cursor-pointer"
      >
        <span className="truncate">{selectedOption?.label}</span>
        <svg
          className={`w-3.5 h-3.5 text-cyan-400 transition-transform duration-300 shrink-0 ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute left-0 mt-2 w-full min-w-[170px] max-h-56 overflow-y-auto rounded-2xl bg-slate-950/90 border border-white/20 backdrop-blur-2xl shadow-[0_12px_40px_rgba(0,0,0,0.6)] py-1.5 z-50 animate-fade-in custom-scrollbar">
          {options.map((opt) => {
            const isSelected = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  onChange(opt.value);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center justify-between gap-2 px-4 py-2 text-left text-xs transition-colors duration-150 cursor-pointer ${
                  isSelected ? "bg-cyan-500/20 text-cyan-300 font-semibold border-l-2 border-cyan-400" : "text-slate-300 hover:bg-white/10 hover:text-white"
                }`}
              >
                <span>{opt.label}</span>
                {isSelected && (
                  <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
