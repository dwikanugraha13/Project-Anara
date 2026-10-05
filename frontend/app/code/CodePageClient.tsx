"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo, Suspense, lazy } from "react";
import Link from "next/link";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { TranscriptPayload, ToolProgressPayload } from "@/hooks/useWebSocket";
import { useStreamingQueue } from "@/hooks/useStreamingQueue";
import type { TranscriptItem, AssistantStatus } from "@/components/workbench";
import { AIModelInfo } from "@/components/dock/ModelSelectorDropdown";
import { formatModelDisplayName } from "@/lib/modelFormat";
import { restoreTranscriptFromMessages } from "@/lib/sessionRestoration";
import { anaraApi, apiRequest, getWebSocketUrl } from "@/lib/apiClient";
import {
  ReasoningEffortLevel,
  saveReasoningEffortForModel,
  getSavedReasoningEffortForModel,
} from "@/lib/reasoningEffort";
import type { AnaraBrainProps } from "@/components/brain/types";
import type { IdeTabFile } from "@/components/ide";
import type { WorkspaceTreeData, GitStatusData, ChatSession } from "@/components/sidebar/types";
import { CodeStudioHeader } from "./CodeStudioHeader";
import { CodeStudioWorkspace } from "./CodeStudioWorkspace";
import { useCodeStudioLayout } from "./useCodeStudioLayout";
import { playAnaraCompletionChime, playAnaraAlertChime } from "@/lib/anaraSoundSynthesizer";

