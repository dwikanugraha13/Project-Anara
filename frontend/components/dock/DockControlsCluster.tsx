"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import ModelSelectorDropdown, { AIModelInfo, isReasoningSupported } from "./ModelSelectorDropdown";
import ReasoningPill from "./ReasoningPill";
import ApprovalModePill from "./ApprovalModePill";
import { getModelModalities, findModelById } from "@/lib/reasoningEffort";
import { formatModelDisplayName } from "@/lib/modelFormat";
import type { AssistantStatus } from "./BottomDock";

export interface DockControlsClusterProps {
  models: AIModelInfo[];
  activeModelId: string;
  onSelectModel: (id: string) => void;
  reasoningEffort?: "off" | "low" | "medium" | "high" | string;
  onSelectReasoningEffort?: (effort: "off" | "low" | "medium" | "high") => void;
  interactionMode: "voice" | "chat";
  onSetInteractionMode?: (mode: "voice" | "chat") => void;
  isInteractionModeVisible: boolean;
  agentMode?: "plan" | "build";
  setAgentMode?: (mode: "plan" | "build") => void;
  isAgentToggleVisible?: boolean;
  status: AssistantStatus;
  isMicActive: boolean;
  isMuted: boolean;
  onToggleMute: () => void;
  onStartSession: () => void;
  onInterrupt: () => void;
  isConnected: boolean;
  activeSessionId: number | null;
  onNewSession: () => void;
  onFolderUpload: () => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  isBusy: boolean;
  canSend: boolean;
  onSend: () => void;
  compact?: boolean;
  isCodeStudio?: boolean;
}

/**
 * DockControlsCluster — Responsive bottom action toolbar row.
 * - Dynamic width awareness: When the agent bar is wide, model button expands automatically,
 *   and reasoning & approval stay on the top line as default.
 * - When the agent bar is narrowed (< 430px in Code Studio), reasoning and approval mode
 *   drop down cleanly to the row below.
 */
