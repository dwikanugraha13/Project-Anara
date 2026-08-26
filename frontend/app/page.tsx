"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import LoadingScreen from "@/components/LoadingScreen";
import VoiceControls, { type AssistantStatus } from "@/components/VoiceControls";
import Scene from "@/components/Scene";
import { useWebSocket, type EmotionState } from "@/hooks/useWebSocket";
import { useMicrophone } from "@/hooks/useMicrophone";
import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import { playDanceMusic, speakAnaraReady, type ActiveDanceMusic } from "@/lib/danceMusic";
import type { Avatar3DHandle } from "@/components/Avatar3D";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
const AVATAR_URL = "/avatar.glb";

const DANCE_ACTION_WORDS = [
  "nari", "menari", "joget", "dance", "dansa", "rumba",
];

const COMMAND_MARKERS = [
  "dong", "ayo", "coba", "tolong", "bisa", "yuk", "silakan", "coba kamu", "mohon"
];

const INFO_QUERY_MARKERS = [
  "apa itu", "apa tarian", "sejarah", "adat", "tradisional", "nama tarian", "jenis tarian", "asal usul", "artinya", "definisi"
];

const REPEAT_WORDS = [
  "lagi", "sekali lagi", "ulang", "satu lagi", "encore",
];

const NAME_VARIATIONS = [
  "anara", "hanara", "annara", "anarah", "nara"
];

function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ") // Remove all punctuation (case-insensitive Unicode)
    .replace(/\s+/g, " ")
    .trim();
}

const DANCE_STRICT_PATTERNS = [
  /\b(?:ayo|yuk|coba|tolong|minta|silakan)\s+(?:nari|menari|joget|dansa|dance)\b/,
  /\b(?:nari|menari|joget|dansa|dance)\s+(?:dong|sekarang|lagi|yuk|nih|untukku)\b/,
  /\b(?:anara|nara)\s+(?:ayo|yuk|coba|tolong)?\s*(?:nari|menari|joget|dansa|dance)\b/,
  /\b(?:tunjukkan|tampilkan|mainkan)\s+(?:tarian|dance|joget)\s+(?:rumba|3d|mu|kamu)?\b/,
  /\b(?:hibur|hiburan)\s+(?:aku|kami|saya)\s+(?:dengan|pake|pakai)?\s*(?:tarian|nari|joget|dance)\b/,
  /\b(?:dance|nari)\s+for\s+me\b/,
];

function isFrontendDanceCommand(text: string): boolean {
  const norm = normalizeText(text);
  if (!norm) return false;

  // Block questions (e.g. "apa tarian...", "kamu bisa nari gak", "apakah kamu bisa...")
  if (
    INFO_QUERY_MARKERS.some((q) => norm.includes(q)) ||
    /\b(?:apa|apakah|bisa\s+nggak|bisa\s+gak|kenapa|mengapa|siapa|sebutkan)\b/.test(norm)
  ) {
    return false;
  }

  const words = norm.split(" ");
  // Strict rule: Require at least 2 words (never trigger on single words like 'nari' or 'rumba')
  if (words.length < 2) {
    return false;
  }

  const matched = DANCE_STRICT_PATTERNS.some((pat) => pat.test(norm));
  console.log(`[Dance Check] input="${text}" norm="${norm}" matched=${matched}`);
  return matched;
}

function getDanceReplyPrompt(text: string): string {
  const norm = normalizeText(text);
  // 1. Perintah Menari Lagi -> "Oke, musik!"
  if (REPEAT_WORDS.some((q) => norm.includes(q))) {
    return "Sistem: Perintah menari lagi diterima. Ucapkan dengan suara ceria dan manis hanya kalimat ini tanpa kata lain: Oke, musik!";
  }
  // 2. Perintah Langsung -> "Anara siap!"
  return "Sistem: Perintah menari diterima. Ucapkan dengan suara ceria hanya dua kata ini tanpa kata lain: Anara siap!";
}

