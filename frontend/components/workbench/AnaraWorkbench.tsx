"use client";

import React, { useRef, useEffect, useState, useCallback, useMemo, Suspense, lazy } from "react";
import dynamic from "next/dynamic";
import AnaraHUD, { PlanData } from "../hud/AnaraHUD";
import ChatSessionSidebar from "../sidebar/ChatSessionSidebar";
import type { MediaSession, AnaraMediaPlayerProps } from "../dock/AnaraMediaPlayer";
import type { TokenUsagePayload, ToolProgressPayload } from "@/hooks/useWebSocket";
import { AIModelInfo } from "../dock/ModelSelectorDropdown";
import ChatTimeline from "../chat/ChatTimeline";
import type { InteractiveQuestionData } from "../chat/InteractiveQuestionCard";
import BottomDock from "../dock/BottomDock";
import type { AnaraBrainProps } from "../brain/types";
import { getBackendUrl } from "@/lib/apiClient";
import { getSavedReasoningEffortForModel, resolveSiblingTierModelId } from "@/lib/reasoningEffort";
import type { AnaraCodeIDEProps } from "../ide/AnaraCodeIDE";
import CommandPalette, { CommandItem } from "../command/CommandPalette";
import { useLayoutSplitter } from "@/hooks/useLayoutSplitter";

const AnaraCodeIDE = dynamic<AnaraCodeIDEProps>(() => import("../ide/AnaraCodeIDE"), {
  ssr: false,
});

const WorkbenchTerminal = dynamic(() => import("../ide/WorkbenchTerminal"), {
  ssr: false,
});

const ReviewGitPane = dynamic(() => import("../sidebar/ReviewGitPane"), {
  ssr: false,
});

const AnaraBrain = lazy(() => import("../brain/AnaraBrain"));
const AnaraMediaPlayer = lazy(() => import("../dock/AnaraMediaPlayer"));

export type AssistantStatus = "idle" | "listening" | "thinking" | "speaking";

export interface TranscriptItem {
  speaker: "input" | "output";
  text: string;
  id?: string;
  timestamp?: number | string;
  visualType?: "image" | "weather" | "code" | "system_hud" | "knowledge_card" | "todo_list" | "briefing" | "agent_action" | "document_viewer" | "folder_workspace" | "plan_card" | "interactive_question" | "none";
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
}

const BACKEND_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  (typeof window !== "undefined" ? getBackendUrl() : "http://localhost:8000")
).replace(/\/+$/, "");