export function DockControlsCluster({
  models,
  activeModelId,
  onSelectModel,
  reasoningEffort,
  onSelectReasoningEffort,
  interactionMode,
  onSetInteractionMode,
  isInteractionModeVisible,
  agentMode,
  setAgentMode,
  isAgentToggleVisible,
  status,
  isMicActive,
  isMuted,
  onToggleMute,
  onStartSession,
  onInterrupt,
  isConnected,
  activeSessionId,
  onNewSession,
  onFolderUpload,
  fileInputRef,
  isBusy,
  canSend,
  onSend,
  compact = false,
  isCodeStudio = false,
}: DockControlsClusterProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(600);

  const [isAttachMenuOpen, setIsAttachMenuOpen] = useState(false);
  const [isVoiceChatDropdownOpen, setIsVoiceChatDropdownOpen] = useState(false);
  const [isAgentModeDropdownOpen, setIsAgentModeDropdownOpen] = useState(false);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);

  // Measure container width dynamically to adapt between 1-tier and 2-tier layouts
  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setContainerWidth(entry.contentRect.width);
        }
      }
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

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

  // Condition to drop reasoning & approval to the bottom row
  const isNarrow = isCodeStudio && containerWidth < 430;

  // ── Render Helpers ──

  const renderAttachmentButton = () => (
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
            onClick={() => {
              fileInputRef.current?.click();
              closeDropdown();
            }}
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
  );

  const renderInteractionMode = () => {
    if (!isInteractionModeVisible) return null;
    return (
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
                <p className="text-[10px] text-slate-400">Live bidirectional voice interaction &amp; 3D avatar active.</p>
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
    );
  };

  const renderModelSelector = (flexibleWidth: boolean) => {
    const cur = findModelById(models, activeModelId) || { id: activeModelId, name: activeModelId, supports_reasoning: true };
    const displayName = formatModelDisplayName(cur?.name || cur?.id || activeModelId);
    const modalities = getModelModalities(cur);

    return (
      <div
        className={`relative min-w-0 ${
          flexibleWidth
            ? "flex-1 max-w-[320px]"
            : "shrink-0 max-w-[200px] sm:max-w-[280px]"
        }`}
        data-dropdown-root="true"
      >
        <button
          type="button"
          onClick={(e) => toggleDropdown("model", e)}
          title={`Active Model: ${cur?.id || activeModelId} (${modalities.map((m) => m.label).join(", ")})`}
          className={`flex items-center gap-1.5 py-1 rounded-lg border text-[11px] font-medium font-mono transition-colors cursor-pointer select-none min-w-0 w-full justify-between px-2.5 ${
            isModelDropdownOpen
              ? "bg-white/[0.08] border-white/20 text-white"
              : "bg-white/[0.03] border-white/[0.08] hover:border-white/[0.16] hover:bg-white/[0.06] text-zinc-300 hover:text-white"
          }`}
        >
          <span className="truncate font-semibold tracking-tight min-w-0" suppressHydrationWarning>
            {displayName}
          </span>
          <svg className="w-3 h-3 text-zinc-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

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
    );
  };

  const renderReasoningPill = (isCompactPill: boolean) => {
    const cur = findModelById(models, activeModelId) || { id: activeModelId, name: activeModelId, supports_reasoning: true };
    const hasReasoning = isReasoningSupported(cur);
    if (!hasReasoning || interactionMode === "voice") return null;
    return (
      <ReasoningPill
        model={cur}
        modelId={cur?.id || activeModelId}
        reasoningEffort={reasoningEffort}
        onSelectReasoningEffort={(effort) => {
          onSelectReasoningEffort?.(effort as any);
        }}
        modelName={formatModelDisplayName(cur?.name || cur?.id || activeModelId)}
        compact={isCompactPill}
      />
    );
  };

  const renderApprovalModePill = (isCompactPill: boolean) => {
    if (interactionMode === "voice") return null;
    return <ApprovalModePill compact={isCompactPill} />;
  };

  const renderSendStopButton = (isCompactButton: boolean) => {
    if (interactionMode === "voice") {
      if (status === "speaking") {
        return (
          <button
            type="button"
            onClick={onInterrupt}
            className="p-1 px-2 rounded-lg bg-rose-500/20 hover:bg-rose-500/35 text-rose-200 border border-rose-400/40 transition-all active:scale-95 cursor-pointer flex items-center gap-1.5 text-[11px] font-mono shrink-0"
            title="Interrupt AI"
          >
            <span className="w-2 h-2 rounded-xs bg-rose-400" />
            <span className="text-[10px]">Interrupt</span>
          </button>
        );
      }
      return !isMicActive ? (
        <button
          type="button"
          onClick={() => {
            if (!activeSessionId) onNewSession();
            onStartSession();
          }}
          disabled={!isConnected}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 text-cyan-100 text-xs font-semibold shadow-[0_0_15px_rgba(34,211,238,0.2)] cursor-pointer active:scale-95 transition-all font-mono shrink-0"
          title="Click to start bidirectional voice chat"
        >
          <svg className="w-3.5 h-3.5 text-cyan-300 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
          <span>Start</span>
        </button>
      ) : (
        <button
          type="button"
          onClick={onToggleMute}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-xl border text-xs font-semibold transition-all cursor-pointer font-mono shrink-0 ${
            isMuted
              ? "bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-[0_0_10px_rgba(244,63,94,0.3)]"
              : "bg-cyan-500/20 text-cyan-300 border-cyan-400/40 shadow-[0_0_8px_rgba(34,211,238,0.25)] animate-pulse"
          }`}
          title={isMuted ? "Unmute Mic" : "Mute Mic"}
        >
          <span>{isMuted ? "Unmute" : "Mute"}</span>
        </button>
      );
    }

    // Chat Mode Send / Stop
    if (isBusy) {
      return (
        <button
          type="button"
          onClick={onInterrupt}
          className={`${isCompactButton ? "w-7 h-7" : "w-8 h-8"} rounded-full flex items-center justify-center transition-all duration-200 cursor-pointer bg-rose-500/20 hover:bg-rose-500/35 text-rose-200 border border-rose-400/40 shadow-sm active:scale-95 group shrink-0`}
          title="Stop generating response (Escape or Click)"
        >
          <div className="w-2.5 h-2.5 rounded-[2px] bg-rose-400 group-hover:bg-white transition-colors shadow-sm" />
        </button>
      );
    }

    if (isCompactButton) {
      return (
        <button
          type="button"
          onClick={onSend}
          disabled={!canSend}
          className={`w-7 h-7 rounded-full flex items-center justify-center transition-all duration-200 cursor-pointer shadow-md shrink-0 ${
            canSend
              ? "bg-[#ECEEF2] hover:bg-white text-[#0F131A] shadow-[0_0_12px_rgba(255,255,255,0.25)] active:scale-95 font-semibold"
              : "bg-white/[0.06] text-slate-500 border border-white/10 cursor-not-allowed opacity-40"
          }`}
          title="Send prompt (Enter)"
        >
          <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
            <path d="M12 3v10m0-10l-4 4m4-4l4 4M5 14v4a2 2 0 002 2h10a2 2 0 002-2v-4" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
        </button>
      );
    }

    return (
      <button
        type="button"
        onClick={onSend}
        disabled={!canSend}
        className={`h-8 px-2.5 rounded-full flex items-center gap-1 transition-all duration-200 cursor-pointer shadow-md shrink-0 ${
          canSend
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
    );
  };

  return (
    <div ref={containerRef} className="w-full">
      {/* ── 2-TIER LAYOUT (Used when narrowed in Code Studio) ── */}
      {isNarrow ? (
        <div className="flex flex-col gap-1.5 w-full min-w-0 pt-0.5 animate-in fade-in duration-150">
          {/* Row 1: Attachment + Model Selector (widens flexibly) on Left, Send/Stop on Right */}
          <div className="flex items-center justify-between gap-1.5 w-full min-w-0">
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              {renderAttachmentButton()}
              {renderModelSelector(true)}
            </div>
            <div className="shrink-0 flex items-center gap-1">
              {renderSendStopButton(true)}
            </div>
          </div>

          {/* Row 2 (Turun di bawah): [ Reasoning Pill ] [ Approval Mode Pill ] */}
          <div className="flex items-center gap-1.5 w-full min-w-0 pt-0.5">
            {renderReasoningPill(true)}
            {renderApprovalModePill(true)}
          </div>
        </div>
      ) : (
        /* ── 1-TIER DEFAULT LAYOUT (When wide in Code Studio, or on Desktop) ── */
        <div className="flex items-center justify-between gap-2 pt-1 w-full animate-in fade-in duration-150">
          {/* Left Cluster: [+] [Voice/Chat] + Model Selector (expands as bar widens) */}
          <div className="flex items-center gap-1.5 min-w-0 flex-1">
            {renderAttachmentButton()}
            {renderInteractionMode()}
            {renderModelSelector(true)}
          </div>

          {/* Right Cluster: [Reasoning] [Approval] [Send/Stop] */}
          <div className="flex items-center gap-1.5 shrink-0 justify-end">
            {renderReasoningPill(false)}
            {renderApprovalModePill(false)}
            {renderSendStopButton(false)}
          </div>
        </div>
      )}
    </div>
  );
}
