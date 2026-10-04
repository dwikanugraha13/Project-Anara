"use client";

import React, { useRef, useEffect, useState, useMemo, useCallback } from "react";
import AgentMarkdown from "./AgentMarkdown";
import AgentToolCard, { ToolRunGroupCard, ExplorationGroupCard, ThinkingCard } from "./AgentToolCard";
import InteractiveQuestionCard from "./InteractiveQuestionCard";
import { ToolRunTicker } from "./ToolRunTicker";
import FindBar from "./FindBar";
import type { TranscriptItem, AssistantStatus } from "../workbench/AnaraWorkbench";
import type { ToolProgressPayload } from "@/hooks/useWebSocket";

export interface ChatTimelineProps {
  transcript: TranscriptItem[];
  status: AssistantStatus;
  activeSessionId?: number;
  activeSpeaker?: string | null;
  activeModelId?: string;
  liveToolProgress?: ToolProgressPayload | null;
  activeThinkingText?: string | null;
  footerDockHeight?: number;
  onApprovePlan?: (plan?: any) => void;
  onRejectPlan?: () => void;
  onOpenFile?: (path: string, fileName?: string) => void;
  onOpenLightbox?: (data: { url: string; title: string; sourceDomain?: string; sourceUrl?: string; prompt?: string }) => void;
  onDismissVisual?: () => void;
  onSelectPrompt?: (prompt: string) => void;
  onAnswerQuestion?: (questionId: string, answers: any, dismissed?: boolean) => void;
}