function mergeTranscriptText(existing: string, incoming: string): string {
  const ex = existing.trim();
  const inc = incoming.trim();
  if (!ex) return incoming;
  if (!inc) return existing;

  // 1. If incoming progressive STT refinement starts with existing, use incoming
  if (inc.startsWith(ex)) return incoming;

  // 2. If existing already contains incoming at the end, keep existing
  if (ex.endsWith(inc)) return existing;

  // 3. If incoming is a progressive sentence expansion from the first word
  const exWords = ex.split(/\s+/);
  const incWords = inc.split(/\s+/);
  if (incWords.length >= exWords.length && incWords[0].toLowerCase() === exWords[0].toLowerCase()) {
    return incoming;
  }

  // 4. Otherwise append delta cleanly with space formatting
  return existing + (existing.endsWith(" ") || incoming.startsWith(" ") ? "" : " ") + incoming;
}

import { type TranscriptPayload } from "@/hooks/useWebSocket";

export interface TranscriptEntry {
  speaker: "input" | "output";
  text: string;
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

export default function HomePage() {
  const avatarRef = useRef<Avatar3DHandle | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [isAvatarLoaded, setIsAvatarLoaded] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus>("idle");
  const [activeSpeaker, setActiveSpeaker] = useState<string | null>(null);
  const [audioIntensity, setAudioIntensity] = useState(0);
  const [userIntensity, setUserIntensity] = useState(0);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const intensityIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // ── Audio player ──────────────────────────────────────────────────────────
  const { isPlaying, playAudioChunk, getIntensity, stopAudio, forceUnlock } = useAudioPlayer();

  // ── Dance mode protection ─────────────────────────────────────────────────
  const danceActiveRef = useRef(false);
  const danceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── WebSocket ─────────────────────────────────────────────────────────────
  const handleAudioChunk = useCallback(
    async (audioData: ArrayBuffer, intensity: number, sampleRate: number) => {
      if (danceActiveRef.current) return; // drop audio during dance mode
      await playAudioChunk(audioData, sampleRate);
      setAssistantStatus("speaking");
    },
    [playAudioChunk]
  );

  const accumulatedAiTextRef = useRef("");
  const sendInterruptRef = useRef<(() => void) | null>(null);
  const sendTextRef = useRef<((text: string) => void) | null>(null);
  const activeDanceMusicRef = useRef<ActiveDanceMusic | null>(null);
  const danceAudioCtxRef = useRef<AudioContext | null>(null);

  const getDanceAudioCtx = useCallback(() => {
    if (!danceAudioCtxRef.current || danceAudioCtxRef.current.state === "closed") {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      danceAudioCtxRef.current = new AudioCtx();
    }
    return danceAudioCtxRef.current;
  }, []);

  // Activate dance mode via Gemini Live LLM voice + Latin music beat!
  const activateDance = useCallback((userText: string = "") => {
    console.log(`[Dance] activateDance() CALLED for userText="${userText}"`);
    activeDanceMusicRef.current?.stop();
    accumulatedAiTextRef.current = "";

    // Queue dance on avatar so it begins Rumba right when Gemini speech ends
    avatarRef.current?.applyBackendEmotion("dance", "joy");

    // Prompt Gemini Live model with contextual phrase
    const prompt = getDanceReplyPrompt(userText);
    sendTextRef.current?.(prompt);
  }, []);

  const handleTranscript = useCallback(
    (payload: TranscriptPayload | string, rawSpeaker?: "input" | "output") => {
      const text = typeof payload === "string" ? payload : payload.text;
      const speaker = typeof payload === "string" ? (rawSpeaker ?? "output") : payload.speaker;
      const visualType = typeof payload === "string" ? undefined : payload.visualType;
      const imageUrl = typeof payload === "string" ? undefined : payload.imageUrl;
      const imagePrompt = typeof payload === "string" ? undefined : payload.imagePrompt;
      const imageTitle = typeof payload === "string" ? undefined : payload.imageTitle;
      const sourceDomain = typeof payload === "string" ? undefined : payload.sourceDomain;
      const sourceUrl = typeof payload === "string" ? undefined : payload.sourceUrl;
      const weatherData = typeof payload === "string" ? undefined : payload.weatherData;
      const codeData = typeof payload === "string" ? undefined : payload.codeData;
      const systemHudData = typeof payload === "string" ? undefined : payload.systemHudData;
      const knowledgeCardData = typeof payload === "string" ? undefined : payload.knowledgeCardData;
      const todoData = typeof payload === "string" ? undefined : payload.todoData;
      const images = typeof payload === "string" ? undefined : payload.images;
      const mediaType = typeof payload === "string" ? undefined : payload.mediaType;

      // Frontend dance interception — fires immediately when input transcript arrives
      if (speaker === "input" && isFrontendDanceCommand(text)) {
        console.log(`[Dance] INTERCEPTED input transcript: "${text}"`);
        setTranscript((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.speaker === "input") {
            return [...prev.slice(0, -1), { speaker: "input", text: mergeTranscriptText(last.text, text) }];
          }
          return [...prev, { speaker: "input", text }];
        });
        avatarRef.current?.applyBackendEmotion("dance", "joy");
        return;
      }

      console.log(`[Transcript] speaker=${speaker} visualType=${visualType} text="${text?.substring(0, 50)}"`);

      // Always update transcript for text bubbles and chat history
      setTranscript((prev) => {
        const newEntry: TranscriptEntry = {
          speaker,
          text,
          visualType,
          imageUrl,
          imagePrompt,
          imageTitle,
          sourceDomain,
          sourceUrl,
          images,
          weatherData,
          codeData,
          systemHudData,
          knowledgeCardData,
          todoData,
          mediaType,
        };

        if (prev.length === 0) return [newEntry];
        const lastIdx = prev.length - 1;
        const last = prev[lastIdx];

        // 1. If incoming has visual projection, attach or append
        if (visualType && visualType !== "none") {
          if (last && last.speaker === "output") {
            return [...prev.slice(0, lastIdx), newEntry];
          }
          return [...prev, newEntry];
        }

        // 2. If incoming is AI output and last bubble is also AI output, merge text while preserving existing visual data
        if (speaker === "output" && last && last.speaker === "output") {
          const updatedText = last.text ? mergeTranscriptText(last.text, text) : text;
          return [
            ...prev.slice(0, lastIdx),
            {
              ...last,
              speaker: "output",
              text: updatedText,
            },
          ];
        }

        // 3. If same speaker continues, merge cleanly
        if (last && last.speaker === speaker) {
          return [...prev.slice(0, lastIdx), { ...last, text: mergeTranscriptText(last.text, text) }];
        }

        return [...prev, newEntry];
      });

      if (avatarRef.current) {
        if (speaker === "output") {
          if (!danceActiveRef.current) {
            avatarRef.current.queueTranscriptVisemes(text, text.length * 80);
            accumulatedAiTextRef.current += " " + text;
            avatarRef.current.triggerTextMotion(accumulatedAiTextRef.current);
          }
        } else if (speaker === "input") {
          avatarRef.current.triggerTextMotion(text);
        }
      }
    },
    [activateDance]
  );