const AnaraBrain = lazy(() => import("@/components/brain/AnaraBrain"));
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
  const activeSessionIdRef = useRef<number | null>(null);
  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

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

  // Streaming queue: coalesces deltas and flushes to React state at ~30fps
  const codeStreamingFlush = useCallback((accumulatedText: string) => {
    setTranscript((prev) => {
      const lastIdx = prev.length - 1;
      const last = prev[lastIdx];
      if (last && last.speaker === "output") {
        return [...prev.slice(0, lastIdx), { ...last, text: accumulatedText, isStreaming: true }];
      }
      return [...prev, { speaker: "output" as const, text: accumulatedText, isStreaming: true, startTime: Date.now() }];
    });
  }, []);
  const { appendDelta: cStreamAppendDelta, setAccumulated: cStreamSetAccumulated, reset: cStreamReset, flushNow: cStreamFlushNow } = useStreamingQueue(codeStreamingFlush);
  const [inputMessage, setInputMessage] = useState("");
  const [agentMode, setAgentMode] = useState<"plan" | "build">("build");
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
    setActiveModelId(modelId);
    try {
      localStorage.setItem("anara_code_model", modelId);
      await anaraApi.models.setActive(modelId);
    } catch (err) {
      console.warn("[CodeStudio] setActiveModel error:", err);
    }
  }, []);

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
      // Clean up ghost editor tabs if no workspace is attached to this session
      setIdeTabs([]);
      setActiveIdeFile({ isOpen: false, fileName: "", filePath: "", fileExt: "", fileSizeKb: 0, content: "" });
      localStorage.removeItem("anara_code_ide_tabs");
      localStorage.removeItem("anara_code_ide_active_file");
    } catch (e) {
      console.warn("[CodeStudio] loadWorkspaceTree error:", e);
      setWorkspaceTree(null);
      setIdeTabs([]);
      setActiveIdeFile({ isOpen: false, fileName: "", filePath: "", fileExt: "", fileSizeKb: 0, content: "" });
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
      // Session Isolation Guard: Prevent foreign session messages from polluting current timeline
      const msgSessionId = typeof payload === "string" ? undefined : payload.sessionId;
      const currentSid = activeSessionIdRef.current;
      if (msgSessionId && currentSid && msgSessionId !== currentSid) {
        return;
      }

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
      const delta = typeof payload === "string" ? undefined : payload.delta;
      const payloadTokenUsage = typeof payload === "string" ? undefined : payload.tokenUsage;
      const payloadToolsUsed = typeof payload === "string" ? undefined : (payload.toolsUsed || payload.tokenUsage?.toolsUsed);

      // ── Streaming fast-path: route through adaptive delta queue (~30fps) ──
      if (isPartial && payloadIsStreaming && speaker === "output" && (!visualType || visualType === "none")) {
        if (delta) {
          cStreamAppendDelta(delta);
        } else {
          cStreamSetAccumulated(text);
        }
        return;
      }

      // ── Final message: flush any pending queue first ──
      if (!isPartial && !payloadIsStreaming) {
        cStreamFlushNow();
        cStreamReset();
      }

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
    onSubagentEvent: (msg) => {
      console.log(`[CodeStudio] Subagent Event: ${msg.type}`, msg);
      const taskId = String(msg.task_id || "1");
      const status: any =
        msg.type === "subagent_task_completed" ? "completed" :
        msg.type === "subagent_task_failed" ? (msg.status === "timed_out" ? "timed_out" : "failed") :
        "running";

      setTranscript((prev) => {
        const lastIdx = prev.length - 1;
        const last = prev[lastIdx];
        if (last && last.visualType === "subagent" && last.subagentData) {
          const currentTasks = [...last.subagentData.tasks];
          const taskIdx = currentTasks.findIndex((t) => t.taskId === taskId);
          const currentActivity = msg.tool_name
            ? `${msg.tool_name}: ${msg.detail || msg.status || "executing"}`
            : (msg.detail || msg.summary || "Running subagent mission...");

          if (taskIdx >= 0) {
            const existing = currentTasks[taskIdx];
            currentTasks[taskIdx] = {
              ...existing,
              status,
              durationSec: msg.duration_sec ?? existing.durationSec,
              summary: msg.summary ?? existing.summary,
              findings: msg.findings ?? existing.findings,
              keyFindings: msg.key_findings ?? existing.keyFindings,
              referencedFiles: msg.referenced_files ?? existing.referencedFiles,
              error: msg.error ?? existing.error,
              activity: [...existing.activity, currentActivity].slice(-8),
            };
          } else {
            currentTasks.push({
              id: taskId,
              taskId,
              goal: msg.goal || msg.title || "Subagent Mission",
              model: msg.model,
              status,
              depth: msg.depth || 1,
              startedAt: Date.now(),
              activity: [currentActivity],
              summary: msg.summary,
              findings: msg.findings,
              keyFindings: msg.key_findings,
              referencedFiles: msg.referenced_files,
              error: msg.error,
            });
          }

          const updatedData = {
            ...last.subagentData,
            status: currentTasks.some((t) => t.status === "running") ? "running" : "completed",
            tasks: currentTasks,
          };

          return [
            ...prev.slice(0, lastIdx),
            {
              ...last,
              subagentData: updatedData,
            },
          ];
        }

        const initialTask = {
          id: taskId,
          taskId,
          goal: msg.goal || msg.title || "Subagent Mission",
          model: msg.model,
          status,
          depth: msg.depth || 1,
          startedAt: Date.now(),
          activity: [msg.tool_name ? `${msg.tool_name}: running` : (msg.detail || "Spawning autonomous worker...")],
          summary: msg.summary,
          findings: msg.findings,
          keyFindings: msg.key_findings,
          referencedFiles: msg.referenced_files,
          error: msg.error,
        };

        const subagentData = {
          delegationId: `del_${Date.now()}`,
          goal: msg.goal || msg.title || "Delegated Subagent Mission",
          status,
          tasks: [initialTask],
        };

        return [
          ...prev,
          {
            speaker: "output",
            text: "",
            visualType: "subagent" as any,
            subagentData,
          },
        ];
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
    onPlanPending: (msg) => {
      const planId = msg.plan_id || msg.planId || `plan_${Date.now()}`;
      const toolName = msg.tool_name || msg.toolName || "";
      const toolArgs = msg.tool_args || msg.toolArgs || {};
      const commandPreview = toolArgs.command || toolArgs.file_path || toolArgs.title || "";
      const rationale = msg.text || msg.rationale || "";
      const actionMeta = msg.action_metadata || {};
      const riskLevel = (actionMeta.risk_level || actionMeta.riskLevel || "medium") as "low" | "medium" | "high" | "critical";

      cStreamFlushNow();
      cStreamReset();
      playAnaraAlertChime();

      setTranscript((prev) => [
        ...prev,
        {
          speaker: "output",
          text: rationale,
          visualType: "approval" as const,
          approvalData: { planId, toolName, commandPreview, rationale, riskLevel },
        },
      ]);
      setAssistantStatus("idle");
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
      playAnaraCompletionChime();
      loadGitStatus(activeSessionId);
      setTranscript((prev) => {
        const last = prev[prev.length - 1];
        if (
          last &&
          last.speaker === "output" &&
          !last.text &&
          (!last.visualType || last.visualType === "none") &&
          (!last.toolsUsed || last.toolsUsed.length === 0)
        ) {
          return prev.slice(0, -1).map((t) => (t.isStreaming ? { ...t, isStreaming: false } : t));
        }
        return prev.map((t) => (t.isStreaming ? { ...t, isStreaming: false } : t));
      });
    },
    onSessionSwitched: (payload) => {
      if (payload.sessionId) {
        setActiveSessionId(payload.sessionId);
        localStorage.setItem("anara_active_code_session_id", String(payload.sessionId));
        setSessionRefreshKey((k) => k + 1);
        if (payload.messages && Array.isArray(payload.messages)) {
          setTranscript(restoreTranscriptFromMessages(payload.messages));
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
        const urlSid = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("session_id") : null;
        const savedSess = urlSid || localStorage.getItem("anara_active_session_id") || localStorage.getItem("anara_active_code_session_id");

        if (Array.isArray(list) && list.length > 0) {
          const match = savedSess ? list.find((s) => s.id === Number(savedSess)) : null;
          const targetId = match ? match.id : list[0].id;
          setActiveSessionId(targetId);
          localStorage.setItem("anara_active_session_id", String(targetId));
          if (typeof window !== "undefined") {
            const url = new URL(window.location.href);
            url.searchParams.set("session_id", String(targetId));
            window.history.replaceState({}, "", url.toString());
          }
          if (wsStatus === "connected") {
            sendJSON({ type: "switch_session", sessionId: targetId });
          }
        } else {
          setActiveSessionId(null);
          localStorage.removeItem("anara_active_session_id");
          localStorage.removeItem("anara_active_code_session_id");
          localStorage.removeItem("anara_code_ide_tabs");
          localStorage.removeItem("anara_code_ide_active_file");
          setIdeTabs([]);
          setActiveIdeFile({ isOpen: false, fileName: "", filePath: "", fileExt: "", fileSizeKb: 0, content: "" });
          if (typeof window !== "undefined") {
            const url = new URL(window.location.href);
            url.searchParams.delete("session_id");
            window.history.replaceState({}, "", url.toString());
          }
        }
      } catch (err) {
        console.warn("[CodeStudio] init session error:", err);
      }
    };
    initCodeSession();
  }, [wsStatus, sendJSON]);

  // ── Sync activeSessionId with browser URL query param ──
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const url = new URL(window.location.href);
      if (activeSessionId) {
        if (url.searchParams.get("session_id") !== String(activeSessionId)) {
          url.searchParams.set("session_id", String(activeSessionId));
          window.history.replaceState({}, "", url.toString());
        }
      } else {
        if (url.searchParams.has("session_id")) {
          url.searchParams.delete("session_id");
          window.history.replaceState({}, "", url.toString());
        }
      }
    } catch {}
  }, [activeSessionId]);

  const handleSelectSession = (id: number) => {
    // Eager-clear stale workspace state BEFORE switching session (Anara Parity)
    setWorkspaceTree(null);
    setGitStatus(null);
    setTranscript([]);
    setActiveSessionId(id);
    localStorage.setItem("anara_active_session_id", String(id));
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("session_id", String(id));
      window.history.replaceState({}, "", url.toString());
    }
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
    localStorage.removeItem("anara_code_ide_tabs");
    localStorage.removeItem("anara_code_ide_active_file");
    setIdeTabs([]);
    setActiveIdeFile({ isOpen: false, fileName: "", filePath: "", fileExt: "", fileSizeKb: 0, content: "" });
    setTranscript([]);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.delete("session_id");
      window.history.replaceState({}, "", url.toString());
    }
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

  const handleSendText = (text: string, mode?: "plan" | "build") => {
    if (!text.trim()) return;
    const trimmed = text.trim();

    let activeApproval = "smart";
    if (typeof window !== "undefined") {
      try {
        activeApproval = (localStorage.getItem("anara_approval_mode") || "smart").toLowerCase();
      } catch {}
    }
    const effectiveMode: "plan" | "build" = mode || (activeApproval === "plan" || activeApproval === "manual" ? "plan" : agentMode);

    setTranscript((prev) => [
      ...prev,
      { speaker: "input", text: trimmed },
      { speaker: "output", text: "", agentMode: effectiveMode, startTime: Date.now() },
    ]);
    sendJSON({
      type: "text_input",
      text: trimmed,
      channel: "code",
      platform: "code",
      agent_mode: effectiveMode,
      approval_mode: activeApproval,
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

  const handleApproveAction = useCallback(
    (planId: string, scope: "once" | "session") => {
      sendJSON({
        type: "text_input",
        text: "Yes, approve and execute.",
        channel: "code",
        platform: "code",
        agent_mode: "build",
        sessionId: activeSessionId,
        session_type: "code",
        workspace_path: workspaceTree?.root_path || "",
      });
      setTranscript((prev) =>
        prev.map((item) => {
          if (item.visualType === "approval" && item.approvalData?.planId === planId) {
            return { ...item, text: `${item.text}\n\n✓ Approved (${scope})` };
          }
          return item;
        })
      );
    },
    [sendJSON, activeSessionId]
  );

  const handleRejectAction = useCallback(
    (planId: string) => {
      sendJSON({
        type: "text_input",
        text: "No, reject this action.",
        channel: "code",
        platform: "code",
        agent_mode: "build",
        sessionId: activeSessionId,
        session_type: "code",
        workspace_path: workspaceTree?.root_path || "",
      });
      setTranscript((prev) =>
        prev.map((item) => {
          if (item.visualType === "approval" && item.approvalData?.planId === planId) {
            return { ...item, text: `${item.text}\n\n✗ Rejected` };
          }
          return item;
        })
      );
    },
    [sendJSON, activeSessionId]
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

  // Sync active session title to local cache for instant zero-flicker hydration on refresh
  useEffect(() => {
    if (activeSession?.title) {
      localStorage.setItem("anara_active_session_title", activeSession.title);
    } else if (activeSessionId === null) {
      localStorage.removeItem("anara_active_session_title");
    }
  }, [activeSession, activeSessionId]);

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
        sessionsLoading={sessionsLoading}
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
          2. THREE-PANE AUTONOMOUS CODING STUDIO WORKBENCH (Modularized)
         ══════════════════════════════════════════════════════════════════════ */}
      <CodeStudioWorkspace
        isLeftOpen={isLeftOpen}
        setIsLeftOpen={setIsLeftOpen}
        explorerMode={explorerMode}
        setExplorerMode={setExplorerMode}
        explorerFilter={explorerFilter}
        setExplorerFilter={setExplorerFilter}
        isTerminalOpen={isTerminalOpen}
        setIsTerminalOpen={setIsTerminalOpen}
        isRightOpen={isRightOpen}
        setIsRightOpen={setIsRightOpen}
        setIsBrainDrawerOpen={setIsBrainDrawerOpen}
        gitStatus={gitStatus}
        loadGitStatus={loadGitStatus}
        workspaceTree={workspaceTree}
        activeIdeFile={activeIdeFile}
        setActiveIdeFile={setActiveIdeFile}
        ideTabs={ideTabs}
        handleSelectIdeTab={handleSelectIdeTab}
        handleCloseIdeTab={handleCloseIdeTab}
        handleSaveIdeFile={handleSaveIdeFile}
        leftWidth={leftWidth}
        startResizingLeft={startResizingLeft}
        terminalHeight={terminalHeight}
        startResizingTerminal={startResizingTerminal}
        rightWidth={rightWidth}
        startResizingRight={startResizingRight}
        agentMode={agentMode}
        setAgentMode={setAgentMode}
        activeModelId={activeModelId}
        models={models}
        handleSelectModel={handleSelectModel}
        assistantStatus={assistantStatus}
        setAssistantStatus={setAssistantStatus}
        activeSpeaker={activeSpeaker}
        transcript={transcript}
        liveToolProgress={liveToolProgress}
        footerDockHeight={footerDockHeight}
        setFooterDockHeight={setFooterDockHeight}
        activeThinkingText={activeThinkingText}
        handleApprovePlan={handleApprovePlan}
        handleRejectPlan={handleRejectPlan}
        handleApproveAction={handleApproveAction}
        handleRejectAction={handleRejectAction}
        handleAnswerQuestion={handleAnswerQuestion}
        handleOpenFileIDE={handleOpenFileIDE}
        handlePickLocalFolder={handlePickLocalFolder}
        handleClearWorkspace={handleClearWorkspace}
        handleSendText={handleSendText}
        inputMessage={inputMessage}
        setInputMessage={setInputMessage}
        sendJSON={sendJSON}
        sendSteer={sendSteer}
        wsStatus={wsStatus}
        activeSessionId={activeSessionId}
        handleNewSession={handleNewSession}
        reasoningEffort={reasoningEffort}
        handleSelectReasoningEffort={handleSelectReasoningEffort}
        workspaceFilesList={workspaceFilesList}
        activeUnansweredQuestion={activeUnansweredQuestion}
      />

      {/* ── Unified Agent Statusbar (Anara Desktop Standard) ── */}
      <Suspense fallback={null}>
        <AgentStatusBar
          isConnected={wsStatus === "connected"}
          activeSessionId={activeSessionId}
          workspaceName={workspaceTree?.is_custom_folder && workspaceTree?.workspace_name ? workspaceTree.workspace_name : ""}
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
