"use client";

import React, { useRef, useEffect, useState, useMemo } from "react";
import AgentMarkdown from "./AgentMarkdown";
import AgentToolCard, { ExplorationGroupCard, ThinkingCard } from "./AgentToolCard";
import InteractiveQuestionCard from "./InteractiveQuestionCard";
import type { TranscriptItem, AssistantStatus } from "../workbench/AnaraWorkbench";
import type { ToolProgressPayload, AgentActionPayload } from "@/hooks/useWebSocket";

export interface ChatTimelineProps {
  transcript: TranscriptItem[];
  status: AssistantStatus;
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
  const [copiedMessageIndex, setCopiedMessageIndex] = useState<number | null>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const handleCopyMessage = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedMessageIndex(idx);
    setTimeout(() => {
      setCopiedMessageIndex(null);
    }, 2000);
  };

  const compactTokenCount = (value: number) =>
    value >= 1000000
      ? `${(value / 1000000).toFixed(value >= 10000000 ? 0 : 1)}M`
      : value >= 1000
      ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}K`
      : value.toLocaleString();

  const renderBlocks = useMemo(() => {
    const blocks: Array<
      | { kind: "item"; item: TranscriptItem; idx: number }
      | { kind: "exploration"; items: any[]; isRunning: boolean; key: string }
    > = [];

    let currentExploration: any[] = [];

    const flushExploration = (running: boolean) => {
      if (currentExploration.length > 0) {
        blocks.push({
          kind: "exploration",
          items: [...currentExploration],
          isRunning: running,
          key: `explore-${blocks.length}`,
        });
        currentExploration = [];
      }
    };

    for (let i = 0; i < transcript.length; i++) {
      const item = transcript[i];
      if (item.visualType === "agent_action" && item.agentActionData) {
        const tool = (item.agentActionData.toolName || "").toLowerCase();
        const isExploration =
          tool.includes("read") ||
          tool.includes("scan") ||
          tool.includes("grep") ||
          tool.includes("glob") ||
          tool.includes("list");

        if (isExploration) {
          currentExploration.push(item.agentActionData);
          continue;
        } else {
          flushExploration(false);
          blocks.push({ kind: "item", item, idx: i });
        }
      } else {
        flushExploration(false);
        blocks.push({ kind: "item", item, idx: i });
      }
    }

    flushExploration(status === "thinking");
    return blocks;
  }, [transcript, status]);

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full relative pt-4 pb-4">
      {/* Scrollable Chat Message Stream */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-2 sm:px-4">
        <div className="max-w-3xl xl:max-w-4xl mx-auto w-full flex flex-col gap-3 py-3">
          {transcript.length === 0 ? (
            <div className="flex flex-col items-center justify-center min-h-[50vh] text-center px-4 animate-fade-in select-none my-auto">
              <div className="w-12 h-12 rounded-2xl bg-white/[0.04] border border-white/10 flex items-center justify-center shadow-inner mb-4">
                <svg className="w-6 h-6 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h2 className="text-xl sm:text-2xl font-semibold text-slate-100 tracking-tight leading-relaxed">
                Hello{activeSpeaker ? <> <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 via-slate-100 to-indigo-300 font-bold">{activeSpeaker}</span></> : ""}, what should we build today?
              </h2>
              <p className="text-xs text-slate-400 mt-1.5 max-w-md mx-auto">
                Discuss architecture in Plan Mode, or execute autonomous code modifications in Build Mode.
              </p>

              {/* Clean Starter Prompt Chips */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-6 w-full max-w-xl">
                <button
                  type="button"
                  onClick={() => onSelectPrompt?.("Create an architectural implementation plan for this project")}
                  className="p-3.5 rounded-2xl starter-card-glow text-left cursor-pointer group flex items-start gap-3 select-none"
                >
                  <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-400/25 flex items-center justify-center text-cyan-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-100 group-hover:text-cyan-300 transition-colors">
                      Architecture Blueprint
                    </p>
                    <p className="text-[11px] text-slate-400 mt-0.5 font-sans leading-relaxed">
                      Formulate blueprint &amp; dependencies in Plan Mode
                    </p>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => onSelectPrompt?.("Analyze the project files and identify potential improvements")}
                  className="p-3.5 rounded-2xl starter-card-glow text-left cursor-pointer group flex items-start gap-3 select-none"
                >
                  <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-400/25 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-100 group-hover:text-indigo-300 transition-colors">
                      Code Analysis &amp; Review
                    </p>
                    <p className="text-[11px] text-slate-400 mt-0.5 font-sans leading-relaxed">
                      Inspect workspace files and logic optimizations
                    </p>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => onSelectPrompt?.("Create a priority task checklist for this session")}
                  className="p-3.5 rounded-2xl starter-card-glow text-left cursor-pointer group flex items-start gap-3 select-none"
                >
                  <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-400/25 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-100 group-hover:text-emerald-300 transition-colors">
                      Task Checklist
                    </p>
                    <p className="text-[11px] text-slate-400 mt-0.5 font-sans leading-relaxed">
                      Record priority deliverables to memory
                    </p>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => onSelectPrompt?.("What tools and capabilities do you have available?")}
                  className="p-3.5 rounded-2xl starter-card-glow text-left cursor-pointer group flex items-start gap-3 select-none"
                >
                  <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-400/25 flex items-center justify-center text-amber-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-100 group-hover:text-amber-300 transition-colors">
                      Agent Capabilities
                    </p>
                    <p className="text-[11px] text-slate-400 mt-0.5 font-sans leading-relaxed">
                      Explore multi-modal tools and skill catalog
                    </p>
                  </div>
                </button>
              </div>
            </div>
          ) : (() => {
            const lastAiIndex = transcript.map((t) => t.speaker).lastIndexOf("output");

            return (
              <>
                {renderBlocks.map((block) => {
                  if (block.kind === "exploration") {
                    return (
                      <div key={block.key} className="w-full my-1 px-1 animate-fade-in">
                        <ExplorationGroupCard items={block.items} isRunning={block.isRunning} />
                      </div>
                    );
                  }

                  const { item, idx } = block;
                  const isAi = item.speaker === "output";
                  const isLatestAi = isAi && idx === transcript.length - 1;
                  const rawModel = item.modelId || activeModelId || "model";
                  const footerModel = rawModel.startsWith("9router/9router/")
                    ? rawModel.replace("9router/9router/", "9router/")
                    : rawModel;
                  const footerUsage = item.tokenUsage && item.tokenUsage.contextLimit > 0 ? item.tokenUsage : null;
                  const footerUsed = footerUsage ? Math.max(0, footerUsage.contextLimit - footerUsage.contextRemaining) : 0;
                  const footerPercent = footerUsage ? Math.min(100, Math.max(0, (footerUsed / footerUsage.contextLimit) * 100)) : 0;

                  const isLatestAiMessage = idx === lastAiIndex;
                  const footerElement = item.text ? (
                    <div className={`flex min-w-0 items-center gap-2 pt-2.5 text-[11px] font-mono text-white select-none whitespace-nowrap transition-opacity duration-200 ${
                      isLatestAiMessage
                        ? "opacity-100"
                        : "opacity-0 group-hover/turn:opacity-100 active:opacity-100 focus-within:opacity-100"
                    }`}>
                      <button
                        type="button"
                        onClick={() => handleCopyMessage(item.text, idx)}
                        className="p-1.5 -ml-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.12] border border-white/10 hover:border-white/20 text-slate-400 hover:text-white transition-all cursor-pointer flex items-center gap-1 active:scale-95 shadow-sm"
                        title={copiedMessageIndex === idx ? "Tersalin!" : "Salin jawaban"}
                      >
                        {copiedMessageIndex === idx ? (
                          <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                          </svg>
                        ) : (
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                        )}
                      </button>
                      {/* Operational Mode Badge (Plan / Build) */}
                      <span
                        className={`px-2 py-0.5 rounded-md border text-[10px] font-mono font-bold shrink-0 ${
                          (item.agentMode || "plan") === "plan"
                            ? "bg-cyan-500/15 border-cyan-400/30 text-cyan-300 shadow-[0_0_8px_rgba(34,211,238,0.15)]"
                            : "bg-amber-500/15 border-amber-400/30 text-amber-300 shadow-[0_0_8px_rgba(245,158,11,0.15)]"
                        }`}
                      >
                        {(item.agentMode || "plan") === "plan" ? "Plan" : "Build"}
                      </span>
                      <span className="text-slate-600">·</span>
                      <span className="px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/10 text-slate-200 font-semibold text-[10.5px] truncate max-w-[200px]" title={footerModel}>
                        {footerModel}
                      </span>
                      {footerUsage && (
                        <>
                          <span className="text-slate-600">|</span>
                          <span className="text-slate-300 shrink-0 font-medium">
                            {compactTokenCount(footerUsed)}/{compactTokenCount(footerUsage.contextLimit)}
                          </span>
                          <span className="text-slate-600">|</span>
                          <span className="inline-flex items-center gap-1.5 text-slate-300 shrink-0">
                            <span className="inline-block h-2 w-16 overflow-hidden rounded-full bg-white/10 align-middle shadow-inner">
                              <span
                                className={`block h-full transition-all duration-300 ${footerPercent >= 85 ? "bg-rose-400" : footerPercent >= 60 ? "bg-amber-400" : "bg-emerald-400"}`}
                                style={{ width: `${Math.max(footerPercent, 1)}%` }}
                              />
                            </span>
                            <span className="text-[10px] font-bold tabular-nums">{footerPercent.toFixed(0)}%</span>
                          </span>
                        </>
                      )}
                      <span className="text-slate-600">|</span>
                      <span className="text-slate-400 shrink-0">
                        {item.durationText || (item.startTime ? `${Math.max(1, Math.round((Date.now() - item.startTime) / 1000))}dtk` : "1dtk")}
                      </span>
                    </div>
                  ) : null;

                  if (item.speaker === "input") {
                    return (
                      <div key={idx} className="flex flex-col items-end my-2 animate-fade-in">
                        <div className="max-w-[85%] sm:max-w-[75%] px-4 py-2.5 rounded-2xl rounded-br-sm obsidian-bubble-user text-white text-[13.5px] leading-relaxed select-text transition-all font-sans">
                          <p className="whitespace-pre-wrap">{item.text}</p>
                        </div>
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

                  // ── Action item (Diff card, shell command, task list) ──
                  if (item.visualType === "agent_action" && item.agentActionData) {
                    return (
                      <div key={idx} className="w-full my-1 px-1 animate-fade-in">
                        <AgentToolCard action={item.agentActionData} onOpenFile={onOpenFile} />
                      </div>
                    );
                  }

                  // ── Narrative Markdown Turn ──
                  return (
                    <div key={idx} className="flex flex-col items-start w-full my-2 px-1 animate-fade-in select-text group/turn">
                      <div className="w-full text-slate-100">
                        {!item.text ? (
                          <div className="space-y-2 w-full max-w-xl">
                            <div className="py-2 text-xs text-slate-400 font-mono select-none animate-pulse flex items-center gap-2">
                              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                              <span>
                                {isLatestAi && liveToolProgress
                                  ? `${liveToolProgress.icon || "⚡"} Running ${liveToolProgress.toolName}...`
                                  : "Processing..."}
                              </span>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="relative">
                              <AgentMarkdown
                                content={item.text}
                                isStreaming={Boolean(item.isStreaming)}
                              />
                            </div>
                            {!item.isStreaming && footerElement}
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Live Thinking Status Pill (Screenshot match) */}
                {activeThinkingText && (
                  <div className="w-full my-1.5 px-1 animate-fade-in">
                    <ThinkingCard text={activeThinkingText} />
                  </div>
                )}
              </>
            );
          })()}
          {/* Dynamic bottom spacer */}
          <div
            style={{
              height: `${footerDockHeight + 12}px`,
            }}
            className="w-full shrink-0 pointer-events-none transition-[height] duration-150 ease-out"
          />
          <div ref={transcriptEndRef} />
        </div>
      </div>
    </div>
  );
}