  const handleInterrupted = useCallback(() => {
    if (danceActiveRef.current) return; // don't reset during dance
    stopAudio();
    accumulatedAiTextRef.current = "";
    avatarRef.current?.resetLipSync();
    setAssistantStatus("idle");
    setAudioIntensity(0);
  }, [stopAudio]);

  const assistantStatusRef = useRef<AssistantStatus>("idle");
  useEffect(() => {
    assistantStatusRef.current = assistantStatus;
  }, [assistantStatus]);

  const handleTurnComplete = useCallback(() => {
    if (danceActiveRef.current) return; // don't reset emotion during dance
    accumulatedAiTextRef.current = "";
    // Brief 300ms buffer after speech ends before unpausing microphone
    setTimeout(() => {
      setAssistantStatus("idle");
      avatarRef.current?.setEmotion("neutral");
    }, 300);
  }, []);

  // ── Backend Emotion & Acoustic Tone (Speech Emotion Recognition) ───────────
  const handleEmotionUpdate = useCallback((state: EmotionState) => {
    if (avatarRef.current) {
      avatarRef.current.applyBackendEmotion(state.emotion, state.gesture);
    }
  }, []);

  const handleAcousticEmotion = useCallback((data: any) => {
    if (!data) return;
    // Apply subtle avatar listening reaction in background when not actively speaking
    if (avatarRef.current && !isPlayingRef.current && assistantStatusRef.current !== "speaking") {
      if (data.emotion === "sad") {
        avatarRef.current.applyBackendEmotion("empathy", "empathy");
      } else if (data.emotion === "angry") {
        avatarRef.current.applyBackendEmotion("curious", "question");
      } else if (data.emotion === "happy") {
        avatarRef.current.applyBackendEmotion("laughing", "joy");
      }
    }
  }, []);

