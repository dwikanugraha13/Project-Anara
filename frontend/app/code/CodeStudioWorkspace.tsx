"use client";

import React, { Suspense, useState, useEffect, useMemo } from "react";
import { ActivityBar } from "./ActivityBar";
import ReviewGitPane from "@/components/sidebar/ReviewGitPane";
import WorkspaceTreeView from "@/components/sidebar/WorkspaceTreeView";
import AnaraCodeIDE from "@/components/ide/AnaraCodeIDE";
import WorkbenchTerminal from "@/components/ide/WorkbenchTerminal";
import ChatTimeline from "@/components/chat/ChatTimeline";
import BottomDock from "@/components/dock/BottomDock";
import CommandPalette, { CommandItem } from "@/components/command/CommandPalette";
import { formatModelDisplayName } from "@/lib/modelFormat";
import type { IdeTabFile } from "@/components/ide";
import type { GitStatusData } from "@/components/sidebar/types";
import type { AIModelInfo } from "@/components/dock/ModelSelectorDropdown";
import type { ReasoningEffortLevel } from "@/lib/reasoningEffort";

export interface CodeStudioWorkspaceProps {
  isLeftOpen: boolean;
  setIsLeftOpen: React.Dispatch<React.SetStateAction<boolean>>;
  explorerMode: "tree" | "git";
  setExplorerMode: React.Dispatch<React.SetStateAction<"tree" | "git">>;
  explorerFilter: string;
  setExplorerFilter: (f: string) => void;
  isTerminalOpen: boolean;
  setIsTerminalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  isRightOpen: boolean;
  setIsRightOpen: React.Dispatch<React.SetStateAction<boolean>>;
  setIsBrainDrawerOpen: (v: boolean) => void;
  gitStatus: GitStatusData | null;
  loadGitStatus: (sid?: number | null) => void;
  workspaceTree: any;
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
  ideTabs: IdeTabFile[];
  handleSelectIdeTab: (filePath: string, fileName: string) => void;
  handleCloseIdeTab: (fp: string) => void;
  handleSaveIdeFile: (fp: string, cnt: string) => Promise<boolean>;
  leftWidth: number;
  startResizingLeft: (e: React.MouseEvent) => void;
  terminalHeight: number;
  startResizingTerminal: (e: React.MouseEvent) => void;
  rightWidth: number;
  startResizingRight: (e: React.MouseEvent) => void;
  agentMode: "plan" | "build";
  setAgentMode: React.Dispatch<React.SetStateAction<"plan" | "build">>;
  activeModelId: string;
  models: AIModelInfo[];
  handleSelectModel: (id: string) => void;
  assistantStatus: "idle" | "listening" | "thinking" | "speaking";
  setAssistantStatus: (s: "idle" | "listening" | "thinking" | "speaking") => void;
  activeSpeaker: string | null;
  transcript: any[];
  liveToolProgress: any;
  footerDockHeight: number;
  setFooterDockHeight: (h: number) => void;
  activeThinkingText: string | null;
  handleApprovePlan: (data: any) => void;
  handleRejectPlan: () => void;
  handleApproveAction?: (planId: string, scope: "once" | "session") => void;
  handleRejectAction?: (planId: string) => void;
  handleAnswerQuestion: (qid: string, answers: any) => void;
  handleOpenFileIDE: (path: string, name: string) => void;
  handlePickLocalFolder: (initialPath?: string) => void;
  handleClearWorkspace: () => void;
  handleSendText: (text: string, mode?: "plan" | "build") => void;
  inputMessage: string;
  setInputMessage: (msg: string) => void;
  sendJSON: (msg: any) => void;
  sendSteer: (text: string) => void;
  wsStatus: string;
  activeSessionId: number | null;
  handleNewSession: () => void;
  reasoningEffort: ReasoningEffortLevel;
  handleSelectReasoningEffort: (tier: ReasoningEffortLevel) => void;
  workspaceFilesList: Array<{ path: string; name: string; isDir?: boolean }>;
  activeUnansweredQuestion: any;
}

