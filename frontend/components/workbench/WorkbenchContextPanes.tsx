"use client";

import React from "react";
import dynamic from "next/dynamic";
import type { AnaraCodeIDEProps } from "../ide/AnaraCodeIDE";
import type { GitStatusData } from "../sidebar/types";

const AnaraCodeIDE = dynamic<AnaraCodeIDEProps>(() => import("../ide/AnaraCodeIDE"), {
  ssr: false,
});

const WorkbenchTerminal = dynamic(() => import("../ide/WorkbenchTerminal"), {
  ssr: false,
});

const ReviewGitPane = dynamic(() => import("../sidebar/ReviewGitPane"), {
  ssr: false,
});

export interface WorkbenchContextPanesProps {
  isContextPaneOpen: boolean;
  setIsContextPaneOpen: React.Dispatch<React.SetStateAction<boolean>>;
  contextPaneRef: React.RefObject<HTMLDivElement | null>;
  contextPaneWidth: number;
  contextTab: "editor" | "terminal" | "review";
  setContextTab: (tab: "editor" | "terminal" | "review") => void;
  activeIdeFile: {
    isOpen: boolean;
    fileName: string;
    filePath: string;
    fileExt: string;
    fileSizeKb: number;
    content: string;
    originalContent?: string;
  };
  setActiveIdeFile: React.Dispatch<React.SetStateAction<any>>;
  gitStatus: GitStatusData | null;
  fetchGitStatus: () => Promise<void> | void;
  isTerminalOpen: boolean;
  setIsTerminalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  ideTabs?: any[];
  handleSelectIdeTab: (filePath: string, fileName: string) => void;
  handleCloseIdeTab: (filePath: string) => void;
  handleSaveIdeFile: (filePath: string, newContent: string) => Promise<boolean>;
  handleToggleTerminal: () => void;
  onSendText?: (text: string, mode?: "plan" | "build") => void;
  activeSessionId: number | null;
  handleOpenFileIDE: (filePath: string, fileName: string) => void;
}

/**
 * WorkbenchContextPanes — Docked multi-tenant context pane for the dual-pane workbench.
 * Houses Keep-Alive tab zones for CodeMirror IDE Editor, Git Review diff view, and PTY Terminal.
 */
export function WorkbenchContextPanes({
  isContextPaneOpen,
  setIsContextPaneOpen,
  contextPaneRef,
  contextPaneWidth,
  contextTab,
  setContextTab,
  activeIdeFile,
  setActiveIdeFile,
  gitStatus,
  fetchGitStatus,
  isTerminalOpen,
  setIsTerminalOpen,
  ideTabs,
  handleSelectIdeTab,
  handleCloseIdeTab,
  handleSaveIdeFile,
  handleToggleTerminal,
  onSendText,
  activeSessionId,
  handleOpenFileIDE,
}: WorkbenchContextPanesProps) {
  if (!isContextPaneOpen) return null;

  return (
    <div
      ref={contextPaneRef as any}
      style={{ width: `${contextPaneWidth}px` }}
      className="flex flex-col min-w-[320px] h-full bg-[#060913]/95 backdrop-blur-xl border-l border-white/[0.08] relative z-10"
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
            setActiveIdeFile((prev: any) => ({ ...prev, isOpen: false }));
          }}
          className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer"
          title="Close Context Pane (Ctrl+\)"
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
              setActiveIdeFile((prev: any) => ({ ...prev, isOpen: false }));
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
            onAskAnara={onSendText ? (fp) => onSendText(`Explain or inspect file: ${fp}`, "plan") : undefined}
          />

          {/* Docked Split Terminal */}
          {isTerminalOpen && (
            <div className="h-56 border-t border-white/[0.08] shrink-0 flex flex-col">
              <WorkbenchTerminal
                embedded={true}
                isVisible={isTerminalOpen && contextTab === "editor"}
                onClose={() => setIsTerminalOpen(false)}
                cwd={typeof window !== "undefined" ? localStorage.getItem("anara_ide_workspace_key") || undefined : undefined}
              />
            </div>
          )}
        </div>

        {/* Review Git Container */}
        <div
          className="h-full w-full"
          style={{ display: contextTab === "review" ? "flex" : "none" }}
        >
          <ReviewGitPane
            gitStatus={gitStatus}
            onRefreshGit={async () => { await fetchGitStatus(); }}
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
            cwd={typeof window !== "undefined" ? localStorage.getItem("anara_ide_workspace_key") || undefined : undefined}
          />
        </div>
      </div>
    </div>
  );
}
