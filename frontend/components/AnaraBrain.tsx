"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";

interface Memory {
  id: number;
  speaker_name: string;
  key: string;
  value: string;
  category: string;
  created_at: string;
  updated_at: string;
}

interface Note {
  id: number;
  title: string;
  content: string;
  category: string;
  is_completed: number;
  due_date?: string;
  speaker_name?: string;
  created_at: string;
}

interface Project {
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

interface Speaker {
  id: number;
  name: string;
  sample_count: number;
  has_voice_embedding?: number | boolean;
  memory_count: number;
  last_seen: string;
  created_at?: string;
}

interface Conversation {
  id: number;
  speaker_name: string;
  user_text: string;
  ai_text: string;
  media_type?: string;
  media_url?: string;
  visual_data?: any;
  created_at: string;
}

interface BrainStats {
  speakers_count: number;
  memories_count: number;
  notes_count: number;
  completed_todos: number;
  conversations_count: number;
  animations_count: number;
  db_size_bytes: number;
  db_path: string;
}

interface Telemetry {
  core_status: string;
  ai_model: string;
  key_pool_total: number;
  active_key_preview: string;
  memory_nodes: number;
  notes_count: number;
  conversations_logged: number;
  db_size_kb: number;
}

interface AnimationProfile {
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

export interface AnaraBrainProps {
  isOpen: boolean;
  onClose: () => void;
  onTriggerAnimation?: (animName: string, emotion: string) => void;
  activeSpeaker?: string | null;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// Fallback animation profiles shown when the /api/brain/animations endpoint is unreachable.
// Mirrors the default seeds in backend memory_service._seed_default_animations().
const FALLBACK_ANIMATIONS: AnimationProfile[] = [
  { id: -1, name: "dance", category: "dance", emotion: "dance", gesture: "dance", intensity: 1.0, duration_sec: 9.0, keywords: ["nari"], description: "Animasi tarian penuh ritme Latin dengan sinkronisasi musik beat" },
  { id: -2, name: "salute", category: "gesture", emotion: "happy", gesture: "salute", intensity: 0.85, duration_sec: 3.0, keywords: ["hormat"], description: "Gestur memberi hormat tegak ala asisten profesional" },
  { id: -3, name: "greeting", category: "gesture", emotion: "happy", gesture: "wave", intensity: 0.8, duration_sec: 3.0, keywords: ["hai"], description: "Melambaikan tangan kanan dengan senyuman ramah" },
  { id: -4, name: "laughing", category: "emotion", emotion: "happy", gesture: "joy", intensity: 0.9, duration_sec: 3.5, keywords: ["tertawa"], description: "Ekspresi tertawa riang dan gestur gembira" },
  { id: -5, name: "shy", category: "emotion", emotion: "shy", gesture: "shy_movement", intensity: 0.7, duration_sec: 3.0, keywords: ["malu"], description: "Gestur tersipu manis saat menerima pujian" },
  { id: -6, name: "thinking", category: "emotion", emotion: "thinking", gesture: "think", intensity: 0.75, duration_sec: 4.0, keywords: ["berpikir"], description: "Tangan di dagu dan mata menganalisis konteks" },
  { id: -7, name: "angry", category: "emotion", emotion: "angry", gesture: "angry_pointing", intensity: 0.9, duration_sec: 3.5, keywords: ["marah"], description: "Menunjuk tegas dengan alis menekuk" },
  { id: -8, name: "crying", category: "emotion", emotion: "sad", gesture: "sad", intensity: 0.8, duration_sec: 4.0, keywords: ["sedih"], description: "Menunduk dengan mata berkaca-kaca" },
  { id: -9, name: "explaining", category: "gesture", emotion: "curious", gesture: "explaining", intensity: 0.75, duration_sec: 4.0, keywords: ["jelaskan"], description: "Gestur tangan terbuka saat memaparkan data" },
];

// Friendly display labels for known animation names (fallback: capitalized name)
const ANIMATION_LABELS: Record<string, string> = {
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
  talking: "Berbicara Natural",
  question: "Sikap Penasaran",
  nod: "Mengangguk Setuju",
  empathy: "Gestur Empati & Penghiburan",
  agree: "Mengangguk Setuju",
  disagree: "Menggeleng Tenang",
};

function animationLabel(name: string): string {
  return ANIMATION_LABELS[name] || (name.charAt(0).toUpperCase() + name.slice(1));
}

// AudioWorklet recorder used during voice biometric calibration.
// Collects raw Float32 samples in large chunks and posts them to the main thread.
const CALIBRATION_WORKLET_CODE = `
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

interface SelectOption {
  value: string;
  label: string;
}

interface LiquidGlassSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  className?: string;
}

function LiquidGlassSelect({ value, onChange, options, className = "" }: LiquidGlassSelectProps) {
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
                className={`w-full text-left px-4 py-2 text-xs transition-colors flex items-center justify-between cursor-pointer ${
                  isSelected
                    ? "bg-cyan-500/20 text-cyan-300 font-semibold border-l-2 border-cyan-400"
                    : "text-slate-300 hover:bg-white/10 hover:text-white"
                }`}
              >
                <span>{opt.label}</span>
                {isSelected && (
                  <svg className="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

export default function AnaraBrain({ isOpen, onClose, onTriggerAnimation, activeSpeaker }: AnaraBrainProps) {
  const [activeTab, setActiveTab] = useState<"memories" | "todos" | "projects" | "speakers" | "animations" | "conversations" | "telemetry">("memories");
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<BrainStats | null>(null);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [animations, setAnimations] = useState<AnimationProfile[]>([]);

  // Filters & Form States
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [todoFilter, setTodoFilter] = useState<"all" | "active" | "completed">("all");

  // New Memory Modal State
  const [isAddMemoryOpen, setIsAddMemoryOpen] = useState(false);
  const [newSpeaker, setNewSpeaker] = useState("Agnan");
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newCategory, setNewCategory] = useState("preference");

  // New Note Modal State
  const [isAddNoteOpen, setIsAddNoteOpen] = useState(false);
  const [newNoteTitle, setNewNoteTitle] = useState("");
  const [newNoteContent, setNewNoteContent] = useState("");
  const [newNoteCategory, setNewNoteCategory] = useState("todo");

  // New Project Modal State
  const [isAddProjectOpen, setIsAddProjectOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectStack, setNewProjectStack] = useState("");
  const [newProjectGoal, setNewProjectGoal] = useState("");
  const [newProjectNotes, setNewProjectNotes] = useState("");

  // Semantic RAG Search State
  const [ragQuery, setRagQuery] = useState("");
  const [ragResults, setRagResults] = useState<Array<{ type: string; title: string; content: string; category: string; score: number }>>([]);
  const [isRagSearching, setIsRagSearching] = useState(false);

  // Speaker Calibration & Add Speaker State
  const [isAddSpeakerOpen, setIsAddSpeakerOpen] = useState(false);
  const [newSpeakerInput, setNewSpeakerInput] = useState("");
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibratingSpeaker, setCalibratingSpeaker] = useState<string | null>(null);
  const [calibrationCountdown, setCalibrationCountdown] = useState<number | null>(null);
  const [calibrationStatusText, setCalibrationStatusText] = useState<string | null>(null);

  const categoryOptions: SelectOption[] = [
    { value: "all", label: "Semua Kategori" },
    { value: "preference", label: "Preferensi" },
    { value: "personal", label: "Pribadi" },
    { value: "work", label: "Pekerjaan" },
    { value: "belonging", label: "Kepemilikan" },
    { value: "health", label: "Kesehatan" },
    { value: "relationship", label: "Hubungan" },
    { value: "general", label: "Umum" },
  ];

  const formCategoryOptions: SelectOption[] = [
    { value: "preference", label: "Preferensi" },
    { value: "personal", label: "Pribadi" },
    { value: "work", label: "Pekerjaan" },
    { value: "belonging", label: "Kepemilikan" },
    { value: "health", label: "Kesehatan" },
    { value: "relationship", label: "Hubungan" },
    { value: "general", label: "Umum" },
  ];

  const noteCategoryOptions: SelectOption[] = [
    { value: "todo", label: "To-Do Checklist" },
    { value: "note", label: "Catatan Bebas" },
    { value: "reminder", label: "Pengingat" },
  ];

  const fetchBrainData = async () => {
    setLoading(true);
    try {
      const [ovRes, telRes, animRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/brain/overview`),
        fetch(`${BACKEND_URL}/api/brain/system-status`),
        fetch(`${BACKEND_URL}/api/brain/animations`).catch(() => null),
      ]);

      if (ovRes.ok) {
        const data = await ovRes.json();
        setStats(data.stats);
        setSpeakers(data.speakers || []);
        setNotes(data.notes || []);
        setMemories(data.memories || []);
        setProjects(data.projects || []);
        setConversations(data.recent_conversations || []);
        if (data.speakers && data.speakers.length > 0) {
          setNewSpeaker(data.speakers[0].name);
        }
      }

      if (telRes.ok) {
        const telData = await telRes.json();
        setTelemetry(telData);
      }

      if (animRes && animRes.ok) {
        const animData = await animRes.json();
        if (Array.isArray(animData) && animData.length > 0) {
          setAnimations(animData);
        } else {
          setAnimations(FALLBACK_ANIMATIONS);
        }
      } else {
        setAnimations(FALLBACK_ANIMATIONS);
      }
    } catch (err) {
      console.error("Error fetching brain overview:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchBrainData();
    }
  }, [isOpen]);

  // Live WebSocket Brain Synchronization
  useEffect(() => {
    const handleBrainSync = () => {
      console.log("[AnaraBrain] Received real-time brain_sync event, refreshing data...");
      fetchBrainData();
    };

    window.addEventListener("anara-brain-sync", handleBrainSync);
    return () => {
      window.removeEventListener("anara-brain-sync", handleBrainSync);
    };
  }, []);

  const handleSaveMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.trim() || !newValue.trim() || !newSpeaker.trim()) return;

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/memories`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          speaker_name: newSpeaker.trim(),
          key: newKey.trim(),
          value: newValue.trim(),
          category: newCategory,
        }),
      });

      if (res.ok) {
        setIsAddMemoryOpen(false);
        setNewKey("");
        setNewValue("");
        fetchBrainData();
      }
    } catch (err) {
      console.error("Save memory error:", err);
    }
  };

  const handleDeleteMemory = async (id: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/memories/${id}`, { method: "DELETE" });
      if (res.ok) {
        setMemories((prev) => prev.filter((m) => m.id !== id));
        fetchBrainData();
      }
    } catch (err) {
      console.error("Delete memory error:", err);
    }
  };

  const handleSaveNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNoteTitle.trim() || !newSpeaker.trim()) return;

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newNoteTitle.trim(),
          content: newNoteContent.trim(),
          category: newNoteCategory,
          speaker_name: newSpeaker.trim(),
        }),
      });

      if (res.ok) {
        setIsAddNoteOpen(false);
        setNewNoteTitle("");
        setNewNoteContent("");
        fetchBrainData();
      }
    } catch (err) {
      console.error("Save note error:", err);
    }
  };

  const handleSaveProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newProjectName.trim(),
          speaker_name: activeSpeaker || newSpeaker,
          tech_stack: newProjectStack.trim(),
          goal: newProjectGoal.trim(),
          notes: newProjectNotes.trim(),
          status: "active"
        }),
      });

      if (res.ok) {
        setIsAddProjectOpen(false);
        setNewProjectName("");
        setNewProjectStack("");
        setNewProjectGoal("");
        setNewProjectNotes("");
        fetchBrainData();
      }
    } catch (err) {
      console.error("Save project error:", err);
    }
  };

  const handleDeleteProject = async (id: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/projects/${id}`, { method: "DELETE" });
      if (res.ok) {
        setProjects((prev) => prev.filter((p) => p.id !== id));
        fetchBrainData();
      }
    } catch (err) {
      console.error("Delete project error:", err);
    }
  };

  const handleSemanticSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!ragQuery.trim()) {
      setRagResults([]);
      return;
    }
    setIsRagSearching(true);
    try {
      const spParam = activeSpeaker ? `&speaker_name=${encodeURIComponent(activeSpeaker)}` : "";
      const res = await fetch(`${BACKEND_URL}/api/brain/semantic-search?query=${encodeURIComponent(ragQuery.trim())}${spParam}`);
      if (res.ok) {
        const data = await res.json();
        setRagResults(data || []);
      }
    } catch (err) {
      console.error("Semantic search error:", err);
    } finally {
      setIsRagSearching(false);
    }
  };

  const handleToggleTodo = async (id: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/notes/${id}/toggle`, { method: "PATCH" });
      if (res.ok) {
        setNotes((prev) =>
          prev.map((n) => (n.id === id ? { ...n, is_completed: n.is_completed ? 0 : 1 } : n))
        );
        fetchBrainData();
      }
    } catch (err) {
      console.error("Toggle todo error:", err);
    }
  };

  const handleDeleteNote = async (id: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/notes/${id}`, { method: "DELETE" });
      if (res.ok) {
        setNotes((prev) => prev.filter((n) => n.id !== id));
        fetchBrainData();
      }
    } catch (err) {
      console.error("Delete note error:", err);
    }
  };

  const handleDeleteSpeaker = async (speakerName: string) => {
    if (!confirm(`Apakah Anda yakin ingin menghapus profil '${speakerName}' beserta semua ingatan dan catatannya?`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/speakers/${encodeURIComponent(speakerName)}`, { method: "DELETE" });
      if (res.ok) {
        setSpeakers((prev) => prev.filter((s) => s.name !== speakerName));
        if (activeSpeaker === speakerName) {
          // Clear backend Gemini Live context AND local UI state
          window.dispatchEvent(
            new CustomEvent("anara-set-active-speaker", { detail: { name: null } })
          );
        }
        fetchBrainData();
      }
    } catch (err) {
      console.error("Delete speaker error:", err);
    }
  };

  const handleSaveSpeaker = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSpeakerInput.trim()) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/speakers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newSpeakerInput.trim() }),
      });
      if (res.ok) {
        setIsAddSpeakerOpen(false);
        setNewSpeakerInput("");
        fetchBrainData();
      }
    } catch (err) {
      console.error("Save speaker error:", err);
    }
  };

  const handleSelectActiveSpeaker = (speakerName: string) => {
    // Propagate to page.tsx which forwards {type: "set_active_speaker"} to the
    // backend WebSocket so the Gemini Live session context switches profiles too.
    window.dispatchEvent(
      new CustomEvent("anara-set-active-speaker", {
        detail: { name: speakerName },
      })
    );
  };

  const handleStartVoiceCalibration = async (speakerName: string) => {
    try {
      setIsCalibrating(true);
      setCalibratingSpeaker(speakerName);
      setCalibrationStatusText("Menyiapkan mikrofon...");

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const audioCtx = new AudioContextClass();
      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }

      // Load calibration AudioWorklet from Blob URL
      const workletBlobUrl = URL.createObjectURL(
        new Blob([CALIBRATION_WORKLET_CODE], { type: "application/javascript" })
      );
      await audioCtx.audioWorklet.addModule(workletBlobUrl);
      URL.revokeObjectURL(workletBlobUrl);

      const source = audioCtx.createMediaStreamSource(stream);
      const recorder = new AudioWorkletNode(audioCtx, "calibration-recorder");

      const rawFloatChunks: Float32Array[] = [];
      recorder.port.onmessage = (e) => {
        if (e.data instanceof Float32Array) {
          rawFloatChunks.push(new Float32Array(e.data));
        }
      };

      // Connecting to destination via zero-gain node is CRITICAL in Chromium so the
      // browser doesn't garbage-collect or pause the AudioWorklet during recording!
      const silentGain = audioCtx.createGain();
      silentGain.gain.value = 0;
      source.connect(recorder);
      recorder.connect(silentGain);
      silentGain.connect(audioCtx.destination);

      for (let sec = 3; sec > 0; sec--) {
        setCalibrationCountdown(sec);
        setCalibrationStatusText(`Bicaralah sekarang... (${sec}s)`);
        await new Promise((r) => setTimeout(r, 1000));
      }

      setCalibrationStatusText("Mengekstrak & mengenkripsi sidik suara...");
      setCalibrationCountdown(null);

      source.disconnect();
      recorder.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      const nativeSampleRate = audioCtx.sampleRate;
      await audioCtx.close();

      // Merge and Resample to 16000Hz
      const totalLen = rawFloatChunks.reduce((acc, c) => acc + c.length, 0);
      const mergedFloat = new Float32Array(totalLen);
      let off = 0;
      for (const c of rawFloatChunks) {
        mergedFloat.set(c, off);
        off += c.length;
      }

      const targetSampleRate = 16000;
      let pcm16: Int16Array;
      if (Math.abs(nativeSampleRate - targetSampleRate) < 100) {
        pcm16 = new Int16Array(mergedFloat.length);
        for (let i = 0; i < mergedFloat.length; i++) {
          const s = Math.max(-1, Math.min(1, mergedFloat[i]));
          pcm16[i] = s < 0 ? s * 32768 : s * 32767;
        }
      } else {
        const ratio = nativeSampleRate / targetSampleRate;
        const targetLen = Math.round(mergedFloat.length / ratio);
        pcm16 = new Int16Array(targetLen);
        for (let i = 0; i < targetLen; i++) {
          const srcIdx = i * ratio;
          const i0 = Math.floor(srcIdx);
          const i1 = Math.min(i0 + 1, mergedFloat.length - 1);
          const frac = srcIdx - i0;
          const s = mergedFloat[i0] * (1 - frac) + mergedFloat[i1] * frac;
          const clamped = Math.max(-1, Math.min(1, s));
          pcm16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
        }
      }

      const uint8 = new Uint8Array(pcm16.buffer);
      let binaryStr = "";
      for (let i = 0; i < uint8.length; i++) {
        binaryStr += String.fromCharCode(uint8[i]);
      }
      const base64Audio = btoa(binaryStr);

      const res = await fetch(
        `${BACKEND_URL}/api/brain/speakers/${encodeURIComponent(speakerName)}/calibrate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ audio_base64: base64Audio }),
        }
      );

      if (res.ok) {
        setCalibrationStatusText(`Sukses! Sidik suara untuk '${speakerName}' berhasil dikalibrasi ke database.`);
        handleSelectActiveSpeaker(speakerName);
        setTimeout(() => {
          setIsCalibrating(false);
          setCalibratingSpeaker(null);
          setCalibrationStatusText(null);
          fetchBrainData();
        }, 1500);
      } else {
        const errData = await res.json().catch(() => ({}));
        setCalibrationStatusText(`Gagal: ${errData.detail || "Audio tidak valid"}`);
        setTimeout(() => {
          setIsCalibrating(false);
          setCalibratingSpeaker(null);
          setCalibrationStatusText(null);
        }, 2000);
      }
    } catch (err: any) {
      console.error("Calibration error:", err);
      setCalibrationStatusText(`Error mikrofon: ${err.message || err}`);
      setTimeout(() => {
        setIsCalibrating(false);
        setCalibratingSpeaker(null);
        setCalibrationStatusText(null);
      }, 2500);
    }
  };

  const handleClearConversations = async () => {
    if (!confirm("Apakah Anda yakin ingin mengosongkan seluruh riwayat log percakapan di database?")) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/conversations`, { method: "DELETE" });
      if (res.ok) {
        setConversations([]);
        fetchBrainData();
      }
    } catch (err) {
      console.error("Clear conversations error:", err);
    }
  };

  const handleDeleteConversation = async (id: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/conversations/${id}`, { method: "DELETE" });
      if (res.ok) {
        setConversations((prev) => prev.filter((c) => c.id !== id));
        fetchBrainData();
      }
    } catch (err) {
      console.error("Delete conversation error:", err);
    }
  };

  const [conversationFilter, setConversationFilter] = useState<"all" | "active">("all");

  const [selectedViewingSpeaker, setSelectedViewingSpeaker] = useState<string | null>(null);

  const effectiveViewingSpeaker = activeSpeaker || selectedViewingSpeaker || (speakers[0]?.name ?? null);

  const currentSpeakerMemories = useMemo(() => {
    if (!effectiveViewingSpeaker) return [];
    return memories.filter((m) => m.speaker_name && m.speaker_name.toLowerCase() === effectiveViewingSpeaker.toLowerCase());
  }, [memories, effectiveViewingSpeaker]);

  const currentSpeakerNotes = useMemo(() => {
    if (!effectiveViewingSpeaker) return [];
    return notes.filter((n) => !n.speaker_name || n.speaker_name.toLowerCase() === effectiveViewingSpeaker.toLowerCase());
  }, [notes, effectiveViewingSpeaker]);

  const currentSpeakerProjects = useMemo(() => {
    if (!effectiveViewingSpeaker) return [];
    return projects.filter((p) => !p.speaker_name || p.speaker_name.toLowerCase() === effectiveViewingSpeaker.toLowerCase());
  }, [projects, effectiveViewingSpeaker]);

  const filteredMemories = useMemo(() => {
    if (!effectiveViewingSpeaker) return [];
    return currentSpeakerMemories.filter((m) => {
      const matchQuery =
        m.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.value.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (m.speaker_name && m.speaker_name.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchCat = selectedCategory === "all" || m.category === selectedCategory;
      return matchQuery && matchCat;
    });
  }, [currentSpeakerMemories, searchQuery, selectedCategory, effectiveViewingSpeaker]);

  const filteredNotes = useMemo(() => {
    if (!effectiveViewingSpeaker) return [];
    return currentSpeakerNotes.filter((n) => {
      if (todoFilter === "active") return !n.is_completed;
      if (todoFilter === "completed") return !!n.is_completed;
      return true;
    });
  }, [currentSpeakerNotes, todoFilter, effectiveViewingSpeaker]);

  const filteredConversations = useMemo(() => {
    if (conversationFilter === "active" && activeSpeaker) {
      return conversations.filter((c) => c.speaker_name && c.speaker_name.toLowerCase() === activeSpeaker.toLowerCase());
    }
    return conversations;
  }, [conversations, conversationFilter, activeSpeaker]);

  const completedNotesCount = useMemo(() => currentSpeakerNotes.filter((n) => n.is_completed).length, [currentSpeakerNotes]);
  const progressPercent = useMemo(() => (currentSpeakerNotes.length > 0 ? Math.round((completedNotesCount / currentSpeakerNotes.length) * 100) : 0), [currentSpeakerNotes, completedNotesCount]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-slate-950/70 backdrop-blur-xl animate-fade-in select-none"
      onClick={onClose}
    >
      {/* ── Ambient Liquid Light Blobs ── */}
      <div className="absolute top-0 left-1/4 w-[560px] h-[560px] bg-cyan-500/[0.07] rounded-full blur-[160px] pointer-events-none animate-liquid-1" />
      <div className="absolute bottom-0 right-1/5 w-[520px] h-[520px] bg-indigo-600/[0.08] rounded-full blur-[160px] pointer-events-none animate-liquid-2" />
      <div className="absolute top-1/3 right-1/3 w-[380px] h-[380px] bg-purple-600/[0.06] rounded-full blur-[140px] pointer-events-none animate-liquid-3" />

      {/* ── Liquid Glass Main Modal Container ── */}
      <div
        className="relative w-[96vw] max-w-5xl h-[88vh] max-h-[900px] rounded-[28px] overflow-hidden flex flex-col pointer-events-auto animate-scale-up liquid-glass-drawer"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Specular Top Light Reflection ── */}
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/60 to-transparent pointer-events-none" />
        {/* ── Inner Liquid Tint ── */}
        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/[0.04] via-transparent to-indigo-600/[0.06] pointer-events-none" />

        {/* ── Liquid Glass Header ── */}
        <div className="relative flex items-center justify-between gap-4 px-6 sm:px-7 py-4 border-b border-white/10 liquid-glass-subtle backdrop-blur-2xl shrink-0">
          <div className="flex items-center gap-3.5 min-w-0">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-cyan-500/25 to-indigo-500/25 border border-white/20 flex items-center justify-center shadow-[inset_0_1px_1px_rgba(255,255,255,0.4),0_4px_16px_rgba(34,211,238,0.15)] shrink-0 text-cyan-300">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h2 className="text-[15px] sm:text-base font-semibold text-white tracking-wide">
                  Anara Brain Console
                </h2>
                {activeSpeaker ? (
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-400/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse mr-1.5 shadow-[0_0_6px_#34d399]" />
                    {activeSpeaker}
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-medium bg-amber-500/15 text-amber-300 border border-amber-400/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse mr-1.5 shadow-[0_0_6px_#f59e0b]" />
                    Sesi Baru
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5 truncate">
                {activeSpeaker
                  ? `${currentSpeakerMemories.length} fakta • ${currentSpeakerNotes.length} tugas • profil terkalibrasi`
                  : `${speakers.length} profil terdaftar di SQLite`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={fetchBrainData}
              className="crystal-glass-btn px-3.5 py-2 rounded-xl text-slate-200 hover:text-white text-xs font-medium flex items-center gap-1.5 cursor-pointer"
              title="Sinkronkan database"
            >
              <svg className={`w-3.5 h-3.5 text-cyan-300 ${loading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span className="hidden sm:inline">Sinkronkan</span>
            </button>
            <button
              onClick={onClose}
              className="crystal-glass-btn p-2.5 rounded-xl text-slate-300 hover:text-white cursor-pointer"
              title="Tutup (Esc)"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* ── Liquid Glass Tab Strip (single row, scrollable) ── */}
        <div className="flex items-center gap-1.5 px-4 py-2.5 overflow-x-auto no-scrollbar border-b border-white/10 bg-black/20 backdrop-blur-xl shrink-0">
          {[
            {
              id: "memories",
              label: "Ingatan & Fakta",
              icon: (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              ),
              count: activeSpeaker ? currentSpeakerMemories.length : 0,
            },
            {
              id: "todos",
              label: "Catatan & Tugas",
              icon: (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              ),
              count: activeSpeaker ? currentSpeakerNotes.length : 0,
            },
            {
              id: "projects",
              label: "Proyek",
              icon: (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
              ),
              count: activeSpeaker ? currentSpeakerProjects.length : 0,
            },
            {
              id: "speakers",
              label: "Profil Pengguna",
              icon: (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              ),
              count: stats?.speakers_count,
            },
            {
              id: "animations",
              label: "Animasi 3D",
              icon: (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              ),
              count: stats?.animations_count,
            },
            {
              id: "conversations",
              label: "Log Percakapan",
              icon: (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              ),
              count: stats?.conversations_count,
            },
            {
              id: "telemetry",
              label: "Telemetri",
              icon: (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              ),
            },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-full whitespace-nowrap text-xs transition-all duration-200 cursor-pointer border ${
                activeTab === tab.id
                  ? "bg-gradient-to-r from-cyan-500/25 to-indigo-500/25 text-white border-cyan-400/40 font-semibold shadow-[inset_0_1px_1px_rgba(255,255,255,0.3),0_0_16px_rgba(34,211,238,0.15)]"
                  : "liquid-glass-subtle text-slate-400 hover:text-slate-200 hover:bg-white/[0.07] border-transparent"
              }`}
            >
              <span className={activeTab === tab.id ? "text-cyan-300" : "text-slate-500"}>{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.count !== undefined && tab.count > 0 && (
                <span className={`px-1.5 py-px rounded-full text-[10px] font-mono ${
                  activeTab === tab.id ? "bg-cyan-400/20 text-cyan-200" : "bg-white/10 text-slate-400"
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Tab Content Viewport ── */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 select-text custom-scrollbar">
          {/* TAB 1: MEMORIES & FACTS */}
          {activeTab === "memories" && (
            <div className="space-y-5">
              {/* Information Metric Ribbon */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-4 rounded-2xl liquid-glass-subtle">
                  <span className="text-[10px] uppercase tracking-wider text-slate-400">Node Memori</span>
                  <p className="text-base font-bold text-white mt-0.5">{currentSpeakerMemories.length} Fakta</p>
                </div>
                <div className="p-4 rounded-2xl liquid-glass-subtle">
                  <span className="text-[10px] uppercase tracking-wider text-slate-400">Profil Sesi</span>
                  <p className="text-base font-bold text-cyan-300 mt-0.5 truncate">{effectiveViewingSpeaker || "Belum Terdaftar"}</p>
                </div>
                <div className="p-4 rounded-2xl liquid-glass-subtle">
                  <span className="text-[10px] uppercase tracking-wider text-slate-400">Status Sesi</span>
                  <p className={`text-base font-bold mt-0.5 ${activeSpeaker ? "text-emerald-300" : "text-amber-300"}`}>
                    {activeSpeaker ? "Terautentikasi" : "Pratinjau"}
                  </p>
                </div>
                <div className="p-4 rounded-2xl liquid-glass-subtle">
                  <span className="text-[10px] uppercase tracking-wider text-slate-400">Penyimpanan</span>
                  <p className="text-base font-bold text-indigo-300 mt-0.5">SQLite</p>
                </div>
              </div>

              {speakers.length === 0 ? (
                /* Unauthenticated / Fresh Session Standby Card */
                <div className="p-10 sm:p-14 rounded-3xl liquid-glass-subtle text-center flex flex-col items-center justify-center gap-3 animate-fade-in">
                  <div className="w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-400/30 flex items-center justify-center text-cyan-300 shadow-[0_0_24px_rgba(34,211,238,0.2)]">
                    <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  </div>
                  <h4 className="text-sm sm:text-base font-bold text-white uppercase tracking-wider">
                    Belum Ada Profil Terdaftar
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-300 max-w-lg leading-relaxed">
                    Aktifkan mikrofon dan perkenalkan namamu (contoh: <span className="text-cyan-300 font-semibold">&quot;Halo Anara, namaku Agnan&quot;</span>) atau tambahkan profil secara manual di tab Profil Pengguna.
                  </p>
                  <span className="text-[11px] text-cyan-300/90 px-3.5 py-1.5 rounded-full bg-cyan-400/10 border border-cyan-400/25 mt-1">
                    Engine Biometrik Suara 128-D & Multi-Profil Aktif
                  </span>
                </div>
              ) : (
                <>
                  {/* Semantic RAG Cognitive Inspector */}
                  <form onSubmit={handleSemanticSearch} className="p-4 rounded-2xl liquid-glass-subtle space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase tracking-wider text-cyan-300 font-semibold flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                        Pencarian Semantik Kognitif
                      </span>
                      <span className="text-[10px] text-slate-500 hidden sm:inline">Konsep & lintas tabel</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={ragQuery}
                        onChange={(e) => setRagQuery(e.target.value)}
                        placeholder="Ketik topik bebas (cth: 'arsitektur proyek', 'makanan kesukaan')..."
                        className="flex-1 liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                      />
                      <button
                        type="submit"
                        disabled={isRagSearching}
                        className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white font-semibold text-xs transition-all hover:opacity-90 cursor-pointer shrink-0 disabled:opacity-50"
                      >
                        {isRagSearching ? "Mencari..." : "Cari"}
                      </button>
                    </div>

                    {ragResults.length > 0 && (
                      <div className="space-y-2 pt-3 border-t border-white/10 animate-fade-in">
                        <span className="text-[10px] uppercase tracking-wider text-slate-400">Hasil temuan tertinggi:</span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {ragResults.map((item, idx) => (
                            <div key={idx} className="p-3 rounded-xl bg-black/30 border border-white/10 text-xs space-y-1">
                              <div className="flex items-center justify-between text-[10px]">
                                <span className="text-cyan-300 uppercase font-semibold truncate">{item.title}</span>
                                <span className="text-emerald-400 font-bold shrink-0 ml-2">{item.score.toFixed(1)}</span>
                              </div>
                              <p className="text-slate-300 text-[11px] line-clamp-2">{item.content}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </form>

                  {/* Filter & Action Toolbar */}
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5 flex-1">
                      <div className="relative flex-1">
                        <svg className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                        <input
                          type="text"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          placeholder={`Cari ingatan${effectiveViewingSpeaker ? ` milik ${effectiveViewingSpeaker}` : ""}...`}
                          className="w-full liquid-glass-input rounded-2xl py-2.5 pl-10 pr-4 text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none"
                        />
                      </div>
                      <LiquidGlassSelect
                        value={selectedCategory}
                        onChange={setSelectedCategory}
                        options={categoryOptions}
                        className="w-44 shrink-0"
                      />
                    </div>

                    <button
                      onClick={() => setIsAddMemoryOpen(true)}
                      className="px-5 py-2.5 rounded-2xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white text-xs sm:text-sm font-semibold flex items-center justify-center gap-2 cursor-pointer shadow-[0_4px_20px_rgba(34,211,238,0.3)] transition-all hover:opacity-90 active:scale-[0.98] shrink-0"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      <span>Tambah Fakta</span>
                    </button>
                  </div>

                  {/* Add Memory Inline Modal */}
                  {isAddMemoryOpen && (
                    <form onSubmit={handleSaveMemory} className="relative z-30 p-5 rounded-2xl liquid-glass space-y-3.5 animate-fade-in">
                      <h4 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">Fakta Kognitif Baru</h4>
                      <div className="relative z-40 grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <input
                          type="text"
                          value={newSpeaker}
                          onChange={(e) => setNewSpeaker(e.target.value)}
                          placeholder="Nama Pengguna"
                          className="liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                          required
                        />
                        <input
                          type="text"
                          value={newKey}
                          onChange={(e) => setNewKey(e.target.value)}
                          placeholder="Kunci (cth: band_favorit)"
                          className="liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                          required
                        />
                        <LiquidGlassSelect
                          value={newCategory}
                          onChange={setNewCategory}
                          options={formCategoryOptions}
                        />
                      </div>
                      <input
                        type="text"
                        value={newValue}
                        onChange={(e) => setNewValue(e.target.value)}
                        placeholder="Nilai (cth: Avenged Sevenfold)"
                        className="w-full liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                        required
                      />
                      <div className="flex justify-end gap-2.5 pt-1">
                        <button
                          type="button"
                          onClick={() => setIsAddMemoryOpen(false)}
                          className="px-4 py-2 rounded-xl liquid-glass-subtle hover:bg-white/[0.12] border border-white/10 text-slate-300 text-xs cursor-pointer"
                        >
                          Batal
                        </button>
                        <button
                          type="submit"
                          className="px-5 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white font-semibold text-xs cursor-pointer shadow-[0_4px_16px_rgba(34,211,238,0.3)] transition-all hover:opacity-90"
                        >
                          Simpan
                        </button>
                      </div>
                    </form>
                  )}

                  {/* Memory Cards Grid */}
                  {filteredMemories.length === 0 ? (
                    <div className="text-center py-16 rounded-2xl liquid-glass-subtle text-slate-400 text-xs">
                      Belum ada catatan memori tersimpan{effectiveViewingSpeaker ? ` untuk ${effectiveViewingSpeaker}` : ""}.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                      {filteredMemories.map((m) => (
                        <div
                          key={m.id}
                          className="p-5 rounded-2xl liquid-glass-subtle hover:border-cyan-400/40 hover:shadow-[0_8px_30px_rgba(34,211,238,0.12)] transition-all duration-300 flex flex-col justify-between group"
                        >
                          <div>
                            <div className="flex items-center justify-between gap-1.5 mb-2.5">
                              <span className="text-[10px] font-medium uppercase tracking-wider px-2.5 py-1 rounded-full bg-indigo-500/15 text-indigo-200 border border-indigo-400/25">
                                {m.category}
                              </span>
                              <button
                                onClick={() => handleDeleteMemory(m.id)}
                                className="text-slate-500 hover:text-rose-400 opacity-0 group-hover:opacity-100 transition-opacity p-1 cursor-pointer"
                                title="Hapus memori"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </div>
                            <h4 className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                              {m.key.replace(/_/g, " ")}
                            </h4>
                            <p className="text-sm sm:text-[15px] font-semibold text-cyan-100 mt-1 leading-relaxed">{m.value}</p>
                          </div>
                          <span className="text-[10px] text-slate-500 mt-4 pt-2.5 border-t border-white/[0.07]">
                            Diperbarui: {new Date(m.updated_at || m.created_at).toLocaleString("id-ID")}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* TAB 2: NOTES & TODOS */}
          {activeTab === "todos" && (
            <div className="space-y-5">
              {!activeSpeaker ? (
                /* Unauthenticated Standby Card for Todos */
                <div className="p-10 sm:p-14 rounded-3xl liquid-glass-subtle text-center flex flex-col items-center justify-center gap-3 animate-fade-in">
                  <div className="w-14 h-14 rounded-2xl bg-purple-500/15 border border-purple-400/30 flex items-center justify-center text-purple-300 shadow-[0_0_24px_rgba(168,85,247,0.2)]">
                    <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                    </svg>
                  </div>
                  <h4 className="text-sm sm:text-base font-bold text-white uppercase tracking-wider">
                    Menunggu Identifikasi Pengguna
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-300 max-w-lg leading-relaxed">
                    Daftar to-do dan catatan personal disimpan berdasarkan profil pengguna. Silakan bicara atau perkenalkan diri agar Anara memuat tugas Anda.
                  </p>
                </div>
              ) : (
                <>
                  {/* Progress Ribbon */}
                  <div className="p-5 rounded-2xl liquid-glass-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-purple-300 font-semibold">
                        Penyelesaian Tugas • {activeSpeaker}
                      </span>
                      <h3 className="text-base font-bold text-white mt-0.5">
                        {completedNotesCount} dari {currentSpeakerNotes.length} Tugas Selesai ({progressPercent}%)
                      </h3>
                    </div>
                    <div className="w-full sm:w-48 h-2 rounded-full bg-black/40 overflow-hidden border border-white/10">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-purple-500 via-indigo-400 to-cyan-400 transition-all duration-500 shadow-[0_0_10px_rgba(168,85,247,0.4)]"
                        style={{ width: `${progressPercent}%` }}
                      />
                    </div>
                  </div>

                  {/* Filter & Add Actions */}
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-1 p-1 rounded-full liquid-glass-subtle">
                      {[
                        { id: "all", label: "Semua" },
                        { id: "active", label: "Aktif" },
                        { id: "completed", label: "Selesai" },
                      ].map((f) => (
                        <button
                          key={f.id}
                          onClick={() => setTodoFilter(f.id as any)}
                          className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer ${
                            todoFilter === f.id
                              ? "bg-purple-500/25 text-purple-100 border border-purple-400/40"
                              : "text-slate-400 hover:text-slate-200 border border-transparent"
                          }`}
                        >
                          {f.label}
                        </button>
                      ))}
                    </div>

                    <button
                      onClick={() => setIsAddNoteOpen(true)}
                      className="px-4 py-2 rounded-2xl bg-gradient-to-r from-purple-500 to-indigo-500 text-white font-semibold text-xs flex items-center gap-1.5 cursor-pointer shadow-[0_4px_20px_rgba(168,85,247,0.3)] transition-all hover:opacity-90 active:scale-[0.98]"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      Tugas Baru
                    </button>
                  </div>

                  {isAddNoteOpen && (
                    <form onSubmit={handleSaveNote} className="relative z-30 p-5 rounded-2xl liquid-glass space-y-3.5 animate-fade-in">
                      <h4 className="text-xs font-bold text-purple-300 uppercase tracking-wider">Tambah Tugas / Catatan</h4>
                      <div className="relative z-40 grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <input
                          type="text"
                          value={newNoteTitle}
                          onChange={(e) => setNewNoteTitle(e.target.value)}
                          placeholder="Judul Tugas (cth: Evaluasi Laporan)"
                          className="liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none sm:col-span-2"
                          required
                        />
                        <LiquidGlassSelect
                          value={newNoteCategory}
                          onChange={setNewNoteCategory}
                          options={noteCategoryOptions}
                        />
                      </div>
                      <input
                        type="text"
                        value={newNoteContent}
                        onChange={(e) => setNewNoteContent(e.target.value)}
                        placeholder="Deskripsi detail tugas (opsional)"
                        className="w-full liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                      />
                      <div className="flex justify-end gap-2.5 pt-1">
                        <button
                          type="button"
                          onClick={() => setIsAddNoteOpen(false)}
                          className="px-4 py-2 rounded-xl liquid-glass-subtle hover:bg-white/[0.12] border border-white/10 text-slate-300 text-xs cursor-pointer"
                        >
                          Batal
                        </button>
                        <button
                          type="submit"
                          className="px-5 py-2 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-500 text-white font-semibold text-xs cursor-pointer shadow-[0_4px_16px_rgba(168,85,247,0.3)] transition-all hover:opacity-90"
                        >
                          Simpan
                        </button>
                      </div>
                    </form>
                  )}

                  <div className="space-y-2.5">
                    {filteredNotes.length === 0 ? (
                      <p className="text-xs text-slate-400 text-center py-16 rounded-2xl liquid-glass-subtle">Belum ada tugas atau catatan untuk {activeSpeaker}.</p>
                    ) : (
                      filteredNotes.map((n) => (
                        <div
                          key={n.id}
                          className={`p-4 px-5 rounded-2xl border transition-all duration-300 flex items-start justify-between gap-4 ${
                            n.is_completed
                              ? "bg-white/[0.02] border-white/[0.06] opacity-50"
                              : "liquid-glass-subtle hover:border-purple-400/40"
                          }`}
                        >
                          <div className="flex items-start gap-3.5 min-w-0 flex-1">
                            <button
                              onClick={() => handleToggleTodo(n.id)}
                              className={`w-[22px] h-[22px] rounded-lg border flex items-center justify-center shrink-0 mt-0.5 cursor-pointer transition-all duration-200 ${
                                n.is_completed
                                  ? "bg-gradient-to-tr from-emerald-500 to-teal-400 border-emerald-300/60 text-black shadow-[0_0_12px_rgba(52,211,153,0.35)]"
                                  : "border-white/25 hover:border-purple-300 hover:bg-purple-500/20 text-transparent"
                              }`}
                            >
                              <svg className="w-3 h-3 stroke-[3]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                              </svg>
                            </button>
                            <div className="truncate min-w-0 flex-1">
                              <p className={`text-xs sm:text-sm ${n.is_completed ? "line-through text-slate-500 font-normal" : "text-white font-semibold"}`}>
                                {n.title}
                              </p>
                              {n.content && <p className="text-xs text-slate-400 mt-1 leading-relaxed">{n.content}</p>}
                            </div>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-[10px] uppercase tracking-wide px-2.5 py-1 rounded-full bg-purple-500/15 text-purple-300 border border-purple-400/25">
                              {n.category}
                            </span>
                            <button
                              onClick={() => handleDeleteNote(n.id)}
                              className="text-slate-500 hover:text-rose-400 p-1.5 text-xs cursor-pointer transition-colors"
                              title="Hapus tugas"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB: PROJECTS & WORK CONTEXT */}
          {activeTab === "projects" && (
            <div className="space-y-5">
              {!activeSpeaker ? (
                <div className="p-10 sm:p-14 rounded-3xl liquid-glass-subtle text-center flex flex-col items-center justify-center gap-3 animate-fade-in">
                  <div className="w-14 h-14 rounded-2xl bg-amber-500/15 border border-amber-400/30 flex items-center justify-center text-amber-300 shadow-[0_0_24px_rgba(245,158,11,0.2)]">
                    <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                  </div>
                  <h4 className="text-sm sm:text-base font-bold text-white uppercase tracking-wider">
                    Menunggu Identifikasi Pengguna
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-300 max-w-lg leading-relaxed">
                    Proyek kerja dan riwayat target disimpan khusus per profil. Silakan bicara atau pilih profil Anda agar Anara memuat konteks proyek Anda.
                  </p>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-amber-300 font-semibold">
                        Konteks Proyek • {activeSpeaker}
                      </span>
                      <h3 className="text-base sm:text-lg font-bold text-white mt-0.5">
                        {currentSpeakerProjects.length} Proyek Terdaftar
                      </h3>
                    </div>

                    <button
                      onClick={() => setIsAddProjectOpen(true)}
                      className="px-4 py-2 rounded-2xl bg-gradient-to-r from-amber-500 to-orange-500 text-slate-950 font-bold text-xs flex items-center gap-1.5 cursor-pointer shadow-[0_4px_20px_rgba(245,158,11,0.3)] transition-all hover:opacity-90 active:scale-[0.98]"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      Proyek Baru
                    </button>
                  </div>

                  {isAddProjectOpen && (
                    <form onSubmit={handleSaveProject} className="p-5 rounded-2xl liquid-glass space-y-3.5 animate-fade-in">
                      <h4 className="text-xs font-bold text-amber-300 uppercase tracking-wider">Proyek / Konteks Kerja Baru</h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <input
                          type="text"
                          value={newProjectName}
                          onChange={(e) => setNewProjectName(e.target.value)}
                          placeholder="Nama Proyek (cth: Sistem Asisten Anara)"
                          className="liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                          required
                        />
                        <input
                          type="text"
                          value={newProjectStack}
                          onChange={(e) => setNewProjectStack(e.target.value)}
                          placeholder="Tech Stack (cth: Next.js, FastAPI, SQLite)"
                          className="liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                        />
                      </div>
                      <input
                        type="text"
                        value={newProjectGoal}
                        onChange={(e) => setNewProjectGoal(e.target.value)}
                        placeholder="Target / Sasaran Utama Proyek Ini"
                        className="w-full liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                      />
                      <input
                        type="text"
                        value={newProjectNotes}
                        onChange={(e) => setNewProjectNotes(e.target.value)}
                        placeholder="Catatan tambahan untuk Anara (opsional)"
                        className="w-full liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                      />
                      <div className="flex justify-end gap-2.5 pt-1">
                        <button
                          type="button"
                          onClick={() => setIsAddProjectOpen(false)}
                          className="px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/10 text-slate-300 text-xs cursor-pointer"
                        >
                          Batal
                        </button>
                        <button
                          type="submit"
                          className="px-5 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-slate-950 font-bold text-xs cursor-pointer shadow-[0_4px_16px_rgba(245,158,11,0.3)] transition-all hover:opacity-90"
                        >
                          Simpan
                        </button>
                      </div>
                    </form>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                    {currentSpeakerProjects.length === 0 ? (
                      <p className="col-span-2 text-xs text-slate-400 text-center py-16 rounded-2xl liquid-glass-subtle">Belum ada catatan proyek kerja untuk {activeSpeaker}. Klik 'Proyek Baru' atau ceritakan proyek Anda saat mengobrol.</p>
                    ) : (
                      currentSpeakerProjects.map((p) => (
                        <div
                          key={p.id}
                          className="p-5 rounded-2xl liquid-glass-subtle hover:border-amber-400/40 flex flex-col justify-between gap-3 transition-all duration-300"
                        >
                          <div>
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-bold text-white truncate">{p.name}</span>
                              <span className="text-[10px] uppercase tracking-wide px-2.5 py-1 rounded-full bg-amber-400/15 text-amber-300 border border-amber-400/25 shrink-0">
                                {p.status}
                              </span>
                            </div>
                            {p.tech_stack && (
                              <p className="text-[11px] text-cyan-300 mt-1.5">Tech: {p.tech_stack}</p>
                            )}
                            {p.goal && (
                              <p className="text-xs text-slate-200 mt-2 leading-relaxed">Target: {p.goal}</p>
                            )}
                            {p.notes && (
                              <p className="text-xs text-slate-400 mt-1 italic">{p.notes}</p>
                            )}
                          </div>

                          <div className="flex items-center justify-between pt-2.5 border-t border-white/[0.07] text-[10px] text-slate-500">
                            <span>Diperbarui: {new Date(p.updated_at).toLocaleDateString("id-ID")}</span>
                            <button
                              onClick={() => handleDeleteProject(p.id)}
                              className="text-slate-500 hover:text-rose-400 transition-colors p-1 cursor-pointer"
                              title="Hapus proyek"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB 4: SPEAKERS & BIOMETRICS */}
          {activeTab === "speakers" && (
            <div className="space-y-5">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl liquid-glass-subtle text-xs text-slate-300">
                <div>
                  <span className="text-cyan-300 font-semibold uppercase tracking-wider text-[11px] flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                    Engine Biometrik Sidik Suara 128-D
                  </span>
                  <p className="mt-1.5 leading-relaxed text-slate-400">
                    Sistem mengekstrak vektor MFCC, pitch F0, dan formants dari audio mikrofon secara real-time untuk mengenali pembicara dari database tanpa jeda.
                  </p>
                </div>
                <button
                  onClick={() => setIsAddSpeakerOpen(true)}
                  className="px-4 py-2.5 rounded-2xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white text-xs font-semibold shadow-[0_4px_20px_rgba(34,211,238,0.3)] transition-all flex items-center gap-2 cursor-pointer shrink-0 hover:opacity-90"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Tambah Profil
                </button>
              </div>

              {/* Live Calibration Banner Modal */}
              {isCalibrating && (
                <div className="p-4 rounded-2xl liquid-glass border border-cyan-400/40 shadow-[0_0_30px_rgba(34,211,238,0.2)] animate-fade-in flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center text-cyan-300">
                      {calibrationCountdown !== null ? (
                        <span className="font-mono font-bold text-lg">{calibrationCountdown}</span>
                      ) : (
                        <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                        </svg>
                      )}
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-white uppercase tracking-wide">
                        Kalibrasi Sidik Suara: {calibratingSpeaker}
                      </h4>
                      <p className="text-xs text-cyan-300 mt-0.5">{calibrationStatusText}</p>
                    </div>
                  </div>
                  <span className="text-[11px] text-cyan-300/90 bg-cyan-500/10 px-3 py-1.5 rounded-lg border border-cyan-400/25 hidden sm:inline">
                    16kHz PCM
                  </span>
                </div>
              )}

              {/* Add Speaker Modal */}
              {isAddSpeakerOpen && (
                <div className="p-5 rounded-2xl liquid-glass space-y-4 animate-fade-in">
                  <div className="flex items-center justify-between border-b border-white/10 pb-3">
                    <h4 className="text-sm font-bold text-white flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                      Daftarkan Profil Pembicara Baru
                    </h4>
                    <button
                      onClick={() => setIsAddSpeakerOpen(false)}
                      className="text-slate-400 hover:text-white p-1 cursor-pointer"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <form onSubmit={handleSaveSpeaker} className="space-y-4">
                    <div>
                      <label className="block text-xs text-slate-400 mb-1.5 uppercase tracking-wider">
                        Nama Pembicara (Contoh: Agnan, Sarah, Budi)
                      </label>
                      <input
                        type="text"
                        required
                        value={newSpeakerInput}
                        onChange={(e) => setNewSpeakerInput(e.target.value)}
                        placeholder="Ketik nama pembicara..."
                        className="w-full liquid-glass-input rounded-xl px-4 py-2.5 text-white text-xs placeholder-slate-500 focus:outline-none"
                      />
                    </div>
                    <div className="flex justify-end gap-2.5 pt-1">
                      <button
                        type="button"
                        onClick={() => setIsAddSpeakerOpen(false)}
                        className="px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/10 text-slate-300 text-xs cursor-pointer"
                      >
                        Batal
                      </button>
                      <button
                        type="submit"
                        className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white text-xs font-semibold shadow-[0_4px_16px_rgba(34,211,238,0.3)] cursor-pointer hover:opacity-90"
                      >
                        Simpan Profil
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {speakers.length === 0 ? (
                <div className="py-12 px-6 rounded-2xl border border-dashed border-white/15 bg-white/[0.02] text-center space-y-3">
                  <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-400/25 flex items-center justify-center mx-auto text-cyan-300">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                  <h4 className="text-sm font-semibold text-white">Belum Ada Profil Terdaftar</h4>
                  <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
                    Klik tombol <strong className="text-cyan-300">Tambah Profil</strong> di atas atau perkenalkan nama Anda secara langsung melalui mikrofon untuk membuat profil baru.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  {speakers.map((sp) => {
                  const isActive = Boolean(activeSpeaker && sp.name.toLowerCase() === activeSpeaker.toLowerCase());
                  const hasEmbedding = Boolean(sp.has_voice_embedding || (sp.sample_count && sp.sample_count > 0));
                  return (
                    <div
                      key={sp.id}
                      className={`p-5 rounded-2xl border transition-all duration-300 flex flex-col justify-between relative group ${
                        isActive
                          ? "liquid-glass border-emerald-400/50 shadow-[0_0_30px_rgba(52,211,153,0.15)]"
                          : "liquid-glass-subtle hover:border-cyan-400/35"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3.5 min-w-0">
                          <div className={`w-11 h-11 rounded-2xl flex items-center justify-center font-semibold text-white text-sm shrink-0 border ${
                            isActive
                              ? "bg-gradient-to-tr from-emerald-500/40 to-teal-400/40 border-emerald-300/50 shadow-[0_0_15px_rgba(52,211,153,0.3)]"
                              : "bg-gradient-to-tr from-indigo-500/40 via-purple-500/30 to-cyan-400/40 border-white/20"
                          }`}>
                            {sp.name.slice(0, 2).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <h4 className="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-2 truncate">
                              {sp.name}
                              {isActive && (
                                <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399] animate-pulse shrink-0" />
                              )}
                            </h4>
                            <div className="flex items-center gap-2 mt-1">
                              {hasEmbedding ? (
                                <span className="text-[11px] text-emerald-300 flex items-center gap-1">
                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                  </svg>
                                  {sp.sample_count || 1} Sampel Terkalibrasi
                                </span>
                              ) : (
                                <span className="text-[11px] text-amber-300/90 flex items-center gap-1">
                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                  </svg>
                                  Belum Ada Sidik Suara
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className={`px-2.5 py-1 rounded-full text-[10px] font-semibold ${
                            isActive 
                              ? "bg-emerald-500/15 text-emerald-300 border border-emerald-400/35" 
                              : "bg-white/[0.06] text-slate-400 border border-white/10"
                          }`}>
                            {isActive ? "Aktif" : "Tersimpan"}
                          </span>
                          <button
                            onClick={() => handleDeleteSpeaker(sp.name)}
                            className="text-slate-500 hover:text-rose-400 p-1.5 rounded-lg hover:bg-rose-500/10 transition-all cursor-pointer opacity-0 group-hover:opacity-100"
                            title={`Hapus profil ${sp.name}`}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>

                      {/* Action Bar for Voice Calibration & Activation */}
                      <div className="mt-4 pt-3 border-t border-white/[0.07] flex items-center justify-between gap-2 flex-wrap">
                        <button
                          onClick={() => handleStartVoiceCalibration(sp.name)}
                          disabled={isCalibrating}
                          className="px-3 py-1.5 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/30 text-cyan-200 text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
                        >
                          <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                          </svg>
                          {hasEmbedding ? "Rekalibrasi (3s)" : "Kalibrasi (3s)"}
                        </button>

                        {!isActive && (
                          <button
                            onClick={() => handleSelectActiveSpeaker(sp.name)}
                            className="px-3 py-1.5 rounded-xl bg-white/[0.05] hover:bg-emerald-500/15 hover:border-emerald-400/35 border border-white/10 text-slate-300 hover:text-emerald-200 text-xs transition-all cursor-pointer"
                          >
                            Pilih Aktif
                          </button>
                        )}
                      </div>

                      <div className="mt-3 pt-2.5 border-t border-white/[0.05] flex items-center justify-between text-[11px] text-slate-500">
                        <span>{sp.memory_count || (isActive ? currentSpeakerMemories.length : 0)} Node Fakta</span>
                        <span>Terakhir: {new Date(sp.last_seen).toLocaleDateString("id-ID")}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
              )}
            </div>
          )}

          {/* TAB 4: 3D ANIMATIONS & BEHAVIORS (Database-driven) */}
          {activeTab === "animations" && (
            <div className="space-y-5">
              <div className="p-5 rounded-2xl liquid-glass-subtle text-xs text-slate-300">
                <span className="text-emerald-300 font-semibold uppercase tracking-wider text-[11px]">Pustaka Gestur 3D & Ekspresi</span>
                <p className="mt-1.5 leading-relaxed text-slate-400">
                  Daftar gerakan skeletal dan morph target ekspresi wajah yang terdaftar di database untuk mendukung respons visual interaktif.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {animations.map((a) => (
                  <div key={a.id} className="p-4 px-5 rounded-2xl liquid-glass-subtle hover:border-cyan-400/40 transition-all flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-sm font-bold text-white truncate">{animationLabel(a.name)}</h4>
                        <span className="text-[10px] text-cyan-300 bg-cyan-400/10 border border-cyan-400/20 px-2 py-0.5 rounded-md">
                          {a.gesture}
                        </span>
                        <span className="text-[10px] text-purple-300 bg-purple-400/10 border border-purple-400/20 px-2 py-0.5 rounded-md">
                          {a.emotion}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1.5 leading-relaxed line-clamp-2">
                        {a.description || `Animasi ${a.category} dengan intensitas ${(a.intensity * 100).toFixed(0)}% selama ${a.duration_sec.toFixed(1)} detik`}
                      </p>
                      {a.keywords.length > 0 && (
                        <p className="text-[10px] text-slate-500 mt-1.5 truncate">
                          Trigger: {a.keywords.slice(0, 6).join(", ")}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => onTriggerAnimation?.(a.gesture || a.name, a.emotion)}
                      className="px-3.5 py-2 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/30 border border-cyan-400/35 text-cyan-200 text-xs font-semibold transition-all cursor-pointer shrink-0 flex items-center gap-1.5"
                    >
                      <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z" />
                      </svg>
                      <span>Uji</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 5: CONVERSATION LOGS */}
          {activeTab === "conversations" && (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-5 rounded-2xl liquid-glass-subtle">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[11px] uppercase tracking-wider text-cyan-300 font-bold">
                      Riwayat Percakapan Episodik
                    </span>
                    <span className="text-[10px] text-slate-400 bg-white/[0.06] px-2 py-0.5 rounded-full border border-white/10">
                      {filteredConversations.length} / {conversations.length} entri
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Rekaman log dialog multi-sesi yang tersimpan di basis data SQLite.
                  </p>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center">
                  {activeSpeaker && (
                    <div className="flex items-center gap-1 p-1 rounded-full bg-black/30 border border-white/10">
                      <button
                        onClick={() => setConversationFilter("all")}
                        className={`px-2.5 py-1 rounded-full text-xs transition-all cursor-pointer ${
                          conversationFilter === "all"
                            ? "bg-cyan-500/25 text-cyan-100 font-semibold border border-cyan-400/35"
                            : "text-slate-400 hover:text-white border border-transparent"
                        }`}
                      >
                        Semua
                      </button>
                      <button
                        onClick={() => setConversationFilter("active")}
                        className={`px-2.5 py-1 rounded-full text-xs transition-all cursor-pointer ${
                          conversationFilter === "active"
                            ? "bg-emerald-500/25 text-emerald-100 font-semibold border border-emerald-400/35"
                            : "text-slate-400 hover:text-white border border-transparent"
                        }`}
                      >
                        {activeSpeaker}
                      </button>
                    </div>
                  )}

                  {conversations.length > 0 && (
                    <button
                      onClick={handleClearConversations}
                      className="px-3 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/25 border border-rose-400/30 text-rose-300 hover:text-rose-200 text-xs flex items-center gap-1.5 cursor-pointer transition-all"
                      title="Hapus seluruh log riwayat percakapan"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                      <span>Kosongkan</span>
                    </button>
                  )}
                </div>
              </div>

              <div className="space-y-2.5">
                {filteredConversations.length === 0 ? (
                  <div className="text-center py-16 text-slate-400 text-xs liquid-glass-subtle rounded-2xl p-8">
                    Belum ada riwayat percakapan yang cocok dengan filter.
                  </div>
                ) : (
                  filteredConversations.map((c) => {
                    const isCurrentActive = Boolean(
                      c.speaker_name && activeSpeaker && c.speaker_name.toLowerCase() === activeSpeaker.toLowerCase()
                    );
                    const visualImg = c.visual_data?.image_url || c.media_url;

                    return (
                      <div
                        key={c.id}
                        className={`p-4 sm:p-5 rounded-2xl border text-xs sm:text-sm space-y-2.5 transition-all ${
                          isCurrentActive
                            ? "liquid-glass-subtle border-cyan-400/30 hover:border-cyan-400/50"
                            : "liquid-glass-subtle hover:border-white/25"
                        }`}
                      >
                        <div className="flex items-center justify-between text-xs border-b border-white/[0.07] pb-2.5">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span
                              className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                                isCurrentActive
                                  ? "bg-emerald-500/15 text-emerald-300 border-emerald-400/35"
                                  : "bg-indigo-500/15 text-indigo-300 border-indigo-400/25"
                              }`}
                            >
                              {c.speaker_name || "Tamu"}
                            </span>
                            {c.media_type && (
                              <span className="px-2 py-0.5 rounded-md bg-cyan-400/10 text-cyan-300 text-[10px] border border-cyan-400/25 uppercase">
                                {c.media_type}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2.5 shrink-0">
                            <span className="text-slate-500 text-[11px]">
                              {new Date(c.created_at).toLocaleString("id-ID")}
                            </span>
                            <button
                              onClick={() => handleDeleteConversation(c.id)}
                              className="text-slate-500 hover:text-rose-400 p-1 rounded-md hover:bg-rose-500/10 transition-colors cursor-pointer"
                              title="Hapus entri percakapan ini"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        </div>

                        <div className="space-y-1.5">
                          <p className="text-slate-300 leading-relaxed">
                            <span className="text-slate-500 font-semibold">User:</span> {c.user_text}
                          </p>
                          <p className="text-cyan-100 leading-relaxed">
                            <span className="text-cyan-400 font-semibold">Anara:</span> {c.ai_text}
                          </p>
                        </div>

                        {visualImg && (
                          <div className="pt-2 flex items-center gap-2.5">
                            <img
                              src={visualImg}
                              alt="Visual Projection Thumbnail"
                              className="w-12 h-12 object-cover rounded-xl border border-cyan-400/30"
                              onError={(e) => {
                                (e.target as HTMLElement).style.display = "none";
                              }}
                            />
                            <span className="text-[11px] text-cyan-300">
                              {c.visual_data?.image_title || "Gambar Proyeksi Visual"}
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

          {/* TAB 6: ANARA TELEMETRY */}
          {activeTab === "telemetry" && telemetry && (
            <div className="space-y-5 text-xs">
              <div className="p-6 rounded-2xl liquid-glass-subtle space-y-5">
                <div className="flex items-center justify-between pb-4 border-b border-white/10 flex-wrap gap-2">
                  <div className="flex items-center gap-2.5">
                    <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]" />
                    <span className="font-bold text-cyan-300 uppercase tracking-wider text-sm">Status Core Anara</span>
                  </div>
                  <span className="px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-400/30 text-xs font-bold">
                    {telemetry.core_status}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-slate-200">
                  <div className="p-4 rounded-2xl liquid-glass-subtle">
                    <span className="text-slate-400 text-[10px] uppercase tracking-wider">AI Engine Model</span>
                    <p className="font-bold text-white mt-1 text-sm">{telemetry.ai_model}</p>
                  </div>
                  <div className="p-4 rounded-2xl liquid-glass-subtle">
                    <span className="text-slate-400 text-[10px] uppercase tracking-wider">API Key Pool</span>
                    <p className="font-bold text-cyan-300 mt-1 text-sm">{telemetry.key_pool_total} Akun Aktif (Auto Failover)</p>
                  </div>
                  <div className="p-4 rounded-2xl liquid-glass-subtle">
                    <span className="text-slate-400 text-[10px] uppercase tracking-wider">Database SQLite</span>
                    <p className="font-bold text-purple-300 mt-1 text-sm">{telemetry.db_size_kb} KB (anara_brain.db)</p>
                  </div>
                  <div className="p-4 rounded-2xl liquid-glass-subtle">
                    <span className="text-slate-400 text-[10px] uppercase tracking-wider">Total Memori Nodes</span>
                    <p className="font-bold text-emerald-300 mt-1 text-sm">{telemetry.memory_nodes} Node Aktif</p>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.07] text-slate-300 text-[11px] space-y-2">
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Audio Stream Sample Rate:</span>
                    <span className="text-cyan-300 text-right">16kHz Input PCM16 / 24kHz Output PCM16</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Multimodal HUD Engine:</span>
                    <span className="text-emerald-300 text-right">Active (Web Image / Weather / Code / System)</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Interactive Confirmation:</span>
                    <span className="text-purple-300 text-right">Active (Verbatim Staging Before Commit)</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
