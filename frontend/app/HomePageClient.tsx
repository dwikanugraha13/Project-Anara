"use client";

import React, { useRef, useState, useCallback, useEffect, Suspense, lazy } from "react";
import LoadingScreen from "@/components/ui/LoadingScreen";
import AnaraWorkbench, { type AssistantStatus, type TranscriptItem } from "@/components/workbench/AnaraWorkbench";

const Scene = lazy(() => import("@/components/avatar/Scene"));
import { useWebSocket, type EmotionState, type TranscriptPayload, type TokenUsagePayload, type ToolProgressPayload, type MediaPlayPayload, type MediaControlAction, type SessionSwitchedPayload } from "@/hooks/useWebSocket";
import { useMicrophone } from "@/hooks/useMicrophone";
import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import { playDanceMusic, type ActiveDanceMusic } from "@/lib/danceMusic";
import type { Avatar3DHandle } from "@/components/avatar/Avatar3D";
import {
  ReasoningEffortLevel,
  saveReasoningEffortForModel,
  getSavedReasoningEffortForModel,
} from "@/lib/reasoningEffort";

import { getBackendUrl, getWebSocketUrl } from "@/lib/apiClient";

const AVATAR_URL = "/avatar.glb";

import { getDanceReplyPrompt } from "@/lib/danceDetector";
import { mergeTranscriptText } from "@/lib/transcriptStream";
import { restoreTranscriptFromMessages } from "@/lib/sessionRestoration";

export type TranscriptEntry = TranscriptItem;

export interface HomePageClientProps {
  initialSidebarTab?: "history" | "editor";
  initialSidebarWidth?: number;
}

