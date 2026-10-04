"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import { AIModelInfo } from "./ModelSelectorDropdown";
import InteractiveQuestionCard, { InteractiveQuestionData } from "../chat/InteractiveQuestionCard";
import { DockPlanChecklist } from "./DockPlanChecklist";
import { DockAudioWaveform } from "./DockAudioWaveform";
import { TriggerItem } from "./DockTriggerPopover";
import type { ToolProgressPayload } from "@/hooks/useWebSocket";
import { usePromptHistory } from "./usePromptHistory";
import { useComposerQueue } from "@/hooks/useComposerQueue";
import { DockStatusStack } from "./DockStatusStack";
import { DockControlsCluster } from "./DockControlsCluster";
import { DockComposerInput } from "./DockComposerInput";

export type AssistantStatus = "idle" | "listening" | "thinking" | "speaking";

export interface AttachedItem {
  file?: File;
  name: string;
  ext: string;
  sizeKb: number;
  previewUrl?: string;
  content?: string;
}

/** Safely revokes blob: URLs to prevent client memory leaks (Anara Desktop standard) */
export function revokeAttachmentPreviews(items: AttachedItem[]) {
  items.forEach((item) => {
    if (item.previewUrl?.startsWith("blob:")) {
      try {
        URL.revokeObjectURL(item.previewUrl);
      } catch {}
    }
  });
}

export interface BottomDockProps {
  inputMessage: string;
  setInputMessage: (val: string) => void;
  onSend: (text: string, agentMode?: "plan" | "build") => void;
  agentMode?: "plan" | "build";
  setAgentMode?: (mode: "plan" | "build") => void;
  models: AIModelInfo[];
  activeModelId: string;
  onSelectModel: (id: string) => void;
  status: AssistantStatus;
  isMicActive: boolean;
  isMuted: boolean;
  onToggleMute: () => void;
  onStartSession: () => void;
  onInterrupt: () => void;
  micDenied?: boolean;
  activeIntensity: number;
  interactionMode: "voice" | "chat";
  onSetInteractionMode?: (mode: "voice" | "chat") => void;
  isConnected: boolean;
  activeSessionId: number | null;
  onNewSession: () => void;
  onFolderUpload: () => void;
  onFileUpload: (files: FileList | null) => void;
  liveToolProgress?: ToolProgressPayload | null;
  checklistData?: {
    title: string;
    completedCount: number;
    total: number;
    items: Array<{ title: string; isCompleted: boolean; isInProgress?: boolean }>;
  } | null;
  activeQuestion?: InteractiveQuestionData | null;
  onAnswerQuestion?: (questionId: string, answers: any, dismissed?: boolean) => void;
  onHeightChange?: (height: number) => void;
  embedded?: boolean;
  showAgentModeToggle?: boolean;
  showInteractionModeToggle?: boolean;
  onApprovePlan?: (plan?: any) => void;
  onRejectPlan?: (plan?: any) => void;
  reasoningEffort?: "off" | "low" | "medium" | "high" | string;
  onSelectReasoningEffort?: (effort: "off" | "low" | "medium" | "high") => void;
  onSteer?: (text: string) => void;
  workspaceFiles?: Array<{ path: string; name: string; isDir?: boolean }>;
  gitStatus?: {
    is_git: boolean;
    branch?: string;
    changed_count?: number;
    insertions?: number;
    deletions?: number;
  } | null;
  promptTurnsCount?: number;
}