  const { status: wsStatus, sendBinary, sendJSON, sendInterrupt, sendText } = useWebSocket({
    url: WS_URL,
    onAudioChunk: handleAudioChunk,
    onTranscript: handleTranscript,
    onInterrupted: handleInterrupted,
    onTurnComplete: handleTurnComplete,
    onError: (msg) => console.error("[WS Error]", msg),
    onEmotionUpdate: handleEmotionUpdate,
    onAcousticEmotion: handleAcousticEmotion,
    onSpeakerIdentified: (name) => {
      console.log(`[App] Active speaker identified: "${name}"`);
      setActiveSpeaker(name);
    },
  });

  // Wire sendInterrupt & sendText to refs so callbacks can call them without stale closures
  useEffect(() => {
    sendInterruptRef.current = sendInterrupt;
    sendTextRef.current = sendText;
  }, [sendInterrupt, sendText]);

  // ── Active Speaker Console Sync (AnaraBrain → Backend) ─────────────────────
  // When a speaker is selected/changed in the AnaraBrain console, propagate the
  // change to the backend Gemini Live session context AND local UI state.
  useEffect(() => {
    const handleSetActiveSpeaker = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      const name: string | null = detail?.name ?? null;
      console.log(`[Speaker] Console requested active speaker switch -> "${name}"`);
      setActiveSpeaker(name);
      try {
        sendJSON({ type: "set_active_speaker", name });
      } catch (err) {
        console.warn("[Speaker] Failed to send set_active_speaker:", err);
      }
    };

    window.addEventListener("anara-set-active-speaker", handleSetActiveSpeaker);
    return () => window.removeEventListener("anara-set-active-speaker", handleSetActiveSpeaker);
  }, [sendJSON]);

  const isPlayingRef = useRef(false);
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  const userIntensityRef = useRef(0);
  useEffect(() => {
    userIntensityRef.current = userIntensity;
  }, [userIntensity]);

  // ── Mode Separation (Voice Mode vs Chat Mode) ──
  const [interactionMode, setInteractionMode] = useState<"voice" | "chat">("voice");
  const interactionModeRef = useRef<"voice" | "chat">("voice");
  useEffect(() => {
    interactionModeRef.current = interactionMode;
  }, [interactionMode]);

  // ── Microphone (Hands-free Continuous Streaming with Clean Auto-Pause) ────
  const handleAudioChunkFromMic = useCallback(
    (pcm16Buffer: ArrayBuffer) => {
      // ONLY stream audio to Gemini Live when in Voice Mode
      if (interactionModeRef.current !== "voice") return;
      // Block mic entirely during dance
      if (danceActiveRef.current) return;
      // Smart Auto-Pause: Temporarily hold mic stream while AI is speaking or thinking/retrieving
      // Prevents acoustic speaker feedback, stutter, and premature speech cut-offs
      if (isPlayingRef.current || assistantStatusRef.current === "speaking" || assistantStatusRef.current === "thinking") {
        return;
      }
      sendBinary(pcm16Buffer);
    },
    [sendBinary]
  );

  const handleUserIntensity = useCallback((intensity: number) => {
    setUserIntensity(intensity);
  }, []);

  const {
    status: micStatus,
    isMuted,
    startListening,
    toggleMute,
  } = useMicrophone({
    onAudioChunk: handleAudioChunkFromMic,
    onIntensityChange: handleUserIntensity,
    targetSampleRate: 16000,
  });

  // ── Status sync ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (isPlaying) {
      setAssistantStatus("speaking");
    } else if (micStatus === "active" && !isMuted) {
      if (userIntensity > 0.05) {
        setAssistantStatus("listening");
      } else {
        setAssistantStatus((prev) => (prev === "speaking" || prev === "listening" ? "idle" : prev));
      }
    } else {
      setAssistantStatus("idle");
    }
  }, [isPlaying, micStatus, isMuted, userIntensity]);

  // Update audio intensity for 3D avatar lip-sync (zero React re-render overhead)
  useEffect(() => {
    if (isPlaying) {
      let lastReported = 0;
      intensityIntervalRef.current = setInterval(() => {
        const intensity = getIntensity();
        const scaled = intensity * 8;
        // Direct ref update for ultra-smooth 60fps avatar lip-sync without triggering React tree re-renders
        avatarRef.current?.setAudioIntensity(scaled);

        // Throttle UI waveform state updates to 100ms to keep the Web Audio & animation threads 100% fluid
        if (Math.abs(scaled - lastReported) > 0.10 || (scaled === 0 && lastReported > 0)) {
          lastReported = scaled;
          setAudioIntensity(scaled);
        }
      }, 60);
    } else {
      if (intensityIntervalRef.current) {
        clearInterval(intensityIntervalRef.current);
      }
      setAudioIntensity(0);
      avatarRef.current?.setAudioIntensity(0);
    }

    return () => {
      if (intensityIntervalRef.current) {
        clearInterval(intensityIntervalRef.current);
      }
    };
  }, [isPlaying, getIntensity]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleStartSession = useCallback(() => {
    // forceUnlock resumes AudioContext inside a real user-gesture callback
    forceUnlock();
    startListening();
  }, [startListening, forceUnlock]);

  const handleSendText = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      const trimmed = text.trim();
      forceUnlock(); // Ensure audio playback context is active

      // If dance is currently running, gracefully stop dance so Anara answers the user immediately
      if (danceActiveRef.current) {
        console.log("[Dance] User chatted during dance — smoothly stopping dance and switching focus to conversation");
        activeDanceMusicRef.current?.stop();
        activeDanceMusicRef.current = null;
        danceActiveRef.current = false;
        avatarRef.current?.stopDance();
      }

      // Intercept text dance command
      if (isFrontendDanceCommand(trimmed)) {
        console.log(`[Dance] text command detected: "${trimmed}"`);
        setTranscript((prev) => [...prev, { speaker: "input", text: trimmed }]);
        activateDance(trimmed);
        return;
      }

      // Append user turn and a fresh pending AI output placeholder (cleaning up any old orphaned empty items)
      setTranscript((prev) => {
        const cleaned = prev.filter((t, idx, arr) => t.text || idx === arr.length - 1);
        const finalBase = (cleaned.length > 0 && cleaned[cleaned.length - 1].speaker === "output" && !cleaned[cleaned.length - 1].text)
          ? cleaned.slice(0, -1)
          : cleaned;
        return [...finalBase, { speaker: "input", text: trimmed }, { speaker: "output", text: "" }];
      });

      avatarRef.current?.triggerTextMotion(trimmed);
      sendText(trimmed);
      setAssistantStatus("thinking");
    },
    [sendText, forceUnlock, activateDance]
  );

  const handleInterrupt = useCallback(() => {
    activeDanceMusicRef.current?.stop();
    activeDanceMusicRef.current = null;
    danceActiveRef.current = false;
    avatarRef.current?.stopDance();
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    sendInterrupt();
    stopAudio();
    avatarRef.current?.resetLipSync();
    setAssistantStatus("idle");
    setAudioIntensity(0);
  }, [sendInterrupt, stopAudio]);

  const handleClearTranscript = useCallback(() => {
    setTranscript([]);
  }, []);

  const handleAvatarLoad = useCallback(() => {
    setIsAvatarLoaded(true);
  }, []);

  const handleTriggerAnimation = useCallback((animName: string, emotion: string = "happy") => {
    console.log(`[Brain] Trigger animation: ${animName} (${emotion})`);
    if (animName === "dance") {
      activateDance();
    } else {
      avatarRef.current?.applyBackendEmotion(emotion as any, animName as any);
    }
  }, [activateDance]);

  return (
    <main
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        overflow: "hidden",
        background: "#030712",
      }}
    >
      {/* ── Dynamic Liquid Glass Ambient Background ── */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-slate-900/90 to-indigo-950/60 pointer-events-none" />

      {/* Floating Liquid Orbs with Organic Blur */}
      <div className="absolute -top-16 inset-x-0 mx-auto max-w-4xl h-36 bg-gradient-to-r from-indigo-500/25 via-purple-500/20 to-cyan-400/25 rounded-full blur-[80px] pointer-events-none" />
      <div className="absolute -top-20 -left-20 w-[550px] h-[550px] bg-gradient-to-tr from-indigo-600/20 via-purple-600/15 to-pink-500/10 rounded-full blur-[100px] pointer-events-none animate-liquid-1" />
      <div className="absolute top-1/3 -right-20 w-[600px] h-[600px] bg-gradient-to-bl from-cyan-500/20 via-teal-500/15 to-blue-600/15 rounded-full blur-[110px] pointer-events-none animate-liquid-2" />
      <div className="absolute -bottom-20 left-1/4 w-[650px] h-[450px] bg-gradient-to-tr from-violet-600/20 via-indigo-500/15 to-cyan-400/15 rounded-full blur-[120px] pointer-events-none animate-liquid-3" />

      {/* Subtle Refractive Shimmer Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none opacity-40" />

      {/* 3D Scene — rendered at fixed full-screen level */}
      {isMounted && (
        <Scene
          avatarUrl={AVATAR_URL}
          isSpeaking={assistantStatus === "speaking"}
          audioIntensity={audioIntensity}
          avatarRef={avatarRef}
          onAvatarLoad={handleAvatarLoad}
          onDanceStart={() => {
            console.log("[Dance] onDanceStart — starting Latin Rumba music groove & locking mic during dance!");
            danceActiveRef.current = true;
            try {
              sendTextRef.current?.(JSON.stringify({ type: "dance_start" }));
              const ctx = getDanceAudioCtx();
              activeDanceMusicRef.current = playDanceMusic(ctx, 6.5);
            } catch (e) {
              console.warn("[Dance] Music start error:", e);
            }
          }}
          onDanceEnd={() => {
            console.log("[Dance] onDanceEnd — clearing dance music and unblocking mic");
            danceActiveRef.current = false;
            try {
              sendTextRef.current?.(JSON.stringify({ type: "dance_end" }));
            } catch {}
            activeDanceMusicRef.current?.stop();
            activeDanceMusicRef.current = null;
            stopAudio();
          }}
        />
      )}

      {/* Loading overlay */}
      {!isAvatarLoaded && <LoadingScreen />}

      {/* Liquid Glass UI Controls & Chat Dock */}
      {isAvatarLoaded && (
        <VoiceControls
          status={assistantStatus}
          connectionStatus={wsStatus}
          transcript={transcript}
          isMicActive={micStatus === "active"}
          isMuted={isMuted}
          userIntensity={userIntensity}
          aiIntensity={audioIntensity}
          interactionMode={interactionMode}
          onSetInteractionMode={setInteractionMode}
          onStartSession={handleStartSession}
          onSendText={handleSendText}
          onToggleMute={toggleMute}
          onInterrupt={handleInterrupt}
          onClearTranscript={handleClearTranscript}
          onTriggerAnimation={handleTriggerAnimation}
          micDenied={micStatus === "denied"}
          activeSpeaker={activeSpeaker}
        />
      )}
    </main>
  );
}