export default function HomePageClient({
  initialSidebarTab = "history",
  initialSidebarWidth = 260,
}: HomePageClientProps) {
  const avatarRef = useRef<Avatar3DHandle | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [isAvatarLoaded, setIsAvatarLoaded] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus>("idle");
  const [activeSpeaker, setActiveSpeaker] = useState<string | null>(null);
  const [speakerRoster, setSpeakerRoster] = useState<string[]>([]);
  const [mediaSession, setMediaSession] = useState<MediaPlayPayload | null>(null);
  const [mediaControl, setMediaControl] = useState<{ action: MediaControlAction; nonce: number } | null>(null);
  const [interactionMode, setInteractionMode] = useState<"voice" | "chat">("chat");
  const interactionModeRef = useRef<"voice" | "chat">("chat");

  useEffect(() => {
    interactionModeRef.current = interactionMode;
  }, [interactionMode]);

  const handleSetInteractionMode = useCallback((mode: "voice" | "chat") => {
    setInteractionMode(mode);
    interactionModeRef.current = mode;
    try {
      localStorage.setItem("anara_interaction_mode", mode);
    } catch {}
  }, []);

  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const activeSessionIdRef = useRef<number | null>(null);
  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);
  const [sessionRefreshKey, setSessionRefreshKey] = useState(0);
  const [sidebarWidth, setSidebarWidth] = useState<number>(initialSidebarWidth);

  // Hydration-safe initial local storage loader (runs only on client after mount)
  useEffect(() => {
    try {
      const savedWidth = localStorage.getItem("anara_sidebar_width");
      if (savedWidth) {
        const parsed = parseInt(savedWidth, 10);
        if (!isNaN(parsed) && parsed >= 200 && parsed <= 600) {
          setSidebarWidth(parsed);
          document.documentElement.style.setProperty("--sidebar-width", `${parsed}px`);
          document.cookie = `anara_sidebar_width=${parsed}; path=/; max-age=31536000; SameSite=Lax`;
        }
      }

      const savedSession = localStorage.getItem("anara_active_session_id");
      if (savedSession) {
        const parsedSess = Number(savedSession);
        if (!isNaN(parsedSess) && parsedSess > 0) {
          setActiveSessionId(parsedSess);
        }
      }

      const savedMode = localStorage.getItem("anara_interaction_mode");
      if (savedMode === "voice" || savedMode === "chat") {
        setInteractionMode(savedMode);
        interactionModeRef.current = savedMode;
      }

      // Release the transition freeze once hydration and initial layout settle
      setTimeout(() => {
        document.documentElement.classList.remove("preload");
      }, 150);
    } catch {}
  }, []);

  const handleWidthChange = useCallback((newWidth: number) => {
    setSidebarWidth(newWidth);
    try {
      document.documentElement.style.setProperty("--sidebar-width", `${newWidth}px`);
      localStorage.setItem("anara_sidebar_width", newWidth.toString());
      document.cookie = `anara_sidebar_width=${newWidth}; path=/; max-age=31536000; SameSite=Lax`;
    } catch {}
  }, []);



  const [audioIntensity, setAudioIntensity] = useState(0);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [activeThinkingText, setActiveThinkingText] = useState<string | null>(null);
  const pendingTokenUsageRef = useRef<TokenUsagePayload | null>(null);
  const [liveToolProgress, setLiveToolProgress] = useState<ToolProgressPayload | null>(null);
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffortLevel>("medium");
  const intensityIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setIsMounted(true);
    try {
      const activeModel = localStorage.getItem("anara_chat_model") || "";
      const saved = getSavedReasoningEffortForModel(activeModel);
      setReasoningEffort(saved);
    } catch {}
  }, []);

  const handleSelectReasoningEffort = useCallback((lvl: ReasoningEffortLevel) => {
    setReasoningEffort(lvl);
    try {
      const activeModel = localStorage.getItem("anara_chat_model") || "";
      saveReasoningEffortForModel(activeModel, lvl);
    } catch {}
  }, []);

  // ── Audio player ──────────────────────────────────────────────────────────
  const { isPlaying, playAudioChunk, getIntensity, stopAudio, forceUnlock } = useAudioPlayer();

  // ── Dance mode protection ─────────────────────────────────────────────────
  const danceActiveRef = useRef(false);

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

  useEffect(() => {
    return () => {
      try {
        danceAudioCtxRef.current?.close();
      } catch {}
    };
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
      // Session Isolation Guard: Prevent foreign session messages from polluting current timeline
      const msgSessionId = typeof payload === "string" ? undefined : payload.sessionId;
      const currentSid = activeSessionIdRef.current;
      if (msgSessionId && currentSid && msgSessionId !== currentSid) {
        return;
      }

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
      const briefingData = typeof payload === "string" ? undefined : payload.briefingData;
      const agentActionData = typeof payload === "string" ? undefined : payload.agentActionData;
      const documentViewerData = typeof payload === "string" ? undefined : payload.documentViewerData;
      const workspaceFolderData = typeof payload === "string" ? undefined : payload.workspaceFolderData;
      const planData = typeof payload === "string" ? undefined : payload.planData;
      const images = typeof payload === "string" ? undefined : payload.images;
      const mediaType = typeof payload === "string" ? undefined : payload.mediaType;
      const isPartial = typeof payload === "string" ? false : (payload.isPartial ?? false);
      const payloadAgentMode = typeof payload === "string" ? undefined : payload.agentMode;
      const payloadModelId = typeof payload === "string" ? undefined : payload.modelId;
      const payloadDurationText = typeof payload === "string" ? undefined : payload.durationText;
      const payloadIsStreaming = typeof payload === "string" ? false : (payload.isStreaming ?? payload.isPartial ?? false);
      const payloadTokenUsage = typeof payload === "string" ? undefined : payload.tokenUsage;
      const payloadToolsUsed = typeof payload === "string" ? undefined : (payload.toolsUsed || payload.tokenUsage?.toolsUsed);
      const resolvedTokenUsage = payloadTokenUsage || (speaker === "output" ? pendingTokenUsageRef.current || undefined : undefined);
      if (speaker === "output" && resolvedTokenUsage) pendingTokenUsageRef.current = null;

      // Capture thinking snapshot before clearing
      const thinkingSnapshot = activeThinkingText;
      if (!payloadIsStreaming) {
        setActiveThinkingText(null);
      }

      setTranscript((prev) => {
        const lastIdx = prev.length - 1;
        const last = prev[lastIdx];

        const computedDuration = payloadDurationText || (last?.startTime ? `${Math.max(1, Math.round((Date.now() - last.startTime) / 1000))}dtk` : last?.durationText);
        const resolvedToolsUsed = payloadToolsUsed || resolvedTokenUsage?.toolsUsed || last?.toolsUsed;

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
          briefingData,
          agentActionData,
          documentViewerData,
          workspaceFolderData,
          planData,
          mediaType,
          agentMode: payloadAgentMode || last?.agentMode,
          modelId: payloadModelId || last?.modelId,
          durationText: computedDuration,
          tokenUsage: resolvedTokenUsage,
          toolsUsed: resolvedToolsUsed,
          isStreaming: payloadIsStreaming,
          thinkingText: thinkingSnapshot || last?.thinkingText || null,
          startTime: last?.startTime,
        };

        if (prev.length === 0) return [newEntry];

        // 1. User speech / STT input handling
        if (speaker === "input") {
          if (last && last.speaker === "input") {
            return [...prev.slice(0, lastIdx), { ...last, text: isPartial ? text : mergeTranscriptText(last.text, text) }];
          }
          return [...prev, newEntry];
        }

        // 2. Incoming has visual projection (tool execution card, plan card, artifact)
        if (visualType && visualType !== "none") {
          // If updating a running agent action with complete state of the same tool, update in place
          if (
            visualType === "agent_action" &&
            last &&
            last.visualType === "agent_action" &&
            last.agentActionData?.eventType === "agent_action_start" &&
            newEntry.agentActionData?.eventType === "agent_action_complete" &&
            last.agentActionData?.toolName === newEntry.agentActionData?.toolName
          ) {
            return [
              ...prev.slice(0, lastIdx),
              {
                ...last,
                ...newEntry,
                agentMode: payloadAgentMode || last.agentMode,
                modelId: payloadModelId || last.modelId,
                durationText: computedDuration,
                toolsUsed: resolvedToolsUsed,
                startTime: last.startTime,
              },
            ];
          }
          // If replacing an empty pending placeholder without text or visual, replace it
          if (last && last.speaker === "output" && !last.text && (!last.visualType || last.visualType === "none")) {
            return [
              ...prev.slice(0, lastIdx),
              {
                ...newEntry,
                agentMode: payloadAgentMode || last.agentMode,
                modelId: payloadModelId || last.modelId,
                durationText: computedDuration,
                toolsUsed: resolvedToolsUsed,
                startTime: last.startTime,
              },
            ];
          }
          // Otherwise, append as a distinct step in the agent execution timeline (OpenCode style)
          return [...prev, newEntry];
        }

        // 3. Incoming is narrative AI output (no visual card).
        // If last bubble was a visual card (agent_action, plan_card, etc.), this narrative response
        // MUST NEVER merge into it — append as a new narrative output bubble!
        const isLastPlainOutput = Boolean(last && last.speaker === "output" && (!last.visualType || last.visualType === "none"));

        if (!isLastPlainOutput) {
          return [
            ...prev,
            {
              ...newEntry,
              speaker: "output",
              text: text,
              isStreaming: payloadIsStreaming,
              agentMode: payloadAgentMode || last?.agentMode,
              modelId: payloadModelId || last?.modelId,
              durationText: computedDuration,
              tokenUsage: resolvedTokenUsage,
              toolsUsed: resolvedToolsUsed,
              startTime: last?.startTime || Date.now(),
            },
          ];
        }

        // 4. If streaming partial chunk and last is a plain output bubble, update text in-place at 60 FPS
        if (isPartial) {
          return [
            ...prev.slice(0, lastIdx),
            {
              ...last,
              text: text,
              agentMode: payloadAgentMode || last.agentMode,
              modelId: payloadModelId || last.modelId,
              durationText: computedDuration,
              tokenUsage: resolvedTokenUsage || last.tokenUsage,
              toolsUsed: resolvedToolsUsed,
              isStreaming: true,
            },
          ];
        }

        // 5. Final canonical AI response (isPartial === false): replace streaming text with complete canonical text
        return [
          ...prev.slice(0, lastIdx),
          {
            ...last,
            speaker: "output",
            text: text,
            agentMode: payloadAgentMode || last.agentMode,
            modelId: payloadModelId || last.modelId,
            durationText: computedDuration,
            tokenUsage: resolvedTokenUsage || last.tokenUsage,
            toolsUsed: resolvedToolsUsed,
            isStreaming: false,
          },
        ];
      });

      if (speaker === "output" && !isPartial) {
        setAssistantStatus("idle");
        setLiveToolProgress(null);

        // If an artifact was delivered or plan completed, mark active approved plan as completed
        if (visualType === "document_viewer" || visualType === "code" || planData?.planStatus === "completed") {
          setTranscript((prev) =>
            prev.map((item) => {
              if (item.planData && (item.planData.planStatus === "approved" || !item.planData.planStatus)) {
                return {
                  ...item,
                  planData: {
                    ...item.planData,
                    planStatus: "completed" as const,
                  },
                };
              }
              return item;
            })
          );
        }
      }

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
    []
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
    setActiveThinkingText(null);
    // Brief 300ms buffer after speech ends before unpausing microphone
    setTimeout(() => {
      setAssistantStatus("idle");
      avatarRef.current?.setEmotion("neutral");
    }, 300);
  }, []);

  const [latestTokenUsage, setLatestTokenUsage] = useState<any>(null);

  const handleTokenUsage = useCallback((usage: TokenUsagePayload) => {
    setLatestTokenUsage(usage);
    pendingTokenUsageRef.current = usage;
    setTranscript((prev) => {
      const lastIndex = [...prev].map((entry) => entry.speaker).lastIndexOf("output");
      if (lastIndex < 0) return prev;
      const last = prev[lastIndex];
      // Keep usage pending until the final transcript creates/replaces the current reply.
      if (last.text) return prev;
      pendingTokenUsageRef.current = null;
      return [...prev.slice(0, lastIndex), { ...last, tokenUsage: usage, modelId: usage.modelId || last.modelId, toolsUsed: usage.toolsUsed || last.toolsUsed }];
    });
  }, []);

  const handleToolProgress = useCallback((payload: ToolProgressPayload) => {
    setLiveToolProgress(payload);
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

  const handleSessionSwitched = useCallback((payload: SessionSwitchedPayload) => {
    setActiveSessionId(payload.sessionId);
    if (typeof window !== "undefined") {
      localStorage.setItem("anara_active_session_id", String(payload.sessionId));
    }
    const restored = restoreTranscriptFromMessages(payload.messages);

    setTranscript((prev) => {
      // Race-condition guard: ONLY protect if the user is actively waiting for an AI response to finish
      if (prev.length > 0 && restored.length === 0) {
        const lastBubble = prev[prev.length - 1];
        if (lastBubble && lastBubble.speaker === "output" && !lastBubble.text) {
          return prev;
        }
      }
      return restored;
    });

    setSessionRefreshKey((k) => k + 1);
    setAssistantStatus("idle");
    console.log(`[Sessions] Restored ${restored.length} bubble(s) with full HUD artifacts from session #${payload.sessionId}`);
  }, []);

  // Restore messages immediately on mount via fast local HTTP fetch
  useEffect(() => {
    try {
      const savedSession = localStorage.getItem("anara_active_session_id");
      if (savedSession) {
        const parsedSess = Number(savedSession);
        if (!isNaN(parsedSess) && parsedSess > 0) {
          fetch(`${getBackendUrl()}/api/chat/sessions/${parsedSess}`)
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => {
              if (data && data.messages && data.messages.length > 0) {
                handleSessionSwitched({
                  sessionId: parsedSess,
                  title: data.session?.title,
                  messages: data.messages,
                });
              }
            })
            .catch(() => {});
        }
      }
    } catch {}
  }, [handleSessionSwitched]);

  const { status: wsStatus, sendBinary, sendJSON, sendInterrupt, sendText, sendSteer } = useWebSocket({
    url: getWebSocketUrl(),
    onAudioChunk: handleAudioChunk,
    onTranscript: handleTranscript,
    onTokenUsage: handleTokenUsage,
    onToolProgress: handleToolProgress,
    onInterrupted: handleInterrupted,
    onTurnComplete: handleTurnComplete,
    onError: (msg) => {
      if (msg === "Conversation session not found.") {
        localStorage.removeItem("anara_active_session_id");
        setActiveSessionId(null);
        setTranscript([]);
        return;
      }
      // Clean display: do not treat provider limit warnings as fatal browser console crashes
      console.warn("[Provider/WS Notice]", msg);
      setAssistantStatus("idle");
      setTranscript((prev) => {
        if (prev.length === 0) return [{ speaker: "output", text: `${msg}` }];
        const lastIdx = prev.length - 1;
        const last = prev[lastIdx];
        if (last && last.speaker === "output" && !last.text) {
          return [
            ...prev.slice(0, lastIdx),
            { ...last, text: `${msg}` },
          ];
        }
        return prev;
      });
    },
    onEmotionUpdate: handleEmotionUpdate,
    onAcousticEmotion: handleAcousticEmotion,
    onSpeakerIdentified: (name) => {
      console.log(`[App] Active speaker identified: "${name}"`);
      setActiveSpeaker(name || null);
      if (name) {
        setSpeakerRoster((prev) => (prev.includes(name) ? prev : [...prev, name]));
      }
    },
    onSessionSwitched: handleSessionSwitched,
    onSessionIdSync: (sessionId) => {
      setActiveSessionId(sessionId);
      localStorage.setItem("anara_active_session_id", String(sessionId));
    },
    onAgentAction: (payload) => {
      console.log(`[App] Live Agent Action: ${payload.actionTitle} (${payload.eventType})`);
      setTranscript((prev) => {
        const newEntry: TranscriptEntry = {
          speaker: "output",
          text: "",
          visualType: "agent_action",
          agentActionData: payload,
        };
        const lastIdx = prev.length - 1;
        const last = prev[lastIdx];
        if (
          last &&
          last.speaker === "output" &&
          last.visualType === "agent_action" &&
          last.agentActionData?.toolName === payload.toolName
        ) {
          return [...prev.slice(0, lastIdx), newEntry];
        }
        if (last && last.speaker === "output" && !last.text && (!last.visualType || last.visualType === "none")) {
          return [...prev.slice(0, lastIdx), newEntry];
        }
        return [...prev, newEntry];
      });
    },
    onAgentThinking: (text) => {
      setActiveThinkingText(text && text.trim().length > 0 ? text : null);
    },
    onInteractiveQuestion: (payload) => {
      console.log(`[App] Received interactive question: ${payload.question_id}`);
      setActiveThinkingText(null);
      setTranscript((prev) => {
        const newEntry: TranscriptEntry = {
          speaker: "output",
          text: "",
          visualType: "interactive_question",
          questionData: {
            questionId: payload.question_id,
            questions: payload.questions,
            isAnswered: false,
          },
        };
        const lastIdx = prev.length - 1;
        const last = prev[lastIdx];
        if (last && last.speaker === "output" && !last.text && (!last.visualType || last.visualType === "none")) {
          return [...prev.slice(0, lastIdx), newEntry];
        }
        return [...prev, newEntry];
      });
    },
  });

  // Safety watchdog: reset thinking spinner if connection drops or becomes idle
  useEffect(() => {
    if (wsStatus !== "connected" && assistantStatus === "thinking") {
      setAssistantStatus("idle");
    }
  }, [wsStatus, assistantStatus]);

  // Auto-sync saved session on WebSocket connect
  useEffect(() => {
    if (wsStatus === "connected") {
      const savedId = localStorage.getItem("anara_active_session_id");
      if (savedId) {
        const idNum = Number(savedId);
        if (!isNaN(idNum) && idNum > 0) {
          sendJSON({ type: "switch_session", sessionId: idNum });
        }
      }
    }
  }, [wsStatus, sendJSON]);

  const handleSelectSession = useCallback(
    (id: number) => {
      // Eager-clear stale state BEFORE switching session (Anara Parity)
      setTranscript([]);
      setActiveSessionId(id);
      if (typeof window !== "undefined") {
        localStorage.setItem("anara_active_session_id", String(id));
      }
      sendJSON({ type: "switch_session", sessionId: id });
    },
    [sendJSON]
  );

  const handleNewSession = useCallback(() => {
    // Session Pattern: clear state only — session is created lazily on first message send
    // This prevents accumulation of empty "New Chat" sessions
    setActiveSessionId(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("anara_active_session_id");
    }
    setTranscript([]);
  }, []);

  // Wire sendInterrupt & sendText to refs so callbacks can call them without stale closures
  useEffect(() => {
    sendInterruptRef.current = sendInterrupt;
    sendTextRef.current = sendText;
  }, [sendInterrupt, sendText]);

  // ── Active Speaker Console Sync (AnaraBrain → Backend) ─────────────────────
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

  const closeMedia = useCallback(() => {
    setMediaSession(null);
    setMediaControl(null);
  }, []);

  // ── Microphone (Hands-free Continuous Streaming with Clean Auto-Pause) ────
  const handleAudioChunkFromMic = useCallback(
    (pcm16Buffer: ArrayBuffer) => {
      if (interactionModeRef.current !== "voice") return;
      if (danceActiveRef.current) return;
      if (isPlayingRef.current || assistantStatusRef.current === "speaking") {
        return;
      }
      sendBinary(pcm16Buffer);
    },
    [sendBinary]
  );

  const handleUserIntensity = useCallback((intensity: number) => {
    userIntensityRef.current = intensity;
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
      if (userIntensityRef.current > 0.05) {
        setAssistantStatus("listening");
      } else {
        setAssistantStatus((prev: AssistantStatus) => (prev === "speaking" || prev === "listening" ? "idle" : prev));
      }
    } else {
      setAssistantStatus((prev: AssistantStatus) => (prev === "thinking" ? "thinking" : "idle"));
    }
  }, [isPlaying, micStatus, isMuted]);

  useEffect(() => {
    setAssistantStatus("idle");
  }, [interactionMode]);

  useEffect(() => {
    if (assistantStatus === "thinking") {
      const timer = setTimeout(() => {
        setAssistantStatus((prev: AssistantStatus) => (prev === "thinking" ? "idle" : prev));
      }, 15000);
      return () => clearTimeout(timer);
    }
  }, [assistantStatus]);

  useEffect(() => {
    if (isPlaying) {
      let lastReported = 0;
      intensityIntervalRef.current = setInterval(() => {
        const intensity = getIntensity();
        const scaled = intensity * 8;
        avatarRef.current?.setAudioIntensity(scaled);

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
    forceUnlock();
    setAssistantStatus("idle");
    startListening();
  }, [startListening, forceUnlock]);

  const handleSendText = useCallback(
    (text: string, agentMode: "plan" | "build" = "plan") => {
      if (!text.trim()) return;
      const trimmed = text.trim();
      forceUnlock();

      if (danceActiveRef.current) {
        console.log("[Dance] User chatted during dance — smoothly stopping dance and switching focus to conversation");
        activeDanceMusicRef.current?.stop();
        activeDanceMusicRef.current = null;
        danceActiveRef.current = false;
        avatarRef.current?.stopDance();
      }

      const nowMs = Date.now();
      setTranscript((prev) => {
        const cleaned = prev.filter((t, idx, arr) => t.text || idx === arr.length - 1);
        const finalBase = (cleaned.length > 0 && cleaned[cleaned.length - 1].speaker === "output" && !cleaned[cleaned.length - 1].text)
          ? cleaned.slice(0, -1)
          : cleaned;
        return [...finalBase, { speaker: "input", text: trimmed }, { speaker: "output", text: "", agentMode: agentMode, startTime: nowMs }];
      });

      avatarRef.current?.triggerTextMotion(trimmed);
      sendJSON({
        type: "text_input",
        text: trimmed,
        channel: "web",
        platform: "web",
        agent_mode: agentMode,
        reasoning_effort: reasoningEffort,
        sessionId: activeSessionId,
        session_id: activeSessionId,
        session_type: "chat",
      });
      setAssistantStatus("thinking");
    },
    [sendJSON, forceUnlock, activeSessionId, reasoningEffort]
  );

  const handleApprovePlan = useCallback(
    (plan?: any) => {
      const targetPlan = plan || transcript.slice().reverse().find((t) => t.planData)?.planData || {};
      const planTitle = targetPlan.title || "Proposed Plan";

      setTranscript((prev) =>
        prev.map((item) => {
          if (item.planData && (item.planData.title === planTitle || !item.planData.title)) {
            return {
              ...item,
              planData: {
                ...item.planData,
                planStatus: "approved" as const,
              },
            };
          }
          return item;
        })
      );

      const stepsList = (targetPlan.steps || [])
        .map((st: any, i: number) => {
          const title = typeof st === "string" ? st : st?.title || st?.name || "";
          return `${i + 1}. ${title}`;
        })
        .join("\n");

      const techStr = (targetPlan.tech_stack || targetPlan.techStack || []).join(", ");

      const richPrompt = [
        `I approve the plan "${planTitle}". Execute now in Build Mode!`,
        techStr ? `Tech Stack: ${techStr}` : "",
        stepsList ? `Tahapan:\n${stepsList}` : "",
        "Execution Instructions: Implement all required files, components, and logic systematically according to the approved plan.",
      ]
        .filter(Boolean)
        .join("\n\n");

      handleSendText(richPrompt, "build");
    },
    [transcript, handleSendText]
  );

  const handleRejectPlan = useCallback(
    (plan?: any) => {
      const targetPlan = plan || transcript.slice().reverse().find((t) => t.planData)?.planData || {};
      const planTitle = targetPlan.title || "Proposed Plan";

      setTranscript((prev) =>
        prev.map((item) => {
          if (item.planData && (item.planData.title === planTitle || !item.planData.title)) {
            return {
              ...item,
              planData: {
                ...item.planData,
                planStatus: "rejected" as const,
              },
            };
          }
          return item;
        })
      );

      handleSendText(`Plan "${planTitle}" dismissed. Please revise or proceed with another approach.`, "plan");
    },
    [transcript, handleSendText]
  );

  const handleAnswerQuestion = useCallback(
    (questionId: string, answers: any, dismissed: boolean = false) => {
      sendJSON({
        type: "question_response",
        question_id: questionId,
        answers: answers,
        dismissed: dismissed,
      });
      setTranscript((prev) =>
        prev.map((item) => {
          if (item.visualType === "interactive_question" && item.questionData?.questionId === questionId) {
            return {
              ...item,
              questionData: {
                ...item.questionData,
                answers: answers,
                isAnswered: true,
              },
            };
          }
          return item;
        })
      );
    },
    [sendJSON]
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

  // Safety timer: prevent getting permanently stuck on loading screen if WebGL takes too long or fails
  useEffect(() => {
    if (interactionMode === "voice" && !isAvatarLoaded) {
      const timer = setTimeout(() => {
        setIsAvatarLoaded(true);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [interactionMode, isAvatarLoaded]);

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
        background: "radial-gradient(ellipse at 50% 40%, #0b1120 0%, #030712 60%, #010409 100%)",
      }}
    >
      {/* Subtle Refractive Shimmer Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.015)_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none opacity-25" />

      {/* Atmospheric Cosmic Aura Spotlight for 3D Holographic Stage */}
      <div
        className={`absolute inset-0 pointer-events-none transition-opacity duration-700 ${
          interactionMode === "voice" ? "opacity-100" : "opacity-0"
        }`}
        style={{
          background: "radial-gradient(circle at 62% 42%, rgba(34, 211, 238, 0.09) 0%, rgba(99, 102, 241, 0.05) 30%, transparent 65%)",
        }}
      />

      {/* 3D Scene — Kept mounted in WebGL memory to eliminate T-Pose re-initialization glitch, hidden smoothly via CSS GPU in Chat Mode */}
      {isMounted && (
        <div
          className={`absolute inset-0 transition-opacity duration-300 ease-out ${
            interactionMode === "voice"
              ? "opacity-100 pointer-events-auto"
              : "opacity-0 pointer-events-none"
          }`}
          style={{
            transform: interactionMode === "voice" ? "translateX(calc(var(--sidebar-width, 260px) / 2))" : "none",
          }}
          suppressHydrationWarning
        >
          <Suspense fallback={null}>
            <Scene
              avatarUrl={AVATAR_URL}
              isSpeaking={assistantStatus === "speaking"}
              audioIntensity={audioIntensity}
              avatarRef={avatarRef}
              onAvatarLoad={handleAvatarLoad}
              isVoiceMode={interactionMode === "voice"}
              onDanceStart={() => {
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
                danceActiveRef.current = false;
                try {
                  sendTextRef.current?.(JSON.stringify({ type: "dance_end" }));
                } catch {}
                activeDanceMusicRef.current?.stop();
                activeDanceMusicRef.current = null;
                stopAudio();
              }}
            />
          </Suspense>
        </div>
      )}

      {/* Loading overlay (only in voice mode when waiting for 3D model) */}
      {interactionMode === "voice" && !isAvatarLoaded && (
        <LoadingScreen onCancel={() => handleSetInteractionMode("chat")} />
      )}

      {/* Liquid Glass UI Controls & Chat Dock (Always rendered) */}
      {(isAvatarLoaded || interactionMode === "chat") && (
        <AnaraWorkbench
          status={assistantStatus}
          connectionStatus={wsStatus}
          transcript={transcript}
          liveToolProgress={liveToolProgress}
          isMicActive={micStatus === "active"}
          isMuted={isMuted}
          userIntensity={userIntensityRef.current}
          aiIntensity={audioIntensity}
          interactionMode={interactionMode}
          onSetInteractionMode={handleSetInteractionMode}
          onStartSession={handleStartSession}
          onSendText={handleSendText}
          onSteer={sendSteer}
          onToggleMute={toggleMute}
          onInterrupt={handleInterrupt}
          onClearTranscript={handleClearTranscript}
          onTriggerAnimation={handleTriggerAnimation}
          micDenied={micStatus === "denied"}
          activeSpeaker={activeSpeaker}
          speakerRoster={speakerRoster}
          mediaSession={mediaSession}
          mediaControl={mediaControl}
          onCloseMedia={closeMedia}
          activeSessionId={activeSessionId}
          sessionRefreshKey={sessionRefreshKey}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          sidebarWidth={sidebarWidth}
          onWidthChange={handleWidthChange}
          onApprovePlan={handleApprovePlan}
          onRejectPlan={handleRejectPlan}
          onAnswerQuestion={handleAnswerQuestion}
          initialSidebarTab={initialSidebarTab}
          activeThinkingText={activeThinkingText}
          reasoningEffort={reasoningEffort}
          onSelectReasoningEffort={handleSelectReasoningEffort}
          latestTokenUsage={latestTokenUsage}
        />
      )}
    </main>
  );
}