export default function BottomDock({
  inputMessage,
  setInputMessage,
  onSend,
  agentMode,
  setAgentMode,
  models,
  activeModelId,
  onSelectModel,
  status,
  isMicActive,
  isMuted,
  onToggleMute,
  onStartSession,
  onInterrupt,
  micDenied = false,
  activeIntensity,
  interactionMode = "chat",
  onSetInteractionMode,
  isConnected,
  activeSessionId,
  onNewSession,
  onFolderUpload,
  onFileUpload,
  liveToolProgress,
  checklistData,
  activeQuestion,
  onAnswerQuestion,
  onHeightChange,
  embedded = false,
  showAgentModeToggle,
  showInteractionModeToggle,
  onApprovePlan,
  onRejectPlan,
  reasoningEffort,
  onSelectReasoningEffort,
  onSteer,
  workspaceFiles = [],
  gitStatus,
  promptTurnsCount,
}: BottomDockProps) {
  const isAgentToggleVisible = showAgentModeToggle !== undefined ? showAgentModeToggle : false;
  const isInteractionModeVisible = showInteractionModeToggle !== undefined ? showInteractionModeToggle : Boolean(onSetInteractionMode);
  const footerDockRef = useRef<HTMLElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isInputExpanded, setIsInputExpanded] = useState(false);
  const [isInputOverflowed, setIsInputOverflowed] = useState(false);
  const [isPlanChecklistExpanded, setIsPlanChecklistExpanded] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<AttachedItem[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);

  // Multimodal Autocomplete Trigger State (@ Files & / Slash Commands)
  const [triggerKind, setTriggerKind] = useState<"@" | "/" | null>(null);
  const [triggerQuery, setTriggerQuery] = useState("");
  const [triggerSelectedIndex, setTriggerSelectedIndex] = useState(0);
  const [isTriggerPopoverOpen, setIsTriggerPopoverOpen] = useState(false);

  // Modular prompt history ring hook
  const { pushHistory, navigateHistory, resetHistoryIndex } = usePromptHistory();

  const isBusy =
    status === "thinking" ||
    status === "speaking" ||
    Boolean(liveToolProgress && liveToolProgress.status === "running");

  // ── Sequential Turn Queue & Auto-Drain (Anara Composer Queue) ──
  const {
    queuedItems,
    queuedCount,
    enqueue,
    removeQueued,
    clearQueue,
  } = useComposerQueue({
    activeSessionId,
    isBusy,
    onSend,
    onSteer,
  });

  // Cleanup blob preview URLs strictly on unmount
  const attachedFilesRef = useRef(attachedFiles);
  attachedFilesRef.current = attachedFiles;
  useEffect(() => {
    return () => {
      revokeAttachmentPreviews(attachedFilesRef.current);
    };
  }, []);

  // Measure dock height for timeline spacer via ResizeObserver
  useEffect(() => {
    const el = footerDockRef.current;
    if (!el || !onHeightChange) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const height = entry.borderBoxSize?.[0]?.blockSize
          ? Math.round(entry.borderBoxSize[0].blockSize)
          : Math.round(el.offsetHeight);
        onHeightChange(height);
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [onHeightChange]);

  // ── Session Draft Stashing (Anara Standard) ──
  const prevSessionIdRef = useRef<number | null>(activeSessionId);
  useEffect(() => {
    if (prevSessionIdRef.current !== activeSessionId) {
      if (prevSessionIdRef.current) {
        try {
          if (inputMessage.trim()) {
            sessionStorage.setItem(`anara_composer_draft_${prevSessionIdRef.current}`, inputMessage);
          } else {
            sessionStorage.removeItem(`anara_composer_draft_${prevSessionIdRef.current}`);
          }
        } catch {}
      }
      if (activeSessionId) {
        try {
          const stashed = sessionStorage.getItem(`anara_composer_draft_${activeSessionId}`);
          if (stashed !== null) {
            setInputMessage(stashed);
          }
        } catch {}
      }
      prevSessionIdRef.current = activeSessionId;
    }
  }, [activeSessionId, inputMessage, setInputMessage]);

  const handleFormSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputMessage.trim() && attachedFiles.length === 0) return;

    const textToSend =
      inputMessage.trim() ||
      (attachedFiles.some((f) => f.previewUrl)
        ? "Tolong analisa dan periksa screenshot gambar terlampir ini."
        : "Tolong proses file terlampir ini.");

    if (inputMessage.trim()) {
      pushHistory(inputMessage.trim());
    }
    resetHistoryIndex();

    if (activeSessionId) {
      try {
        sessionStorage.removeItem(`anara_composer_draft_${activeSessionId}`);
      } catch {}
    }

    if (isBusy) {
      if (textToSend.startsWith("/steer ")) {
        const steerPayload = textToSend.replace(/^\/steer\s+/, "").trim();
        onSteer?.(steerPayload);
        setInputMessage("");
        return;
      }
      enqueue(textToSend, agentMode);
      setInputMessage("");
      revokeAttachmentPreviews(attachedFiles);
      setAttachedFiles([]);
      return;
    }

    onSend(textToSend, agentMode);
    setInputMessage("");
    revokeAttachmentPreviews(attachedFiles);
    setAttachedFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setIsInputExpanded(false);
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInputMessage(val);

    const cursor = e.target.selectionStart || 0;
    const textBeforeCursor = val.slice(0, cursor);

    // Detect @ file mention trigger: matches @ followed by non-whitespace
    const atMatch = textBeforeCursor.match(/@([^\s]*)$/);
    // Detect / slash command trigger: matches / at start or after whitespace
    const slashMatch = textBeforeCursor.match(/(?:^|\s)\/([a-zA-Z0-9_-]*)$/);

    if (atMatch) {
      setTriggerKind("@");
      setTriggerQuery(atMatch[1]);
      setIsTriggerPopoverOpen(true);
      setTriggerSelectedIndex(0);
    } else if (slashMatch) {
      setTriggerKind("/");
      setTriggerQuery(slashMatch[1]);
      setIsTriggerPopoverOpen(true);
      setTriggerSelectedIndex(0);
    } else {
      setIsTriggerPopoverOpen(false);
      setTriggerKind(null);
      setTriggerQuery("");
    }
  };

  const handleSelectTriggerItem = useCallback(
    (item: TriggerItem) => {
      const el = textareaRef.current;
      const cursor = el ? el.selectionStart || 0 : inputMessage.length;
      const textBeforeCursor = inputMessage.slice(0, cursor);
      const textAfterCursor = inputMessage.slice(cursor);

      let replacedBefore = textBeforeCursor;
      if (triggerKind === "@") {
        replacedBefore = textBeforeCursor.replace(/@([^\s]*)$/, item.value);
      } else if (triggerKind === "/") {
        replacedBefore = textBeforeCursor.replace(/(?:^|\s)\/([a-zA-Z0-9_-]*)$/, (match) => {
          return match.startsWith(" ") ? " " + item.value : item.value;
        });
      }

      const nextVal = replacedBefore + textAfterCursor;
      setInputMessage(nextVal);
      setIsTriggerPopoverOpen(false);
      setTriggerKind(null);
      setTriggerQuery("");

      if (item.id === "cmd-plan") setAgentMode?.("plan");
      else if (item.id === "cmd-build") setAgentMode?.("build");
      else if (item.id === "cmd-voice") onSetInteractionMode?.("voice");
      else if (item.id === "cmd-chat") onSetInteractionMode?.("chat");
      else if (item.id === "cmd-clear") {
        setInputMessage("");
        revokeAttachmentPreviews(attachedFiles);
        setAttachedFiles([]);
      }

      requestAnimationFrame(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          const newPos = replacedBefore.length;
          textareaRef.current.setSelectionRange(newPos, newPos);
        }
      });
    },
    [inputMessage, triggerKind, setInputMessage, setAgentMode, onSetInteractionMode, attachedFiles]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // IME composition guard
    if (e.nativeEvent.isComposing || e.keyCode === 229) {
      return;
    }

    // Handle Multimodal Trigger Popover Navigation
    if (isTriggerPopoverOpen) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setTriggerSelectedIndex((prev) => prev + 1);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setTriggerSelectedIndex((prev) => Math.max(0, prev - 1));
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setIsTriggerPopoverOpen(false);
        setTriggerKind(null);
        return;
      }
    }

    const isBusy =
      status === "thinking" ||
      status === "speaking" ||
      Boolean(liveToolProgress && liveToolProgress.status === "running");

    // Tab completion for slash directives (/plan, /build, /voice, /chat, /clear)
    if (e.key === "Tab" && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const val = inputMessage.trim();
      if (val.startsWith("/")) {
        const commands = [
          { cmd: "/plan", action: () => setAgentMode?.("plan") },
          { cmd: "/build", action: () => setAgentMode?.("build") },
          { cmd: "/voice", action: () => onSetInteractionMode?.("voice") },
          { cmd: "/chat", action: () => onSetInteractionMode?.("chat") },
          {
            cmd: "/clear",
            action: () => {
              setInputMessage("");
              revokeAttachmentPreviews(attachedFiles);
              setAttachedFiles([]);
            },
          },
        ];
        const match = commands.find((c) => c.cmd.startsWith(val.toLowerCase()));
        if (match) {
          e.preventDefault();
          match.action();
          setInputMessage("");
          return;
        }
      }
    }

    // Mid-Turn Steering
    if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (isBusy && onSteer && inputMessage.trim()) {
        e.preventDefault();
        const steerText = inputMessage.trim();
        pushHistory(steerText);
        resetHistoryIndex();
        onSteer(steerText);
        setInputMessage("");
        return;
      }
    }

    // Submit on Enter
    if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (isBusy) {
        return;
      }
      e.preventDefault();
      handleFormSubmit();
      return;
    }

    // Prompt history ring navigation
    const target = e.currentTarget;
    const isAtStart = target.selectionStart === 0 && target.selectionEnd === 0;
    const isAtEnd = target.selectionStart === target.value.length && target.selectionEnd === target.value.length;

    if (e.key === "ArrowUp" && isAtStart) {
      const navPrompt = navigateHistory("up", inputMessage);
      if (navPrompt !== null) {
        e.preventDefault();
        setInputMessage(navPrompt);
      }
    } else if (e.key === "ArrowDown" && isAtEnd) {
      const navPrompt = navigateHistory("down", inputMessage);
      if (navPrompt !== null) {
        e.preventDefault();
        setInputMessage(navPrompt);
      }
    }
  };

  const handleAttachFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const newItems: AttachedItem[] = [];
      const imageItems: AttachedItem[] = [];

      Array.from(files).forEach((file) => {
        const ext = file.name.split(".").pop()?.toLowerCase() || "";
        const sizeKb = Math.round(file.size / 1024);
        let previewUrl: string | undefined;

        if (file.type.startsWith("image/")) {
          previewUrl = URL.createObjectURL(file);
          imageItems.push({ file, name: file.name, ext, sizeKb, previewUrl });
        } else {
          newItems.push({ file, name: file.name, ext, sizeKb });
        }
      });

      setAttachedFiles((prev) => [...prev, ...imageItems, ...newItems]);
      onFileUpload(files);
    },
    [onFileUpload]
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const items = e.clipboardData?.items;
      if (!items) return;

      const files: File[] = [];
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === "file") {
          const file = item.getAsFile();
          if (file) files.push(file);
        }
      }

      if (files.length > 0) {
        const dt = new DataTransfer();
        files.forEach((f) => dt.items.add(f));
        handleAttachFiles(dt.files);
        return;
      }

      // Anara Large Paste Protection: convert >3k chars text paste to file attachment
      const pastedText = e.clipboardData?.getData("text/plain");
      if (pastedText && pastedText.length > 3000) {
        e.preventDefault();
        const blob = new Blob([pastedText], { type: "text/plain" });
        const stamp = Date.now().toString(36);
        const file = new File([blob], `pasted_text_${stamp}.txt`, { type: "text/plain" });
        const dt = new DataTransfer();
        dt.items.add(file);
        handleAttachFiles(dt.files);
      }
    },
    [handleAttachFiles]
  );

  const dragCounterRef = useRef(0);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.types && Array.from(e.dataTransfer.types).includes("Files")) {
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = "copy";
    }
  }, []);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.types && Array.from(e.dataTransfer.types).includes("Files")) {
      setIsDragOver(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragOver(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounterRef.current = 0;
      setIsDragOver(false);
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleAttachFiles(e.dataTransfer.files);
      }
    },
    [handleAttachFiles]
  );

  const canSend = Boolean(inputMessage.trim() || attachedFiles.length > 0);

  return (
    <footer
      ref={footerDockRef}
      className={
        embedded
          ? "relative w-full p-2.5 z-20 flex flex-col items-center gap-1.5 pointer-events-auto shrink-0 bg-transparent mt-auto"
          : `fixed px-3 sm:px-4 z-30 flex flex-col items-center gap-1.5 pointer-events-none mx-auto right-0 transition-[top,bottom,max-width] duration-300 ${
              isInputExpanded
                ? "bottom-4 top-16 max-w-3xl lg:max-w-4xl"
                : "bottom-3 sm:bottom-4 max-w-2xl lg:max-w-3xl"
            }`
      }
      style={!embedded ? { left: "var(--sidebar-width, 260px)", right: 0 } : undefined}
      suppressHydrationWarning
    >
      {/* Non-intrusive Mic Denied Alert Pill */}
      {micDenied && interactionMode === "voice" && (
        <div className="animate-fade-in pointer-events-auto bg-rose-500/20 border border-rose-500/40 text-rose-200 text-xs px-4 py-2 rounded-2xl backdrop-blur-xl shadow-lg flex items-center gap-2 font-mono">
          <svg className="w-4 h-4 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span suppressHydrationWarning>Microphone access denied. Allow microphone permission in your browser.</span>
        </div>
      )}

      {/* Sticky Plan Checklist Widget */}
      {checklistData && (
        <DockPlanChecklist
          checklistData={checklistData}
          isExpanded={isPlanChecklistExpanded}
          onToggle={() => setIsPlanChecklistExpanded((v) => !v)}
          onApprovePlan={() => onApprovePlan?.(checklistData)}
          onRejectPlan={onRejectPlan ? () => onRejectPlan(checklistData) : undefined}
        />
      )}

      {/* Interactive Question Card Wizard */}
      {activeQuestion && !activeQuestion.isAnswered ? (
        <div className="w-full pointer-events-auto">
          <InteractiveQuestionCard
            data={activeQuestion}
            onSubmitAnswers={(qId, ans, dis) => onAnswerQuestion?.(qId, ans, dis)}
          />
        </div>
      ) : null}

      {/* Modular Status Stack: Live Tool Execution Activity */}
      <DockStatusStack liveToolProgress={liveToolProgress} onInterrupt={onInterrupt} />

      {/* Obsidian Liquid Glass Composer Card */}
      {(!activeQuestion || activeQuestion.isAnswered) && (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`w-full rounded-2xl p-2.5 px-3.5 flex flex-col gap-2 pointer-events-auto border shadow-[0_20px_50px_rgba(0,0,0,0.8),inset_0_1px_0_rgba(255,255,255,0.12)] relative transition-[border-color,box-shadow] duration-200 isolate ${
            isDragOver
              ? "border-cyan-400 ring-2 ring-cyan-400/50 shadow-[0_0_30px_rgba(34,211,238,0.25)]"
              : "border-white/[0.10] hover:border-white/[0.20]"
          } ${isInputExpanded ? "h-full flex-1 min-h-0" : ""}`}
        >
          {/* Isolated Glass Backing */}
          <div
            aria-hidden="true"
            className={`pointer-events-none absolute inset-0 -z-10 rounded-[inherit] transition-[background-color] duration-150 ease-out backdrop-blur-2xl ${
              isDragOver ? "bg-cyan-950/40" : "bg-[#060913]/90"
            }`}
          />

          {/* Top Specular Sheen Highlight */}
          <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/[0.12] to-transparent pointer-events-none z-10" />
          {isDragOver && (
            <div className="absolute inset-0 z-40 rounded-2xl bg-slate-950/85 backdrop-blur-md border-2 border-dashed border-cyan-400 flex items-center justify-center gap-2.5 text-cyan-200 text-xs font-mono font-medium animate-fade-in pointer-events-none select-none">
              <svg className="w-5 h-5 text-cyan-300 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <span>Drop files here to attach</span>
            </div>
          )}

          {/* Hidden File Input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.txt,.md,.py,.js,.ts,.tsx,.json,.csv,.yaml,.yml,.toml,.html,.css,.sql,.sh,.bash,.go,.rs,.java,.c,.cpp,.h,.hpp,image/*"
            className="hidden"
            onChange={(e) => {
              handleAttachFiles(e.target.files);
              e.target.value = "";
            }}
          />

          {/* Coding Status Strip: strictly hidden when not in a local git repo */}
          {gitStatus?.is_git && gitStatus?.branch ? (
            <div className="w-full flex items-center justify-between pb-1.5 mb-1 border-b border-white/[0.06] text-[11px] font-mono select-none">
              {/* Left: Branch Indicator */}
              <div className="flex items-center gap-1.5 text-slate-300">
                <svg className="w-3.5 h-3.5 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7a3 3 0 100-6 3 3 0 000 6zm0 0v10m0 0a3 3 0 100 6 3 3 0 000-6zm8-4a3 3 0 100-6 3 3 0 000 6zm0 0v3a4 4 0 01-4 4h-4" />
                </svg>
                <span className="font-semibold text-slate-200">{gitStatus.branch}</span>
              </div>

              {/* Right: Telemetry (Turns & Git Diff Delta) */}
              <div className="flex items-center gap-3 text-slate-400">
                {promptTurnsCount !== undefined && promptTurnsCount > 0 && (
                  <span className="flex items-center gap-0.5 text-slate-300" title="Conversation Turns">
                    <span className="text-slate-400">↑</span>
                    <span>{promptTurnsCount}</span>
                  </span>
                )}
                {(gitStatus.insertions !== undefined || gitStatus.deletions !== undefined) && (
                  <span className="flex items-center gap-1.5 font-mono tabular-nums text-[10.5px]">
                    {gitStatus.insertions ? <span className="text-emerald-400">+{gitStatus.insertions}</span> : null}
                    {gitStatus.deletions ? <span className="text-rose-400">-{gitStatus.deletions}</span> : null}
                  </span>
                )}
              </div>
            </div>
          ) : null}

          {/* Active Sequential Queue Banner */}
          {queuedCount > 0 && (
            <div className="flex items-center justify-between px-3 py-1 mb-1.5 rounded-lg bg-cyan-950/40 border border-cyan-500/20 text-[10.5px] font-mono text-cyan-300 backdrop-blur-md">
              <div className="flex items-center gap-2 truncate">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse shrink-0" />
                <span className="font-semibold uppercase tracking-wider text-cyan-400 shrink-0">
                  Antrean Turn ({queuedCount}):
                </span>
                <span className="truncate text-slate-300 font-sans">{queuedItems[0]?.text}</span>
              </div>
              <button
                type="button"
                onClick={clearQueue}
                className="text-slate-400 hover:text-white px-1.5 py-0.5 rounded text-[10px] bg-white/[0.04] hover:bg-white/[0.08] transition-colors cursor-pointer shrink-0 ml-2"
                title="Batal antrean"
              >
                Batal
              </button>
            </div>
          )}

          {/* Input Area / Voice Waveform */}
          <div className={`w-full flex items-center gap-2 ${isInputExpanded ? "flex-1 min-h-0 overflow-hidden" : "min-h-[36px]"}`}>
            {interactionMode === "voice" && !inputMessage.trim() && attachedFiles.length === 0 ? (
              <DockAudioWaveform
                status={status}
                activeIntensity={activeIntensity}
                isMicActive={isMicActive}
                isMuted={isMuted}
              />
            ) : (
              <DockComposerInput
                inputMessage={inputMessage}
                setInputMessage={setInputMessage}
                attachedFiles={attachedFiles}
                setAttachedFiles={setAttachedFiles}
                isInputExpanded={isInputExpanded}
                setIsInputExpanded={setIsInputExpanded}
                isInputOverflowed={isInputOverflowed}
                setIsInputOverflowed={setIsInputOverflowed}
                textareaRef={textareaRef}
                onSubmit={handleFormSubmit}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                triggerKind={triggerKind}
                triggerQuery={triggerQuery}
                triggerSelectedIndex={triggerSelectedIndex}
                setTriggerSelectedIndex={setTriggerSelectedIndex}
                isTriggerPopoverOpen={isTriggerPopoverOpen}
                onSelectTriggerItem={handleSelectTriggerItem}
                onCloseTriggerPopover={() => {
                  setIsTriggerPopoverOpen(false);
                  setTriggerKind(null);
                }}
                workspaceFiles={workspaceFiles}
                onClearAttachments={() => {
                  revokeAttachmentPreviews(attachedFiles);
                  setAttachedFiles([]);
                }}
                handleTextareaChange={handleTextareaChange}
              />
            )}
          </div>

          {/* Bottom Action Controls Cluster */}
          <DockControlsCluster
            models={models}
            activeModelId={activeModelId}
            onSelectModel={onSelectModel}
            reasoningEffort={reasoningEffort}
            onSelectReasoningEffort={onSelectReasoningEffort}
            interactionMode={interactionMode}
            onSetInteractionMode={onSetInteractionMode}
            isInteractionModeVisible={isInteractionModeVisible}
            agentMode={agentMode}
            setAgentMode={setAgentMode}
            isAgentToggleVisible={isAgentToggleVisible}
            status={status}
            isMicActive={isMicActive}
            isMuted={isMuted}
            onToggleMute={onToggleMute}
            onStartSession={onStartSession}
            onInterrupt={onInterrupt}
            isConnected={isConnected}
            activeSessionId={activeSessionId}
            onNewSession={onNewSession}
            onFolderUpload={onFolderUpload}
            fileInputRef={fileInputRef}
            isBusy={isBusy}
            canSend={canSend}
            onSend={() => handleFormSubmit()}
          />
        </div>
      )}
    </footer>
  );
}
