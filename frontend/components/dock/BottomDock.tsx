"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import ModelSelectorDropdown, { AIModelInfo } from "./ModelSelectorDropdown";
import InteractiveQuestionCard, { InteractiveQuestionData } from "../chat/InteractiveQuestionCard";
import { DockPlanChecklist } from "./DockPlanChecklist";
import { DockAudioWaveform } from "./DockAudioWaveform";
import { DockAttachmentChips } from "./DockAttachmentChips";
import type { ToolProgressPayload } from "@/hooks/useWebSocket";

export type AssistantStatus = "idle" | "listening" | "thinking" | "speaking";

export interface AttachedItem {
  file?: File;
  name: string;
  ext: string;
  sizeKb: number;
  previewUrl?: string;
  content?: string;
}

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
}: BottomDockProps) {
  const isAgentToggleVisible = showAgentModeToggle !== undefined ? showAgentModeToggle : embedded;
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

  const closeDropdown = useCallback(() => {
    setIsAttachMenuOpen(false);
    setIsVoiceChatDropdownOpen(false);
    setIsAgentModeDropdownOpen(false);
    setIsModelDropdownOpen(false);
  }, []);

  useEffect(() => {
    const onWindowClick = () => closeDropdown();
    window.addEventListener("click", onWindowClick);
    return () => window.removeEventListener("click", onWindowClick);
  }, [closeDropdown]);

  const toggleDropdown = (which: "attach" | "mode" | "agentMode" | "model", e: React.MouseEvent) => {
    e.stopPropagation();
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

  // Measure dock height for timeline spacer
  useEffect(() => {
    if (footerDockRef.current) {
      onHeightChange?.(footerDockRef.current.offsetHeight);
    }
  }, [
    inputMessage,
    isInputExpanded,
    attachedFiles.length,
    checklistData,
    isPlanChecklistExpanded,
    onHeightChange,
  ]);

  // Textarea auto-resize
  useEffect(() => {
    const el = textareaRef.current;
    if (!el || isInputExpanded) return;
    if (!inputMessage) {
      el.style.height = "32px";
      setIsInputOverflowed(false);
      return;
    }
    el.style.height = "auto";
    const nextH = Math.min(el.scrollHeight, 180);
    el.style.height = `${nextH}px`;
    setIsInputOverflowed(el.scrollHeight > 180);
  }, [inputMessage, isInputExpanded]);

  const handleFormSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputMessage.trim() && attachedFiles.length === 0) return;
    onSend(inputMessage, agentMode);
    setInputMessage("");
    setAttachedFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setIsInputExpanded(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleFormSubmit();
    }
  };

  const handleAttachFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const newItems: AttachedItem[] = Array.from(files).map((f) => {
      const ext = f.name.split(".").pop() || "";
      return {
        file: f,
        name: f.name,
        ext,
        sizeKb: Math.round(f.size / 1024),
      };
    });
    setAttachedFiles((prev) => [...prev, ...newItems]);
    onFileUpload(files);
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.types && Array.from(e.dataTransfer.types).includes("Files")) {
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = "copy";
      setIsDragOver(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      handleAttachFiles(e.dataTransfer.files);
    }
  }, []);

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
      style={!embedded ? { left: "var(--sidebar-width, 380px)", right: 0 } : undefined}
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
      ) : (
        /* ── Modern Agent Prompt Card ── */
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`w-full liquid-glass rounded-2xl p-2.5 px-3.5 shadow-2xl flex flex-col gap-2 shadow-black/90 pointer-events-auto backdrop-blur-3xl relative transition-[border-color,background-color,box-shadow] duration-200 ${
            isDragOver
              ? "border-cyan-400 bg-cyan-950/40 ring-2 ring-cyan-400/50 shadow-[0_0_30px_rgba(34,211,238,0.25)]"
              : "border-white/15 hover:border-white/25"
          } ${isInputExpanded ? "h-full flex-1 min-h-0" : ""}`}
        >
          {/* Top Specular Sheen Highlight */}
          <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent pointer-events-none z-10" />
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
            accept=".pdf,.txt,.md,.py,.js,.ts,.tsx,.json,.csv,image/*"
            className="hidden"
            onChange={(e) => {
              handleAttachFiles(e.target.files);
              e.target.value = "";
            }}
          />

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
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask anything, / for commands, @ for context..."
                    className={`w-full bg-transparent border-none py-1.5 px-1 text-xs sm:text-sm text-white placeholder:text-slate-500 focus:outline-none font-sans resize-none custom-scrollbar leading-relaxed overflow-y-auto ${
                      isInputExpanded ? "flex-1 h-full max-h-none" : ""
                    }`}
                    style={isInputExpanded ? { minHeight: "140px" } : { maxHeight: "180px", minHeight: "32px" }}
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
                        title={isInputExpanded ? "Kecilkan input" : "Perbesar input"}
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
                          setAttachedFiles([]);
                          if (textareaRef.current) textareaRef.current.style.height = "auto";
                          setIsInputExpanded(false);
                        }}
                        className="w-6 h-6 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-200 hover:bg-white/10 transition-all text-xs cursor-pointer active:scale-95"
                        title="Clear message"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                )}
              </form>
            </div>
          )}
        </div>

        {/* 2. Bottom Action Toolbar Row */}
        <div className="flex items-center justify-between gap-2 pt-1 border-t border-white/[0.07]">
          {/* Left: [+] [Voice/Chat] [Plan/Build] [Model] */}
          <div className="flex items-center gap-2 flex-wrap min-w-0">
            {/* Attachment (+) */}
            <div className="relative shrink-0">
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
                <span className="text-sm font-light">＋</span>
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
                      <p className="text-[10px] text-slate-400 font-sans">PDF, Gambar, Teks, Code</p>
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
                      <p className="font-bold text-slate-200">Import Folder Lokal</p>
                      <p className="text-[10px] text-slate-400 font-sans">Select original folder via Windows dialog</p>
                    </div>
                  </button>
                </div>
              )}
            </div>

            {/* Interaction Mode: Voice vs Chat (Only on 3D Companion page, hidden completely in embedded Code Studio) */}
            {!embedded && (
              <div className="relative shrink-0">
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
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 02-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
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
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 02-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
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
                        <p className="text-[10px] text-slate-400">Workspace teks hening murni (full dual-pane workbench).</p>
                      </div>
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Plan / Build Mode Toggle (Only visible in explicit coding workstation, e.g. Anara Code) */}
            {isAgentToggleVisible && (
              <div className="relative shrink-0">
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
            <div className="relative shrink-0">
              {(() => {
                const cur = models.find((m) => m.id === activeModelId) || models[0];
                return (
                  <button
                    type="button"
                    onClick={(e) => toggleDropdown("model", e)}
                    title="Select AI Model"
                    className={`flex items-center gap-1.5 py-1 px-2.5 rounded-lg border text-[11px] font-medium font-mono transition-all cursor-pointer ${
                      isModelDropdownOpen
                        ? "bg-white/15 border-white/30 text-white"
                        : "bg-white/[0.04] border-white/10 text-slate-300 hover:text-white hover:border-white/20"
                    }`}
                  >
                    <span className="truncate max-w-[120px] sm:max-w-[160px] font-semibold" suppressHydrationWarning>
                      {cur?.name || (interactionMode === "voice" ? "Model Live" : "Model AI")}
                    </span>
                    <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
              />
            </div>
          </div>

          {/* Right: Mic Quick Button, Interrupt & Send Button */}
          <div className="flex items-center gap-1.5 shrink-0">
            {status === "speaking" && (
              <button
                onClick={onInterrupt}
                className="p-1 px-2 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 transition-all active:scale-95 cursor-pointer flex items-center gap-1 text-[11px] font-mono"
                title="Sela AI"
              >
                <span className="text-[10px]">■ Sela</span>
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
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 02-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
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
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 02-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                      </svg>
                      <span>Mute</span>
                    </>
                  )}
                </button>
              )
            )}

            {/* Chat Mode Send / Stop Button */}
            {interactionMode === "chat" && (
              status === "thinking" || status === "speaking" || liveToolProgress !== null ? (
                <button
                  type="button"
                  onClick={onInterrupt}
                  className="w-7 h-7 rounded-lg flex items-center justify-center transition-all duration-200 cursor-pointer shadow-md bg-rose-500/20 hover:bg-rose-500/35 text-rose-200 border border-rose-400/40 shadow-[0_0_12px_rgba(244,63,94,0.3)] active:scale-95"
                  title="Hentikan pembuatan respon AI (Stop)"
                >
                  <div className="w-2.5 h-2.5 rounded-[2px] bg-rose-300 shadow-sm animate-pulse" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => handleFormSubmit()}
                  disabled={!inputMessage.trim() && attachedFiles.length === 0}
                  className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all duration-200 cursor-pointer shadow-md ${
                    inputMessage.trim() || attachedFiles.length > 0
                      ? "bg-gradient-to-tr from-cyan-400 via-teal-500 to-indigo-500 text-white hover:scale-105 active:scale-95 shadow-[0_0_16px_rgba(34,211,238,0.45)] border border-cyan-300/60"
                      : "bg-white/[0.04] text-slate-600 border border-white/10 cursor-not-allowed opacity-50"
                  }`}
                  title="Send message (Enter, Shift+Enter for new line)"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 10l7-7m0 0l7 7m-7-7v18" />
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
