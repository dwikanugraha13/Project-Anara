"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { TranscriptPayload } from "@/hooks/useWebSocket";
import type { TranscriptItem, AssistantStatus } from "@/components/workbench";
import ChatTimeline from "@/components/chat/ChatTimeline";
import BottomDock from "@/components/dock/BottomDock";
import { AIModelInfo } from "@/components/dock/ModelSelectorDropdown";
import type { AnaraBrainProps } from "@/components/brain/types";
import type { AnaraCodeIDEProps, WorkbenchTerminalProps, IdeTabFile } from "@/components/ide";
import WorkspaceTreeView from "@/components/sidebar/WorkspaceTreeView";
import type { WorkspaceTreeData, GitStatusData, ChatSession } from "@/components/sidebar/types";

const AnaraBrain = dynamic<AnaraBrainProps>(() => import("@/components/brain/AnaraBrain"), {
  ssr: false,
});
const AnaraCodeIDE = dynamic<AnaraCodeIDEProps>(() => import("@/components/ide/AnaraCodeIDE"), {
  ssr: false,
});
const WorkbenchTerminal = dynamic<WorkbenchTerminalProps>(() => import("@/components/ide/WorkbenchTerminal"), {
  ssr: false,
});

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || BACKEND_URL.replace(/^http/, "ws") + "/ws";

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
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [sessionRefreshKey, setSessionRefreshKey] = useState(0);
  const [activeSpeaker, setActiveSpeaker] = useState<string>("Agnan");
  const [speakerRoster, setSpeakerRoster] = useState<string[]>([]);
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus>("idle");
  const [liveToolProgress, setLiveToolProgress] = useState<any>(null);
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

  // ── Pane Layout & Resizing State ──
  const [isLeftOpen, setIsLeftOpen] = useState(true);
  const [isRightOpen, setIsRightOpen] = useState(true);
  const [leftWidth, setLeftWidth] = useState(initialSidebarWidth);
  const [rightWidth, setRightWidth] = useState(initialRightWidth);
  const [isTerminalOpen, setIsTerminalOpen] = useState(initialTerminalOpen);
  const [terminalHeight, setTerminalHeight] = useState(initialTerminalHeight);

  const [isResizingLeft, setIsResizingLeft] = useState(false);
  const [isResizingRight, setIsResizingRight] = useState(false);
  const [isResizingTerminal, setIsResizingTerminal] = useState(false);

  const leftStartXRef = useRef(0);
  const startLeftWidthRef = useRef(initialSidebarWidth);
  const rightStartXRef = useRef(0);
  const startRightWidthRef = useRef(initialRightWidth);
  const terminalStartYRef = useRef(0);
  const startTerminalHeightRef = useRef(210);

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
          setActiveIdeFile(parsed);
        }
      }

      // Pre-warm active session id from localStorage for instant workspace tree loading
      const savedSess = localStorage.getItem("anara_active_code_session_id");
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

  // Persist open tabs and active file
  useEffect(() => {
    if (!isIdeHydratedRef.current) return;
    try {
      localStorage.setItem("anara_code_ide_active_file", JSON.stringify(activeIdeFile));
    } catch {}
  }, [activeIdeFile]);

  useEffect(() => {
    if (!isIdeHydratedRef.current) return;
    try {
      localStorage.setItem("anara_code_ide_tabs", JSON.stringify(ideTabs));
    } catch {}
  }, [ideTabs]);

  // ── Check URL search params for session_id on initial mount ──
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const params = new URLSearchParams(window.location.search);
        const sid = params.get("session_id");
        if (sid && !isNaN(Number(sid))) {
          localStorage.setItem("anara_active_code_session_id", sid);
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
      const url = refresh ? `${BACKEND_URL}/api/models?refresh=true` : `${BACKEND_URL}/api/models`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      const all: any[] = data.models || [];
      const configured = all.filter((m: any) => m.is_configured);
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
    setActiveModelId(modelId);
    try {
      await fetch(`${BACKEND_URL}/api/models/active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId }),
      });
    } catch (err) {
      console.warn("[CodeStudio] setActiveModel error:", err);
    }
  }, []);

  // ── Fetch Sessions List ──
  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/sessions?session_type=code`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch (err) {
      console.warn("[CodeStudio] loadSessions error:", err);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  // ── Fetch Workspace Tree & Git Status ──
  const loadWorkspaceTree = useCallback(async (sid?: number | null) => {
    try {
      const q = sid ? `?session_id=${sid}` : "";
      const res = await fetch(`${BACKEND_URL}/api/agent/workspace/tree${q}`);
      if (res.ok) {
        const data = await res.json();
        if (data && (data.total_files > 0 || data.is_custom_folder)) {
          setWorkspaceTree(data);
          return;
        }
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
      const res = await fetch(`${BACKEND_URL}/api/agent/git/status?session_id=${sid}`);
      if (res.ok) {
        setGitStatus(await res.json());
      } else {
        setGitStatus(null);
      }
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
      const res = await fetch(`${BACKEND_URL}/api/agent/pick-local-folder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: activeSessionId || undefined, folder_path: targetPath || "" }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success" && data.tree) {
          setWorkspaceTree(data.tree);
          setExplorerMode("tree");
          setIsLeftOpen(true);
          loadGitStatus(activeSessionId);
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "workspace_updated" } }));
          }
        }
      }
    } catch (err) {
      console.warn("[Workspace] pick local folder error:", err);
    }
  }, [activeSessionId, loadGitStatus]);

  const handleClearWorkspace = async () => {
    if (!confirm(`Tutup & lepaskan folder "${workspaceTree?.workspace_name}" dari sesi ini?`)) return;
    try {
      const q = activeSessionId ? `?session_id=${activeSessionId}` : "";
      await fetch(`${BACKEND_URL}/api/agent/workspace${q}`, { method: "DELETE" });
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
      const q = activeSessionId ? `&session_id=${activeSessionId}` : "";
      const res = await fetch(`${BACKEND_URL}/api/agent/workspace/file-content?path=${encodeURIComponent(filePath)}${q}`);
      if (res.ok) {
        const data = await res.json();
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
    if (existing) {
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
  } = useWebSocket({
    url: WS_URL,
    onTranscript: (payload: TranscriptPayload | string, rawSpeaker?: "input" | "output") => {
      const text = typeof payload === "string" ? payload : payload.text;
      const speaker = typeof payload === "string" ? (rawSpeaker ?? "output") : payload.speaker;
      const isPartial = typeof payload === "string" ? false : (payload.isPartial ?? false);
      const visualType = typeof payload === "string" ? undefined : payload.visualType;
      const agentActionData = typeof payload === "string" ? undefined : payload.agentActionData;
      const planData = typeof payload === "string" ? undefined : payload.planData;

      if (speaker === "output" && text && text.trim().length > 0) {
        setActiveThinkingText(null);
      }

      setTranscript((prev) => {
        const lastIdx = prev.length - 1;
        const last = prev[lastIdx];

        const newEntry: TranscriptItem = {
          speaker,
          text,
          visualType,
          agentActionData,
          planData,
          agentMode,
          modelId: activeModelId,
          isStreaming: isPartial,
          startTime: last?.startTime || Date.now(),
        };

        if (prev.length === 0) return [newEntry];

        if (speaker === "input") {
          return [...prev, newEntry];
        }

        if (visualType && visualType !== "none") {
          if (
            visualType === "agent_action" &&
            last &&
            last.visualType === "agent_action" &&
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
          return [...prev.slice(0, lastIdx), { ...last, text: text, isStreaming: true }];
        }

        return [...prev.slice(0, lastIdx), { ...last, text: text, isStreaming: false }];
      });
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
          const mapped: TranscriptItem[] = payload.messages.flatMap((m: any) => {
            const items: TranscriptItem[] = [];
            if (m.user_text) items.push({ speaker: "input", text: m.user_text });
            if (m.ai_text) items.push({ speaker: "output", text: m.ai_text, agentMode: "plan" });
            return items;
          });
          setTranscript(mapped);
        }
      }
    },
    onSessionIdSync: (sessionId) => {
      setActiveSessionId(sessionId);
      localStorage.setItem("anara_active_code_session_id", String(sessionId));
      setSessionRefreshKey((k) => k + 1);
    },
  });

  // ── Auto-Initialize Code Session on Mount ──
  useEffect(() => {
    const initCodeSession = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/chat/sessions?session_type=code`);
        if (res.ok) {
          const list = await res.json();
          if (Array.isArray(list) && list.length > 0) {
            const savedSess = localStorage.getItem("anara_active_code_session_id");
            const match = savedSess ? list.find((s: any) => s.id === Number(savedSess)) : null;
            const targetId = match ? match.id : list[0].id;
            setActiveSessionId(targetId);
            localStorage.setItem("anara_active_code_session_id", String(targetId));
            if (wsStatus === "connected") {
              sendJSON({ type: "switch_session", sessionId: targetId });
            }
          } else {
            const createRes = await fetch(`${BACKEND_URL}/api/chat/sessions`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ session_type: "code", title: "New Project" }),
            });
            if (createRes.ok) {
              const data = await createRes.json();
              if (data.session?.id) {
                setActiveSessionId(data.session.id);
                localStorage.setItem("anara_active_code_session_id", String(data.session.id));
                if (wsStatus === "connected") {
                  sendJSON({ type: "switch_session", sessionId: data.session.id });
                }
              }
            }
          }
        }
      } catch (err) {
        console.warn("[CodeStudio] init session error:", err);
      }
    };
    initCodeSession();
  }, [wsStatus, sendJSON]);

  const handleSelectSession = (id: number) => {
    setActiveSessionId(id);
    localStorage.setItem("anara_active_code_session_id", String(id));
    sendJSON({ type: "switch_session", sessionId: id });
  };

  const handleNewSession = () => {
    setActiveSessionId(null);
    localStorage.removeItem("anara_active_code_session_id");
    setTranscript([]);
    sendJSON({ type: "new_session", session_type: "code", title: "New Project" });
  };

  const handlePatchSession = async (id: number, body: Record<string, unknown>) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/sessions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, ...body } : s)));
      }
    } catch (e) {
      console.warn("[Session] patch error:", e);
    }
  };

  const handleDeleteSession = async (s: ChatSession) => {
    if (!confirm(`Hapus "${s.title || `Sesi #${s.id}`}"?`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/sessions/${s.id}`, { method: "DELETE" });
      if (res.ok) {
        setSessions((prev) => prev.filter((x) => x.id !== s.id));
        if (activeSessionId === s.id) {
          handleNewSession();
        }
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
      agent_mode: mode,
      sessionId: activeSessionId,
    });
    setAssistantStatus("thinking");
  };

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

  // ── Drag Resizing Handlers (Crisp 1px hairline dividers) ──
  const startResizingLeft = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingLeft(true);
    leftStartXRef.current = e.clientX;
    startLeftWidthRef.current = leftWidth;
  };

  const startResizingRight = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingRight(true);
    rightStartXRef.current = e.clientX;
    startRightWidthRef.current = rightWidth;
  };

  const startResizingTerminal = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingTerminal(true);
    terminalStartYRef.current = e.clientY;
    startTerminalHeightRef.current = terminalHeight;
  };

  useEffect(() => {
    if (!isResizingLeft && !isResizingRight && !isResizingTerminal) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (isResizingLeft) {
        const dx = e.clientX - leftStartXRef.current;
        const newW = Math.max(180, Math.min(500, startLeftWidthRef.current + dx));
        setLeftWidth(newW);
        document.documentElement.style.setProperty("--studio-left-width", `${newW}px`);
      }
      if (isResizingRight) {
        const dx = rightStartXRef.current - e.clientX;
        const newW = Math.max(340, Math.min(700, startRightWidthRef.current + dx));
        setRightWidth(newW);
        document.documentElement.style.setProperty("--studio-right-width", `${newW}px`);
      }
      if (isResizingTerminal) {
        const dy = terminalStartYRef.current - e.clientY;
        const newH = Math.max(100, Math.min(600, startTerminalHeightRef.current + dy));
        setTerminalHeight(newH);
      }
    };

    const handleMouseUp = () => {
      if (isResizingLeft) {
        try {
          localStorage.setItem("anara_studio_left_width", leftWidth.toString());
          document.cookie = `anara_studio_left_width=${leftWidth}; path=/; max-age=31536000; SameSite=Lax`;
          document.documentElement.style.setProperty("--studio-left-width", `${leftWidth}px`);
        } catch {}
      }
      if (isResizingRight) {
        try {
          localStorage.setItem("anara_studio_right_width", rightWidth.toString());
          document.cookie = `anara_studio_right_width=${rightWidth}; path=/; max-age=31536000; SameSite=Lax`;
          document.documentElement.style.setProperty("--studio-right-width", `${rightWidth}px`);
        } catch {}
      }
      if (isResizingTerminal) {
        try {
          localStorage.setItem("anara_studio_term_height", terminalHeight.toString());
          document.cookie = `anara_studio_term_height=${terminalHeight}; path=/; max-age=31536000; SameSite=Lax`;
        } catch {}
      }
      setIsResizingLeft(false);
      setIsResizingRight(false);
      setIsResizingTerminal(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizingLeft, isResizingRight, isResizingTerminal, leftWidth, rightWidth, terminalHeight]);

  const activeSession = useMemo(() => {
    return sessions.find((s) => s.id === activeSessionId) || null;
  }, [sessions, activeSessionId]);

  return (
    <main className="relative w-screen h-screen overflow-hidden flex flex-col font-sans select-none bg-[#030712] text-slate-100">
      {/* ══════════════════════════════════════════════════════════════════════
          1. STUDIO TOP NAVIGATION BAR (Claude Code & OpenCode Standard)
         ══════════════════════════════════════════════════════════════════════ */}
      <header className="h-11 shrink-0 px-3 border-b border-white/10 flex items-center justify-between bg-[#040813] z-30 select-none">
        {/* Left Side: Brand Logo and Session Switcher Dropdown */}
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex items-center gap-2 shrink-0">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]" />
            <h1 className="text-xs font-bold font-mono text-white tracking-wider uppercase">
              Anara Code Studio
            </h1>
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/10 border border-cyan-400/20 text-cyan-300 font-semibold">
              Autonomous
            </span>
          </div>

          <div className="h-4 w-px bg-white/10 shrink-0 mx-0.5" />

          {/* Session Selector Popover */}
          <div className="relative" ref={sessionDropdownRef}>
            <button
              type="button"
              onClick={() => setIsSessionDropdownOpen((v) => !v)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 hover:border-white/20 text-xs font-mono text-slate-200 hover:text-white transition-colors cursor-pointer"
              title="Pilih atau beralih sesi proyek"
            >
              <span>💬</span>
              <span className="font-semibold text-white truncate max-w-[150px]">
                {activeSession?.title || `Sesi #${activeSessionId || 1}`}
              </span>
              <span className="text-[10px] text-slate-400">▾</span>
            </button>

            {isSessionDropdownOpen && (
              <div className="absolute left-0 top-full mt-1.5 w-64 max-h-80 overflow-y-auto custom-scrollbar rounded-xl bg-[#090e1c] border border-white/15 shadow-2xl z-50 p-1.5 select-none font-mono animate-fade-in">
                <div className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-white/10 flex items-center justify-between">
                  <span>Sesi Proyek</span>
                  <span>{sessions.length} sesi</span>
                </div>

                <div className="py-1 space-y-0.5">
                  {sessions.length === 0 ? (
                    <div className="p-3 text-center text-xs text-slate-500">Belum ada sesi</div>
                  ) : (
                    sessions.map((s) => {
                      const isCur = s.id === activeSessionId;
                      return (
                        <div
                          key={s.id}
                          onClick={() => {
                            handleSelectSession(s.id);
                            setIsSessionDropdownOpen(false);
                          }}
                          className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
                            isCur
                              ? "bg-cyan-500/20 text-cyan-200 font-semibold border border-cyan-400/30"
                              : "hover:bg-white/[0.06] text-slate-300 hover:text-white"
                          }`}
                        >
                          <span className="truncate flex-1">{s.title || `Sesi #${s.id}`}</span>
                          <span className="text-[10px] text-slate-500 ml-2 shrink-0">
                            {s.message_count}
                          </span>
                        </div>
                      );
                    })
                  )}
                </div>

                <div className="pt-1 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => {
                      handleNewSession();
                      setIsSessionDropdownOpen(false);
                    }}
                    className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs font-semibold text-cyan-300 hover:text-white transition-colors cursor-pointer"
                  >
                    <span>+ Sesi Baru</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={handleNewSession}
            className="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-xs font-mono text-slate-300 hover:text-white transition-colors cursor-pointer"
            title="Buat sesi koding baru"
          >
            <span>+ Baru</span>
          </button>
        </div>

        {/* Right Side: View Toggles, 3D Companion Link, and Brain */}
        <div className="flex items-center gap-2 shrink-0">
          {/* View Toggles: Explorer, Terminal & Agent */}
          <div className="flex items-center gap-1 bg-white/[0.03] p-0.5 rounded-lg border border-white/10">
            <button
              type="button"
              onClick={() => setIsLeftOpen((v) => !v)}
              className={`px-2 py-1 rounded text-xs font-mono transition-colors cursor-pointer ${
                isLeftOpen ? "bg-white/10 text-white font-medium" : "text-slate-400 hover:text-white"
              }`}
              title="Toggle File Explorer (Kiri)"
            >
              📁 Explorer
            </button>
            <button
              type="button"
              onClick={() => {
                setIsTerminalOpen((v) => {
                  try {
                    localStorage.setItem("anara_studio_term_open", String(!v));
                    document.cookie = `anara_studio_term_open=${!v}; path=/; max-age=31536000; SameSite=Lax`;
                  } catch {}
                  return !v;
                });
              }}
              className={`px-2 py-1 rounded text-xs font-mono transition-colors cursor-pointer ${
                isTerminalOpen ? "bg-white/10 text-white font-medium" : "text-slate-400 hover:text-white"
              }`}
              title="Toggle Terminal Shell (Bawah)"
            >
              ⌨️ Terminal
            </button>
            <button
              type="button"
              onClick={() => setIsRightOpen((v) => !v)}
              className={`px-2 py-1 rounded text-xs font-mono transition-colors cursor-pointer ${
                isRightOpen ? "bg-cyan-500/15 text-cyan-300 font-medium" : "text-slate-400 hover:text-white"
              }`}
              title="Toggle Anara Agent Panel (Kanan)"
            >
              🤖 Agent
            </button>
          </div>

          {/* Link back to 3D Companion */}
          <a
            href="/"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-xs font-mono text-slate-300 hover:text-white transition-colors cursor-pointer"
            title="Beralih ke Asisten 3D & Suara"
          >
            <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            <span className="hidden sm:inline">3D Companion</span>
          </a>

          <button
            type="button"
            onClick={() => setIsBrainDrawerOpen(true)}
            className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-xs font-mono text-slate-300 hover:text-white transition-colors cursor-pointer"
          >
            Anara Brain
          </button>
        </div>
      </header>

      {/* ══════════════════════════════════════════════════════════════════════
          2. THREE-PANE AUTONOMOUS CODING STUDIO WORKBENCH
         ══════════════════════════════════════════════════════════════════════ */}
      <div className="flex-1 flex min-h-0 items-stretch overflow-hidden relative">
        {/* ── PANE 1 (LEFT): File Explorer & Git Status ── */}
        {isLeftOpen && (
          <>
            <div
              style={{ width: `var(--studio-left-width, ${leftWidth}px)`, transition: "none" }}
              className="h-full shrink-0 flex flex-col bg-[#050914] overflow-hidden select-none relative studio-pane"
            >
              {workspaceTree && (workspaceTree.total_files > 0 || workspaceTree.is_custom_folder) ? (
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
                  <div className="w-12 h-12 rounded-2xl bg-white/[0.03] border border-white/10 flex items-center justify-center text-cyan-400">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                  </div>
                  <h4 className="text-xs font-semibold text-white font-mono uppercase tracking-wider">
                    Belum Ada Folder
                  </h4>
                  <p className="text-[11px] text-slate-400 leading-relaxed max-w-[200px]">
                    Hubungkan direktori lokal untuk membaca struktur berkas proyek.
                  </p>
                  <button
                    type="button"
                    onClick={() => handlePickLocalFolder()}
                    className="px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/30 text-cyan-300 hover:text-white text-xs font-mono font-semibold transition-colors cursor-pointer"
                  >
                    Pilih Folder Proyek
                  </button>
                </div>
              )}
            </div>

            {/* Resizer Splitter 1: Left Explorer ↔ Center Editor (1px Razor-Thin White Hairline) */}
            <div
              onMouseDown={startResizingLeft}
              className="relative w-px h-full cursor-col-resize shrink-0 select-none bg-white/10 hover:bg-white/30 active:bg-white/50 transition-colors z-20"
              title="Tarik untuk mengubah lebar panel berkas"
            >
              <div className="absolute inset-y-0 -left-1.5 w-3 cursor-col-resize bg-transparent" />
            </div>
          </>
        )}

        {/* ── PANE 2 (CENTER - MAIN): CodeMirror 6 Editor & Terminal Dock (FLEX-1) ── */}
        <div
          style={{ transition: "none" }}
          className="flex-1 min-w-0 h-full flex flex-col overflow-hidden bg-[#070c18] relative studio-pane"
        >
          {/* Main Editor Surface */}
          <div className="flex-1 min-h-[140px] w-full flex flex-col overflow-hidden relative">
            {activeIdeFile && activeIdeFile.isOpen ? (
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
                  handleSendText(`Tolong analisa dan jelaskan arsitektur berkas @${n} (${p})`, agentMode);
                }}
              />
            ) : (
              /* Studio Welcome Empty State when no file is open (Clean Zen Minimal) */
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-3 bg-[#070c18] select-none text-slate-400 font-mono">
                <div className="w-10 h-10 rounded-xl bg-white/[0.03] border border-white/10 flex items-center justify-center text-slate-500 shadow-inner">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                  </svg>
                </div>
                <p className="text-xs text-slate-400 max-w-sm leading-relaxed">
                  Pilih berkas dari explorer di sebelah kiri untuk mulai membaca &amp; menyunting kode
                </p>
              </div>
            )}
          </div>

          {/* Integrated PowerShell Terminal Dock */}
          {isTerminalOpen && (
            <>
              {/* Resizer Splitter between Editor and Terminal (1px Horizontal Line) */}
              <div
                onMouseDown={startResizingTerminal}
                className="relative h-px w-full cursor-row-resize shrink-0 select-none bg-white/10 hover:bg-white/30 active:bg-white/50 transition-colors z-10"
                title="Tarik untuk mengubah tinggi terminal"
              >
                <div className="absolute inset-x-0 -top-1.5 h-3 cursor-row-resize bg-transparent" />
              </div>

              <div
                style={{ height: `${terminalHeight}px` }}
                className="w-full shrink-0 overflow-hidden bg-black/60"
              >
                <WorkbenchTerminal
                  logs={[
                    `[anara-agent] Mode aktif: ${agentMode.toUpperCase()}`,
                    `[system] Terminal worker ready (Workspace: ${workspaceTree?.workspace_name || "default"}).`,
                  ]}
                  activeTask={assistantStatus === "thinking" ? "Model AI Sedang Berpikir..." : undefined}
                  onExecuteCommand={() => {}}
                  onClose={() => setIsTerminalOpen(false)}
                />
              </div>
            </>
          )}
        </div>

        {/* Resizer Splitter 2: Center Editor ↔ Right Agent (1px Razor-Thin White Hairline) */}
        {isRightOpen && (
          <div
            onMouseDown={startResizingRight}
            className="relative w-px h-full cursor-col-resize shrink-0 select-none bg-white/10 hover:bg-white/30 active:bg-white/50 transition-colors z-20"
            title="Tarik untuk mengubah lebar panel AI Agent"
          >
            <div className="absolute inset-y-0 -left-1.5 w-3 cursor-col-resize bg-transparent" />
          </div>
        )}

        {/* ── PANE 3 (RIGHT): Anara Autonomous Agent Console & Prompt Command Dock ── */}
        {isRightOpen && (
          <div
            style={{ width: `var(--studio-right-width, ${rightWidth}px)`, transition: "none" }}
            className="h-full shrink-0 flex flex-col overflow-hidden bg-[#040813] relative select-none studio-pane"
          >
            {/* Agent Narrative & Tool Execution Timeline */}
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden relative">
              <ChatTimeline
                transcript={transcript}
                status={assistantStatus}
                activeSpeaker={activeSpeaker}
                activeModelId={activeModelId}
                liveToolProgress={liveToolProgress}
                footerDockHeight={0}
                activeThinkingText={activeThinkingText}
                onAnswerQuestion={handleAnswerQuestion}
                onOpenFile={(p: string) => handleOpenFileIDE(p, p.split("/").pop() || "file")}
                onSelectPrompt={(text: string) => setInputMessage(text)}
              />
            </div>

            {/* Dedicated Agent Command & Prompt Input Dock */}
            <BottomDock
              embedded={true}
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
              onFolderUpload={() => {}}
              onFileUpload={() => {}}
              liveToolProgress={liveToolProgress}
              activeQuestion={activeUnansweredQuestion}
              onAnswerQuestion={handleAnswerQuestion}
              onHeightChange={() => {}}
            />
          </div>
        )}
      </div>

      {/* ── Anara Brain Modal Drawer ── */}
      <AnaraBrain
        isOpen={isBrainDrawerOpen}
        onClose={() => {
          setIsBrainDrawerOpen(false);
          fetchModels(true);
        }}
        activeSpeaker={activeSpeaker}
      />
    </main>
  );
}
