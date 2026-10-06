"use client";

import React, { useState, useEffect, useRef, useCallback, Suspense, lazy } from "react";
import { useRouter } from "next/navigation";

import {
  BACKEND_URL,
  DEFAULT_SIDEBAR_WIDTH,
  MIN_SIDEBAR_WIDTH,
  MAX_SIDEBAR_WIDTH,
  ChatSession,
  WorkspaceFile,
  WorkspaceNode,
  WorkspaceTreeData,
  GitStatusData,
  ChatSessionSidebarProps,
  toDate,
  formatFullDateTime,
  formatSmartDateTime,
  resolveSessionDisplay,
  groupSessions,
} from "./types";

import { renderFileSvgIcon } from "./FileIcons";
import { anaraApi } from "@/lib/apiClient";
import WorkspaceTreeView, { nodeHasMatch, RecursiveTreeNode } from "./WorkspaceTreeView";
import SessionHistoryList from "./SessionHistoryList";
import SegmentedStudioTabs from "./SegmentedStudioTabs";
import type { AnaraCodeIDEProps, WorkbenchTerminalProps } from "../ide";

const AnaraCodeIDE = lazy(() => import("../ide/AnaraCodeIDE"));
const WorkbenchTerminal = lazy(() => import("../ide/WorkbenchTerminal"));

// Re-export all types and helper functions for 100% backward compatibility
export {
  DEFAULT_SIDEBAR_WIDTH,
  MIN_SIDEBAR_WIDTH,
  MAX_SIDEBAR_WIDTH,
  toDate,
  formatFullDateTime,
  formatSmartDateTime,
  resolveSessionDisplay,
  groupSessions,
  renderFileSvgIcon,
  nodeHasMatch,
  RecursiveTreeNode,
};
export type {
  ChatSession,
  WorkspaceFile,
  WorkspaceNode,
  WorkspaceTreeData,
  GitStatusData,
  ChatSessionSidebarProps,
};

