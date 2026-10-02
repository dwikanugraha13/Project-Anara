"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import ModelSelectorDropdown, { AIModelInfo, isReasoningSupported } from "./ModelSelectorDropdown";
import ReasoningPill from "./ReasoningPill";
import { getModelModalities, resolveSiblingTierModelId } from "@/lib/reasoningEffort";
import InteractiveQuestionCard, { InteractiveQuestionData } from "../chat/InteractiveQuestionCard";
import { DockPlanChecklist } from "./DockPlanChecklist";
import { DockAudioWaveform } from "./DockAudioWaveform";
import { DockAttachmentChips } from "./DockAttachmentChips";
import DockTriggerPopover, { TriggerItem } from "./DockTriggerPopover";
import type { ToolProgressPayload } from "@/hooks/useWebSocket";
import { formatModelDisplayName } from "@/lib/modelFormat";

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

const useIsomorphicLayoutEffect = typeof window !== "undefined" ? React.useLayoutEffect : React.useEffect;

export interface BottomDockProps {
  inputMessage: string;
  setInputMessage: (val: string) => void;
  onSend: (text: string, agentMode: "plan" | "build") => void;
  agentMode: "plan" | "build";
  setAgentMode: (mode: "plan" | "build") => void;
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
  const [isAttachMenuOpen, setIsAttachMenuOpen] = useState(false);
  const [isVoiceChatDropdownOpen, setIsVoiceChatDropdownOpen] = useState(false);
  const [isAgentModeDropdownOpen, setIsAgentModeDropdownOpen] = useState(false);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
  const [isPlanChecklistExpanded, setIsPlanChecklistExpanded] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<AttachedItem[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);

  // ── Multimodal Autocomplete Trigger State (@ Files & / Slash Commands) ──
  const [triggerKind, setTriggerKind] = useState<"@" | "/" | null>(null);
  const [triggerQuery, setTriggerQuery] = useState("");
  const [triggerSelectedIndex, setTriggerSelectedIndex] = useState(0);
  const [isTriggerPopoverOpen, setIsTriggerPopoverOpen] = useState(false);

  const closeDropdown = useCallback(() => {
    setIsAttachMenuOpen(false);
    setIsVoiceChatDropdownOpen(false);
    setIsAgentModeDropdownOpen(false);
    setIsModelDropdownOpen(false);
  }, []);

