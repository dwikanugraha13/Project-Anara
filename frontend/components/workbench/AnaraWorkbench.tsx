"use client";

import React, { useRef, useEffect, useState, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import AnaraHUD, { PlanData } from "../hud/AnaraHUD";
import ChatSessionSidebar from "../sidebar/ChatSessionSidebar";
import type { MediaSession, AnaraMediaPlayerProps } from "../dock/AnaraMediaPlayer";
import { playAlarmChime, type ActiveAlarm, type AlarmVariant } from "@/lib/alarmSound";
import type { TokenUsagePayload, ToolProgressPayload } from "@/hooks/useWebSocket";
import { AIModelInfo } from "../dock/ModelSelectorDropdown";
import ChatTimeline from "../chat/ChatTimeline";
import type { InteractiveQuestionData } from "../chat/InteractiveQuestionCard";
import BottomDock from "../dock/BottomDock";
import type { AnaraBrainProps } from "../brain/types";

const AnaraBrain = dynamic<AnaraBrainProps>(() => import("../brain/AnaraBrain"), {
  ssr: false,
});
const AnaraMediaPlayer = dynamic<AnaraMediaPlayerProps>(() => import("../dock/AnaraMediaPlayer"), {
  ssr: false,
});

export type AssistantStatus = "idle" | "listening" | "thinking" | "speaking";

export interface TranscriptItem {
  speaker: "input" | "output";
  text: string;
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
  tokenUsage?: TokenUsagePayload;
  toolsUsed?: string[];
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
  onSidebarToggle?: (isOpen: boolean) => void;
  sidebarWidth?: number;
  onWidthChange?: (width: number) => void;
  initialSidebarTab?: "history" | "editor";
  activeThinkingText?: string | null;
  onAnswerQuestion?: (questionId: string, answers: any, dismissed?: boolean) => void;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

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
  sidebarWidth,
  onWidthChange,
  initialSidebarTab,
  activeThinkingText = null,
  onAnswerQuestion,
}: AnaraWorkbenchProps) {
  const [inputMessage, setInputMessage] = useState("");
  const [isBrainDrawerOpen, setIsBrainDrawerOpen] = useState(false);
  const [agentMode, setAgentMode] = useState<"plan" | "build">("plan");
  const [voiceModelId, setVoiceModelId] = useState<string>("gemini-3.1-flash-live-preview");
  const [chatModelId, setChatModelId] = useState<string>("9router/ag/gemini-3.8-flash-high");
  const [models, setModels] = useState<AIModelInfo[]>([]);

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
      } catch {}
    } else {
      setChatModelId(newModelId);
      try {
        localStorage.setItem("anara_chat_model", newModelId);
      } catch {}
      try {
        await fetch(`${BACKEND_URL}/api/models/active`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model_id: newModelId }),
        });
      } catch {}
    }
  }, [interactionMode]);
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
        }
      }
      const savedTerm = localStorage.getItem("anara_ide_terminal_open");
      if (savedTerm === "true") {
        setIsTerminalOpen(true);
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
        };
        setActiveIdeFile(fileObj);
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
    setIdeTabs((prev) => {
      const remaining = prev.filter((t) => t.filePath !== filePath);
      if (remaining.length === 0) {
        setActiveIdeFile({
          isOpen: false,
          fileName: "",
          filePath: "",
          fileExt: "",
          fileSizeKb: 0,
          content: "",
        });
      } else if (activeIdeFile.filePath === filePath) {
        setActiveIdeFile({ ...remaining[remaining.length - 1], isOpen: true });
      }
      return remaining;
    });
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
    });
    setIdeTabs([]);
    setIsTerminalOpen(false);
    try {
      localStorage.removeItem("anara_ide_active_file");
      localStorage.removeItem("anara_ide_tabs");
      localStorage.removeItem("anara_ide_terminal_open");
      localStorage.removeItem("anara_ide_edited_contents");
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
    if (nextState && (!activeIdeFile || !activeIdeFile.isOpen)) {
      setActiveIdeFile({
        isOpen: true,
        fileName: "terminal.sh",
        filePath: "workspace/terminal.sh",
        fileExt: "sh",
        fileSizeKb: 0,
        content: "# Terminal Workspace\n# Ready to receive commands or execute code from the agent.\n",
      });
    }
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

  return (
    <div className="relative w-full h-full pointer-events-none">
      {/* ── Media Player ── */}
      {mediaSession && (
        <div className="fixed inset-x-0 mx-auto px-4 z-30 pointer-events-auto animate-fade-in transition-all duration-300 bottom-36 sm:bottom-40 max-w-xl sm:max-w-2xl">
          <AnaraMediaPlayer
            session={mediaSession}
            ducked={status === "speaking" || status === "thinking"}
            controlSignal={mediaControl}
            onClose={() => onCloseMedia?.()}
          />
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
            initialSidebarTab="history"
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
            style={{ width: "var(--sidebar-width, 380px)", transition: "none" }}
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
              initialSidebarTab="history"
            />
          </div>

          {/* RIGHT PANEL: CHAT TIMELINE STREAM & INPUT PROMPT (Default Right Pane) */}
          <div className="flex-1 flex flex-col min-w-0 h-full relative overflow-hidden">
            <ChatTimeline
              transcript={transcript}
              status={status}
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
        </div>
      )}

      {/* ── VOICE MODE FLOATING HUD ── */}
      {interactionMode === "voice" && latestVisual && (
        <div
          className="fixed mx-auto max-w-2xl lg:max-w-3xl px-4 z-20 pointer-events-auto animate-fade-in transition-all duration-300 bottom-36 sm:bottom-40"
          style={{ left: "var(--sidebar-width, 380px)", right: 0 }}
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

      {/* ── UNIVERSAL BOTTOM DOCK ── */}
      <BottomDock
        inputMessage={inputMessage}
        setInputMessage={setInputMessage}
        onSend={(text: string, mode: "plan" | "build") => onSendText?.(text, mode)}
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
        activeQuestion={activeUnansweredQuestion}
        onAnswerQuestion={onAnswerQuestion}
        onHeightChange={setFooterDockHeight}
      />

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
      <AnaraBrain
        isOpen={isBrainDrawerOpen}
        onClose={() => {
          setIsBrainDrawerOpen(false);
          fetchModels(true);
        }}
        onTriggerAnimation={onTriggerAnimation}
        activeSpeaker={activeSpeaker}
      />
    </div>
  );
}
