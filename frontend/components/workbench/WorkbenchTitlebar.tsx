"use client";

import React from "react";
import type { GitStatusData } from "../sidebar/types";

export interface OpenSessionTab {
  id: number;
  title: string;
}

export interface WorkbenchTitlebarProps {
  sessionTitle?: string;
  openSessionTabs?: OpenSessionTab[];
  onSelectSessionTab?: (id: number) => void;
  onCloseSessionTab?: (id: number) => void;
  activeIdeFile?: {
    isOpen: boolean;
    fileName: string;
    filePath: string;
  } | null;
  transcript: any[];
  activeSessionId: number | null;
  handleNewSession: () => void;
  setIsBrainDrawerOpen: (v: boolean) => void;
  isContextPaneOpen: boolean;
  setIsContextPaneOpen: React.Dispatch<React.SetStateAction<boolean>>;
  contextTab: "preview" | "editor" | "terminal" | "review";
  setContextTab: (tab: "preview" | "editor" | "terminal" | "review") => void;
  fetchGitStatus: () => void;
  gitStatus: GitStatusData | null;
  setIsTerminalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  previewTitle?: string;
  onClosePreview?: () => void;
  onCloseEditor?: () => void;
}

/**
 * WorkbenchTitlebar — Unified 38px titlebar band for dual-pane companion workbench.
 * Houses active session badge, quick actions, context pane toggle, git status, and window glyphs.
 */