  useEffect(() => {
    const onWindowClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (target?.closest?.("[data-dropdown-root]")) return;
      closeDropdown();
    };
    window.addEventListener("click", onWindowClick);
    return () => window.removeEventListener("click", onWindowClick);
  }, [closeDropdown]);

  const toggleDropdown = (which: "attach" | "mode" | "agentMode" | "model", e: React.MouseEvent) => {
    e.stopPropagation();
    e.nativeEvent?.stopImmediatePropagation?.();
    if (which === "attach") {
      setIsAttachMenuOpen((p) => !p);
      setIsVoiceChatDropdownOpen(false);
      setIsAgentModeDropdownOpen(false);
      setIsModelDropdownOpen(false);
    } else if (which === "mode") {
      setIsVoiceChatDropdownOpen((p) => !p);
      setIsAttachMenuOpen(false);
      setIsAgentModeDropdownOpen(false);
      setIsModelDropdownOpen(false);
    } else if (which === "agentMode") {
      setIsAgentModeDropdownOpen((p) => !p);
      setIsAttachMenuOpen(false);
      setIsVoiceChatDropdownOpen(false);
      setIsModelDropdownOpen(false);
    } else if (which === "model") {
      setIsModelDropdownOpen((p) => !p);
      setIsAttachMenuOpen(false);
      setIsVoiceChatDropdownOpen(false);
      setIsAgentModeDropdownOpen(false);
    }
  };

  // Prompt history ring (Anara input history standard)
  const promptHistoryRef = useRef<string[]>([]);
  const historyIndexRef = useRef<number>(-1);
  const draftSnapshotRef = useRef<string>("");

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("anara:prompt-history");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          promptHistoryRef.current = parsed.filter((item) => typeof item === "string");
        }
      }
    } catch {}
  }, []);

  // Cleanup blob preview URLs strictly on unmount (Anara composer standard)
  const attachedFilesRef = useRef(attachedFiles);
  attachedFilesRef.current = attachedFiles;
  useEffect(() => {
    return () => {
      revokeAttachmentPreviews(attachedFilesRef.current);
    };
  }, []);

  // Measure dock height for timeline spacer via ResizeObserver (border-box accuracy)
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

  // Textarea auto-resize (single-pass layout without oscillation or post-paint jumping)
  useIsomorphicLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el || isInputExpanded) return;
    if (!inputMessage) {
      el.style.height = "36px";
      el.style.overflowY = "hidden";
      setIsInputOverflowed(false);
      return;
    }
    el.style.height = "auto";
    const scrollH = el.scrollHeight;
    const nextH = Math.min(scrollH, 180);
    el.style.height = `${nextH}px`;
    el.style.overflowY = scrollH > 180 ? "auto" : "hidden";
    setIsInputOverflowed(scrollH > 180);
  }, [inputMessage, isInputExpanded]);

  const handleFormSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputMessage.trim() && attachedFiles.length === 0) return;

    const textToSend = inputMessage.trim();
    if (textToSend) {
      if (promptHistoryRef.current[0] !== textToSend) {
        promptHistoryRef.current.unshift(textToSend);
        if (promptHistoryRef.current.length > 50) {
          promptHistoryRef.current.pop();
        }
        try {
          sessionStorage.setItem("anara:prompt-history", JSON.stringify(promptHistoryRef.current.slice(0, 50)));
        } catch {}
      }
    }

    historyIndexRef.current = -1;
    draftSnapshotRef.current = "";

    onSend(inputMessage, agentMode);
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

      // Execute mode switch if slash command
      if (item.id === "cmd-plan") setAgentMode("plan");
      else if (item.id === "cmd-build") setAgentMode("build");
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
    // IME composition guard (Japanese, Chinese, accented character composition)
    if (e.nativeEvent.isComposing || e.keyCode === 229) {
      return;
    }

    // ── Handle Multimodal Trigger Popover Navigation ──
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
          { cmd: "/plan", action: () => setAgentMode("plan") },
          { cmd: "/build", action: () => setAgentMode("build") },
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
          setInputMessage(match.cmd + " ");
          match.action();
          return;
        }
      }
    }

    // ArrowUp / ArrowDown prompt history navigation (Anara & Anara CLI REPL standard)
    if (e.key === "ArrowUp") {
      const el = textareaRef.current;
      const isAtStart = !inputMessage || (el ? el.selectionStart === 0 && el.selectionEnd === 0 : false);
      if (isAtStart && promptHistoryRef.current.length > 0) {
        e.preventDefault();
        if (historyIndexRef.current === -1) {
          draftSnapshotRef.current = inputMessage;
          historyIndexRef.current = 0;
        } else if (historyIndexRef.current < promptHistoryRef.current.length - 1) {
          historyIndexRef.current += 1;
        }
        const text = promptHistoryRef.current[historyIndexRef.current];
        setInputMessage(text);
        requestAnimationFrame(() => {
          if (textareaRef.current) {
            textareaRef.current.setSelectionRange(text.length, text.length);
          }
        });
        return;
      }
    }

    if (e.key === "ArrowDown") {
      if (historyIndexRef.current !== -1) {
        e.preventDefault();
        if (historyIndexRef.current > 0) {
          historyIndexRef.current -= 1;
          const text = promptHistoryRef.current[historyIndexRef.current];
          setInputMessage(text);
          requestAnimationFrame(() => {
            if (textareaRef.current) {
              textareaRef.current.setSelectionRange(text.length, text.length);
            }
          });
        } else {
          // Returned to present draft
          historyIndexRef.current = -1;
          const restored = draftSnapshotRef.current;
          setInputMessage(restored);
          draftSnapshotRef.current = "";
          requestAnimationFrame(() => {
            if (textareaRef.current) {
              textareaRef.current.setSelectionRange(restored.length, restored.length);
            }
          });
        }
        return;
      }
    }

    // Escape shortcut to close popovers, restore draft, collapse expanded input, stop/interrupt response, or blur
    if (e.key === "Escape") {
      if (isAttachMenuOpen || isVoiceChatDropdownOpen || isAgentModeDropdownOpen || isModelDropdownOpen) {
        e.preventDefault();
        closeDropdown();
        return;
      }
      if (historyIndexRef.current !== -1) {
        e.preventDefault();
        setInputMessage(draftSnapshotRef.current);
        historyIndexRef.current = -1;
        draftSnapshotRef.current = "";
        return;
      }
      if (isInputExpanded) {
        e.preventDefault();
        setIsInputExpanded(false);
        return;
      }
      if (isBusy) {
        e.preventDefault();
        onInterrupt();
        return;
      }
      // REPL blur standard
      textareaRef.current?.blur();
      return;
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isBusy) {
        // Mid-Turn Steering (Anara Native Parity)
        if (inputMessage.trim() && onSteer) {
          const steerText = inputMessage.trim();
          setInputMessage("");
          onSteer(steerText);
        }
        return;
      }
      handleFormSubmit();
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items || items.length === 0) return;
    const files: File[] = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) files.push(file);
      }
    }
    if (files.length > 0) {
      e.preventDefault();
      const dt = new DataTransfer();
      files.forEach((f) => dt.items.add(f));
      handleAttachFiles(dt.files);
    }
  };

  const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB cap

  const handleAttachFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return;
    const validItems: AttachedItem[] = [];
    const validFiles: File[] = [];

    Array.from(files).forEach((f) => {
      if (f.size > MAX_FILE_SIZE_BYTES) {
        console.warn(`[Attachment] File ${f.name} exceeds 25MB limit.`);
        return;
      }
      const isDuplicate = attachedFiles.some(
        (existing) => existing.name === f.name && existing.sizeKb === Math.round(f.size / 1024)
      );
      if (isDuplicate) return;

      const ext = f.name.split(".").pop()?.toLowerCase() || "";
      const isImage = f.type.startsWith("image/");
      let previewUrl: string | undefined;
      if (isImage) {
        try {
          previewUrl = URL.createObjectURL(f);
        } catch {}
      }

      validItems.push({
        file: f,
        name: f.name,
        ext,
        sizeKb: Math.round(f.size / 1024),
        previewUrl,
      });
      validFiles.push(f);
    });

    if (validItems.length > 0) {
      setAttachedFiles((prev) => [...prev, ...validItems]);
      try {
        const dt = new DataTransfer();
        validFiles.forEach((file) => dt.items.add(file));
        onFileUpload(dt.files);
      } catch {
        onFileUpload(files);
      }
    }
  }, [attachedFiles, onFileUpload]);

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

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleAttachFiles(e.dataTransfer.files);
    }
  }, [handleAttachFiles]);

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

      {/* ── Sticky Plan / Todo Checklist Widget (Modular Anara Semantic Slot) ── */}
      {checklistData && (
        <DockPlanChecklist
          checklistData={checklistData}
          isExpanded={isPlanChecklistExpanded}
          onToggle={() => setIsPlanChecklistExpanded((v) => !v)}
          onApprovePlan={() => onApprovePlan?.(checklistData)}
          onRejectPlan={onRejectPlan ? () => onRejectPlan(checklistData) : undefined}
        />
      )}

      {/* ── INTERACTIVE QUESTION CARD WIZARD IN BOTTOM DOCK (OpenCode Style) ── */}
      {activeQuestion && !activeQuestion.isAnswered ? (
        <div className="w-full pointer-events-auto">
          <InteractiveQuestionCard
            data={activeQuestion}
            onSubmitAnswers={(qId, ans, dis) => onAnswerQuestion?.(qId, ans, dis)}
          />
        </div>
      ) : null}

      {/* ── Status Stack: Live Tool Execution Activity (Anara Engineering Standard) ── */}
      {liveToolProgress && (
        <div className="w-full flex items-center justify-between px-3 py-1.5 rounded-xl border border-cyan-400/25 bg-[#030712]/95 backdrop-blur-2xl font-mono text-xs text-cyan-200 select-none animate-fade-in shadow-[0_4px_20px_rgba(0,0,0,0.6)]">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping shrink-0" />
            <span className="font-bold text-slate-100 text-[11px] shrink-0">&gt; executing</span>
            <span className="text-cyan-300 font-semibold truncate text-[11.5px]">{liveToolProgress.toolName}</span>
            {liveToolProgress.summary && (
              <span className="text-slate-400 truncate text-[11px]">{liveToolProgress.summary}</span>
            )}
          </div>
          <button
            type="button"
            onClick={onInterrupt}
            className="px-2 py-0.5 rounded-md text-[10.5px] font-mono text-rose-300 hover:text-white bg-rose-500/15 hover:bg-rose-500/30 border border-rose-400/30 transition-all cursor-pointer shrink-0 ml-2 active:scale-95"
            title="Interrupt tool execution"
          >
            Stop
          </button>
        </div>
      )}

      {/* ── Modern Agent Prompt Card (True Obsidian Liquid Glass) ── */}
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
          {/* Isolated Glass Backing: Keep backdrop-filter off the hot editable path to avoid typing frame drops (Composer Dock) */}
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

          {/* Hidden File & Folder Inputs */}
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

        {/* Center Drag Handle (Anara Desktop Standard) */}
        <div
          onClick={() => setIsInputExpanded((v) => !v)}
          className="w-16 h-1 bg-white/20 hover:bg-white/35 rounded-full mx-auto -mt-0.5 mb-1 cursor-pointer transition-colors"
          title={isInputExpanded ? "Collapse composer" : "Expand composer"}
        />

        {/* Context & Git Telemetry Strip (Anara Desktop Standard) */}
        <div className="w-full flex items-center justify-between pb-1.5 border-b border-white/[0.06] text-[11px] font-mono select-none">
          {/* Left: Branch Indicator */}
          <div className="flex items-center gap-1.5 text-slate-300">
            <svg className="w-3.5 h-3.5 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7a3 3 0 100-6 3 3 0 000 6zm0 0v10m0 0a3 3 0 100 6 3 3 0 000-6zm8-4a3 3 0 100-6 3 3 0 000 6zm0 0v3a4 4 0 01-4 4h-4" />
            </svg>
            <span className="font-semibold text-slate-200">{gitStatus?.branch || "main"}</span>
          </div>

          {/* Right: Telemetry (Turns & Git Diff Delta) */}
          <div className="flex items-center gap-3 text-slate-400">
            {promptTurnsCount !== undefined && promptTurnsCount > 0 && (
              <span className="flex items-center gap-0.5 text-slate-300" title="Conversation Turns">
                <span className="text-slate-400">↑</span>
                <span>{promptTurnsCount}</span>
              </span>
            )}
            {(gitStatus?.insertions !== undefined || gitStatus?.deletions !== undefined) && (
              <span className="flex items-center gap-1.5 font-mono tabular-nums text-[10.5px]">
                {gitStatus.insertions ? <span className="text-emerald-400">+{gitStatus.insertions}</span> : null}
                {gitStatus.deletions ? <span className="text-rose-400">-{gitStatus.deletions}</span> : null}
              </span>
            )}
          </div>
        </div>

        {/* 1. Top Section: Input / Voice Waveform */}
        <div className={`w-full flex items-center gap-2 ${isInputExpanded ? "flex-1 min-h-0 overflow-hidden" : "min-h-[36px]"}`}>
          {interactionMode === "voice" && !inputMessage.trim() && attachedFiles.length === 0 ? (
            <DockAudioWaveform
              status={status}
              activeIntensity={activeIntensity}
              isMicActive={isMicActive}
              isMuted={isMuted}
            />
          ) : (
            <div className={`w-full flex flex-col gap-1.5 relative ${isInputExpanded ? "h-full flex-1 min-h-0" : ""}`}>
              <DockAttachmentChips
                attachedFiles={attachedFiles}
                onRemove={(idx) => setAttachedFiles((prev) => prev.filter((_, i) => i !== idx))}
              />

              {/* Multimodal Trigger Popover (@ Mentions & / Slash Commands) */}
              <DockTriggerPopover
                isOpen={isTriggerPopoverOpen}
                triggerKind={triggerKind}
                query={triggerQuery}
                onSelect={handleSelectTriggerItem}
                onClose={() => {
                  setIsTriggerPopoverOpen(false);
                  setTriggerKind(null);
                }}
                workspaceFiles={workspaceFiles}
                selectedIndex={triggerSelectedIndex}
                onSelectedIndexChange={setTriggerSelectedIndex}
              />

              {/* Textarea Form */}
              <form
                onSubmit={handleFormSubmit}
                className={`w-full flex ${isInputExpanded ? "h-full flex-1 min-h-0 items-stretch" : "items-stretch"} gap-1.5`}
              >
                <div className={`flex-1 min-w-0 flex flex-col ${isInputExpanded ? "h-full min-h-0" : ""}`}>
                  <textarea
                    ref={textareaRef}
                    rows={1}
                    value={inputMessage}
                    onChange={handleTextareaChange}
                    onKeyDown={handleKeyDown}
                    onPaste={handlePaste}
                    placeholder="What's on your mind? (Shift+Enter for newline, / for commands, @ for files)"
                    className={`w-full bg-transparent border-none py-1.5 px-1 text-xs sm:text-sm text-white placeholder:text-slate-500 focus:outline-none font-sans resize-none custom-scrollbar leading-relaxed ${
                      isInputOverflowed || isInputExpanded ? "overflow-y-auto" : "overflow-hidden"
                    } ${isInputExpanded ? "flex-1 h-full max-h-none" : ""}`}
                    style={isInputExpanded ? { minHeight: "140px" } : { maxHeight: "180px", minHeight: "36px" }}
                    autoFocus
                  />
                </div>

                {/* Fullscreen Expand / Clear buttons */}
                {(isInputOverflowed || isInputExpanded || inputMessage) && (
                  <div className={`shrink-0 flex flex-col items-center ${isInputOverflowed || isInputExpanded ? "justify-between" : "justify-end"} py-0.5`}>
                    {(isInputOverflowed || isInputExpanded) && (
                      <button
                        type="button"
                        onClick={() => setIsInputExpanded((v) => !v)}
                        className="w-6 h-6 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer active:scale-95"
                        title={isInputExpanded ? "Collapse input" : "Expand input"}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          {isInputExpanded ? (
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9L4 4m0 0l5 0m-5 0l0 5m6 6l5 5m0 0l-5 0m5 0l0-5" />
                          ) : (
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5m-6 6l-5 5m0 0h4m-4 0v-4m16 4l-5-5m5 5v-4m0 4h-4" />
                          )}
                        </svg>
                      </button>
                    )}
                    {inputMessage && (
                      <button
                        type="button"
                        onClick={() => {
                          setInputMessage("");
                          revokeAttachmentPreviews(attachedFiles);
                          setAttachedFiles([]);
                          if (textareaRef.current) textareaRef.current.style.height = "auto";
                          setIsInputExpanded(false);
                        }}
                        className="w-6 h-6 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-200 hover:bg-white/10 transition-all text-xs cursor-pointer active:scale-95"
                        title="Clear message"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}
                  </div>
                )}
              </form>
            </div>
          )}
        </div>

        {/* 2. Bottom Action Toolbar Row (Zero divider line, seamless obsidian glass) */}
        <div className="flex items-center justify-between gap-2 pt-1">
          {/* Left: [+] [Voice/Chat] [Plan/Build] [Model] */}
          <div className="flex items-center gap-2 flex-wrap min-w-0">
            {/* Attachment (+) */}
            <div className="relative shrink-0" data-dropdown-root="true">
              <button
                type="button"
                onClick={(e) => toggleDropdown("attach", e)}
                className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all cursor-pointer border ${
                  isAttachMenuOpen
                    ? "bg-white/15 border-white/30 text-white"
                    : "bg-white/[0.04] hover:bg-white/10 border-white/10 text-slate-300 hover:text-white hover:border-white/20"
                }`}
                title="Add attachment / file / folder"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
              </button>

              {isAttachMenuOpen && (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="absolute bottom-9 left-0 z-50 w-60 p-1.5 rounded-2xl bg-slate-950/95 border border-white/15 backdrop-blur-2xl shadow-2xl animate-scale-up space-y-1 text-xs font-mono"
                >
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full flex items-center gap-3 p-2 rounded-xl text-left hover:bg-white/10 text-slate-200 hover:text-white cursor-pointer transition-all"
                  >
                    <svg className="w-5 h-5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <div>
                      <p className="font-bold text-slate-200">Upload File</p>
                      <p className="text-[10px] text-slate-400 font-sans">PDF, Images, Text, Code</p>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      onFolderUpload();
                      closeDropdown();
                    }}
                    className="w-full flex items-center gap-3 p-2 rounded-xl text-left hover:bg-white/10 text-slate-200 hover:text-white cursor-pointer transition-all"
                  >
                    <svg className="w-5 h-5 text-amber-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                    <div>
                      <p className="font-bold text-slate-200">Import Local Folder</p>
                      <p className="text-[10px] text-slate-400 font-sans">Select project directory via native file dialog</p>
                    </div>
                  </button>
                </div>
              )}
            </div>

            {/* Interaction Mode: Voice vs Chat (Active in Main Workbench/Companion, hidden in pure Code Studio) */}
            {isInteractionModeVisible && (
              <div className="relative shrink-0" data-dropdown-root="true">
                <button
                  type="button"
                  onClick={(e) => toggleDropdown("mode", e)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-medium font-mono transition-all cursor-pointer ${
                    isVoiceChatDropdownOpen
                      ? "bg-white/15 border-white/25 text-white"
                      : "bg-white/[0.04] hover:bg-white/10 border-white/10 text-slate-300 hover:text-white"
                  }`}
                  title="Select Interaction Mode: Voice or Chat"
                >
                  {interactionMode === "voice" ? (
                    <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  )}
                  <span className="font-semibold">{interactionMode === "voice" ? "Voice" : "Chat"}</span>
                  <svg className="w-3 h-3 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {isVoiceChatDropdownOpen && (
                  <div
                    onClick={(e) => e.stopPropagation()}
                    className="absolute bottom-9 left-0 z-50 w-60 p-1.5 rounded-2xl bg-slate-950/95 border border-white/15 backdrop-blur-2xl shadow-2xl animate-scale-up space-y-1 text-xs font-mono"
                  >
                    <button
                      type="button"
                      onClick={() => {
                        onSetInteractionMode?.("voice");
                        closeDropdown();
                      }}
                      className={`w-full flex items-start gap-2.5 p-2 rounded-xl text-left transition-all cursor-pointer ${
                        interactionMode === "voice" ? "bg-white/15 text-white border border-white/20" : "hover:bg-white/5 text-slate-300"
                      }`}
                    >
                      <div className="w-6 h-6 rounded-lg bg-cyan-500/15 border border-cyan-400/30 flex items-center justify-center shrink-0 mt-0.5">
                        <svg className="w-3.5 h-3.5 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                        </svg>
                      </div>
                      <div>
                        <p className="font-bold">Voice Mode</p>
                        <p className="text-[10px] text-slate-400">Live bidirectional voice interaction & 3D avatar active.</p>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        onSetInteractionMode?.("chat");
                        closeDropdown();
                      }}
                      className={`w-full flex items-start gap-2.5 p-2 rounded-xl text-left transition-all cursor-pointer ${
                        interactionMode === "chat" ? "bg-white/15 text-white border border-white/20" : "hover:bg-white/5 text-slate-300"
                      }`}
                    >
                      <div className="w-6 h-6 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center shrink-0 mt-0.5">
                        <svg className="w-3.5 h-3.5 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                      </div>
                      <div>
                        <p className="font-bold">Chat Mode</p>
                        <p className="text-[10px] text-slate-400">Pure silent text workspace (full dual-pane workbench).</p>
                      </div>
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Plan / Build Mode Toggle (Only visible in explicit coding workstation, e.g. Anara Code) */}
            {isAgentToggleVisible && (
              <div className="relative shrink-0" data-dropdown-root="true">
                <button
                  type="button"
                  onClick={(e) => toggleDropdown("agentMode", e)}
                  className={`flex items-center gap-1.5 py-1 px-2.5 rounded-lg border text-[11px] font-medium font-mono transition-all cursor-pointer ${
                    agentMode === "plan"
                      ? "pill-plan-mode font-bold"
                      : "pill-build-mode font-bold"
                  }`}
                  title="Select Agent Mode: Plan Mode or Build Mode"
                >
                  {agentMode === "plan" ? (
                    <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5 text-amber-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  )}
                  <span className="font-semibold tracking-wide">{agentMode === "plan" ? "Plan" : "Build"}</span>
                  <svg className="w-3 h-3 opacity-60 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {isAgentModeDropdownOpen && (
                  <div
                    onClick={(e) => e.stopPropagation()}
                    className="absolute bottom-9 left-0 z-50 w-64 p-1.5 rounded-2xl bg-slate-950/95 border border-white/15 backdrop-blur-2xl shadow-2xl animate-scale-up space-y-1 text-xs font-mono"
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setAgentMode("plan");
                        closeDropdown();
                      }}
                      className={`w-full flex items-start gap-2.5 p-2 rounded-xl text-left transition-all cursor-pointer ${
                        agentMode === "plan" ? "bg-cyan-500/20 text-cyan-100 border border-cyan-400/40" : "hover:bg-white/5 text-slate-300"
                      }`}
                    >
                      <div className="w-6 h-6 rounded-lg bg-cyan-500/15 border border-cyan-400/30 flex items-center justify-center shrink-0 mt-0.5">
                        <svg className="w-3.5 h-3.5 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                        </svg>
                      </div>
                      <div>
                        <p className="font-bold">Plan Mode</p>
                        <p className="text-[10px] text-slate-400">Research &amp; compose step-by-step plans without modifying files.</p>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setAgentMode("build");
                        closeDropdown();
                      }}
                      className={`w-full flex items-start gap-2.5 p-2 rounded-xl text-left transition-all cursor-pointer ${
                        agentMode === "build" ? "bg-amber-500/20 text-amber-100 border border-amber-400/40" : "hover:bg-white/5 text-slate-300"
                      }`}
                    >
                      <div className="w-6 h-6 rounded-lg bg-amber-500/15 border border-amber-400/30 flex items-center justify-center shrink-0 mt-0.5">
                        <svg className="w-3.5 h-3.5 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                      </div>
                      <div>
                        <p className="font-bold">Build Mode</p>
                        <p className="text-[10px] text-slate-400">Autonomous execution, write files, and complete tasks.</p>
                      </div>
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* AI Model Selector Button & Popover */}
            <div className="relative shrink-0" data-dropdown-root="true">
              {(() => {
                const cur = models.find((m) => m.id === activeModelId) || models[0];
                const displayName = formatModelDisplayName(cur?.name || cur?.id || activeModelId);
                const modalities = getModelModalities(cur);
                const hasVision = modalities.some((m) => m.id === "image");
                const hasVideo = modalities.some((m) => m.id === "video");

                return (
                  <button
                    type="button"
                    onClick={(e) => toggleDropdown("model", e)}
                    title={`Active Model: ${cur?.id || activeModelId} (${modalities.map((m) => m.label).join(", ")})`}
                    className={`flex items-center gap-1.5 py-1 px-2.5 rounded-lg border text-[11px] font-medium font-mono transition-colors cursor-pointer select-none ${
                      isModelDropdownOpen
                        ? "bg-white/[0.08] border-white/20 text-white"
                        : "bg-white/[0.03] border-white/[0.08] hover:border-white/[0.16] hover:bg-white/[0.06] text-zinc-300 hover:text-white"
                    }`}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
                    <span className="truncate max-w-[120px] sm:max-w-[170px] font-semibold tracking-tight" suppressHydrationWarning>
                      {displayName}
                    </span>
                    <svg className="w-3 h-3 text-zinc-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                );
              })()}

              <ModelSelectorDropdown
                isOpen={isModelDropdownOpen}
                onClose={() => setIsModelDropdownOpen(false)}
                models={models}
                activeModelId={activeModelId}
                onSelectModel={onSelectModel}
                interactionMode={interactionMode}
                reasoningEffort={reasoningEffort}
                onSelectReasoningEffort={onSelectReasoningEffort as any}
              />
            </div>

            {/* Dedicated Reasoning Pill (Directly next to Model Selector, shown when model supports reasoning) */}
            {(() => {
              const cur = models.find((m) => m.id === activeModelId) || models[0];
              const hasReasoning = isReasoningSupported(cur);
              if (!hasReasoning || interactionMode === "voice") return null;
              return (
                <ReasoningPill
                  model={cur}
                  modelId={cur?.id || activeModelId}
                  reasoningEffort={reasoningEffort}
                  onSelectReasoningEffort={(effort) => {
                    onSelectReasoningEffort?.(effort as any);
                    // Sibling model resolution for providers with slug variants (e.g. 9router ag/gemini-3.8-flash-low -> ag/gemini-3.8-flash-high)
                    const siblingId = resolveSiblingTierModelId(activeModelId, effort as any, models);
                    if (siblingId && siblingId !== activeModelId) {
                      onSelectModel(siblingId);
                    }
                  }}
                  modelName={formatModelDisplayName(cur?.name || cur?.id || activeModelId)}
                />
              );
            })()}
          </div>

          {/* Right: Mic Quick Button, Interrupt & Send Button */}
          <div className="flex items-center gap-1.5 shrink-0">
            {interactionMode === "voice" && status === "speaking" && (
              <button
                type="button"
                onClick={onInterrupt}
                className="p-1 px-2 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 transition-all active:scale-95 cursor-pointer flex items-center gap-1.5 text-[11px] font-mono"
                title="Interrupt AI"
              >
                <span className="w-2 h-2 rounded-xs bg-rose-400" />
                <span className="text-[10px]">Interrupt</span>
              </button>
            )}

            {/* Voice Mode Mic Toggle Button */}
            {interactionMode === "voice" && (
              !isMicActive ? (
                <button
                  type="button"
                  onClick={() => {
                    if (!activeSessionId) {
                      onNewSession();
                    }
                    onStartSession();
                  }}
                  disabled={!isConnected}
                  className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 text-cyan-100 text-xs font-semibold shadow-[0_0_15px_rgba(34,211,238,0.2)] cursor-pointer active:scale-95 transition-all font-mono"
                  title="Click to start bidirectional voice chat"
                >
                  <svg className="w-3.5 h-3.5 text-cyan-300 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                  </svg>
                  <span>Start Chat</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onToggleMute}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-xl border text-xs font-semibold transition-all cursor-pointer font-mono ${
                    isMuted
                      ? "bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-[0_0_10px_rgba(244,63,94,0.3)]"
                      : "bg-cyan-500/20 text-cyan-300 border-cyan-400/40 shadow-[0_0_8px_rgba(34,211,238,0.25)] animate-pulse"
                  }`}
                  title={isMuted ? "Unmute Mic" : "Mute Mic"}
                >
                  {isMuted ? (
                    <>
                      <svg className="w-3.5 h-3.5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                      </svg>
                      <span>Unmute</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-3.5 h-3.5 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                      </svg>
                      <span>Mute</span>
                    </>
                  )}
                </button>
              )
            )}

            {/* Chat Mode Send / Stop Button (Anara Desktop Standard) */}
            {interactionMode === "chat" && (
              status === "thinking" || status === "speaking" || Boolean(liveToolProgress && liveToolProgress.status === "running") ? (
                <button
                  type="button"
                  onClick={onInterrupt}
                  className="w-8 h-8 rounded-full flex items-center justify-center transition-all duration-200 cursor-pointer bg-rose-500/20 hover:bg-rose-500/35 text-rose-200 border border-rose-400/40 shadow-sm active:scale-95 group"
                  title="Stop generating response (Escape or Click)"
                >
                  <div className="w-2.5 h-2.5 rounded-[2px] bg-rose-400 group-hover:bg-white transition-colors shadow-sm" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => handleFormSubmit()}
                  disabled={!inputMessage.trim() && attachedFiles.length === 0}
                  className={`h-8 px-2.5 rounded-full flex items-center gap-1 transition-all duration-200 cursor-pointer shadow-md ${
                    inputMessage.trim() || attachedFiles.length > 0
                      ? "bg-[#ECEEF2] hover:bg-white text-[#0F131A] shadow-[0_0_15px_rgba(255,255,255,0.25)] active:scale-95 font-semibold"
                      : "bg-white/[0.06] text-slate-500 border border-white/10 cursor-not-allowed opacity-40"
                  }`}
                  title="Send prompt (Enter, Shift+Enter for new line)"
                >
                  <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                    <path d="M12 3v10m0-10l-4 4m4-4l4 4M5 14v4a2 2 0 002 2h10a2 2 0 002-2v-4" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" fill="none" />
                  </svg>
                  <svg className="w-3 h-3 opacity-60 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              )
            )}
          </div>
        </div>
      </div>
      )}
    </footer>
  );
}
