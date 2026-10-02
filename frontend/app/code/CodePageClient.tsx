"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo, Suspense, lazy } from "react";
import Link from "next/link";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { TranscriptPayload, ToolProgressPayload } from "@/hooks/useWebSocket";
import type { TranscriptItem, AssistantStatus } from "@/components/workbench";
import ChatTimeline from "@/components/chat/ChatTimeline";
import BottomDock from "@/components/dock/BottomDock";
import { AIModelInfo } from "@/components/dock/ModelSelectorDropdown";
import { formatModelDisplayName } from "@/lib/modelFormat";
import { anaraApi, apiRequest, getWebSocketUrl } from "@/lib/apiClient";
import {
  ReasoningEffortLevel,
  saveReasoningEffortForModel,
  getSavedReasoningEffortForModel,
  resolveSiblingTierModelId,
} from "@/lib/reasoningEffort";
import type { AnaraBrainProps } from "@/components/brain/types";
import type { AnaraCodeIDEProps, WorkbenchTerminalProps, IdeTabFile } from "@/components/ide";
import WorkspaceTreeView from "@/components/sidebar/WorkspaceTreeView";
import type { WorkspaceTreeData, GitStatusData, ChatSession } from "@/components/sidebar/types";
import { CodeStudioHeader } from "./CodeStudioHeader";
import { ActivityBar } from "./ActivityBar";
import { useCodeStudioLayout } from "./useCodeStudioLayout";

const AnaraBrain = lazy(() => import("@/components/brain/AnaraBrain"));
const AnaraCodeIDE = lazy(() => import("@/components/ide/AnaraCodeIDE"));
const WorkbenchTerminal = lazy(() => import("@/components/ide/WorkbenchTerminal"));
const ReviewGitPane = lazy(() => import("@/components/sidebar/ReviewGitPane"));
const AgentStatusBar = lazy(() => import("@/components/statusbar/AgentStatusBar"));

export interface CodePageClientProps {
  initialSidebarWidth?: number;
  initialRightWidth?: number;
  initialTerminalHeight?: number;
  initialTerminalOpen?: boolean;
}