export default function ChatSessionSidebar({
  isOpen,
  activeSessionId,
  activeSpeaker,
  isConnected = false,
  connectionStatus = "disconnected",
  onSelectSession,
  onNewSession,
  onOpenBrain,
  onOpenMessaging,
  onOpenScheduled,
  onOpenArtifacts,
  onOpenFileIDE,
  onOpenFolder,
  refreshKey = 0,
  sidebarWidth = DEFAULT_SIDEBAR_WIDTH,
  onWidthChange,
  activeIdeFile,
  ideTabs = [],
  onSelectIdeTab,
  onCloseIdeTab,
  onSaveIdeFile,
  onCloseIDE,
  isTerminalOpen = true,
  onToggleTerminal,
  onAskAnaraIDE,
  onSendText,
  agentMode = "plan",
  status,
  embedded = false,
  initialSidebarTab = "history",
  sessionType,
  onResetIDE,
}: ChatSessionSidebarProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [isResizing, setIsResizing] = useState(false);
  const [draggedSession, setDraggedSession] = useState<ChatSession | null>(null);
  const [dragOverTarget, setDragOverTarget] = useState<"pin" | "unpin" | null>(null);
  const [hoveredDropSessionId, setHoveredDropSessionId] = useState<number | null>(null);
  const [workspaceTree, setWorkspaceTree] = useState<WorkspaceTreeData | null>(null);
  const [activeSidebarTab, setActiveSidebarTab] = useState<"history" | "editor">(initialSidebarTab);
  const isSidebarHydratedRef = useRef(false);

  // Hydration-safe initial local storage loader
  useEffect(() => {
    try {
      const storageKey = sessionType === "code" ? "anara_code_sidebar_tab" : "anara_active_sidebar_tab";
      const saved = localStorage.getItem(storageKey);
      if (saved === "editor" || saved === "history") {
        setActiveSidebarTab(saved);
        document.cookie = `${storageKey}=${saved}; path=/; max-age=31536000; SameSite=Lax`;
      } else if (sessionType === "code") {
        setActiveSidebarTab("editor");
      }
    } catch {}
    isSidebarHydratedRef.current = true;
  }, [sessionType]);

  useEffect(() => {
    if (!isSidebarHydratedRef.current) return;
    try {
      const storageKey = sessionType === "code" ? "anara_code_sidebar_tab" : "anara_active_sidebar_tab";
      localStorage.setItem(storageKey, activeSidebarTab);
      document.cookie = `${storageKey}=${activeSidebarTab}; path=/; max-age=31536000; SameSite=Lax`;
    } catch {}
  }, [activeSidebarTab, sessionType]);

  const [gitStatus, setGitStatus] = useState<GitStatusData | null>(null);
  const [explorerFilter, setExplorerFilter] = useState("");
  const [explorerMode, setExplorerMode] = useState<"tree" | "git" | "sessions">("tree");

  const loadGitStatus = useCallback(async (sessionId?: number | null) => {
    if (!sessionId) {
      setGitStatus(null);
      return;
    }
    try {
      const res = await fetch(`${BACKEND_URL}/api/agent/git/status?session_id=${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setGitStatus(data);
      }
    } catch {
      setGitStatus(null);
    }
  }, []);

  const [terminalHeight, setTerminalHeight] = useState(200);
  const [isResizingTerminal, setIsResizingTerminal] = useState(false);
  const terminalStartYRef = useRef(0);
  const startTerminalHeightRef = useRef(terminalHeight);

  const startResizingTerminal = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      terminalStartYRef.current = e.clientY;
      startTerminalHeightRef.current = terminalHeight;
      setIsResizingTerminal(true);
    },
    [terminalHeight]
  );

  useEffect(() => {
    if (!isResizingTerminal) return;

    const handleMouseMove = (e: MouseEvent) => {
      const dy = e.clientY - terminalStartYRef.current;
      const newH = Math.max(100, Math.min(480, startTerminalHeightRef.current - dy));
      setTerminalHeight(newH);
    };

    const handleMouseUp = () => {
      setIsResizingTerminal(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizingTerminal]);

  // Resizable File Tree Splitter
  const [treeWidth, setTreeWidth] = useState<number>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("anara_tree_width");
        if (saved) {
          const parsed = parseInt(saved, 10);
          if (!isNaN(parsed) && parsed >= 140 && parsed <= 380) {
            return parsed;
          }
        }
      } catch {}
    }
    return 210;
  });
  const [isResizingTree, setIsResizingTree] = useState(false);
  const treeStartXRef = useRef(0);
  const startTreeWidthRef = useRef(treeWidth);

  const startResizingTree = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      treeStartXRef.current = e.clientX;
      startTreeWidthRef.current = treeWidth;
      setIsResizingTree(true);
    },
    [treeWidth]
  );

  useEffect(() => {
    if (!isResizingTree) return;

    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - treeStartXRef.current;
      const maxAllowed = Math.min(600, Math.max(140, (sidebarWidth || 950) - 260));
      const newW = Math.max(140, Math.min(maxAllowed, startTreeWidthRef.current + dx));
      setTreeWidth(newW);
      document.documentElement.style.setProperty("--tree-width", `${newW}px`);
    };

    const handleMouseUp = () => {
      setIsResizingTree(false);
      try {
        const finalW = parseInt(document.documentElement.style.getPropertyValue("--tree-width")) || treeWidth;
        localStorage.setItem("anara_tree_width", finalW.toString());
        document.cookie = `anara_tree_width=${finalW}; path=/; max-age=31536000; SameSite=Lax`;
      } catch {}
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizingTree, sidebarWidth]);

  const handlePickLocalFolder = useCallback(async (targetPath?: string) => {
    if (onOpenFolder && !targetPath) {
      onOpenFolder();
      return;
    }
    try {
      const res = await fetch(`${BACKEND_URL}/api/agent/pick-local-folder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: activeSessionId || undefined, folder_path: targetPath || "" }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success" && data.tree) {
          onResetIDE?.();
          setWorkspaceTree(data.tree);
          setActiveSidebarTab("editor");
          if (typeof window !== "undefined") {
            const currentKey = data.tree.root_path || data.tree.workspace_name || "";
            localStorage.setItem("anara_ide_workspace_key", currentKey);
            window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "workspace_updated" } }));
          }
        }
      }
    } catch (err) {
      console.warn("[Workspace] pick local folder error:", err);
    }
  }, [activeSessionId, onOpenFolder, onResetIDE]);

  const loadWorkspaceTree = useCallback(async (sessionId?: number | null) => {
    try {
      const data = await anaraApi.workspace.getTree(sessionId || undefined);
      if (data && (data.total_files > 0 || data.is_custom_folder || (data.entries && data.entries.length > 0))) {
          const currentKey = data.root_path || data.workspace_name;
          const savedKey = typeof window !== "undefined" ? localStorage.getItem("anara_ide_workspace_key") : null;
          if (savedKey && currentKey && savedKey !== currentKey) {
            onResetIDE?.();
          }
          if (currentKey && typeof window !== "undefined") {
            localStorage.setItem("anara_ide_workspace_key", currentKey);
          }
          setWorkspaceTree(data);
          return;
      }
      setWorkspaceTree(null);
    } catch (e) {
      console.warn("[Workspace] load tree error:", e);
      setWorkspaceTree(null);
    }
  }, [onResetIDE]);

  const [showClearWorkspaceConfirm, setShowClearWorkspaceConfirm] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<ChatSession | null>(null);

  const handleClearWorkspace = () => {
    setShowClearWorkspaceConfirm(true);
  };

  const confirmClearWorkspace = async () => {
    setShowClearWorkspaceConfirm(false);
    try {
      const q = activeSessionId ? `?session_id=${activeSessionId}` : "";
      await fetch(`${BACKEND_URL}/api/agent/workspace${q}`, { method: "DELETE" });
      setWorkspaceTree(null);
      onResetIDE?.();
      if (typeof window !== "undefined") {
        localStorage.removeItem("anara_ide_workspace_key");
        window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "workspace_updated" } }));
      }
    } catch (e) {
      console.warn("[Workspace] clear error:", e);
    }
  };

  const startXRef = useRef(0);
  const startWidthRef = useRef(sidebarWidth);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      // Universal session list: fetch all conversations across Chat & Code Studio (Anara Parity)
      const res = await fetch(`${BACKEND_URL}/api/chat/sessions`);
      if (res.ok) {
        const all: ChatSession[] = await res.json();
        // Session Pattern: hide sessions with 0 messages (created lazily but never used)
        const active = all.filter((s) => s.message_count > 0);
        setSessions(active);
      }
    } catch (err) {
      console.warn("[Sessions] load failed:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadSessions();
      loadWorkspaceTree(activeSessionId);
      loadGitStatus(activeSessionId);
    }
  }, [isOpen, refreshKey, activeSessionId, loadSessions, loadWorkspaceTree, loadGitStatus]);

  // Real-time SQLite & Workspace Mutation Listener
  const brainSyncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const handleBrainSync = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (!detail) return;
      const { event } = detail;
      if (
        event === "session_created" ||
        event === "session_updated" ||
        event === "session_deleted" ||
        event === "session_workspace_updated" ||
        event === "conversation_logged" ||
        event === "conversation_deleted" ||
        event === "batch"
      ) {
        if (brainSyncTimerRef.current) clearTimeout(brainSyncTimerRef.current);
        brainSyncTimerRef.current = setTimeout(() => {
          loadSessions();
          brainSyncTimerRef.current = null;
        }, event === "conversation_logged" ? 1000 : 300);
      }
      if (
        event === "workspace_updated" ||
        event === "workspace_folder_imported" ||
        event === "workspace_file_uploaded" ||
        event === "session_workspace_updated"
      ) {
        loadWorkspaceTree(activeSessionId);
      }
    };

    window.addEventListener("anara-brain-sync", handleBrainSync);
    return () => {
      window.removeEventListener("anara-brain-sync", handleBrainSync);
      if (brainSyncTimerRef.current) clearTimeout(brainSyncTimerRef.current);
    };
  }, [activeSessionId, loadSessions, loadWorkspaceTree]);

  const latestWidthRef = useRef<number>(sidebarWidth || DEFAULT_SIDEBAR_WIDTH);

  // Drag to resize sidebar width with ultra-smooth 60fps CSS variable updates
  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    startXRef.current = e.clientX;
    const computed = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--sidebar-width"), 10);
    const minW = sessionType === "code" ? 480 : MIN_SIDEBAR_WIDTH;
    const defaultW = sessionType === "code" ? 950 : DEFAULT_SIDEBAR_WIDTH;
    const initialW = sidebarWidth || (!isNaN(computed) && computed >= minW ? computed : defaultW);
    startWidthRef.current = initialW;
    latestWidthRef.current = initialW;
  }, [sidebarWidth, sessionType]);

  useEffect(() => {
    if (!isResizing) return;

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const handleMouseMove = (e: MouseEvent) => {
      const delta = e.clientX - startXRef.current;
      const minW = sessionType === "code" ? 480 : MIN_SIDEBAR_WIDTH;
      const maxW = sessionType === "code" ? Math.max(1200, window.innerWidth - 360) : MAX_SIDEBAR_WIDTH;
      const newWidth = Math.min(maxW, Math.max(minW, startWidthRef.current + delta));
      latestWidthRef.current = newWidth;
      document.documentElement.style.setProperty("--sidebar-width", `${newWidth}px`);
    };

    const handleMouseUp = () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      const finalW = latestWidthRef.current;
      onWidthChange?.(finalW);
      setIsResizing(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing, onWidthChange, sessionType]);

  const patchSession = async (id: number, body: Record<string, unknown>) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/sessions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) loadSessions();
    } catch (err) {
      console.warn("[Sessions] patch failed:", err);
    }
  };

  const handleDropPin = useCallback((sessionId: number) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, is_pinned: 1 } : s))
    );
    setDragOverTarget(null);
    setHoveredDropSessionId(null);
    setDraggedSession(null);
    patchSession(sessionId, { is_pinned: 1 });
  }, []);

  const handleDropUnpin = useCallback((sessionId: number) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, is_pinned: 0 } : s))
    );
    setDragOverTarget(null);
    setHoveredDropSessionId(null);
    setDraggedSession(null);
    patchSession(sessionId, { is_pinned: 0 });
  }, []);

  const deleteSession = async (s: ChatSession) => {
    setSessionToDelete(s);
  };

  const confirmDeleteSession = async (s: ChatSession) => {
    setSessionToDelete(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/sessions/${s.id}`, { method: "DELETE" });
      if (res.ok) {
        setSessions((prev) => prev.filter((x) => x.id !== s.id));
        if (activeSessionId === s.id) {
          setActiveSidebarTab("history");
          onNewSession();
        }
      }
    } catch (err) {
      console.warn("[Sessions] delete failed:", err);
    }
  };

  const forkSession = async (s: ChatSession) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/sessions/${s.id}/fork`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.session && data.session.id) {
          await loadSessions();
          onSelectSession(data.session.id);
        }
      }
    } catch (err) {
      console.warn("[Sessions] fork failed:", err);
    }
  };

  return (
    <aside
      className={`${
        embedded
          ? "relative w-full"
          : `fixed top-0 left-0 z-40 transition-transform duration-200 ease-out ${
              isOpen ? "translate-x-0" : "-translate-x-full pointer-events-none"
            }`
      } h-full flex flex-col pointer-events-auto select-none group/sidebar`}
      style={{
        ...(!embedded ? { width: "var(--sidebar-width, 260px)" } : {}),
        background: embedded ? "#050811" : "rgba(6,9,19,0.85)",
        backdropFilter: embedded ? "none" : "blur(28px) saturate(140%)",
        WebkitBackdropFilter: embedded ? "none" : "blur(28px) saturate(140%)",
        borderRight: "1px solid rgba(255,255,255,0.08)",
        boxShadow: embedded ? "none" : "6px 0 40px rgba(0,0,0,0.55)",
      }}
    >
      {/* ── Non-Blocking In-App Confirm Dialogs ── */}
      {sessionToDelete && (
        <div className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-[240px] p-3.5 rounded-2xl bg-slate-900 border border-white/15 shadow-2xl text-center space-y-3 font-sans">
            <p className="text-xs font-semibold text-white">Delete conversation?</p>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              &ldquo;{sessionToDelete.title || `Conversation #${sessionToDelete.id}`}&rdquo; and its messages will be permanently deleted.
            </p>
            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={() => setSessionToDelete(null)}
                className="flex-1 py-1.5 rounded-xl bg-white/10 hover:bg-white/15 text-xs text-slate-300 font-medium transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => confirmDeleteSession(sessionToDelete)}
                className="flex-1 py-1.5 rounded-xl bg-rose-500 hover:bg-rose-600 text-xs text-white font-medium shadow-md shadow-rose-500/30 transition-colors cursor-pointer"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {showClearWorkspaceConfirm && (
        <div className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-[240px] p-3.5 rounded-2xl bg-slate-900 border border-white/15 shadow-2xl text-center space-y-3 font-sans">
            <p className="text-xs font-semibold text-white">Close folder?</p>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              Remove &ldquo;{workspaceTree?.workspace_name || "workspace"}&rdquo; from this chat history?
            </p>
            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={() => setShowClearWorkspaceConfirm(false)}
                className="flex-1 py-1.5 rounded-xl bg-white/10 hover:bg-white/15 text-xs text-slate-300 font-medium transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmClearWorkspace}
                className="flex-1 py-1.5 rounded-xl bg-rose-500 hover:bg-rose-600 text-xs text-white font-medium shadow-md shadow-rose-500/30 transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      {/* ── Top Header: Sidebar Tabs [SESSIONS | CODE | BOTS] ── */}
      <div className="h-[38px] px-2.5 bg-[#060913] border-b border-white/[0.08] flex items-center justify-between shrink-0 select-none font-mono">
        <SegmentedStudioTabs
          activeTab="sessions"
          activeSessionId={activeSessionId}
          onOpenBrain={onOpenBrain}
          onSelectSessions={() => setActiveSidebarTab("history")}
        />

        {/* Gateway Online Status Pill */}
        <div className="flex items-center gap-1.5 shrink-0 pl-2">
          <span
            className={`w-2 h-2 rounded-full transition-all duration-300 ${
              isConnected
                ? "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                : connectionStatus === "connecting"
                ? "bg-amber-400 animate-pulse shadow-[0_0_8px_#fbbf24]"
                : "bg-rose-500 shadow-[0_0_8px_#f43f5e]"
            }`}
            title={isConnected ? "Gateway Online" : connectionStatus === "connecting" ? "Connecting..." : "Disconnected"}
          />
        </div>
      </div>

      {/* ── TAB 1: Chat Sessions ── */}
      {activeSidebarTab === "history" && (
        <SessionHistoryList
          sessions={sessions}
          loading={loading}
          activeSessionId={activeSessionId}
          search={search}
          setSearch={setSearch}
          sessionType={sessionType}
          onSelectSession={(id) => {
            // Eager-clear stale workspace before switching (Anara Parity)
            setWorkspaceTree(null);
            onSelectSession(id);
            if (sessionType === "code") {
              setActiveSidebarTab("editor");
            }
          }}
          onNewSession={() => {
            setWorkspaceTree(null);
            onNewSession();
            if (sessionType === "code") {
              setActiveSidebarTab("editor");
            }
          }}
          onOpenBrain={onOpenBrain}
          onOpenMessaging={onOpenMessaging}
          onOpenScheduled={onOpenScheduled}
          onOpenArtifacts={onOpenArtifacts}
          onOpenCode={() => {
            setActiveSidebarTab("editor");
          }}
          onPatchSession={patchSession}
          onDeleteSession={deleteSession}
          onForkSession={forkSession}
          onDropPin={handleDropPin}
          onDropUnpin={handleDropUnpin}
          draggedSession={draggedSession}
          setDraggedSession={setDraggedSession}
          dragOverTarget={dragOverTarget}
          setDragOverTarget={setDragOverTarget}
          hoveredDropSessionId={hoveredDropSessionId}
          setHoveredDropSessionId={setHoveredDropSessionId}
        />
      )}

      {/* ── TAB 2: VS Code Dual-Column Workbench (Tree + Editor + Terminal) ── */}
      {activeSidebarTab === "editor" && (
        <div className={`flex-1 min-h-0 flex flex-col ${embedded ? "m-0" : "m-1.5"} overflow-hidden`}>
          {workspaceTree && (workspaceTree.total_files > 0 || workspaceTree.is_custom_folder || (workspaceTree.entries && workspaceTree.entries.length > 0)) ? (
            <div className={`flex-1 min-h-0 flex flex-row w-full h-full overflow-hidden ${embedded ? "rounded-none border-0 shadow-none" : "rounded-xl border border-white/10 shadow-2xl"} bg-[#070c18]`}>
              <WorkspaceTreeView
                workspaceTree={workspaceTree}
                gitStatus={gitStatus}
                explorerMode={explorerMode}
                setExplorerMode={setExplorerMode}
                explorerFilter={explorerFilter}
                setExplorerFilter={setExplorerFilter}
                activeFilePath={activeIdeFile?.filePath}
                onOpenFileIDE={onOpenFileIDE}
                handlePickLocalFolder={handlePickLocalFolder}
                handleClearWorkspace={handleClearWorkspace}
                startResizingTree={startResizingTree}
              />

              {/* ── RIGHT COLUMN: Code Editor & Terminal Dock (Flex-1) ── */}
              <div className="flex-1 min-w-0 h-full flex flex-col overflow-hidden bg-slate-950/80">
                <div className="flex-1 min-h-[140px] w-full overflow-hidden flex flex-col">
                  {activeIdeFile && activeIdeFile.isOpen ? (
                    <Suspense fallback={null}>
                      <AnaraCodeIDE
                        isOpen={true}
                        embedded={true}
                        onClose={onCloseIDE ?? (() => {})}
                        fileName={activeIdeFile.fileName}
                        filePath={activeIdeFile.filePath}
                        fileExt={activeIdeFile.fileExt}
                        fileSizeKb={activeIdeFile.fileSizeKb}
                        content={activeIdeFile.content}
                        originalContent={activeIdeFile.originalContent}
                        isTerminalOpen={isTerminalOpen}
                        onToggleTerminal={() => onToggleTerminal?.(!isTerminalOpen)}
                        tabs={ideTabs}
                        onSelectTab={onSelectIdeTab}
                        onCloseTab={onCloseIdeTab}
                        onSaveFile={onSaveIdeFile}
                        onAskAnara={(p: string, n: string) => {
                          if (onAskAnaraIDE) {
                            onAskAnaraIDE(p, n);
                          } else if (onSendText) {
                            onSendText(`Please analyze file @${n} (${p})`, agentMode);
                          }
                        }}
                      />
                    </Suspense>
                  ) : (
                    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center text-slate-500">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                        </svg>
                      </div>
                      <p className="text-xs text-slate-400 font-mono">
                        Select a file from the tree on the left to view &amp; edit code
                      </p>
                    </div>
                  )}
                </div>

                {isTerminalOpen && (
                  <>
                    <div
                      onMouseDown={startResizingTerminal}
                      className="h-1.5 w-full cursor-row-resize shrink-0 select-none bg-transparent border-y border-white/10 hover:border-white/30 hover:bg-white/[0.04] transition-colors"
                      title="Drag to resize terminal height"
                    />

                    <div
                      style={{ height: terminalHeight }}
                      className="w-full shrink-0 overflow-hidden transition-[height] duration-75"
                    >
                      <Suspense fallback={null}>
                        <WorkbenchTerminal
                          logs={[
                            `[anara-agent] Active mode: ${agentMode.toUpperCase()}`,
                            `[system] Terminal worker ready (Files: ${activeIdeFile?.filePath || "workspace"}).`,
                          ]}
                          activeTask={status === "thinking" ? "AI Model Thinking..." : undefined}
                          onExecuteCommand={() => {}}
                          onClose={() => onToggleTerminal?.(false)}
                          cwd={workspaceTree?.root_path || undefined}
                        />
                      </Suspense>
                    </div>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="flex-1 min-h-0 flex flex-col items-center justify-center p-4 sm:p-6 overflow-y-auto custom-scrollbar select-none font-sans">
              <div className="w-full max-w-sm p-6 rounded-2xl bg-[#070c18] border border-white/10 shadow-2xl flex flex-col items-center text-center relative overflow-hidden">
                {/* Top Specular Sheen Highlight */}
                <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none" />

                {/* Hero Node Icon */}
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-cyan-950/60 to-indigo-950/60 border border-cyan-400/30 flex items-center justify-center text-cyan-300 shadow-[0_0_24px_rgba(34,211,238,0.2)] mb-3">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                </div>

                {/* Micro-Badge */}
                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-400/20 text-cyan-300 text-[10px] font-mono font-semibold tracking-wider uppercase mb-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#22d3ee]" />
                  <span>Workspace Developer</span>
                </div>

                {/* Heading & Description */}
                <h4 className="text-base font-semibold text-white tracking-tight leading-snug">
                  Connect Project Directory
                </h4>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed max-w-xs font-sans">
                  Open a local folder on your computer to let Anara browse files, edit code precisely, and run terminal shell.
                </p>

                {/* Primary Action Button */}
                <button
                  type="button"
                  onClick={() => handlePickLocalFolder()}
                  className="mt-4 flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500/25 to-indigo-500/25 hover:from-cyan-500/40 hover:to-indigo-500/40 border border-cyan-400/40 text-cyan-100 hover:text-white text-xs font-semibold font-mono transition-all active:scale-95 cursor-pointer shadow-[0_0_18px_rgba(34,211,238,0.25)]"
                >
                  <svg className="w-4 h-4 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                   <span>Open Project Folder</span>
                </button>

                {/* Capabilities Matrix */}
                <div className="w-full mt-5 pt-4 border-t border-white/10 space-y-2 text-left">
                  <span className="text-[9.5px] font-mono font-bold tracking-widest text-slate-500 uppercase px-0.5">
                    Workbench Capabilities:
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2.5 rounded-xl bg-white/[0.025] border border-white/[0.08] space-y-1">
                      <div className="flex items-center gap-1.5 text-cyan-300 font-mono text-[10.5px] font-semibold">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
                        </svg>
                        <span>Tree &amp; Git</span>
                      </div>
                      <p className="text-[10px] text-slate-400 leading-normal">
                        Branch status and file diff
                      </p>
                    </div>

                    <div className="p-2.5 rounded-xl bg-white/[0.025] border border-white/[0.08] space-y-1">
                      <div className="flex items-center gap-1.5 text-indigo-300 font-mono text-[10.5px] font-semibold">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                        </svg>
                        <span>CodeMirror 6</span>
                      </div>
                      <p className="text-[10px] text-slate-400 leading-normal">
                        Syntax tabs &amp; in-place patch
                      </p>
                    </div>
                  </div>

                  <div className="p-2.5 rounded-xl bg-white/[0.025] border border-white/[0.08] space-y-1">
                    <div className="flex items-center gap-1.5 text-emerald-300 font-mono text-[10.5px] font-semibold">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span>Integrated Terminal Shell</span>
                    </div>
                    <p className="text-[10px] text-slate-400 leading-normal">
                      Execute build, testing, linting, and automated scripts
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Sidebar Footer Rail (Anara Desktop Standard) ── */}
      <div className="h-[36px] px-3 bg-[#080B11] border-t border-white/[0.08] flex items-center justify-between shrink-0 select-none text-slate-400">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onNewSession}
            className="hover:text-white transition-colors cursor-pointer"
            title="Home Workspace"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </button>
          <button
            type="button"
            onClick={onNewSession}
            className="hover:text-white transition-colors cursor-pointer"
            title="Create New Project"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
          <button
            type="button"
            className="hover:text-white transition-colors cursor-pointer"
            title="Sync Status: Up to date"
          >
            <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenBrain}
            className="hover:text-cyan-300 transition-colors cursor-pointer"
            title="Providers & Gateway"
          >
            <svg className="w-3.5 h-3.5 text-slate-400 hover:text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </button>
        </div>
      </div>

      {/* ── Resizable Drag Handle on Right Border with Full Selection Shield ── */}
      {isOpen && (
        <>
          {isResizing && (
            <div className="fixed inset-0 z-[99999] cursor-col-resize select-none bg-transparent" />
          )}
          <div
            onMouseDown={startResizing}
            className="absolute top-0 -right-1.5 w-3 h-full cursor-col-resize z-50 select-none bg-transparent hover:bg-transparent active:bg-transparent"
            title="Drag to resize panel width"
          />
        </>
      )}
    </aside>
  );
}