export default function AnaraWorkbench({
  status,
  connectionStatus,
  transcript,
  liveToolProgress = null,
  isMicActive,
  isMuted,
  userIntensity,
  aiIntensity,
  interactionMode = "voice",
  activeSpeaker,
  speakerRoster = [],
  onSetInteractionMode,
  onStartSession,
  onSendText,
  onSteer,
  onToggleMute,
  onInterrupt,
  onClearTranscript,
  onTriggerAnimation,
  micDenied = false,
  mediaSession = null,
  mediaControl = null,
  onCloseMedia,
  activeSessionId = null,
  sessionRefreshKey = 0,
  onSelectSession,
  onNewSession,
  onApprovePlan,
  onRejectPlan,
  sidebarWidth,
  onWidthChange,
  initialSidebarTab,
  activeThinkingText = null,
  onAnswerQuestion,
  reasoningEffort,
  onSelectReasoningEffort,
}: AnaraWorkbenchProps) {
  const [inputMessage, setInputMessage] = useState("");
  const [isBrainDrawerOpen, setIsBrainDrawerOpen] = useState(false);
  const [agentMode, setAgentMode] = useState<"plan" | "build">("plan");
  const [voiceModelId, setVoiceModelId] = useState<string>("gemini-3.1-flash-live-preview");
  const [chatModelId, setChatModelId] = useState<string>("9router/ag/gemini-3.8-flash-high");
  const [models, setModels] = useState<AIModelInfo[]>([]);

  const latestPlanChecklist = useMemo(() => {
    const item = transcript.slice().reverse().find((t) => t.planData);
    if (!item?.planData) return null;
    const pd = item.planData;
    const steps = (pd.steps || []).map((s: any) => ({
      title: typeof s === "string" ? s : s?.title || s?.name || "",
      isCompleted: Boolean(s?.completed ?? s?.isCompleted ?? s?.done),
      isInProgress: Boolean(s?.in_progress ?? s?.isInProgress),
    }));
    const completedCount = steps.filter((s: any) => s.isCompleted).length;
    return {
      title: pd.title || "Execution Plan",
      completedCount,
      total: steps.length,
      items: steps,
      status: pd.planStatus || "pending_approval",
    };
  }, [transcript]);

  // Load saved model choices independently for Voice and Chat modes
  useEffect(() => {
    try {
      const vm = localStorage.getItem("anara_voice_model");
      if (vm) setVoiceModelId(vm);
      const cm = localStorage.getItem("anara_chat_model");
      if (cm) setChatModelId(cm);
    } catch {}
  }, []);

  const activeModelId = interactionMode === "voice" ? voiceModelId : chatModelId;

  const handleSelectModel = useCallback(async (newModelId: string) => {
    if (interactionMode === "voice") {
      setVoiceModelId(newModelId);
      try {
        localStorage.setItem("anara_voice_model", newModelId);
        await fetch(`${BACKEND_URL}/api/models/active`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model_id: newModelId }),
        });
      } catch {}
    } else {
      setChatModelId(newModelId);
      try {
        localStorage.setItem("anara_chat_model", newModelId);
      } catch {}
      // Automatically synchronize per-model reasoning effort
      const savedEffort = getSavedReasoningEffortForModel(newModelId);
      onSelectReasoningEffort?.(savedEffort as any);
      // Resolve sibling tier variant if provider encodes tier in model slug (e.g. 9router ag/gemini-3.8-flash -> ag/gemini-3.8-flash-high)
      const resolvedId = resolveSiblingTierModelId(newModelId, savedEffort as any, models);
      const targetModelId = resolvedId || newModelId;
      if (targetModelId !== newModelId) {
        setChatModelId(targetModelId);
        try {
          localStorage.setItem("anara_chat_model", targetModelId);
        } catch {}
      }
      try {
        await fetch(`${BACKEND_URL}/api/models/active`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model_id: targetModelId }),
        });
      } catch {}
    }
  }, [interactionMode, onSelectReasoningEffort, models]);

  const contextPaneRef = useRef<HTMLDivElement>(null);
  const [isContextPaneOpen, setIsContextPaneOpen] = useState(false);
  const [contextTab, setContextTab] = useState<"editor" | "review" | "terminal">("editor");
  const [gitStatus, setGitStatus] = useState<any>(null);

  const fetchGitStatus = useCallback(async () => {
    try {
      const q = activeSessionId ? `?session_id=${activeSessionId}` : "";
      const res = await fetch(`${BACKEND_URL}/api/agent/git/status${q}`);
      if (res.ok) {
        const data = await res.json();
        setGitStatus(data);
      }
    } catch {}
  }, [activeSessionId]);

  useEffect(() => {
    fetchGitStatus();
  }, [fetchGitStatus]);

  // ── Integrated Workbench Context Pane Resizing (Hermes Track-Model Parity) ──
  const {
    size: contextPaneWidth,
    isResizing: isResizingContextPane,
    startResizing: startResizingContextPane,
  } = useLayoutSplitter({
    dimension: "width",
    direction: "left",
    min: 380,
    max: 1100,
    initialSize: 640,
    storageKey: "anara_workbench_context_pane_width",
    targetRef: contextPaneRef,
    throttleReactUpdates: true,
  });
  const [footerDockHeight, setFooterDockHeight] = useState(120);
  const [selectedPreviewImage, setSelectedPreviewImage] = useState<{
    url: string;
    title?: string;
    sourceDomain?: string;
    sourceUrl?: string;
    prompt?: string;
  } | null>(null);

  const handleOpenLightbox = useCallback((data: { url: string; title?: string; sourceDomain?: string; sourceUrl?: string; prompt?: string }) => {
    setSelectedPreviewImage(data);
  }, []);

  // ── Integrated IDE Workbench State with Persistence ──
  const [activeIdeFile, setActiveIdeFile] = useState<{
    isOpen: boolean;
    fileName: string;
    filePath: string;
    fileExt: string;
    fileSizeKb: number;
    content: string;
    originalContent?: string;
  }>({
    isOpen: false,
    fileName: "",
    filePath: "",
    fileExt: "",
    fileSizeKb: 0,
    content: "",
  });

  const [ideTabs, setIdeTabs] = useState<Array<{
    filePath: string;
    fileName: string;
    fileExt: string;
    fileSizeKb: number;
    content: string;
    originalContent?: string;
  }>>([]);

  const [isTerminalOpen, setIsTerminalOpen] = useState(false);
  const isIdeHydratedRef = useRef(false);

  useEffect(() => {
    try {
      const savedTabs = localStorage.getItem("anara_ide_tabs");
      if (savedTabs) {
        const parsed = JSON.parse(savedTabs);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setIdeTabs(parsed);
        }
      }
      const savedFile = localStorage.getItem("anara_ide_active_file");
      if (savedFile) {
        const parsed = JSON.parse(savedFile);
        if (parsed && typeof parsed === "object" && parsed.isOpen) {
          setActiveIdeFile(parsed);
          setIsContextPaneOpen(true);
        }
      }
      const savedTerm = localStorage.getItem("anara_ide_terminal_open");
      if (savedTerm === "true") {
        setIsTerminalOpen(true);
      }
      const savedPaneOpen = localStorage.getItem("anara_context_pane_open");
      if (savedPaneOpen === "true") {
        setIsContextPaneOpen(true);
      }
    } catch {}
    isIdeHydratedRef.current = true;
  }, []);

  useEffect(() => {
    if (!isIdeHydratedRef.current) return;
    try {
      localStorage.setItem("anara_ide_active_file", JSON.stringify(activeIdeFile));
    } catch {}
  }, [activeIdeFile]);

  useEffect(() => {
    if (!isIdeHydratedRef.current) return;
    try {
      localStorage.setItem("anara_ide_tabs", JSON.stringify(ideTabs));
    } catch {}
  }, [ideTabs]);

  useEffect(() => {
    if (!isIdeHydratedRef.current) return;
    try {
      localStorage.setItem("anara_ide_terminal_open", isTerminalOpen ? "true" : "false");
    } catch {}
  }, [isTerminalOpen]);

  // ── Keyboard-First Command Palette & Hotkeys (Hermes/Cursor standard) ──
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      // Ignore hotkeys when typing in regular input or textarea unless it is Escape or Ctrl+K / Ctrl+P
      const isInput = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;

      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "p")) {
        e.preventDefault();
        setIsCommandPaletteOpen((v) => !v);
      } else if (!isInput && (e.ctrlKey || e.metaKey) && e.key === "\\") {
        e.preventDefault();
        setIsContextPaneOpen((v) => !v);
      } else if (!isInput && (e.ctrlKey || e.metaKey) && e.key === "`") {
        e.preventDefault();
        setIsContextPaneOpen(true);
        setContextTab("terminal");
        setIsTerminalOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, []);

  const handleOpenFileIDE = async (filePath: string, fileName: string) => {
    try {
      const q = activeSessionId ? `&session_id=${activeSessionId}` : "";
      const res = await fetch(`${BACKEND_URL}/api/agent/workspace/file-content?path=${encodeURIComponent(filePath)}${q}`);
      if (res.ok) {
        const data = await res.json();
        const fileObj = {
          isOpen: true,
          fileName: data.filename,
          filePath: data.path,
          fileExt: data.ext,
          fileSizeKb: data.size_kb,
          content: data.content,
          originalContent: data.content,
        };
        setActiveIdeFile(fileObj);
        setIsContextPaneOpen(true);
        setContextTab("editor");
        setIdeTabs((prev) => {
          const exists = prev.some((t) => t.filePath === data.path);
          if (exists) {
            return prev.map((t) => (t.filePath === data.path ? { ...t, ...fileObj } : t));
          }
          return [...prev, fileObj];
        });
      }
    } catch (e) {
      console.warn("[IDE Viewer] error loading file:", e);
    }
  };

  const handleSelectIdeTab = (filePath: string, fileName: string) => {
    const existing = ideTabs.find((t) => t.filePath === filePath);
    if (existing) {
      setActiveIdeFile({ ...existing, isOpen: true });
    } else {
      handleOpenFileIDE(filePath, fileName);
    }
  };

  const handleCloseIdeTab = (filePath: string) => {
    const remaining = ideTabs.filter((t) => t.filePath !== filePath);
    setIdeTabs(remaining);
    if (remaining.length === 0) {
      setActiveIdeFile({
        isOpen: false,
        fileName: "",
        filePath: "",
        fileExt: "",
        fileSizeKb: 0,
        content: "",
        originalContent: "",
      });
    } else if (activeIdeFile.filePath === filePath) {
      setActiveIdeFile({ ...remaining[remaining.length - 1], isOpen: true });
    }
  };

  const handleSaveIdeFile = async (filePath: string, newContent: string): Promise<boolean> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/agent/workspace/save-file`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: filePath,
          content: newContent,
          session_id: activeSessionId || undefined,
        }),
      });
      if (res.ok) {
        setActiveIdeFile((prev) => ({ ...prev, content: newContent }));
        setIdeTabs((prev) => prev.map((t) => (t.filePath === filePath ? { ...t, content: newContent } : t)));
        return true;
      }
      return false;
    } catch (e) {
      console.error("[IDE Save Error]:", e);
      return false;
    }
  };

  const handleResetIDE = useCallback(() => {
    setActiveIdeFile({
      isOpen: false,
      fileName: "",
      filePath: "",
      fileExt: "",
      fileSizeKb: 0,
      content: "",
      originalContent: "",
    });
    setIdeTabs([]);
    setIsTerminalOpen(false);
    try {
      localStorage.removeItem("anara_ide_active_file");
      localStorage.removeItem("anara_ide_tabs");
      localStorage.removeItem("anara_ide_terminal_open");
      localStorage.removeItem("anara_ide_edited_contents");
      sessionStorage.removeItem("anara_ide_edited_contents");
      localStorage.removeItem("anara_ide_workspace_key");
    } catch {}
  }, []);

  const handleNewSession = useCallback(() => {
    handleResetIDE();
    onNewSession?.();
  }, [handleResetIDE, onNewSession]);

  const handleSelectSession = useCallback(
    (id: number) => {
      handleResetIDE();
      onSelectSession?.(id);
    },
    [handleResetIDE, onSelectSession]
  );

  const handleToggleTerminal = (targetState?: boolean) => {
    const nextState = targetState !== undefined ? targetState : !isTerminalOpen;
    setIsTerminalOpen(nextState);
  };

  // Fetch AI Models
  const fetchModels = useCallback(async (refresh: boolean = false) => {
    try {
      const url = refresh ? `${BACKEND_URL}/api/models?refresh=true` : `${BACKEND_URL}/api/models`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      const all: any[] = data.models || [];
      const filtered = all.filter((m: any) => m.is_configured);
      setModels(filtered);
    } catch {}
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleFolderUpload = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/agent/pick-local-folder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: activeSessionId || undefined, folder_path: "" }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success") {
          handleResetIDE();
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "workspace_updated" } }));
          }
        }
      }
    } catch (e) {
      console.error("[Workspace Native Folder Picker Error]:", e);
    }
  };

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const fd = new FormData();
      fd.append("file", f);
      if (activeSessionId) {
        fd.append("session_id", String(activeSessionId));
      }
      try {
        await fetch(`${BACKEND_URL}/api/agent/upload`, {
          method: "POST",
          body: fd,
        });
      } catch (e) {
        console.warn("[File Upload] failed:", e);
      }
    }
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "workspace_updated" } }));
    }
  };

  const latestVisual = useMemo(
    () => transcript.slice().reverse().find((t) => Boolean(t.visualType && t.visualType !== "none")),
    [transcript]
  );

  const activeIntensity = status === "speaking" ? aiIntensity : userIntensity;
  const isConnected = connectionStatus === "connected";

  // Find active unanswered question if present in current session
  const activeUnansweredQuestion = useMemo(() => {
    for (let i = transcript.length - 1; i >= 0; i--) {
      const item = transcript[i];
      if (item.visualType === "interactive_question" && item.questionData && !item.questionData.isAnswered) {
        return item.questionData;
      }
    }
    return null;
  }, [transcript]);

  // Command palette items for fast keyboard-driven actions
  const commandPaletteItems: CommandItem[] = useMemo(() => {
    const items: CommandItem[] = [
      {
        id: "new-session",
        label: "New Chat Session",
        category: "Workstation",
        shortcut: "Ctrl+N",
        onSelect: () => handleNewSession(),
      },
      {
        id: "toggle-editor",
        label: activeIdeFile.isOpen ? "Close Context Editor" : "Open Context Editor",
        category: "Context Panes",
        sublabel: activeIdeFile.fileName || "Workspace code editor",
        shortcut: "Ctrl+\\",
        onSelect: () => {
          if (activeIdeFile.isOpen) {
            setActiveIdeFile((prev) => ({ ...prev, isOpen: false }));
          } else if (activeIdeFile.filePath) {
            setActiveIdeFile((prev) => ({ ...prev, isOpen: true }));
          } else {
            handleOpenFileIDE("README.md", "README.md");
          }
        },
      },
      {
        id: "toggle-terminal",
        label: isTerminalOpen ? "Hide Terminal Dock" : "Show Terminal Dock",
        category: "Context Panes",
        shortcut: "Ctrl+`",
        onSelect: () => handleToggleTerminal(!isTerminalOpen),
      },
      {
        id: "toggle-mode",
        label: interactionMode === "voice" ? "Switch to Chat Mode (Silent Text)" : "Switch to Voice Mode (3D Avatar)",
        category: "Workstation",
        shortcut: "Ctrl+M",
        onSelect: () => onSetInteractionMode?.(interactionMode === "voice" ? "chat" : "voice"),
      },
      {
        id: "open-brain",
        label: "Anara Brain (Memory, Skills & Providers)",
        category: "Workstation",
        onSelect: () => setIsBrainDrawerOpen(true),
      },
      {
        id: "clear-transcript",
        label: "Clear Conversation Transcript",
        category: "Chat",
        onSelect: () => onClearTranscript?.(),
      },
      {
        id: "open-code-studio",
        label: "Open Fullscreen Anara Code Studio (/code)",
        category: "Navigation",
        onSelect: () => {
          if (typeof window !== "undefined") window.open("/code", "_blank");
        },
      },
    ];

    models.forEach((m) => {
      items.push({
        id: `model-${m.id}`,
        label: `Switch Model: ${m.name || m.id}`,
        category: "AI Models",
        sublabel: m.description,
        onSelect: () => handleSelectModel(m.id),
      });
    });

    return items;
  }, [
    activeIdeFile,
    isTerminalOpen,
    interactionMode,
    models,
    handleNewSession,
    handleToggleTerminal,
    onSetInteractionMode,
    onClearTranscript,
    handleSelectModel,
    handleOpenFileIDE,
  ]);

  return (
    <div className="relative w-full h-full pointer-events-none">
      {/* ── Media Player ── */}
      {mediaSession && (
        <div className="fixed inset-x-0 mx-auto px-4 z-30 pointer-events-auto animate-fade-in transition-all duration-300 bottom-36 sm:bottom-40 max-w-xl sm:max-w-2xl">
          <Suspense fallback={null}>
            <AnaraMediaPlayer
              session={mediaSession}
              ducked={status === "speaking" || status === "thinking"}
              controlSignal={mediaControl}
              onClose={() => onCloseMedia?.()}
            />
          </Suspense>
        </div>
      )}

      {/* ── VOICE MODE ── */}
      {interactionMode === "voice" && (
        <div className="hidden md:block pointer-events-auto">
          <ChatSessionSidebar
            isOpen={true}
            onClose={() => {}}
            activeSessionId={activeSessionId}
            activeSpeaker={activeSpeaker}
            speakerRoster={speakerRoster}
            isConnected={isConnected}
            connectionStatus={connectionStatus}
            onSelectSession={handleSelectSession}
            onNewSession={handleNewSession}
            onOpenBrain={() => setIsBrainDrawerOpen(true)}
            onOpenFileIDE={handleOpenFileIDE}
            onOpenFolder={handleFolderUpload}
            refreshKey={sessionRefreshKey}
            sidebarWidth={sidebarWidth}
            onWidthChange={onWidthChange}
            activeIdeFile={activeIdeFile}
            ideTabs={ideTabs}
            onSelectIdeTab={handleSelectIdeTab}
            onCloseIdeTab={handleCloseIdeTab}
            onSaveIdeFile={handleSaveIdeFile}
            onCloseIDE={() => setActiveIdeFile((prev) => ({ ...prev, isOpen: false }))}
            onResetIDE={handleResetIDE}
            isTerminalOpen={isTerminalOpen}
            onToggleTerminal={handleToggleTerminal}
            onSendText={onSendText}
            agentMode={agentMode}
            status={status}
            embedded={false}
            sessionType="chat"
            initialSidebarTab={initialSidebarTab || "history"}
          />
        </div>
      )}

      {/* ── CHAT MODE: FULL WORKSPACE DUAL-PANE WORKBENCH ── */}
      {interactionMode === "chat" && (
        <div
          className="fixed top-0 bottom-0 z-20 pointer-events-auto flex items-stretch overflow-hidden"
          style={{ left: 0, right: 0 }}
        >
          {/* LEFT PANEL: SIDEBAR CHAT SESSION & EDITOR (Default Left Pane) */}
          <div
            className="hidden md:flex flex-col min-w-0 h-full shrink-0 border-r border-white/10"
            style={{ width: sidebarWidth ? `${sidebarWidth}px` : "var(--sidebar-width, 260px)", transition: "none" }}
            suppressHydrationWarning
          >
            <ChatSessionSidebar
              isOpen={true}
              onClose={() => {}}
              activeSessionId={activeSessionId}
              activeSpeaker={activeSpeaker}
              speakerRoster={speakerRoster}
              isConnected={isConnected}
              connectionStatus={connectionStatus}
              onSelectSession={handleSelectSession}
              onNewSession={handleNewSession}
              onOpenBrain={() => setIsBrainDrawerOpen(true)}
              onOpenFileIDE={handleOpenFileIDE}
              onOpenFolder={handleFolderUpload}
              refreshKey={sessionRefreshKey}
              sidebarWidth={sidebarWidth}
              onWidthChange={onWidthChange}
              activeIdeFile={activeIdeFile}
              ideTabs={ideTabs}
              onSelectIdeTab={handleSelectIdeTab}
              onCloseIdeTab={handleCloseIdeTab}
              onSaveIdeFile={handleSaveIdeFile}
              onCloseIDE={() => setActiveIdeFile((prev) => ({ ...prev, isOpen: false }))}
              onResetIDE={handleResetIDE}
              isTerminalOpen={isTerminalOpen}
              onToggleTerminal={handleToggleTerminal}
              onSendText={onSendText}
              agentMode={agentMode}
              status={status}
              embedded={true}
              sessionType="chat"
              initialSidebarTab={initialSidebarTab || "history"}
            />
          </div>

          {/* RIGHT PANEL: CHAT TIMELINE STREAM & INPUT PROMPT (Default Right Pane) */}
          <div className="flex-1 flex min-w-0 h-full relative overflow-hidden bg-[#060913]">
            {/* Floating Selection Shield during Active Drag */}
            {isResizingContextPane && (
              <div className="absolute inset-0 z-50 cursor-col-resize select-none bg-transparent" />
            )}

            {/* CHAT TIMELINE STREAM & COMPOSER COLUMN */}
            <div
              className="flex flex-col min-w-[360px] h-full relative overflow-hidden"
              style={{
                flex: isContextPaneOpen ? "1 1 auto" : "1 1 100%",
              }}
            >
              {/* Unified Desktop Titlebar Band (Hermes Desktop Parity: 34px) */}
              <div className="h-[34px] shrink-0 px-3 border-b border-white/[0.08] bg-[#060913]/95 backdrop-blur-xl flex items-center justify-between text-xs font-mono select-none z-10">
                <div className="flex items-center gap-2 text-slate-400">
                  <span className="text-white font-medium">Project Anara</span>
                  <span className="text-slate-600">/</span>
                  <span className="text-slate-300">Session #{activeSessionId || "live"}</span>
                  {activeIdeFile && activeIdeFile.isOpen && (
                    <>
                      <span className="text-slate-600">/</span>
                      <span className="text-cyan-300 truncate max-w-[180px]">{activeIdeFile.fileName}</span>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/[0.08] text-[11px] text-slate-300">
                    <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-emerald-400 shadow-[0_0_8px_#34d399]" : "bg-rose-400"}`} />
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider">{activeModelId.split("/").pop()}</span>
                  </div>

                  {/* Context Pane Quick Toggle */}
                  <button
                    type="button"
                    onClick={() => setIsContextPaneOpen((v) => !v)}
                    className={`p-1 rounded-md border transition-all cursor-pointer ${
                      isContextPaneOpen
                        ? "bg-cyan-500/20 border-cyan-400/40 text-cyan-300"
                        : "bg-white/[0.02] border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.06]"
                    }`}
                    title={isContextPaneOpen ? "Hide Context Pane (Ctrl+\\)" : "Show Context Pane (Ctrl+\\)"}
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
                    </svg>
                  </button>

                  {/* Git Review Quick Toggle (Hermes Desktop Parity) */}
                  <button
                    type="button"
                    onClick={() => {
                      setIsContextPaneOpen(true);
                      setContextTab("review");
                      fetchGitStatus();
                    }}
                    className={`p-1 rounded-md border transition-all cursor-pointer flex items-center gap-1 ${
                      isContextPaneOpen && contextTab === "review"
                        ? "bg-cyan-500/20 border-cyan-400/40 text-cyan-300"
                        : "bg-white/[0.02] border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.06]"
                    }`}
                    title="Toggle Git Review Diff Panel"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7a3 3 0 100-6 3 3 0 000 6zm0 0v10m0 0a3 3 0 100 6 3 3 0 000-6zm8-4a3 3 0 100-6 3 3 0 000 6zm0 0v3a4 4 0 01-4 4h-4" />
                    </svg>
                    {gitStatus && gitStatus.changed_count > 0 && (
                      <span className="text-[10px] font-mono font-bold text-cyan-300 pr-0.5">
                        {gitStatus.changed_count}
                      </span>
                    )}
                  </button>

                  {/* Terminal Quick Toggle */}
                  <button
                    type="button"
                    onClick={() => {
                      setIsContextPaneOpen(true);
                      setContextTab("terminal");
                      setIsTerminalOpen((v) => !v);
                    }}
                    className={`p-1 rounded-md border transition-all cursor-pointer ${
                      isContextPaneOpen && contextTab === "terminal"
                        ? "bg-cyan-500/20 border-cyan-400/40 text-cyan-300"
                        : "bg-white/[0.02] border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.06]"
                    }`}
                    title="Toggle Terminal Panel (Ctrl+`)"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </button>

                  {/* Switch to Code Studio IDE Page */}
                  <a
                    href="/code"
                    className="px-2 py-0.5 rounded-md bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] text-[11px] text-slate-300 hover:text-white transition-all flex items-center gap-1"
                    title="Open Full Code Studio IDE"
                  >
                    <span>Studio</span>
                    <svg className="w-2.5 h-2.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                </div>
              </div>

              {/* Scrollable message timeline fills remaining vertical space */}
              <div className="flex-1 min-h-0 relative flex flex-col overflow-hidden">
                <ChatTimeline
                  transcript={transcript}
                  status={status}
                  activeSessionId={activeSessionId || undefined}
                  activeSpeaker={activeSpeaker}
                  activeModelId={activeModelId}
                  liveToolProgress={liveToolProgress}
                  footerDockHeight={footerDockHeight}
                  onApprovePlan={onApprovePlan}
                  activeThinkingText={activeThinkingText}
                  onAnswerQuestion={onAnswerQuestion}
                  onOpenFile={(p: string) => handleOpenFileIDE(p, p.split("/").pop() || "file")}
                  onOpenLightbox={handleOpenLightbox}
                  onSelectPrompt={(text: string) => {
                    setInputMessage(text);
                    const inputEl = document.querySelector('footer textarea') as HTMLTextAreaElement;
                    inputEl?.focus();
                  }}
                />
              </div>

              {/* Anchored Composer Dock — seamless floating card, zero divider lines */}
              <div className="shrink-0 px-3 py-2 sm:px-5 sm:py-3 relative z-20 bg-transparent">
                <div className="max-w-3xl xl:max-w-4xl mx-auto w-full">
                  <BottomDock
                    embedded={true}
                    showAgentModeToggle={false}
                    showInteractionModeToggle={true}
                    inputMessage={inputMessage}
                    setInputMessage={setInputMessage}
                    onSend={(text: string, mode: "plan" | "build") => onSendText?.(text, mode)}
                    onSteer={onSteer}
                    agentMode={agentMode}
                    setAgentMode={setAgentMode}
                    models={models}
                    activeModelId={activeModelId}
                    onSelectModel={handleSelectModel}
                    status={status}
                    isMicActive={isMicActive}
                    isMuted={isMuted}
                    onToggleMute={onToggleMute}
                    onStartSession={onStartSession}
                    onInterrupt={onInterrupt}
                    micDenied={micDenied}
                    activeIntensity={activeIntensity}
                    interactionMode={interactionMode}
                    onSetInteractionMode={onSetInteractionMode}
                    isConnected={isConnected}
                    activeSessionId={activeSessionId}
                    onNewSession={handleNewSession}
                    onFolderUpload={handleFolderUpload}
                    onFileUpload={handleFileUpload}
                    liveToolProgress={liveToolProgress}
                    checklistData={latestPlanChecklist}
                    activeQuestion={activeUnansweredQuestion}
                    onAnswerQuestion={onAnswerQuestion}
                    onHeightChange={setFooterDockHeight}
                    onApprovePlan={onApprovePlan}
                    onRejectPlan={onRejectPlan}
                    reasoningEffort={reasoningEffort}
                    onSelectReasoningEffort={onSelectReasoningEffort}
                  />
                </div>
              </div>
            </div>

            {/* RESIZABLE SASH SPLITTER (Hermes Desktop Parity) */}
            {isContextPaneOpen && (
              <div
                onMouseDown={startResizingContextPane}
                className="relative w-px h-full cursor-col-resize shrink-0 select-none bg-white/[0.08] hover:bg-cyan-400/50 active:bg-cyan-400 transition-colors z-20"
                title="Drag to resize Context Pane"
              >
                <div className="absolute inset-y-0 -left-1.5 w-3 cursor-col-resize bg-transparent" />
              </div>
            )}

            {/* DOCKED CONTEXT PANE: MULTI-TENANT WORKBENCH (Hermes Desktop Parity) */}
            {isContextPaneOpen && (
              <div
                ref={contextPaneRef}
                style={{ width: `${contextPaneWidth}px` }}
                className="hidden lg:flex flex-col min-w-[380px] h-full bg-[#060913]/95 backdrop-blur-xl border-l border-white/[0.08] relative z-10"
              >
                {/* Context Pane Zone Header */}
                <div className="h-[34px] px-3 bg-[#060913] border-b border-white/[0.08] flex items-center justify-between shrink-0 select-none">
                  <div className="flex items-center gap-1.5 font-mono text-xs">
                    <button
                      type="button"
                      onClick={() => setContextTab("editor")}
                      className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all ${
                        contextTab === "editor"
                          ? "bg-white/10 text-cyan-300 font-semibold"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      Editor {activeIdeFile.fileName ? `(${activeIdeFile.fileName})` : ""}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setContextTab("review");
                        fetchGitStatus();
                      }}
                      className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all flex items-center gap-1.5 ${
                        contextTab === "review"
                          ? "bg-white/10 text-cyan-300 font-semibold"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <span>Review</span>
                      {gitStatus && gitStatus.changed_count > 0 && (
                        <span className="w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/40 text-[9.5px] font-bold flex items-center justify-center font-mono">
                          {gitStatus.changed_count}
                        </span>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setContextTab("terminal");
                        setIsTerminalOpen(true);
                      }}
                      className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all ${
                        contextTab === "terminal"
                          ? "bg-white/10 text-cyan-300 font-semibold"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      Terminal
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setIsContextPaneOpen(false);
                      setActiveIdeFile((prev) => ({ ...prev, isOpen: false }));
                    }}
                    className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer"
                    title="Close Context Pane (Ctrl+\\)"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {/* Keep-Alive Pane Zones */}
                <div className="flex-1 min-h-0 relative overflow-hidden flex flex-col">
                  {/* Editor Container */}
                  <div
                    className="flex-1 min-h-0 w-full flex flex-col"
                    style={{ display: contextTab === "editor" ? "flex" : "none" }}
                  >
                    <AnaraCodeIDE
                      isOpen={true}
                      onClose={() => {
                        setIsContextPaneOpen(false);
                        setActiveIdeFile((prev) => ({ ...prev, isOpen: false }));
                      }}
                      fileName={activeIdeFile.fileName}
                      filePath={activeIdeFile.filePath}
                      fileExt={activeIdeFile.fileExt}
                      fileSizeKb={activeIdeFile.fileSizeKb}
                      content={activeIdeFile.content}
                      originalContent={activeIdeFile.originalContent}
                      embedded={true}
                      tabs={ideTabs}
                      onSelectTab={handleSelectIdeTab}
                      onCloseTab={handleCloseIdeTab}
                      onSaveFile={handleSaveIdeFile}
                      isTerminalOpen={isTerminalOpen}
                      onToggleTerminal={handleToggleTerminal}
                      onAskAnara={onSendText ? (fp, fn) => onSendText(`Explain or inspect file: ${fp}`, "plan") : undefined}
                    />

                    {/* Docked Split Terminal */}
                    {isTerminalOpen && (
                      <div className="h-56 border-t border-white/[0.08] shrink-0 flex flex-col">
                        <WorkbenchTerminal
                          embedded={true}
                          isVisible={isTerminalOpen && contextTab === "editor"}
                          onClose={() => setIsTerminalOpen(false)}
                        />
                      </div>
                    )}
                  </div>

                  {/* Review Git Container (Hermes Desktop Parity) */}
                  <div
                    className="h-full w-full"
                    style={{ display: contextTab === "review" ? "flex" : "none" }}
                  >
                    <ReviewGitPane
                      gitStatus={gitStatus}
                      onRefreshGit={fetchGitStatus}
                      sessionId={activeSessionId}
                      activeFilePath={activeIdeFile?.filePath}
                      onSelectDiffFile={(path) => handleOpenFileIDE(path, path.split("/").pop() || "file")}
                      onAgentShip={onSendText ? () => onSendText("Ship active git changes: review diffs, commit changes, and push PR to origin", "build") : undefined}
                    />
                  </div>

                  {/* Full Terminal Container */}
                  <div
                    className="h-full w-full"
                    style={{ display: contextTab === "terminal" ? "flex" : "none" }}
                  >
                    <WorkbenchTerminal
                      embedded={true}
                      isVisible={contextTab === "terminal"}
                      onClose={() => setContextTab("editor")}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── VOICE MODE FLOATING HUD ── */}
      {interactionMode === "voice" && latestVisual && (
        <div
          className="fixed mx-auto max-w-2xl lg:max-w-3xl px-4 z-20 pointer-events-auto animate-fade-in transition-all duration-300 bottom-36 sm:bottom-40"
          style={{ left: "var(--sidebar-width, 260px)", right: 0 }}
        >
          <AnaraHUD
            visualType={latestVisual.visualType === "interactive_question" ? "none" : latestVisual.visualType}
            imageUrl={latestVisual.imageUrl}
            imageTitle={latestVisual.imageTitle}
            sourceDomain={latestVisual.sourceDomain}
            sourceUrl={latestVisual.sourceUrl}
            imagePrompt={latestVisual.imagePrompt}
            images={latestVisual.images}
            weatherData={latestVisual.weatherData}
            codeData={latestVisual.codeData}
            systemHudData={latestVisual.systemHudData}
            knowledgeCardData={latestVisual.knowledgeCardData}
            todoData={latestVisual.todoData}
            briefingData={latestVisual.briefingData}
            agentActionData={latestVisual.agentActionData}
            documentViewerData={latestVisual.documentViewerData}
            workspaceFolderData={latestVisual.workspaceFolderData}
            planData={latestVisual.planData}
            onOpenLightbox={handleOpenLightbox}
            onOpenFile={(p: string) => handleOpenFileIDE(p, p.split("/").pop() || "file")}
            onApprovePlan={onApprovePlan}
          />
        </div>
      )}

      {/* ── VOICE MODE FLOATING BOTTOM DOCK ── */}
      {interactionMode === "voice" && (
        <BottomDock
          embedded={false}
          showAgentModeToggle={false}
          showInteractionModeToggle={true}
          inputMessage={inputMessage}
          setInputMessage={setInputMessage}
          onSend={(text: string, mode: "plan" | "build") => onSendText?.(text, mode)}
          onSteer={onSteer}
          agentMode={agentMode}
          setAgentMode={setAgentMode}
          models={models}
          activeModelId={activeModelId}
          onSelectModel={handleSelectModel}
          status={status}
          isMicActive={isMicActive}
          isMuted={isMuted}
          onToggleMute={onToggleMute}
          onStartSession={onStartSession}
          onInterrupt={onInterrupt}
          micDenied={micDenied}
          activeIntensity={activeIntensity}
          interactionMode={interactionMode}
          onSetInteractionMode={onSetInteractionMode}
          isConnected={isConnected}
          activeSessionId={activeSessionId}
          onNewSession={handleNewSession}
          onFolderUpload={handleFolderUpload}
          onFileUpload={handleFileUpload}
          liveToolProgress={liveToolProgress}
          checklistData={latestPlanChecklist}
          activeQuestion={activeUnansweredQuestion}
          onAnswerQuestion={onAnswerQuestion}
          onHeightChange={setFooterDockHeight}
          onApprovePlan={onApprovePlan}
          onRejectPlan={onRejectPlan}
          reasoningEffort={reasoningEffort}
          onSelectReasoningEffort={onSelectReasoningEffort}
          />
      )}

      {/* ── Lightbox Modal ── */}
      {selectedPreviewImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/85 backdrop-blur-2xl animate-fade-in select-none"
          onClick={() => setSelectedPreviewImage(null)}
        >
          <div
            className="relative max-w-4xl w-full bg-slate-950/90 border border-cyan-400/50 rounded-3xl overflow-hidden shadow-[0_0_60px_rgba(34,211,238,0.3)] flex flex-col pointer-events-auto animate-scale-up"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3.5 bg-gradient-to-r from-cyan-950 via-slate-900 to-indigo-950 border-b border-cyan-400/30">
              <h3 className="text-xs sm:text-sm font-bold text-white tracking-wider font-mono uppercase truncate">
                {selectedPreviewImage.title || "ORIGINAL WEB SEARCH PHOTOS"}
              </h3>
              <button
                onClick={() => setSelectedPreviewImage(null)}
                className="p-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition-all cursor-pointer"
              >
                ✕
              </button>
            </div>
            <div className="relative w-full max-h-[70vh] overflow-hidden flex items-center justify-center bg-black/90 p-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={selectedPreviewImage.url}
                alt={selectedPreviewImage.title}
                className="max-h-[66vh] w-auto max-w-full object-contain rounded-2xl shadow-2xl"
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Anara Brain Modal ── */}
      {isBrainDrawerOpen && (
        <Suspense fallback={null}>
          <AnaraBrain
            isOpen={isBrainDrawerOpen}
            onClose={() => {
              setIsBrainDrawerOpen(false);
              fetchModels(true);
            }}
            onTriggerAnimation={onTriggerAnimation}
            activeSpeaker={activeSpeaker}
          />
        </Suspense>
      )}

      {/* ── Quick Command Palette Overlay (Ctrl+K / Ctrl+P) ── */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        commands={commandPaletteItems}
        onSelectSession={(sid) => handleSelectSession(Number(sid))}
        onOpenFile={(p) => handleOpenFileIDE(p, p.split("/").pop() || "file")}
      />
    </div>
  );
}