export function WorkbenchTitlebar({
  sessionTitle,
  openSessionTabs,
  onSelectSessionTab,
  onCloseSessionTab,
  activeIdeFile,
  transcript,
  activeSessionId,
  handleNewSession,
  setIsBrainDrawerOpen,
  isContextPaneOpen,
  setIsContextPaneOpen,
  contextTab,
  setContextTab,
  fetchGitStatus,
  gitStatus,
  setIsTerminalOpen,
  previewTitle,
  onClosePreview,
  onCloseEditor,
}: WorkbenchTitlebarProps) {
  // Resolve effective chat tab label (Anara Standard: Clean Title/Sentence Case)
  const chatTabLabel = React.useMemo(() => {
    if (sessionTitle && sessionTitle.trim()) {
      const clean = sessionTitle.trim();
      const lower = clean.toLowerCase();
      if (lower === "new chat" || lower === "new session" || lower === "untitled session" || lower === "untitled") {
        return "New Session";
      }
      return clean.length > 30 ? clean.slice(0, 28) + "…" : clean;
    }
    const firstUserMsg = transcript.find((t) => t.speaker === "input" && t.text);
    if (firstUserMsg?.text) {
      const line = firstUserMsg.text.split("\n")[0].trim();
      return line.length > 30 ? line.slice(0, 28) + "…" : line;
    }
    return "New Session";
  }, [sessionTitle, transcript, activeSessionId]);

  // Resolve list of session tabs (Anara Standard: Multi-Session Open Tabs)
  const effectiveSessionTabs = React.useMemo(() => {
    if (openSessionTabs && openSessionTabs.length > 0) {
      return openSessionTabs;
    }
    return [
      {
        id: activeSessionId || 0,
        title: chatTabLabel,
      },
    ];
  }, [openSessionTabs, activeSessionId, chatTabLabel]);

  const isChatActive = !isContextPaneOpen;
  const isPreviewOpen = Boolean(previewTitle);
  const isEditorOpen = Boolean(activeIdeFile && activeIdeFile.isOpen);
  const isReviewOpen = Boolean(gitStatus && gitStatus.changed_count > 0);

  return (
    <div className="h-[38px] shrink-0 px-2 bg-[#080B11] border-b border-white/[0.08] flex items-center justify-between text-xs font-mono select-none z-10 overflow-hidden">
      {/* ── LEFT: MULTI-DOCUMENT TAB BAR (Anara Desktop Standard) ── */}
      <div className="flex items-center gap-1 min-w-0 max-w-[calc(100%-180px)] overflow-x-auto custom-scrollbar">
        {/* Multi-Session Tabs (Anara Standard: 2+ Sessions Side-by-Side) */}
        {effectiveSessionTabs.map((tab) => {
          const isActive = isChatActive && activeSessionId === tab.id;
          let rawClean = (tab.title || "New Session").replace(/\s*\[.*?:.*?\]/g, "").replace(/\s*\[.*?\]/g, "").trim();
          const channelPrefixMatch = rawClean.match(/^(?:Telegram|Whatsapp|Cli)\s*Chat\s*\((.*?)\)$/i);
          if (channelPrefixMatch) {
            rawClean = "NEW SESSION";
          }
          const lower = rawClean.toLowerCase();
          const displayTitle =
            lower === "new chat" || lower === "new session" || lower === "untitled session" || lower === "untitled"
              ? "New Session"
              : rawClean.length > 28 ? rawClean.slice(0, 26) + "…" : rawClean;

          return (
            <div
              key={tab.id}
              onClick={() => {
                if (isContextPaneOpen) {
                  setIsContextPaneOpen(false);
                }
                if (activeSessionId !== tab.id) {
                  onSelectSessionTab?.(tab.id);
                }
              }}
              className={`group/tab relative flex items-center gap-2 h-7 px-2.5 rounded-lg text-xs font-sans font-medium transition-all shrink-0 cursor-pointer select-none ${
                isActive
                  ? "bg-white/[0.05] border border-white/[0.1] text-white shadow-sm backdrop-blur-md"
                  : "bg-transparent border border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]"
              }`}
              title={rawClean}
              suppressHydrationWarning
            >
              <span
                className={`w-1.5 h-1.5 rounded-full shrink-0 transition-all ${
                  isActive
                    ? "bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.6)]"
                    : "bg-slate-600 group-hover/tab:bg-slate-400"
                }`}
              />
              <span className="truncate max-w-[180px] tracking-tight" suppressHydrationWarning>{displayTitle}</span>

              {/* Close Tab Affordance (✕) */}
              {effectiveSessionTabs.length > 1 && onCloseSessionTab && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onCloseSessionTab(tab.id);
                  }}
                  className="opacity-0 group-hover/tab:opacity-100 p-0.5 -mr-0.5 rounded text-slate-500 hover:text-white hover:bg-white/10 transition-all cursor-pointer"
                  title="Close tab"
                >
                  ✕
                </button>
              )}
            </div>
          );
        })}

        {/* Plus Tab Affordance (+ New Session) — sits right beside session tabs (Anara Standard) */}
        <button
          type="button"
          onClick={handleNewSession}
          className="h-7 w-7 rounded-lg bg-transparent border border-white/[0.06] hover:border-white/10 hover:bg-white/[0.04] text-slate-400 hover:text-white flex items-center justify-center transition-all cursor-pointer shrink-0"
          title="New session (Ctrl+N)"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>

        {/* Secondary Context Tabs: Live Preview, Git Review, Code Editor */}
        {(isPreviewOpen || isReviewOpen || isEditorOpen) && (
          <div className="h-4 w-[1px] bg-white/[0.08] mx-1 shrink-0" />
        )}

        {/* Tab: Live HTML / Browser Preview Tab (If active/open) */}
        {isPreviewOpen && (
          <div
            onClick={() => {
              setIsContextPaneOpen(true);
              setContextTab("preview");
            }}
            className={`flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-xs font-sans font-medium transition-all shrink-0 cursor-pointer group/tab ${
              isContextPaneOpen && contextTab === "preview"
                ? "bg-white/[0.05] border border-cyan-400/25 text-cyan-300 shadow-sm backdrop-blur-md"
                : "bg-transparent border border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]"
            }`}
            title={`Preview: ${previewTitle}`}
          >
            <span className="text-[11px] shrink-0">🌐</span>
            <span className="truncate max-w-[160px] tracking-tight">{previewTitle}</span>
            {onClosePreview && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onClosePreview();
                }}
                className="p-0.5 rounded text-slate-500 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                title="Close preview"
              >
                ✕
              </button>
            )}
          </div>
        )}

        {/* Tab: Git Review Tab (If opened or uncommitted files exist) */}
        {(isReviewOpen || (isContextPaneOpen && contextTab === "review")) && (
          <div
            onClick={() => {
              setIsContextPaneOpen(true);
              setContextTab("review");
              fetchGitStatus();
            }}
            className={`flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-xs font-sans font-medium transition-all shrink-0 cursor-pointer ${
              isContextPaneOpen && contextTab === "review"
                ? "bg-white/[0.05] border border-cyan-400/25 text-cyan-300 shadow-sm backdrop-blur-md"
                : "bg-transparent border border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]"
            }`}
            title="Review uncommitted changes"
          >
            <span className="text-[11px] shrink-0">🌿</span>
            <span className="tracking-tight">Review</span>
            {gitStatus && gitStatus.changed_count > 0 && (
              <span className="px-1 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 text-[9.5px] font-mono">
                +{gitStatus.changed_count}
              </span>
            )}
          </div>
        )}

        {/* Tab: Code Editor Tab (If file is open) */}
        {isEditorOpen && activeIdeFile && (
          <div
            onClick={() => {
              setIsContextPaneOpen(true);
              setContextTab("editor");
            }}
            className={`flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-xs font-sans font-medium transition-all shrink-0 cursor-pointer group/tab ${
              isContextPaneOpen && contextTab === "editor"
                ? "bg-white/[0.05] border border-cyan-400/25 text-cyan-300 shadow-sm backdrop-blur-md"
                : "bg-transparent border border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]"
            }`}
            title={activeIdeFile.filePath}
          >
            <span className="text-[11px] shrink-0">📄</span>
            <span className="truncate max-w-[140px]">{activeIdeFile.fileName}</span>
            {onCloseEditor && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onCloseEditor();
                }}
                className="p-0.5 rounded text-slate-500 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                title="Close editor tab"
              >
                ✕
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── RIGHT: TOOLS & PANE CONTROLS CLUSTER ── */}
      <div className="flex items-center gap-1 text-slate-400 shrink-0">
        {/* Browser / Preview Pane Trigger */}
        <button
          type="button"
          onClick={() => {
            setIsContextPaneOpen(true);
            setContextTab("preview");
          }}
          className={`p-1.5 rounded-md transition-colors cursor-pointer flex items-center gap-1 ${
            isContextPaneOpen && contextTab === "preview"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-400/30"
              : "hover:bg-white/10 hover:text-white"
          }`}
          title="Toggle Browser / Preview Pane"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
          </svg>
        </button>

        {/* Git Review Pane Trigger */}
        <button
          type="button"
          onClick={() => {
            setIsContextPaneOpen(true);
            setContextTab("review");
            fetchGitStatus();
          }}
          className={`p-1.5 rounded-md transition-colors cursor-pointer flex items-center gap-1 ${
            isContextPaneOpen && contextTab === "review"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-400/30"
              : "hover:bg-white/10 hover:text-white"
          }`}
          title="Toggle Git Review Diff Panel"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7a3 3 0 100-6 3 3 0 000 6zm0 0v10m0 0a3 3 0 100 6 3 3 0 000-6zm8-4a3 3 0 100-6 3 3 0 000 6zm0 0v3a4 4 0 01-4 4h-4" />
          </svg>
          {gitStatus && gitStatus.changed_count > 0 && (
            <span className="text-[10px] font-mono font-bold text-cyan-300">
              {gitStatus.changed_count}
            </span>
          )}
        </button>

        {/* Terminal Trigger */}
        <button
          type="button"
          onClick={() => {
            setIsContextPaneOpen(true);
            setContextTab("terminal");
            setIsTerminalOpen(true);
          }}
          className={`p-1.5 rounded-md transition-colors cursor-pointer ${
            isContextPaneOpen && contextTab === "terminal"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-400/30"
              : "hover:bg-white/10 hover:text-white"
          }`}
          title="Toggle Terminal Panel"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </button>

        {/* Split Context Pane Toggle */}
        <button
          type="button"
          onClick={() => setIsContextPaneOpen((v) => !v)}
          className={`p-1.5 rounded-md transition-colors cursor-pointer ${
            isContextPaneOpen
              ? "bg-white/[0.1] text-white"
              : "hover:bg-white/10 hover:text-white text-slate-400"
          }`}
          title="Toggle Split View Pane (Ctrl+\)"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
          </svg>
        </button>

        {/* Settings & Brain */}
        <button
          type="button"
          onClick={() => setIsBrainDrawerOpen(true)}
          className="p-1.5 rounded-md hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
          title="Settings & Brain"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
