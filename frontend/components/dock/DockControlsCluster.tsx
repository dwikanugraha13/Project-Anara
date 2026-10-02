"use client";

import React, { useState, useEffect, useCallback } from "react";
import ModelSelectorDropdown, { AIModelInfo, isReasoningSupported } from "./ModelSelectorDropdown";
import ReasoningPill from "./ReasoningPill";
import { getModelModalities, resolveSiblingTierModelId } from "@/lib/reasoningEffort";
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
  agentMode: "plan" | "build";
  setAgentMode: (mode: "plan" | "build") => void;
  isAgentToggleVisible: boolean;
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
}

/**
 * DockControlsCluster — Bottom action toolbar row (Zero divider line, seamless obsidian glass).
 * Houses attachments, interaction mode, agent mode, model picker, reasoning pill, mic, and send/stop.
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
}: DockControlsClusterProps) {
  const [isAttachMenuOpen, setIsAttachMenuOpen] = useState(false);
  const [isVoiceChatDropdownOpen, setIsVoiceChatDropdownOpen] = useState(false);
  const [isAgentModeDropdownOpen, setIsAgentModeDropdownOpen] = useState(false);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);

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

  return (
    <div className="flex items-center justify-between gap-2 pt-1">
      {/* Left Cluster: [+] [Voice/Chat] [Plan/Build] [Model] [Reasoning] */}
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

        {/* Interaction Mode: Voice vs Chat */}
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
        )}

        {/* Plan / Build Mode Toggle */}
        {isAgentToggleVisible && (
          <div className="relative shrink-0" data-dropdown-root="true">
            <button
              type="button"
              onClick={(e) => toggleDropdown("agentMode", e)}
              className={`flex items-center gap-1.5 py-1 px-2.5 rounded-lg border text-[11px] font-medium font-mono transition-all cursor-pointer ${
                agentMode === "plan" ? "pill-plan-mode font-bold" : "pill-build-mode font-bold"
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

        {/* Dedicated Reasoning Pill */}
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

      {/* Right Cluster: Quick Mic, Interrupt & Send Button */}
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

        {/* Chat Mode Send / Stop Button */}
        {interactionMode === "chat" && (
          isBusy ? (
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
              onClick={onSend}
              disabled={!canSend}
              className={`h-8 px-2.5 rounded-full flex items-center gap-1 transition-all duration-200 cursor-pointer shadow-md ${
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
          )
        )}
      </div>
    </div>
  );
}
