"use client";

import React from "react";
import { WorkbenchTitlebar } from "./WorkbenchTitlebar";
import ChatTimeline from "@/components/chat/ChatTimeline";
import BottomDock from "@/components/dock/BottomDock";
import type { GitStatusData } from "@/components/sidebar/types";
import type { AIModelInfo } from "@/components/dock/ModelSelectorDropdown";
import type { ReasoningEffortLevel } from "@/lib/reasoningEffort";
import type { AssistantStatus, TranscriptItem } from "./types";

export interface WorkbenchChatColumnProps {
  isContextPaneOpen: boolean;
  setIsContextPaneOpen: React.Dispatch<React.SetStateAction<boolean>>;
  activeIdeFile: {
    isOpen: boolean;
    fileName: string;
    filePath: string;
    fileExt: string;
    fileSizeKb: number;
    content: string;
    originalContent?: string;
  };
  transcript: TranscriptItem[];
  activeSessionId: number | null;
  handleNewSession: () => void;
  setIsBrainDrawerOpen: (open: boolean) => void;
  contextTab: "editor" | "review" | "terminal";
  setContextTab: (tab: "editor" | "review" | "terminal") => void;
  fetchGitStatus: () => Promise<void> | void;
  gitStatus: GitStatusData | null;
  setIsTerminalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  status: AssistantStatus;
  activeSpeaker?: string | null;
  activeModelId?: string;
  liveToolProgress?: any;
  footerDockHeight: number;
  setFooterDockHeight: (h: number) => void;
  onApprovePlan?: (planData: any) => void;
  onRejectPlan?: (planData?: any) => void;
  activeThinkingText?: string | null;
  onAnswerQuestion?: (questionId: string, answers: any, dismissed?: boolean) => void;
  handleOpenFileIDE: (path: string, name: string) => void;
  handleOpenLightbox?: (data: { url: string; title: string; sourceDomain?: string; sourceUrl?: string; prompt?: string }) => void;
  inputMessage: string;
  setInputMessage: (msg: string) => void;
  onSendText?: (text: string, mode?: "plan" | "build") => void;
  onSteer?: (text: string) => void;
  agentMode: "plan" | "build";
  setAgentMode: React.Dispatch<React.SetStateAction<"plan" | "build">>;
  models: AIModelInfo[];
  handleSelectModel: (id: string) => void;
  isMicActive: boolean;
  isMuted: boolean;
  onToggleMute?: () => void;
  onStartSession?: () => void;
  onInterrupt?: () => void;
  activeIntensity: number;
  interactionMode?: "voice" | "chat";
  onSetInteractionMode?: (mode: "voice" | "chat") => void;
  isConnected: boolean;
  handleFolderUpload?: () => void;
  handleFileUpload?: (files: FileList | null) => void;
  activeUnansweredQuestion?: any;
  checklistData?: any;
  reasoningEffort?: string;
  onSelectReasoningEffort?: (effort: "off" | "low" | "medium" | "high") => void;
  workspaceFilesList?: Array<{ path: string; name: string; isDir?: boolean }>;
}

export function WorkbenchChatColumn({
  isContextPaneOpen,
  setIsContextPaneOpen,
  activeIdeFile,
  transcript,
  activeSessionId,
  handleNewSession,
  setIsBrainDrawerOpen,
  contextTab,
  setContextTab,
  fetchGitStatus,
  gitStatus,
  setIsTerminalOpen,
  status,
  activeSpeaker,
  activeModelId,
  liveToolProgress,
  footerDockHeight,
  setFooterDockHeight,
  onApprovePlan,
  onRejectPlan,
  activeThinkingText,
  onAnswerQuestion,
  handleOpenFileIDE,
  handleOpenLightbox,
  inputMessage,
  setInputMessage,
  onSendText,
  onSteer,
  agentMode,
  setAgentMode,
  models,
  handleSelectModel,
  isMicActive,
  isMuted,
  onToggleMute,
  onStartSession,
  onInterrupt,
  activeIntensity,
  interactionMode,
  onSetInteractionMode,
  isConnected,
  handleFolderUpload,
  handleFileUpload,
  activeUnansweredQuestion,
  checklistData,
  reasoningEffort,
  onSelectReasoningEffort,
  workspaceFilesList,
}: WorkbenchChatColumnProps) {
  return (
    <div
      className="flex flex-col min-w-[360px] h-full relative overflow-hidden"
      style={{
        flex: isContextPaneOpen ? "1 1 auto" : "1 1 100%",
      }}
    >
      {/* Unified Desktop Titlebar Band (Modularized Component) */}
      <WorkbenchTitlebar
        activeIdeFile={activeIdeFile}
        transcript={transcript}
        activeSessionId={activeSessionId}
        handleNewSession={handleNewSession}
        setIsBrainDrawerOpen={setIsBrainDrawerOpen}
        isContextPaneOpen={isContextPaneOpen}
        setIsContextPaneOpen={setIsContextPaneOpen}
        contextTab={contextTab}
        setContextTab={setContextTab}
        fetchGitStatus={fetchGitStatus}
        gitStatus={gitStatus}
        setIsTerminalOpen={setIsTerminalOpen}
      />

      {/* Scrollable message timeline fills remaining vertical space */}
      <div className="flex-1 min-h-0 relative flex flex-col overflow-hidden">
        <ChatTimeline
          transcript={transcript}
          status={status}
          activeSessionId={activeSessionId || undefined}
          activeSpeaker={activeSpeaker || undefined}
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
            const inputEl = document.querySelector("textarea") as HTMLTextAreaElement;
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
            activeModelId={activeModelId || ""}
            onSelectModel={handleSelectModel}
            status={status}
            isMicActive={isMicActive}
            isMuted={isMuted}
            onToggleMute={onToggleMute || (() => {})}
            onStartSession={onStartSession || (() => {})}
            onInterrupt={onInterrupt || (() => {})}
            activeIntensity={activeIntensity}
            interactionMode={interactionMode || "chat"}
            onSetInteractionMode={onSetInteractionMode}
            isConnected={isConnected}
            activeSessionId={activeSessionId}
            onNewSession={handleNewSession}
            onFolderUpload={handleFolderUpload || (() => {})}
            onFileUpload={handleFileUpload || (() => {})}
            liveToolProgress={liveToolProgress}
            checklistData={checklistData}
            activeQuestion={activeUnansweredQuestion}
            onAnswerQuestion={onAnswerQuestion}
            onHeightChange={setFooterDockHeight}
            onApprovePlan={onApprovePlan}
            onRejectPlan={onRejectPlan}
            reasoningEffort={reasoningEffort}
            onSelectReasoningEffort={onSelectReasoningEffort}
            workspaceFiles={workspaceFilesList}
            gitStatus={gitStatus}
            promptTurnsCount={transcript.length}
          />
        </div>
      </div>
    </div>
  );
}