export function CodeStudioWorkspace({
  isLeftOpen,
  setIsLeftOpen,
  explorerMode,
  setExplorerMode,
  explorerFilter,
  setExplorerFilter,
  isTerminalOpen,
  setIsTerminalOpen,
  isRightOpen,
  setIsRightOpen,
  setIsBrainDrawerOpen,
  gitStatus,
  loadGitStatus,
  workspaceTree,
  activeIdeFile,
  setActiveIdeFile,
  ideTabs,
  handleSelectIdeTab,
  handleCloseIdeTab,
  handleSaveIdeFile,
  leftWidth,
  startResizingLeft,
  terminalHeight,
  startResizingTerminal,
  rightWidth,
  startResizingRight,
  agentMode,
  setAgentMode,
  activeModelId,
  models,
  handleSelectModel,
  assistantStatus,
  setAssistantStatus,
  activeSpeaker,
  transcript,
  liveToolProgress,
  footerDockHeight,
  setFooterDockHeight,
  activeThinkingText,
  handleApprovePlan,
  handleRejectPlan,
  handleApproveAction,
  handleRejectAction,
  handleAnswerQuestion,
  handleOpenFileIDE,
  handlePickLocalFolder,
  handleClearWorkspace,
  handleSendText,
  inputMessage,
  setInputMessage,
  sendJSON,
  sendSteer,
  wsStatus,
  activeSessionId,
  handleNewSession,
  reasoningEffort,
  handleSelectReasoningEffort,
  workspaceFilesList,
  activeUnansweredQuestion,
}: CodeStudioWorkspaceProps) {
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "p")) {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const commandItems = useMemo<CommandItem[]>(() => {
    const list: CommandItem[] = [
      {
        id: "toggle-explorer",
        label: "Toggle File Explorer",
        category: "Commands",
        shortcut: "Ctrl+B",
        onSelect: () => setIsLeftOpen((prev) => !prev),
      },
      {
        id: "toggle-terminal",
        label: "Toggle Integrated Terminal",
        category: "Commands",
        shortcut: "Ctrl+`",
        onSelect: () => setIsTerminalOpen((prev) => !prev),
      },
      {
        id: "toggle-timeline",
        label: "Toggle Agent Chat Timeline",
        category: "Commands",
        onSelect: () => setIsRightOpen((prev) => !prev),
      },
      {
        id: "new-session",
        label: "Start New Chat Session",
        category: "Commands",
        shortcut: "Ctrl+N",
        onSelect: handleNewSession,
      },
      {
        id: "switch-to-git",
        label: "Open Git Review & Diff Inspector",
        category: "Commands",
        onSelect: () => {
          setIsLeftOpen(true);
          setExplorerMode("git");
        },
      },
    ];

    // Add model choices
    if (models && models.length > 0) {
      models.forEach((m) => {
        list.push({
          id: `model-${m.id}`,
          label: `Switch Model: ${formatModelDisplayName(m.id)}`,
          sublabel: m.provider,
          category: "AI Models",
          onSelect: () => handleSelectModel(m.id),
        });
      });
    }

    return list;
  }, [
    models,
    handleSelectModel,
    handleNewSession,
    setIsLeftOpen,
    setIsTerminalOpen,
    setIsRightOpen,
    setExplorerMode,
  ]);

  return (
    <div className="flex-1 flex min-h-0 items-stretch overflow-hidden relative">
      {/* ── ACTIVITY BAR (Anara Code Studio Primary Icon Rail) ── */}
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
                onRefreshGit={async () => { await loadGitStatus(activeSessionId); }}
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
            className="relative w-px h-full cursor-col-resize shrink-0 select-none bg-white/[0.08] hover:bg-white/[0.16] active:bg-white/[0.22] transition-colors z-20"
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
                onClose={() => setActiveIdeFile((prev: any) => ({ ...prev, isOpen: false }))}
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
            /* Studio Welcome Empty State: Liquid Glass Anara Hub */
            <div className="flex-1 flex flex-col items-center justify-center p-8 select-none bg-gradient-to-b from-[#060a16]/60 via-[#040813]/80 to-[#02050e] text-slate-300 font-sans relative overflow-hidden">
              <div className="absolute w-[450px] h-[450px] rounded-full bg-cyan-500/[0.04] blur-[120px] pointer-events-none" />
              <div className="absolute w-[300px] h-[300px] rounded-full bg-purple-500/[0.03] blur-[100px] pointer-events-none" />

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

        {/* Integrated Terminal Dock with Keep-Alive (Anara Desktop Standard) */}
        {isTerminalOpen && (
          <div
            onMouseDown={startResizingTerminal}
            className="relative h-px w-full cursor-row-resize shrink-0 select-none bg-white/[0.08] hover:bg-white/[0.16] active:bg-white/[0.22] transition-colors z-10"
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
          className="relative w-px h-full cursor-col-resize shrink-0 select-none bg-white/[0.08] hover:bg-white/[0.16] active:bg-white/[0.22] transition-colors z-20"
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
          {/* Anara Agent Console Header */}
          <div className="h-9 shrink-0 px-3 border-b border-white/[0.08] flex items-center justify-between bg-[#060913]/95 font-mono text-xs select-none">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${assistantStatus === "thinking" ? "bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]" : "bg-emerald-400 shadow-[0_0_8px_#34d399]"}`} />
              <span className="font-bold text-white tracking-wider text-[11px] uppercase">Agent Console</span>
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
              onApproveAction={handleApproveAction}
              onRejectAction={handleRejectAction}
              onAnswerQuestion={handleAnswerQuestion}
              onOpenFile={(p: string) => handleOpenFileIDE(p, p.split("/").pop() || "file")}
              onSelectPrompt={(text: string) => setInputMessage(text)}
            />
          </div>

          {/* Dedicated Agent Command & Prompt Input Dock */}
          <BottomDock
            embedded={true}
            isCodeStudio={true}
            showAgentModeToggle={false}
            showInteractionModeToggle={false}
            inputMessage={inputMessage}
            setInputMessage={setInputMessage}
            onSend={(text: string, mode?: "plan" | "build") => handleSendText(text, mode)}
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

      {/* Global Command Palette (Ctrl+K / Cmd+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        commands={commandItems}
      />
    </div>
  );
}