export default function CodePageClient({
  initialSidebarWidth = 260,
  initialRightWidth = 450,
  initialTerminalHeight = 210,
  initialTerminalOpen = true,
}: CodePageClientProps) {
  // ── Session & Chat State ──
  const [isMounted, setIsMounted] = useState(false);
  const [footerDockHeight, setFooterDockHeight] = useState(120);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);

  useEffect(() => {
    setIsMounted(true);
  }, []);
  const [sessionRefreshKey, setSessionRefreshKey] = useState(0);
  const [activeSpeaker, setActiveSpeaker] = useState<string>("Agnan");
  const [speakerRoster, setSpeakerRoster] = useState<string[]>([]);
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus>("idle");
  const [liveToolProgress, setLiveToolProgress] = useState<ToolProgressPayload | null>(null);
  const [activeThinkingText, setActiveThinkingText] = useState<string | null>(null);
  const [inputMessage, setInputMessage] = useState("");
  const [agentMode, setAgentMode] = useState<"plan" | "build">("plan");
  const [activeModelId, setActiveModelId] = useState<string>("9router/ag/gemini-3.8-flash-high");
  const [models, setModels] = useState<AIModelInfo[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [isSessionDropdownOpen, setIsSessionDropdownOpen] = useState(false);
  const sessionDropdownRef = useRef<HTMLDivElement>(null);
  const [isBrainDrawerOpen, setIsBrainDrawerOpen] = useState(false);

  // ── Workspace & Git State ──
  const [workspaceTree, setWorkspaceTree] = useState<WorkspaceTreeData | null>(null);
  const [gitStatus, setGitStatus] = useState<GitStatusData | null>(null);
  const [explorerMode, setExplorerMode] = useState<"tree" | "git">("tree");
  const [explorerFilter, setExplorerFilter] = useState("");
  const [latestTokenUsage, setLatestTokenUsage] = useState<any>(null);

  // ── Pane Layout & Resizing State (Modularized Hook) ──
  const {
    leftWidth,
    setLeftWidth,
    rightWidth,
    setRightWidth,
    terminalHeight,
    setTerminalHeight,
    isLeftOpen,
    setIsLeftOpen,
    isRightOpen,
    setIsRightOpen,
    isTerminalOpen,
    setIsTerminalOpen,
    isResizingLeft,
    isResizingRight,
    isResizingTerminal,
    startResizingLeft,
    startResizingRight,
    startResizingTerminal,
    handleResetLayout,
  } = useCodeStudioLayout({
    initialSidebarWidth,
    initialRightWidth,
    initialTerminalHeight,
    initialTerminalOpen,
  });

  // ── Code Studio IDE State ──
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

  const [ideTabs, setIdeTabs] = useState<IdeTabFile[]>([]);
  const isIdeHydratedRef = useRef(false);

  // ── Reasoning Effort State ──
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffortLevel>("medium");

  useEffect(() => {
    try {
      const active = localStorage.getItem("anara_code_model") || activeModelId || "";
      const saved = getSavedReasoningEffortForModel(active);
      setReasoningEffort(saved);
    } catch {}
  }, [activeModelId]);

  const handleSelectReasoningEffort = useCallback((lvl: ReasoningEffortLevel) => {
    setReasoningEffort(lvl);
    try {
      saveReasoningEffortForModel(activeModelId, lvl);
    } catch {}
  }, [activeModelId]);

  // ── Load saved pane preferences from localStorage & release transition freeze ──
  useEffect(() => {
    try {
      const savedLeft = localStorage.getItem("anara_studio_left_width");
      if (savedLeft) {
        const p = parseInt(savedLeft, 10);
        if (!isNaN(p) && p >= 180 && p <= 500) {
          setLeftWidth(p);
          document.documentElement.style.setProperty("--studio-left-width", `${p}px`);
          document.cookie = `anara_studio_left_width=${p}; path=/; max-age=31536000; SameSite=Lax`;
        }
      }
      const savedRight = localStorage.getItem("anara_studio_right_width");
      if (savedRight) {
        const p = parseInt(savedRight, 10);
        if (!isNaN(p) && p >= 340 && p <= 700) {
          setRightWidth(p);
          document.documentElement.style.setProperty("--studio-right-width", `${p}px`);
          document.cookie = `anara_studio_right_width=${p}; path=/; max-age=31536000; SameSite=Lax`;
        }
      }
      const savedTermH = localStorage.getItem("anara_studio_term_height");
      if (savedTermH) {
        const p = parseInt(savedTermH, 10);
        if (!isNaN(p) && p >= 100 && p <= 500) {
          setTerminalHeight(p);
          document.cookie = `anara_studio_term_height=${p}; path=/; max-age=31536000; SameSite=Lax`;
        }
      }
      const savedTermOpen = localStorage.getItem("anara_studio_term_open");
      if (savedTermOpen !== null) {
        setIsTerminalOpen(savedTermOpen === "true");
        document.cookie = `anara_studio_term_open=${savedTermOpen}; path=/; max-age=31536000; SameSite=Lax`;
      }

      // Restore open tabs and active file to prevent blank editor flicker
      const savedTabs = localStorage.getItem("anara_code_ide_tabs");
      if (savedTabs) {
        const parsed = JSON.parse(savedTabs);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setIdeTabs(parsed);
        }
      }
      const savedFile = localStorage.getItem("anara_code_ide_active_file");
      if (savedFile) {
        const parsed = JSON.parse(savedFile);
        if (parsed && typeof parsed === "object" && parsed.isOpen) {
          setActiveIdeFile({ ...parsed, content: parsed.content || "" });
          if (parsed.filePath) {
            anaraApi.workspace.getFileContent(parsed.filePath)
              .then((res) => {
                if (res && res.status === "success" && res.content !== undefined) {
                  setActiveIdeFile((cur) => (cur.filePath === parsed.filePath ? { ...cur, content: res.content, originalContent: res.content } : cur));
                }
              })
              .catch(() => {});
          }
        }
      }

      // Pre-warm active session id from localStorage for instant workspace tree loading
      const urlSid = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("session_id") : null;
      const savedSess = urlSid || localStorage.getItem("anara_active_session_id") || localStorage.getItem("anara_active_code_session_id");
      if (savedSess && !isNaN(Number(savedSess))) {
        setActiveSessionId(Number(savedSess));
      }

      // Release transition freeze once layout settles
      setTimeout(() => {
        document.documentElement.classList.remove("preload");
      }, 150);
    } catch {}
    isIdeHydratedRef.current = true;
  }, []);

  // Persist open tabs and active file (metadata only to prevent quota exhaustion and code leaks)
  useEffect(() => {
    if (!isIdeHydratedRef.current) return;
    try {
      const meta = {
        isOpen: activeIdeFile.isOpen,
        fileName: activeIdeFile.fileName,
        filePath: activeIdeFile.filePath,
        fileExt: activeIdeFile.fileExt,
        fileSizeKb: activeIdeFile.fileSizeKb,
      };
      localStorage.setItem("anara_code_ide_active_file", JSON.stringify(meta));
    } catch {}
  }, [activeIdeFile]);

  useEffect(() => {
    if (!isIdeHydratedRef.current) return;
    try {
      const tabsMeta = ideTabs.map((t) => ({
        fileName: t.fileName,
        filePath: t.filePath,
        fileExt: t.fileExt,
        fileSizeKb: t.fileSizeKb,
      }));
      localStorage.setItem("anara_code_ide_tabs", JSON.stringify(tabsMeta));
    } catch {}
  }, [ideTabs]);

  const workspaceFilesList = useMemo(() => {
    if (!workspaceTree || !Array.isArray(workspaceTree.files)) return [];
    return workspaceTree.files.map((f: any) => ({
      path: typeof f === "string" ? f : f.path || f.name || "",
      name: (typeof f === "string" ? f : f.name || f.path || "").split("/").pop() || "",
      isDir: typeof f === "object" && Boolean(f.is_dir),
    }));
  }, [workspaceTree]);

  // ── Check URL search params for session_id on initial mount ──
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const params = new URLSearchParams(window.location.search);
        const sid = params.get("session_id");
        if (sid && !isNaN(Number(sid))) {
          localStorage.setItem("anara_active_session_id", sid);
          setActiveSessionId(Number(sid));
        }
      } catch {}
    }
  }, []);

  // ── Close session dropdown when clicking outside ──
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (sessionDropdownRef.current && !sessionDropdownRef.current.contains(e.target as Node)) {
        setIsSessionDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // ── Fetch AI Models ──
  const fetchModels = useCallback(async (refresh: boolean = false) => {
    try {
      const endpoint = refresh ? "/api/models?refresh=true" : "/api/models";
      const data = await apiRequest<{ models?: AIModelInfo[]; active_model_id?: string }>(endpoint);
      const all = data.models || [];
      const configured = all.filter((m) => m.is_configured);
      setModels(configured);
      if (data.active_model_id) {
        setActiveModelId(data.active_model_id);
      }
    } catch (err) {
      console.warn("[CodeStudio] fetchModels error:", err);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleSelectModel = useCallback(async (modelId: string) => {
    const saved = getSavedReasoningEffortForModel(modelId);
    setReasoningEffort(saved);
    const resolvedId = resolveSiblingTierModelId(modelId, saved as any, models);
    const targetModelId = resolvedId || modelId;
    setActiveModelId(targetModelId);
    try {
      localStorage.setItem("anara_code_model", targetModelId);
      await anaraApi.models.setActive(targetModelId);
    } catch (err) {
      console.warn("[CodeStudio] setActiveModel error:", err);
    }
  }, [models]);

  // ── Fetch Sessions List (Universal: All sessions accessible in Code Studio) ──
  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const data = await anaraApi.sessions.list();
      setSessions(data || []);
    } catch (err) {
      console.warn("[CodeStudio] loadSessions error:", err);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  // ── Fetch Workspace Tree & Git Status ──
  const loadWorkspaceTree = useCallback(async (sid?: number | null) => {
    try {
      const data = await anaraApi.workspace.getTree(sid || undefined);
      if (data && (data.total_files > 0 || data.is_custom_folder || (data.entries && data.entries.length > 0))) {
        setWorkspaceTree(data);
        return;
      }
      setWorkspaceTree(null);
    } catch (e) {
      console.warn("[CodeStudio] loadWorkspaceTree error:", e);
      setWorkspaceTree(null);
    }
  }, []);

  const loadGitStatus = useCallback(async (sid?: number | null) => {
    if (!sid) {
      setGitStatus(null);
      return;
    }
    try {
      const data = await anaraApi.workspace.getGitStatus(sid);
      setGitStatus(data);
    } catch {
      setGitStatus(null);
    }
  }, []);

  useEffect(() => {
    loadSessions();
    loadWorkspaceTree(activeSessionId);
    loadGitStatus(activeSessionId);
  }, [activeSessionId, sessionRefreshKey, loadSessions, loadWorkspaceTree, loadGitStatus]);

  // ── Real-time Event Listener for Workspace Mutations ──
  useEffect(() => {
    const handleBrainSync = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (!detail) return;
      if (
        detail.event === "workspace_updated" ||
        detail.event === "checkpoint_created" ||
        detail.event === "file_saved" ||
        detail.table === "workspace"
      ) {
        loadWorkspaceTree(activeSessionId);
        loadGitStatus(activeSessionId);
      }
    };
    window.addEventListener("anara-brain-sync", handleBrainSync);
    return () => window.removeEventListener("anara-brain-sync", handleBrainSync);
  }, [activeSessionId, loadWorkspaceTree, loadGitStatus]);

  // ── Workspace Folder Actions ──
  const handlePickLocalFolder = useCallback(async (targetPath?: string) => {
    try {
      const data = await anaraApi.workspace.importFolder(targetPath || "", activeSessionId || undefined);
      if (data && data.status === "success" && data.tree) {
        setWorkspaceTree(data.tree);
        setExplorerMode("tree");
        setIsLeftOpen(true);
        loadGitStatus(activeSessionId);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "workspace_updated" } }));
        }
      }
    } catch (err) {
      console.warn("[Workspace] pick local folder error:", err);
    }
  }, [activeSessionId, loadGitStatus]);

  const handleClearWorkspace = async () => {
    try {
      await anaraApi.workspace.clear(activeSessionId || undefined);
      setWorkspaceTree(null);
      setGitStatus(null);
      setActiveIdeFile({ isOpen: false, fileName: "", filePath: "", fileExt: "", fileSizeKb: 0, content: "" });
      setIdeTabs([]);
    } catch (e) {
      console.warn("[Workspace] clear error:", e);
    }
  };

  // ── File Management & CodeMirror Actions ──
  const handleOpenFileIDE = async (filePath: string, fileName: string) => {
    try {
      const data = await anaraApi.workspace.getFileContent(filePath, activeSessionId || undefined);
      if (data) {
        const fileObj: IdeTabFile = {
          fileName: data.filename || fileName,
          filePath: data.path || filePath,
          fileExt: data.ext || "",
          fileSizeKb: data.size_kb || 0,
          content: data.content || "",
          originalContent: data.content || "",
        };
        setActiveIdeFile({ ...fileObj, isOpen: true });
        setIdeTabs((prev) => {
          const exists = prev.some((t) => t.filePath === fileObj.filePath);
          if (exists) return prev.map((t) => (t.filePath === fileObj.filePath ? { ...t, ...fileObj } : t));
          return [...prev, fileObj];
        });
      }
    } catch (e) {
      console.warn("[CodeStudio] file load error:", e);
    }
  };

  const handleSelectIdeTab = (filePath: string, fileName: string) => {
    const existing = ideTabs.find((t) => t.filePath === filePath);
    if (existing && existing.content !== undefined && existing.content !== "") {
      setActiveIdeFile({ ...existing, isOpen: true });
    } else {
      handleOpenFileIDE(filePath, fileName);
    }
  };

  const handleCloseIdeTab = (filePath: string) => {
    setIdeTabs((prev) => {
      const rem = prev.filter((t) => t.filePath !== filePath);
      if (rem.length === 0) {
        setActiveIdeFile({ isOpen: false, fileName: "", filePath: "", fileExt: "", fileSizeKb: 0, content: "" });
      } else if (activeIdeFile.filePath === filePath) {
        setActiveIdeFile({ ...rem[rem.length - 1], isOpen: true });
      }
      return rem;
    });
  };

  const handleSaveIdeFile = async (filePath: string, newContent: string): Promise<boolean> => {
    try {
      const res = await anaraApi.workspace.saveFile(filePath, newContent, activeSessionId || undefined);
      if (res && res.status === "success") {
        setActiveIdeFile((prev) => ({ ...prev, content: newContent }));
        setIdeTabs((prev) => prev.map((t) => (t.filePath === filePath ? { ...t, content: newContent } : t)));
        loadGitStatus(activeSessionId);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  };

  // ── WebSocket Pipeline & Agent Dispatch ──
  const {
    status: wsStatus,
    sendJSON,
    sendSteer,
  } = useWebSocket({
    url: getWebSocketUrl(),
    onTranscript: (payload: TranscriptPayload | string, rawSpeaker?: "input" | "output") => {
      const text = typeof payload === "string" ? payload : payload.text;
      const speaker = typeof payload === "string" ? (rawSpeaker ?? "output") : payload.speaker;
      const isPartial = typeof payload === "string" ? false : (payload.isPartial ?? false);
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
      const payloadAgentMode = typeof payload === "string" ? undefined : payload.agentMode;
      const payloadModelId = typeof payload === "string" ? undefined : payload.modelId;
      const payloadDurationText = typeof payload === "string" ? undefined : payload.durationText;
      const payloadIsStreaming = typeof payload === "string" ? false : (payload.isStreaming ?? payload.isPartial ?? false);
      const payloadTokenUsage = typeof payload === "string" ? undefined : payload.tokenUsage;
      const payloadToolsUsed = typeof payload === "string" ? undefined : (payload.toolsUsed || payload.tokenUsage?.toolsUsed);

      // Capture thinking snapshot before clearing
      const thinkingSnapshot = activeThinkingText;
      if (!isPartial) {
        setActiveThinkingText(null);
      }

      setTranscript((prev) => {
        const lastIdx = prev.length - 1;
        const last = prev[lastIdx];

        const computedDuration = payloadDurationText || (last?.startTime ? `${Math.max(1, Math.round((Date.now() - last.startTime) / 1000))}s` : last?.durationText);
        const resolvedToolsUsed = payloadToolsUsed || payloadTokenUsage?.toolsUsed || last?.toolsUsed;

        const newEntry: TranscriptItem = {
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
          agentMode: payloadAgentMode || last?.agentMode || agentMode,
          modelId: payloadModelId || last?.modelId || activeModelId,
          durationText: computedDuration,
          tokenUsage: payloadTokenUsage || last?.tokenUsage,
          toolsUsed: resolvedToolsUsed,
          isStreaming: payloadIsStreaming,
          thinkingText: thinkingSnapshot || last?.thinkingText || null,
          startTime: last?.startTime || Date.now(),
        };

        if (prev.length === 0) return [newEntry];

        if (speaker === "input") {
          return [...prev, newEntry];
        }

        if (visualType && visualType !== "none") {
          // Only update last tool card if it is the completion event of the currently running action
          if (
            visualType === "agent_action" &&
            last &&
            last.visualType === "agent_action" &&
            last.agentActionData?.eventType === "agent_action_start" &&
            agentActionData?.eventType === "agent_action_complete" &&
            last.agentActionData?.toolName === agentActionData?.toolName
          ) {
            return [...prev.slice(0, lastIdx), { ...last, ...newEntry }];
          }
          return [...prev, newEntry];
        }

        const isLastPlain = Boolean(last && last.speaker === "output" && (!last.visualType || last.visualType === "none"));
        if (!isLastPlain) {
          return [...prev, newEntry];
        }

        if (isPartial) {
          return [...prev.slice(0, lastIdx), { ...last, text: text, isStreaming: true, thinkingText: thinkingSnapshot || last.thinkingText }];
        }

        return [...prev.slice(0, lastIdx), { ...last, text: text, isStreaming: false, thinkingText: thinkingSnapshot || last.thinkingText }];
      });
    },
    onToolProgress: (payload: ToolProgressPayload) => {
      setLiveToolProgress(payload);
      if (payload.status === "done") {
        setTimeout(() => {
          setLiveToolProgress((prev) => (prev?.toolName === payload.toolName ? null : prev));
        }, 1000);
      }
    },
    onAgentAction: (payload) => {
      setTranscript((prev) => {
        const newEntry: TranscriptItem = {
          speaker: "output",
          text: "",
          visualType: "agent_action",
          agentActionData: payload,
          agentMode: agentMode,
          modelId: activeModelId,
          startTime: Date.now(),
        };
        const lastIdx = prev.length - 1;
        const last = prev[lastIdx];
        if (
          last &&
          last.speaker === "output" &&
          last.visualType === "agent_action" &&
          last.agentActionData?.toolName === payload.toolName
        ) {
          return [...prev.slice(0, lastIdx), { ...last, ...newEntry }];
        }
        if (last && last.speaker === "output" && !last.text && (!last.visualType || last.visualType === "none")) {
          return [...prev.slice(0, lastIdx), newEntry];
        }
        return [...prev, newEntry];
      });
    },
    onTokenUsage: (usage) => {
      setLatestTokenUsage(usage);
      setTranscript((prev) => {
        if (prev.length === 0) return prev;
        const lastIdx = prev.length - 1;
        const last = prev[lastIdx];
        if (last && last.speaker === "output") {
          return [...prev.slice(0, lastIdx), { ...last, tokenUsage: usage }];
        }
        return prev;
      });
    },
    onError: (msg) => {
      if (msg === "Conversation session not found.") {
        localStorage.removeItem("anara_active_session_id");
        localStorage.removeItem("anara_active_code_session_id");
        setActiveSessionId(null);
        setTranscript([]);
        return;
      }
      console.warn("[CodeStudio/WS Notice]", msg);
      setAssistantStatus("idle");
    },
    onInterrupted: () => {
      setAssistantStatus("idle");
      setActiveThinkingText(null);
    },
    onSpeakerIdentified: (name, roster) => {
      if (name) setActiveSpeaker(name);
      if (roster && Array.isArray(roster)) setSpeakerRoster(roster);
    },
    onAgentThinking: (t: string) => {
      setActiveThinkingText(t && t.trim().length > 0 ? t : null);
    },
    onInteractiveQuestion: (payload) => {
      setActiveThinkingText(null);
      setTranscript((prev) => [
        ...prev,
        {
          speaker: "output",
          text: "",
          visualType: "interactive_question",
          questionData: {
            questionId: payload.question_id,
            questions: payload.questions,
            isAnswered: false,
          },
        },
      ]);
    },
    onTurnComplete: () => {
      setAssistantStatus("idle");
      setActiveThinkingText(null);
      loadGitStatus(activeSessionId);
    },
    onSessionSwitched: (payload) => {
      if (payload.sessionId) {
        setActiveSessionId(payload.sessionId);
        localStorage.setItem("anara_active_code_session_id", String(payload.sessionId));
        setSessionRefreshKey((k) => k + 1);
        if (payload.messages && Array.isArray(payload.messages)) {
          const restored: TranscriptItem[] = [];
          for (const m of payload.messages) {
            const u = (m.user_text || "").trim();
            const a = (m.ai_text || "").trim();
            const vis = m.visual_data || {};
            if (u) {
              restored.push({ speaker: "input", text: u });
            }
            if (a || vis.visualType || m.media_type) {
              restored.push({
                speaker: "output",
                text: a,
                visualType: vis.visualType || (m.media_type as any),
                imageUrl: vis.imageUrl || m.media_url,
                imageTitle: vis.imageTitle,
                sourceDomain: vis.sourceDomain,
                sourceUrl: vis.sourceUrl,
                images: vis.images,
                weatherData: vis.weatherData,
                codeData: vis.codeData,
                systemHudData: vis.systemHudData,
                knowledgeCardData: vis.knowledgeCardData,
                todoData: vis.todoData,
                briefingData: vis.briefingData,
                agentActionData: vis.agentActionData,
                documentViewerData: vis.documentViewerData,
                workspaceFolderData: vis.workspaceFolderData,
                planData: vis.planData,
                mediaType: m.media_type as any,
                agentMode: (vis.agent_mode || vis.agentMode || "plan") as "plan" | "build",
                modelId: vis.model || vis.model_id || vis.modelId,
                durationText: vis.duration_text || vis.durationText || (vis.duration ? `${Math.round(vis.duration)}s` : undefined),
                tokenUsage: vis.tokenUsage || vis.token_usage,
                toolsUsed: vis.tools_used || vis.toolsUsed || vis.token_usage?.tools_used || vis.tokenUsage?.toolsUsed,
                toolRecordsCount: vis.tool_records_count || vis.toolRecordsCount,
              });
            }
          }
          setTranscript(restored);
        }
      }
    },
    onSessionIdSync: (sessionId) => {
      setActiveSessionId(sessionId);
      localStorage.setItem("anara_active_session_id", String(sessionId));
      setSessionRefreshKey((k) => k + 1);
    },
  });

  // ── Auto-Initialize Code Session on Mount (Universal Session Standard) ──
  useEffect(() => {
    const initCodeSession = async () => {
      try {
        const list = await anaraApi.sessions.list();
        if (Array.isArray(list) && list.length > 0) {
          const urlSid = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("session_id") : null;
          const savedSess = urlSid || localStorage.getItem("anara_active_session_id") || localStorage.getItem("anara_active_code_session_id");
          const match = savedSess ? list.find((s) => s.id === Number(savedSess)) : null;
          const targetId = match ? match.id : list[0].id;
          setActiveSessionId(targetId);
          localStorage.setItem("anara_active_session_id", String(targetId));
          if (wsStatus === "connected") {
            sendJSON({ type: "switch_session", sessionId: targetId });
          }
        }
        // Session Pattern: if no sessions exist, leave activeSessionId null.
        // A session will be created lazily on first message send via ensure_session().
      } catch (err) {
        console.warn("[CodeStudio] init session error:", err);
      }
    };
    initCodeSession();
  }, [wsStatus, sendJSON]);

  const handleSelectSession = (id: number) => {
    // Eager-clear stale workspace state BEFORE switching session (Anara Parity)
    setWorkspaceTree(null);
    setGitStatus(null);
    setTranscript([]);
    setActiveSessionId(id);
    localStorage.setItem("anara_active_session_id", String(id));
    sendJSON({ type: "switch_session", sessionId: id });
  };

  const handleNewSession = () => {
    // Session Pattern: clear state only — session is created lazily on first message send
    // This prevents accumulation of empty "New Chat" / "New Project" sessions
    setWorkspaceTree(null);
    setGitStatus(null);
    setActiveSessionId(null);
    localStorage.removeItem("anara_active_session_id");
    localStorage.removeItem("anara_active_code_session_id");
    setTranscript([]);
  };

  const handlePatchSession = async (id: number, body: Record<string, unknown>) => {
    try {
      await anaraApi.sessions.update(id, body);
      setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, ...body } : s)));
    } catch (e) {
      console.warn("[Session] patch error:", e);
    }
  };

  const handleDeleteSession = async (s: ChatSession) => {
    try {
      await anaraApi.sessions.delete(s.id);
      setSessions((prev) => prev.filter((x) => x.id !== s.id));
      if (activeSessionId === s.id) {
        handleNewSession();
      }
    } catch (e) {
      console.warn("[Session] delete error:", e);
    }
  };

  const handleSendText = (text: string, mode: "plan" | "build" = agentMode) => {
    if (!text.trim()) return;
    const trimmed = text.trim();
    setTranscript((prev) => [
      ...prev,
      { speaker: "input", text: trimmed },
      { speaker: "output", text: "", agentMode: mode, startTime: Date.now() },
    ]);
    sendJSON({
      type: "text_input",
      text: trimmed,
      channel: "code",
      platform: "code",
      agent_mode: mode,
      reasoning_effort: reasoningEffort,
      sessionId: activeSessionId,
      session_type: "code",
      workspace_path: workspaceTree?.root_path || "",
    });
    setAssistantStatus("thinking");
  };

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

      setAgentMode("build");
      handleSendText(richPrompt, "build");
    },
    [transcript, agentMode, reasoningEffort, activeSessionId]
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

      sendJSON({
        type: "text_input",
        text: `Plan "${planTitle}" rejected. Let's reconsider the implementation approach.`,
        channel: "code",
        platform: "code",
        agent_mode: "plan",
        sessionId: activeSessionId,
        session_type: "code",
        workspace_path: workspaceTree?.root_path || "",
      });
    },
    [transcript, sendJSON, activeSessionId]
  );

  // Synchronize speaker selection with AnaraBrain
  useEffect(() => {
    const handleBrainSpeakerSync = (e: Event) => {
      const customEvent = e as CustomEvent<{ speaker_name?: string }>;
      const name = customEvent.detail?.speaker_name;
      if (name && wsStatus === "connected") {
        sendJSON({ type: "set_active_speaker", name });
        setActiveSpeaker(name);
        setSpeakerRoster((prev) => (prev.includes(name) ? prev : [...prev, name]));
      }
    };
    window.addEventListener("anara-speaker-changed", handleBrainSpeakerSync);
    return () => window.removeEventListener("anara-speaker-changed", handleBrainSpeakerSync);
  }, [wsStatus, sendJSON]);

  const handleAnswerQuestion = (questionId: string, answers: any, dismissed: boolean = false) => {
    sendJSON({
      type: "question_response",
      question_id: questionId,
      answers: answers,
      dismissed: dismissed,
    });
    setTranscript((prev) =>
      prev.map((item) =>
        item.visualType === "interactive_question" && item.questionData?.questionId === questionId
          ? { ...item, questionData: { ...item.questionData, answers, isAnswered: true } }
          : item
      )
    );
  };

  const activeUnansweredQuestion = useMemo(() => {
    for (let i = transcript.length - 1; i >= 0; i--) {
      const item = transcript[i];
      if (item.visualType === "interactive_question" && item.questionData && !item.questionData.isAnswered) {
        return item.questionData;
      }
    }
    return null;
  }, [transcript]);

  const activeSession = useMemo(() => {
    return sessions.find((s) => s.id === activeSessionId) || null;
  }, [sessions, activeSessionId]);

  return (
    <main className="relative w-screen h-screen overflow-hidden flex flex-col font-sans select-none bg-[#030712] text-slate-100">
      {/* ══════════════════════════════════════════════════════════════════════
          1. STUDIO TOP NAVIGATION BAR (Modularized Header)
         ══════════════════════════════════════════════════════════════════════ */}
      <CodeStudioHeader
        workspaceTree={workspaceTree}
        gitStatus={gitStatus}
        activeSession={activeSession}
        activeSessionId={activeSessionId}
        sessions={sessions}
        isSessionDropdownOpen={isSessionDropdownOpen}
        setIsSessionDropdownOpen={setIsSessionDropdownOpen}
        sessionDropdownRef={sessionDropdownRef}
        handleSelectSession={handleSelectSession}
        handleNewSession={handleNewSession}
        isLeftOpen={isLeftOpen}
        setIsLeftOpen={setIsLeftOpen}
        isTerminalOpen={isTerminalOpen}
        setIsTerminalOpen={setIsTerminalOpen}
        isRightOpen={isRightOpen}
        setIsRightOpen={setIsRightOpen}
        setIsBrainDrawerOpen={setIsBrainDrawerOpen}
      />

      {/* ══════════════════════════════════════════════════════════════════════
          2. THREE-PANE AUTONOMOUS CODING STUDIO WORKBENCH
         ══════════════════════════════════════════════════════════════════════ */}
      <div className="flex-1 flex min-h-0 items-stretch overflow-hidden relative">
        {/* ── ACTIVITY BAR (Antigravity Studio Primary Icon Rail) ── */}
        <ActivityBar
          isLeftOpen={isLeftOpen}
          setIsLeftOpen={setIsLeftOpen}
          explorerMode={explorerMode}
          setExplorerMode={setExplorerMode}
          isTerminalOpen={isTerminalOpen}
          setIsTerminalOpen={setIsTerminalOpen}
          isRightOpen={isRightOpen}
          setIsRightOpen={setIsRightOpen}
          gitStatus={gitStatus}
          setIsBrainDrawerOpen={setIsBrainDrawerOpen}
        />

        {/* ── PANE 1 (LEFT): File Explorer & Git Status ── */}
        {isLeftOpen && (
          <>
            <div
              style={{ width: `var(--studio-left-width, ${leftWidth}px)`, transition: "none" }}
              className="h-full shrink-0 flex flex-col bg-[#060913]/90 backdrop-blur-xl overflow-hidden select-none relative studio-pane border-r border-white/[0.08]"
            >
              {explorerMode === "git" ? (
                <ReviewGitPane
                  gitStatus={gitStatus}
                  onRefreshGit={() => loadGitStatus(activeSessionId)}
                  sessionId={activeSessionId}
                  activeFilePath={activeIdeFile?.filePath}
                  onSelectDiffFile={(path) => handleOpenFileIDE(path, path.split("/").pop() || "file")}
                  onAgentShip={() => handleSendText("Ship active git changes: review diffs, commit changes, and push PR to origin", "build")}
                />
              ) : workspaceTree && (workspaceTree.total_files > 0 || workspaceTree.is_custom_folder || (workspaceTree.entries && workspaceTree.entries.length > 0)) ? (
                <WorkspaceTreeView
                  workspaceTree={workspaceTree}
                  gitStatus={gitStatus}
                  explorerMode={explorerMode}
                  setExplorerMode={setExplorerMode}
                  explorerFilter={explorerFilter}
                  setExplorerFilter={setExplorerFilter}
                  activeFilePath={activeIdeFile?.filePath}
                  onOpenFileIDE={handleOpenFileIDE}
                  handlePickLocalFolder={handlePickLocalFolder}
                  handleClearWorkspace={handleClearWorkspace}
                  startResizingTree={() => {}}
                  fullWidth={true}
                />
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-6 text-center gap-3">
                  <div className="w-12 h-12 rounded-2xl bg-white/[0.03] border border-white/10 flex items-center justify-center text-cyan-400 shadow-inner">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                  </div>
                  <h4 className="text-xs font-semibold text-white font-mono uppercase tracking-wider">
                    No Folder Selected
                  </h4>
                  <p className="text-[11px] text-slate-400 leading-relaxed max-w-[200px]">
                    Connect a local directory to read project file structure.
                  </p>
                  <button
                    type="button"
                    onClick={() => handlePickLocalFolder()}
                    className="px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/30 text-cyan-300 hover:text-white text-xs font-mono font-semibold transition-colors cursor-pointer"
                  >
                    Select Project Folder
                  </button>
                </div>
              )}
            </div>

            {/* Resizer Splitter 1: Left Explorer ↔ Center Editor (1px Razor-Thin White Hairline) */}
            <div
              onMouseDown={startResizingLeft}
              className="relative w-px h-full cursor-col-resize shrink-0 select-none bg-white/[0.08] hover:bg-cyan-400/50 active:bg-cyan-400 transition-colors z-20"
              title="Drag to resize file panel width"
            >
              <div className="absolute inset-y-0 -left-1.5 w-3 cursor-col-resize bg-transparent" />
            </div>
          </>
        )}

        {/* ── PANE 2 (CENTER - MAIN): CodeMirror 6 Editor & Terminal Dock (FLEX-1) ── */}
        <div
          style={{ transition: "none" }}
          className="flex-1 min-w-0 h-full flex flex-col overflow-hidden bg-[#070b16] relative studio-pane"
        >
          {/* Main Editor Surface */}
          <div className="flex-1 min-h-[140px] w-full flex flex-col overflow-hidden relative">
            {activeIdeFile && activeIdeFile.isOpen ? (
              <Suspense fallback={null}>
                <AnaraCodeIDE
                  isOpen={true}
                  embedded={true}
                  onClose={() => setActiveIdeFile((prev) => ({ ...prev, isOpen: false }))}
                  fileName={activeIdeFile.fileName}
                  filePath={activeIdeFile.filePath}
                  fileExt={activeIdeFile.fileExt}
                  fileSizeKb={activeIdeFile.fileSizeKb}
                  content={activeIdeFile.content}
                  originalContent={activeIdeFile.originalContent}
                  isTerminalOpen={isTerminalOpen}
                  onToggleTerminal={() => setIsTerminalOpen((v) => !v)}
                  tabs={ideTabs}
                  onSelectTab={handleSelectIdeTab}
                  onCloseTab={handleCloseIdeTab}
                  onSaveFile={handleSaveIdeFile}
                  onAskAnara={(p: string, n: string) => {
                    handleSendText(`Please analyze and explain the architecture of file @${n} (${p})`, agentMode);
                  }}
                />
              </Suspense>
            ) : (
              /* Studio Welcome Empty State: Liquid Glass Antigravity Hub */
              <div className="flex-1 flex flex-col items-center justify-center p-8 select-none bg-gradient-to-b from-[#060a16]/60 via-[#040813]/80 to-[#02050e] text-slate-300 font-sans relative overflow-hidden">
                {/* Ambient luminous glow orbs */}
                <div className="absolute w-[450px] h-[450px] rounded-full bg-cyan-500/[0.04] blur-[120px] pointer-events-none" />
                <div className="absolute w-[300px] h-[300px] rounded-full bg-purple-500/[0.03] blur-[100px] pointer-events-none" />

                {/* Central Antigravity Studio Hub */}
                <div className="max-w-md w-full rounded-2xl bg-[#060913]/90 border border-white/[0.08] shadow-2xl p-6 flex flex-col items-center text-center gap-4 relative z-10 animate-fade-in">
                  <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-400/30 flex items-center justify-center text-cyan-300 shadow-[0_0_20px_rgba(34,211,238,0.15)]">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white font-mono tracking-wider uppercase">
                      Anara Code Studio
                    </h3>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      Autonomous agentic software engineering workbench. Open files from the explorer or prompt Anara Agent to plan and build.
                    </p>
                  </div>

                  {/* Quick Action Buttons */}
                  <div className="w-full grid grid-cols-2 gap-2 pt-2 border-t border-white/[0.08] text-xs font-mono">
                    <button
                      type="button"
                      onClick={() => {
                        setIsLeftOpen(true);
                        setExplorerMode("tree");
                      }}
                      className="flex items-center gap-2.5 p-2.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] hover:border-cyan-400/30 text-slate-300 hover:text-white transition-all text-left cursor-pointer active:scale-95"
                    >
                      <svg className="w-4 h-4 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                      </svg>
                      <div>
                        <div className="font-semibold text-white">Files</div>
                        <div className="text-[10px] text-slate-500">Explorer tree</div>
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsTerminalOpen(true)}
                      className="flex items-center gap-2.5 p-2.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] hover:border-cyan-400/30 text-slate-300 hover:text-white transition-all text-left cursor-pointer active:scale-95"
                    >
                      <svg className="w-4 h-4 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <div>
                        <div className="font-semibold text-white">Terminal</div>
                        <div className="text-[10px] text-slate-500">Integrated shell</div>
                      </div>
                    </button>
                  </div>

                  {/* Keyboard Shortcuts Bar */}
                  <div className="w-full flex items-center justify-between text-[11px] font-mono text-slate-400 pt-2 border-t border-white/[0.06] px-1">
                    <span>Quick Open File</span>
                    <kbd className="px-2 py-0.5 rounded bg-white/[0.06] border border-white/10 text-[10px] text-slate-300">Ctrl + P</kbd>
                  </div>
                  <div className="w-full flex items-center justify-between text-[11px] font-mono text-slate-400 px-1">
                    <span>Save Buffer</span>
                    <kbd className="px-2 py-0.5 rounded bg-white/[0.06] border border-white/10 text-[10px] text-slate-300">Ctrl + S</kbd>
                  </div>
                  <div className="w-full flex items-center justify-between text-[11px] font-mono text-slate-400 px-1">
                    <span>Find in File</span>
                    <kbd className="px-2 py-0.5 rounded bg-white/[0.06] border border-white/10 text-[10px] text-slate-300">Ctrl + F</kbd>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Integrated PowerShell Terminal Dock with Keep-Alive (Anara Desktop Standard) */}
          {isTerminalOpen && (
            <div
              onMouseDown={startResizingTerminal}
              className="relative h-px w-full cursor-row-resize shrink-0 select-none bg-white/[0.08] hover:bg-cyan-400/50 active:bg-cyan-400 transition-colors z-10"
              title="Drag to resize terminal height"
            >
              <div className="absolute inset-x-0 -top-1.5 h-3 cursor-row-resize bg-transparent" />
            </div>
          )}

          <div
            style={{
              height: `${terminalHeight}px`,
              display: isTerminalOpen ? "block" : "none",
            }}
            className="w-full shrink-0 overflow-hidden bg-black/60 backdrop-blur-md"
          >
            <Suspense fallback={null}>
              <WorkbenchTerminal
                logs={[
                  `[anara-agent] Active mode: ${agentMode.toUpperCase()}`,
                  `[system] Terminal worker ready (Workspace: ${workspaceTree?.workspace_name || "default"}).`,
                ]}
                activeTask={assistantStatus === "thinking" ? "AI Model Thinking..." : undefined}
                onExecuteCommand={() => {}}
                onClose={() => setIsTerminalOpen(false)}
                isVisible={isTerminalOpen}
                cwd={workspaceTree?.root_path || undefined}
              />
            </Suspense>
          </div>
        </div>

        {/* Resizer Splitter 2: Center Editor ↔ Right Agent (1px Razor-Thin White Hairline) */}
        {isRightOpen && (
          <div
            onMouseDown={startResizingRight}
            className="relative w-px h-full cursor-col-resize shrink-0 select-none bg-white/[0.08] hover:bg-cyan-400/50 active:bg-cyan-400 transition-colors z-20"
            title="Drag to resize AI Agent panel width"
          >
            <div className="absolute inset-y-0 -left-1.5 w-3 cursor-col-resize bg-transparent" />
          </div>
        )}

        {/* ── PANE 3 (RIGHT): Anara Autonomous Agent Console & Prompt Command Dock ── */}
        {isRightOpen && (
          <div
            style={{ width: `var(--studio-right-width, ${rightWidth}px)`, transition: "none" }}
            className="h-full shrink-0 flex flex-col overflow-hidden bg-[#060913]/90 backdrop-blur-xl relative select-none studio-pane border-l border-white/[0.08]"
          >
            {/* Antigravity Agent Console Header */}
            <div className="h-9 shrink-0 px-3 border-b border-white/[0.08] flex items-center justify-between bg-[#060913]/95 font-mono text-xs select-none">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${assistantStatus === "thinking" ? "bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]" : "bg-emerald-400 shadow-[0_0_8px_#34d399]"}`} />
                <span className="font-bold text-white tracking-wider text-[11px] uppercase">Agent Console</span>
                <button
                  type="button"
                  onClick={() => setAgentMode((m) => (m === "plan" ? "build" : "plan"))}
                  className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase cursor-pointer transition-all active:scale-95 ${
                    agentMode === "build"
                      ? "bg-purple-500/15 border border-purple-400/30 text-purple-300 hover:bg-purple-500/25"
                      : "bg-cyan-500/15 border border-cyan-400/30 text-cyan-300 hover:bg-cyan-500/25"
                  }`}
                  title="Click to toggle Plan / Build mode"
                >
                  {agentMode}
                </button>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-300 font-mono flex items-center gap-1.5" title={activeModelId}>
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400/80" />
                  {formatModelDisplayName(activeModelId)}
                </span>
              </div>
            </div>

            {/* Agent Narrative & Tool Execution Timeline */}
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden relative">
              <ChatTimeline
                transcript={transcript}
                status={assistantStatus}
                activeSessionId={activeSessionId || undefined}
                activeSpeaker={activeSpeaker}
                activeModelId={activeModelId}
                liveToolProgress={liveToolProgress}
                footerDockHeight={footerDockHeight}
                activeThinkingText={activeThinkingText}
                onApprovePlan={handleApprovePlan}
                onRejectPlan={handleRejectPlan}
                onAnswerQuestion={handleAnswerQuestion}
                onOpenFile={(p: string) => handleOpenFileIDE(p, p.split("/").pop() || "file")}
                onSelectPrompt={(text: string) => setInputMessage(text)}
              />
            </div>

            {/* Dedicated Agent Command & Prompt Input Dock */}
            <BottomDock
              embedded={true}
              showAgentModeToggle={true}
              showInteractionModeToggle={false}
              inputMessage={inputMessage}
              setInputMessage={setInputMessage}
              onSend={(text: string, mode: "plan" | "build") => handleSendText(text, mode)}
              agentMode={agentMode}
              setAgentMode={setAgentMode}
              models={models}
              activeModelId={activeModelId}
              onSelectModel={handleSelectModel}
              status={assistantStatus}
              isMicActive={false}
              isMuted={true}
              onToggleMute={() => {}}
              onStartSession={() => {}}
              onInterrupt={() => {
                sendJSON({ type: "interrupt" });
                setAssistantStatus("idle");
              }}
              activeIntensity={0}
              interactionMode="chat"
              isConnected={wsStatus === "connected"}
              activeSessionId={activeSessionId}
              onNewSession={handleNewSession}
              onFolderUpload={() => handlePickLocalFolder()}
              onFileUpload={() => {}}
              liveToolProgress={liveToolProgress}
              activeQuestion={activeUnansweredQuestion}
              onAnswerQuestion={handleAnswerQuestion}
              onHeightChange={setFooterDockHeight}
              reasoningEffort={reasoningEffort}
              onSelectReasoningEffort={handleSelectReasoningEffort}
              onSteer={sendSteer}
              workspaceFiles={workspaceFilesList}
              gitStatus={gitStatus}
              promptTurnsCount={transcript.length}
            />
          </div>
        )}
      </div>

      {/* ── Unified Agent Statusbar (Anara Desktop Standard) ── */}
      <Suspense fallback={null}>
        <AgentStatusBar
          isConnected={wsStatus === "connected"}
          activeSessionId={activeSessionId}
          gitStatus={gitStatus}
          onOpenGitReview={() => {
            setIsLeftOpen(true);
            setExplorerMode("git");
            loadGitStatus(activeSessionId);
          }}
          tokenUsage={latestTokenUsage}
          assistantStatus={assistantStatus}
          activeModelId={activeModelId}
          reasoningEffort={reasoningEffort}
          onToggleTerminal={() => setIsTerminalOpen((v) => !v)}
          isTerminalOpen={isTerminalOpen}
        />
      </Suspense>

      {/* ── Anara Brain Modal Drawer ── */}
      {isBrainDrawerOpen && (
        <Suspense fallback={null}>
          <AnaraBrain
            isOpen={isBrainDrawerOpen}
            onClose={() => {
              setIsBrainDrawerOpen(false);
              fetchModels(true);
            }}
            activeSpeaker={activeSpeaker}
          />
        </Suspense>
      )}
    </main>
  );
}