export default function ChatTimeline({
  transcript,
  status,
  activeSessionId,
  activeSpeaker,
  activeModelId,
  liveToolProgress = null,
  activeThinkingText = null,
  footerDockHeight = 120,
  onApprovePlan,
  onRejectPlan,
  onOpenFile,
  onOpenLightbox,
  onDismissVisual,
  onSelectPrompt,
  onAnswerQuestion,
}: ChatTimelineProps) {
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isFollowingRef = useRef(true);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [hasUnread, setHasUnread] = useState(false);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [copiedMessageIndex, setCopiedMessageIndex] = useState<number | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editText, setEditText] = useState<string>("");

  // In-Conversation Find Bar State (Ctrl+F)
  const [isFindOpen, setIsFindOpen] = useState(false);
  const [findMatches, setFindMatches] = useState<number[]>([]);
  const [activeMatchIdx, setActiveMatchIdx] = useState<number>(0);
  const messageItemRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Global Ctrl+F / Cmd+F shortcut to open FindBar
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        setIsFindOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleFindSearch = useCallback((query: string) => {
    if (!query.trim()) {
      setFindMatches([]);
      setActiveMatchIdx(0);
      return 0;
    }
    const qLower = query.toLowerCase();
    const matches: number[] = [];
    transcript.forEach((item, idx) => {
      if (item.text && item.text.toLowerCase().includes(qLower)) {
        matches.push(idx);
      }
    });
    setFindMatches(matches);
    setActiveMatchIdx(0);
    if (matches.length > 0) {
      const targetEl = messageItemRefs.current.get(matches[0]);
      targetEl?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    return matches.length;
  }, [transcript]);

  const handleFindNext = useCallback(() => {
    if (findMatches.length === 0) return;
    const nextIdx = (activeMatchIdx + 1) % findMatches.length;
    setActiveMatchIdx(nextIdx);
    const targetEl = messageItemRefs.current.get(findMatches[nextIdx]);
    targetEl?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [findMatches, activeMatchIdx]);

  const handleFindPrevious = useCallback(() => {
    if (findMatches.length === 0) return;
    const prevIdx = (activeMatchIdx - 1 + findMatches.length) % findMatches.length;
    setActiveMatchIdx(prevIdx);
    const targetEl = messageItemRefs.current.get(findMatches[prevIdx]);
    targetEl?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [findMatches, activeMatchIdx]);

  const handleScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const near = distanceToBottom < 100;
    setIsNearBottom(near);
    if (near) {
      isFollowingRef.current = true;
      setHasUnread(false);
      setUnreadCount(0);
    }
  };

  // Passive wheel listener: user scrolling up interrupts follow mode immediately
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const onWheel = (e: WheelEvent) => {
      if (e.deltaY < 0) {
        isFollowingRef.current = false;
        setIsNearBottom(false);
      } else if (e.deltaY > 0) {
        const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
        if (distanceToBottom < 80) {
          isFollowingRef.current = true;
          setIsNearBottom(true);
          setHasUnread(false);
        }
      }
    };

    container.addEventListener("wheel", onWheel, { passive: true });
    return () => container.removeEventListener("wheel", onWheel);
  }, []);

  const scrollToBottom = (smooth = true) => {
    isFollowingRef.current = true;
    setIsNearBottom(true);
    setHasUnread(false);
    const el = scrollContainerRef.current;
    if (el) {
      if (smooth) {
        el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      } else {
        el.scrollTop = el.scrollHeight;
      }
    } else {
      transcriptEndRef.current?.scrollIntoView({ behavior: smooth ? "smooth" : "auto" });
    }
  };

  // Immediate auto-scroll when active session changes
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
      isFollowingRef.current = true;
      setIsNearBottom(true);
      setHasUnread(false);
    }
  }, [activeSessionId]);

  // Smart auto-scroll: Follow active stream without trapping user scroll
  const lastItemText = transcript[transcript.length - 1]?.text || "";
  const lastItemLen = lastItemText.length;
  useEffect(() => {
    if (isFollowingRef.current && isNearBottom && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    } else if (!isNearBottom) {
      setHasUnread(true);
      setUnreadCount((c) => c + 1);
    }
  }, [transcript.length, lastItemLen, isNearBottom]);

  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    };
  }, []);

  const handleCopyMessage = (text: string, idx: number) => {
    if (!navigator?.clipboard?.writeText) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopiedMessageIndex(idx);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => {
        setCopiedMessageIndex(null);
      }, 2000);
    }).catch((err) => {
      console.warn("[Clipboard Error]:", err);
    });
  };

  const renderBlocks = useMemo(() => {
    const blocks: Array<
      | { kind: "item"; item: TranscriptItem; idx: number }
      | { kind: "tool_run"; items: any[]; isRunning: boolean; key: string }
    > = [];

    let currentRun: any[] = [];
    let runStartIdx = 0;

    const flushRun = (running: boolean) => {
      if (currentRun.length > 0) {
        blocks.push({
          kind: "tool_run",
          items: [...currentRun],
          isRunning: running,
          key: `tool-run-${runStartIdx}`,
        });
        currentRun = [];
      }
    };

    for (let i = 0; i < transcript.length; i++) {
      const item = transcript[i];
      if (item.visualType === "agent_action" && item.agentActionData) {
        const tool = (item.agentActionData.toolName || "").toLowerCase();
        // Standalone card tools (file edits with diffs) render as dedicated cards
        const isDiffCard =
          (tool.includes("patch") || tool.includes("write") || tool.includes("edit")) &&
          Boolean(item.agentActionData.rawResult || item.agentActionData.content || item.agentActionData.checkpointId);

        if (isDiffCard) {
          flushRun(false);
          blocks.push({ kind: "item", item, idx: i });
        } else {
          // Group consecutive activity runs (file reads, searches, terminal commands)
          if (currentRun.length === 0) {
            runStartIdx = i;
          }
          currentRun.push(item.agentActionData);
          continue;
        }
      } else {
        flushRun(false);
        blocks.push({ kind: "item", item, idx: i });
      }
    }

    flushRun(status === "thinking");
    return blocks;
  }, [transcript, status]);

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full relative pt-4 pb-4">
      {/* Scrollable Chat Message Stream */}
      <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto custom-scrollbar px-2 sm:px-4">
        <div className="max-w-3xl xl:max-w-4xl mx-auto w-full flex flex-col gap-3 py-3">
          {transcript.length === 0 ? (
            <div className="flex flex-col items-center justify-center min-h-[45vh] text-center px-4 animate-fade-in select-none my-auto">
              <div className="w-10 h-10 rounded-xl bg-white/[0.03] border border-white/[0.08] flex items-center justify-center mb-3 text-slate-300">
                <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h2 className="text-base sm:text-lg font-semibold text-slate-100 tracking-tight">
                Anara Studio
              </h2>
              <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                Autonomous coding agent · Plan or execute directly from prompt
              </p>

              {/* Developer Quick Reference HUD */}
              <div className="flex flex-wrap items-center justify-center gap-2 mt-4 text-[11px] font-mono text-slate-400">
                <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.025] border border-white/[0.06]">
                  <kbd className="px-1 py-0.5 rounded bg-white/[0.06] text-[10px] text-slate-300">Enter</kbd>
                  <span>Send</span>
                </span>
                <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.025] border border-white/[0.06]">
                  <kbd className="px-1 py-0.5 rounded bg-white/[0.06] text-[10px] text-slate-300">Shift + Enter</kbd>
                  <span>Newline</span>
                </span>
                <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.025] border border-white/[0.06]">
                  <kbd className="px-1 py-0.5 rounded bg-white/[0.06] text-[10px] text-slate-300">@</kbd>
                  <span>File mention</span>
                </span>
              </div>

              {/* Minimalist Command Chips */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-5 w-full max-w-lg">
                <button
                  type="button"
                  onClick={() => onSelectPrompt?.("Inspect repository structure and status")}
                  className="px-3 py-2 rounded-lg bg-white/[0.025] hover:bg-white/[0.06] border border-white/[0.06] hover:border-white/[0.12] text-slate-300 hover:text-white text-xs font-mono transition-all text-left flex items-center justify-between group cursor-pointer"
                >
                  <span className="truncate">Inspect repository</span>
                  <span className="text-slate-600 group-hover:text-slate-400 transition-colors ml-1">→</span>
                </button>
                <button
                  type="button"
                  onClick={() => onSelectPrompt?.("Create implementation plan for current workspace")}
                  className="px-3 py-2 rounded-lg bg-white/[0.025] hover:bg-white/[0.06] border border-white/[0.06] hover:border-white/[0.12] text-slate-300 hover:text-white text-xs font-mono transition-all text-left flex items-center justify-between group cursor-pointer"
                >
                  <span className="truncate">Create plan</span>
                  <span className="text-slate-600 group-hover:text-slate-400 transition-colors ml-1">→</span>
                </button>
                <button
                  type="button"
                  onClick={() => onSelectPrompt?.("Review recent code changes and audit")}
                  className="px-3 py-2 rounded-lg bg-white/[0.025] hover:bg-white/[0.06] border border-white/[0.06] hover:border-white/[0.12] text-slate-300 hover:text-white text-xs font-mono transition-all text-left flex items-center justify-between group cursor-pointer"
                >
                  <span className="truncate">Code review</span>
                  <span className="text-slate-600 group-hover:text-slate-400 transition-colors ml-1">→</span>
                </button>
              </div>
            </div>
          ) : (() => {
            return (
              <>
                {renderBlocks.map((block) => {
                  if (block.kind === "tool_run") {
                    return (
                      <div key={block.key} className="w-full my-1 px-1 animate-fade-in">
                        <ToolRunGroupCard
                          items={block.items}
                          isRunning={block.isRunning}
                          onOpenFile={onOpenFile}
                        />
                      </div>
                    );
                  }

                  const { item, idx } = block;
                  const isAi = item.speaker === "output";
                  const isLatestAi = isAi && idx === transcript.length - 1;

                  const footerElement = item.text ? (
                    <div className="flex items-center justify-between pt-2 min-h-[28px] opacity-0 group-hover/turn:opacity-100 focus-within:opacity-100 transition-opacity duration-200 select-none pointer-events-none group-hover/turn:pointer-events-auto">
                      <div className="flex items-center gap-2 text-[10.5px] font-mono text-slate-500 tabular-nums">
                        <span>
                          {item.timestamp ? new Date(item.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : null}
                        </span>
                        {item.durationText && (
                          <span className="flex items-center gap-1 text-slate-500/80">
                            <span>·</span>
                            <span>⏱ {item.durationText}</span>
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1 pointer-events-auto">
                        {/* Branch in new session */}
                        {onSelectPrompt && (
                          <button
                            type="button"
                            onClick={() => {
                              onSelectPrompt(`/branch ${item.id || ""}`.trim());
                            }}
                            className="inline-flex items-center gap-1 p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-white/[0.05] border border-white/[0.04] hover:border-white/[0.1] transition-all cursor-pointer"
                            title="Branch in new session"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" />
                            </svg>
                          </button>
                        )}

                        {/* Read Aloud / Speak */}
                        <button
                          type="button"
                          onClick={() => {
                            if (typeof window !== "undefined" && window.speechSynthesis) {
                              window.speechSynthesis.cancel();
                              const utterance = new SpeechSynthesisUtterance(item.text);
                              utterance.rate = 1.05;
                              window.speechSynthesis.speak(utterance);
                            }
                          }}
                          className="inline-flex items-center gap-1 p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-white/[0.05] border border-white/[0.04] hover:border-white/[0.1] transition-all cursor-pointer"
                          title="Read aloud"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                          </svg>
                        </button>

                        {/* Retry Prompt */}
                        {onSelectPrompt && (
                          <button
                            type="button"
                            onClick={() => {
                              const lastUser = [...transcript.slice(0, idx)].reverse().find((t) => t.speaker === "input");
                              if (lastUser?.text) onSelectPrompt(lastUser.text);
                            }}
                            className="inline-flex items-center gap-1 p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-white/[0.05] border border-white/[0.04] hover:border-white/[0.1] transition-all cursor-pointer"
                            title="Retry response"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                          </button>
                        )}

                        {/* Copy message */}
                        <button
                          type="button"
                          onClick={() => handleCopyMessage(item.text, idx)}
                          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono text-slate-500 hover:text-slate-300 hover:bg-white/[0.05] border border-white/[0.04] hover:border-white/[0.1] transition-all cursor-pointer"
                          title={copiedMessageIndex === idx ? "Copied!" : "Copy message"}
                        >
                          {copiedMessageIndex === idx ? (
                            <>
                              <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                              </svg>
                              <span className="text-emerald-400 font-medium">Copied</span>
                            </>
                          ) : (
                            <>
                              <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                              </svg>
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  ) : null;

                  const isFindMatched = findMatches.includes(idx);
                  const isActiveFindMatch = findMatches[activeMatchIdx] === idx;

                  if (item.speaker === "input") {
                    const isEditing = editingIndex === idx;

                    return (
                      <div
                        key={idx}
                        ref={(el) => {
                          if (el) messageItemRefs.current.set(idx, el);
                          else messageItemRefs.current.delete(idx);
                        }}
                        className={`flex flex-col items-end my-3 animate-fade-in group/user ${
                          isActiveFindMatch
                            ? "ring-2 ring-cyan-400/80 rounded-2xl p-1 bg-cyan-950/20"
                            : isFindMatched
                            ? "ring-1 ring-cyan-500/30 rounded-2xl"
                            : ""
                        }`}
                      >
                        {isEditing ? (
                          <div className="w-full max-w-[85%] sm:max-w-[75%] rounded-2xl bg-[#060913]/90 border border-cyan-500/30 p-3 shadow-2xl backdrop-blur-2xl">
                            <textarea
                              value={editText}
                              onChange={(e) => setEditText(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                                  e.preventDefault();
                                  if (editText.trim()) {
                                    setEditingIndex(null);
                                    onSelectPrompt?.(editText.trim());
                                  }
                                } else if (e.key === "Escape") {
                                  setEditingIndex(null);
                                }
                              }}
                              autoFocus
                              rows={Math.min(8, Math.max(2, editText.split("\n").length))}
                              className="w-full resize-none bg-transparent font-sans text-[13.5px] leading-relaxed text-slate-100 placeholder-slate-500 outline-none"
                            />
                            <div className="mt-2 flex items-center justify-end gap-2 border-t border-white/[0.06] pt-2 text-[11px] font-mono">
                              <span className="text-[10px] text-slate-500 mr-auto">Esc to cancel · Ctrl+Enter to send</span>
                              <button
                                type="button"
                                onClick={() => setEditingIndex(null)}
                                className="rounded px-2.5 py-1 text-slate-400 hover:text-white hover:bg-white/[0.05] transition-colors cursor-pointer"
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  if (editText.trim()) {
                                    setEditingIndex(null);
                                    onSelectPrompt?.(editText.trim());
                                  }
                                }}
                                className="rounded bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 px-3 py-1 font-medium text-cyan-200 hover:text-white transition-all cursor-pointer"
                              >
                                Save &amp; Re-run
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="relative max-w-[85%] sm:max-w-[75%] px-4 py-2.5 rounded-2xl bg-white/[0.04] hover:bg-white/[0.06] border border-white/[0.09] hover:border-white/[0.15] text-slate-100 text-[13.5px] leading-relaxed select-text backdrop-blur-xl shadow-[0_4px_20px_rgba(0,0,0,0.35)] transition-all font-sans">
                              {/* Top specular hairline */}
                              <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none rounded-t-2xl" />
                              <p className="whitespace-pre-wrap">{item.text}</p>
                            </div>

                            {/* User Bubble Hover Actions (Edit & Copy) */}
                            <div className="flex items-center gap-1.5 mt-1 mr-1 opacity-0 group-hover/user:opacity-100 transition-opacity duration-150 select-none">
                              <button
                                type="button"
                                onClick={() => {
                                  setEditingIndex(idx);
                                  setEditText(item.text);
                                }}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10.5px] font-mono text-slate-500 hover:text-slate-300 hover:bg-white/[0.05] border border-white/[0.04] hover:border-white/[0.1] transition-all cursor-pointer"
                                title="Edit prompt"
                              >
                                <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                </svg>
                                <span>Edit</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => handleCopyMessage(item.text, idx)}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10.5px] font-mono text-slate-500 hover:text-slate-300 hover:bg-white/[0.05] border border-white/[0.04] hover:border-white/[0.1] transition-all cursor-pointer"
                                title="Copy prompt"
                              >
                                <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                                <span>Copy</span>
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    );
                  }

                  // ── Interactive Questionnaire Card (Render only once answered as Collapsible Accordion in Timeline) ──
                  if (item.visualType === "interactive_question" && item.questionData) {
                    if (!item.questionData.isAnswered) {
                      return null; // Active wizard is rendered inside BottomDock
                    }
                    return (
                      <div key={idx} className="w-full my-1 animate-fade-in">
                        <InteractiveQuestionCard
                          data={item.questionData}
                          onSubmitAnswers={(qId, ans, dis) => onAnswerQuestion?.(qId, ans, dis)}
                        />
                      </div>
                    );
                  }

                  // ── Todo Checklist Card ──
                  if (item.visualType === "todo_list" && item.todoData) {
                    return (
                      <div key={idx} className="w-full my-1 px-1 animate-fade-in">
                        <AgentToolCard todoData={item.todoData} sessionId={activeSessionId} onOpenFile={onOpenFile} />
                      </div>
                    );
                  }

                  // ── Action item (Diff card, shell command, task list) ──
                  if (item.visualType === "agent_action" && item.agentActionData) {
                    return (
                      <div key={idx} className="w-full my-1 px-1 animate-fade-in">
                        <AgentToolCard action={item.agentActionData} sessionId={activeSessionId} onOpenFile={onOpenFile} />
                      </div>
                    );
                  }

                  // ── Narrative Markdown Turn (Direct Canvas Stream, Zero Slop Card-itis) ──
                  const currentThinking = item.thinkingText || (isLatestAi ? activeThinkingText : null);

                  return (
                    <div
                      key={idx}
                      ref={(el) => {
                        if (el) messageItemRefs.current.set(idx, el);
                        else messageItemRefs.current.delete(idx);
                      }}
                      className={`flex flex-col items-start w-full my-2 px-1 animate-fade-in select-text group/turn relative ${
                        isActiveFindMatch
                          ? "ring-2 ring-cyan-400/80 rounded-2xl p-1.5 bg-cyan-950/20"
                          : isFindMatched
                          ? "ring-1 ring-cyan-500/30 rounded-2xl p-1"
                          : ""
                      }`}
                    >
                      <div className="w-full text-slate-200">
                        {/* 1. Reasoning / Thought Process Disclosure (if present) */}
                        {currentThinking && (
                          <div className="w-full mb-2">
                            <ThinkingCard
                              text={currentThinking}
                              durationSec={item.thinkingDuration}
                              isLive={Boolean(isLatestAi && !item.text)}
                            />
                          </div>
                        )}

                        {/* Tool Execution Summary Pill in History (Anara Desktop Standard) */}
                        {item.toolsUsed && item.toolsUsed.length > 0 && !item.agentActionData && (
                          <div className="flex items-center gap-2 mb-2 select-none">
                            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-white/[0.05] border border-white/[0.08] text-[11px] font-mono text-slate-300 transition-colors">
                              <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                              </svg>
                              <span>
                                {item.toolRecordsCount ? `${item.toolRecordsCount} calls` : `${item.toolsUsed.length} tool${item.toolsUsed.length > 1 ? "s" : ""}`}
                                <span className="text-slate-500 ml-1.5 font-normal">
                                  ({Array.from(new Set(item.toolsUsed)).slice(0, 3).join(", ")}
                                  {new Set(item.toolsUsed).size > 3 ? "..." : ""})
                                </span>
                              </span>
                              {item.durationText && (
                                <span className="text-[10px] text-slate-500 font-mono pl-1.5 border-l border-white/[0.08] tabular-nums">
                                  {item.durationText}
                                </span>
                              )}
                            </div>
                          </div>
                        )}

                        {/* 2. In-flight Tool or Initial Wait Indicator (only when NO text and NO thinking card) */}
                        {!item.text && !currentThinking ? (
                          <div className="w-full max-w-full">
                            {isLatestAi && liveToolProgress ? (
                              <ToolRunTicker
                                activeItemText={`Executing ${liveToolProgress.toolName}...`}
                                totalCount={1}
                                isRunning={true}
                              >
                                <span>{liveToolProgress.toolName}</span>
                              </ToolRunTicker>
                            ) : (
                              <div className="py-1.5 text-xs text-slate-400 font-mono select-none flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                                <span>Thinking...</span>
                              </div>
                            )}
                          </div>
                        ) : null}

                        {/* 3. In-flight tool progress when thinking is already showing */}
                        {!item.text && currentThinking && isLatestAi && liveToolProgress ? (
                          <div className="w-full max-w-full mb-2">
                            <ToolRunTicker
                              activeItemText={`Executing ${liveToolProgress.toolName}...`}
                              totalCount={1}
                              isRunning={true}
                            >
                              <span>{liveToolProgress.toolName}</span>
                            </ToolRunTicker>
                          </div>
                        ) : null}

                        {/* 4. Streaming or Final Markdown Content (with zero thought tag leak) */}
                        {(() => {
                          if (!item.text) return null;
                          const rawText = item.text;
                          const hasThoughtTag = /<(?:\/?)(?:thought|think|reasoning)[^>]*>/i.test(rawText);
                          let displayMarkdown = rawText;
                          let inlineThought: string | null = null;
                          if (hasThoughtTag) {
                            const thoughtMatches = rawText.match(/<(?:thought|think|reasoning)[^>]*>([\s\S]*?)<\/(?:thought|think|reasoning)>/gi);
                            if (thoughtMatches) {
                              inlineThought = thoughtMatches.map((m) => m.replace(/<[^>]+>/g, "").trim()).filter(Boolean).join("\n\n");
                            }
                            displayMarkdown = rawText
                              .replace(/<(?:thought|think|reasoning)[^>]*>[\s\S]*?<\/(?:thought|think|reasoning)>/gi, "")
                              .replace(/<(?:\/?)(?:thought|think|reasoning)[^>]*>/gi, "")
                              .trim();
                          }
                          return (
                            <>
                              {inlineThought && !currentThinking && (
                                <div className="mb-2 w-full max-w-full">
                                  <ThinkingCard text={inlineThought} isLive={false} />
                                </div>
                              )}
                              {displayMarkdown ? (
                                <div className={`relative leading-relaxed font-sans text-[13.5px] ${
                                  item.isStreaming ? 'streaming-text-gradient streaming-arc-border rounded-lg' : 'text-slate-200'
                                }`}>
                                  <AgentMarkdown
                                    content={displayMarkdown}
                                    isStreaming={Boolean(item.isStreaming)}
                                  />
                                </div>
                              ) : null}
                              {footerElement}
                            </>
                          );
                        })()}

                        {/* 5. Interrupted Status Pill */}
                        {item.interrupted && (
                          <div className="mt-1.5 flex items-center gap-1.5 text-[10.5px] font-mono text-amber-300 select-none">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                            <span>Interrupted</span>
                          </div>
                        )}

                        {/* 6. Explicit Error Card with 1-Click Retry */}
                        {item.isError && (
                          <div className="mt-2.5 flex items-center justify-between rounded-xl border border-rose-500/20 bg-rose-950/20 px-3 py-2 text-xs font-mono text-rose-300 select-none">
                            <div className="flex items-center gap-2 truncate">
                              <span className="w-2 h-2 rounded-full bg-rose-400 shrink-0" />
                              <span className="truncate">{item.errorDetails || "Permintaan tidak dapat diselesaikan."}</span>
                            </div>
                            {item.retryable && onSelectPrompt && (
                              <button
                                type="button"
                                onClick={() => {
                                  const lastUser = [...transcript].reverse().find((t) => t.speaker === "input");
                                  if (lastUser?.text) onSelectPrompt(lastUser.text);
                                }}
                                className="ml-3 shrink-0 rounded-lg border border-rose-400/30 bg-rose-500/15 px-2.5 py-1 text-[11px] font-medium text-rose-200 hover:bg-rose-500/25 hover:text-white transition-all cursor-pointer"
                              >
                                Retry ↺
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </>
            );
          })()}
          {/* Dynamic bottom spacer taking footerDockHeight into account */}
          <div
            style={{ height: `${Math.max(28, (footerDockHeight || 0) + 12)}px` }}
            className="w-full shrink-0 pointer-events-none transition-[height] duration-150 ease-out"
          />
          <div ref={transcriptEndRef} />
        </div>
      </div>

      {/* Floating Circular Scroll Down Button with Unread Pulse (Anara Desktop Standard) */}
      {!isNearBottom && (
        <button
          type="button"
          onClick={() => scrollToBottom(true)}
          style={{ bottom: `${Math.max(16, (footerDockHeight || 0) + 16)}px` }}
          className="absolute left-1/2 -translate-x-1/2 z-40 px-3 py-1.5 rounded-full bg-[#060913]/95 hover:bg-[#0c1328] border border-white/20 hover:border-cyan-400/50 text-slate-300 hover:text-white flex items-center gap-2 shadow-[0_8px_32px_rgba(0,0,0,0.85)] backdrop-blur-xl cursor-pointer transition-all active:scale-95 animate-fade-in group font-mono text-xs"
          title="Scroll to bottom"
          aria-label="Scroll to bottom"
        >
          {hasUnread && (
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_#22d3ee]" />
              {unreadCount > 1 && (
                <span className="rounded bg-cyan-400/20 px-1 py-0.2 text-[9px] font-mono text-cyan-300">
                  {unreadCount}
                </span>
              )}
            </span>
          )}
          <span>Jump to latest</span>
          <svg className="w-3.5 h-3.5 text-slate-400 group-hover:text-cyan-300 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </button>
      )}

      {/* In-Conversation Find Bar (Ctrl+F) */}
      <FindBar
        isOpen={isFindOpen}
        onClose={() => setIsFindOpen(false)}
        onSearch={handleFindSearch}
        onNext={handleFindNext}
        onPrevious={handleFindPrevious}
        activeMatchIndex={activeMatchIdx}
        totalMatches={findMatches.length}
      />
    </div>
  );
}
