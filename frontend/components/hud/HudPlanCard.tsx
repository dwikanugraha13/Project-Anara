"use client";

import React, { useState, useEffect, useCallback } from "react";
import { PlanData, HudDismissButton } from "./types";

export interface HudPlanCardProps {
  planData: PlanData;
  onApprovePlan?: (plan: PlanData) => void;
  onRejectPlan?: () => void;
  onExecutePlan?: (plan: PlanData) => void;
  onToggleStep?: (stepIndex: number, newStatus?: string) => void;
  onOpenFile?: (filePath: string) => void;
  onDismiss?: () => void;
}

export interface PlanStepObject {
  id?: string | number;
  title?: string;
  name?: string;
  step?: string;
  description?: string;
  status?: "pending" | "in_progress" | "completed";
}

export type PlanStepItem = string | PlanStepObject;

export type PlanExecutionState = "pending" | "approved" | "executing" | "completed";

export default function HudPlanCard({
  planData,
  onApprovePlan,
  onRejectPlan,
  onExecutePlan,
  onToggleStep,
  onOpenFile,
  onDismiss,
}: HudPlanCardProps) {
  const steps = (planData.steps || []) as PlanStepItem[];
  const files = planData.filesToModify || [];
  const techStack = planData.tech_stack || planData.techStack || [];
  const effort = planData.estimated_effort || planData.estimatedEffort || planData.estimatedScope;

  // Derive initial execution state
  const rawStatus = planData.planStatus || "pending";
  const propExecutionState: PlanExecutionState =
    rawStatus === "completed"
      ? "completed"
      : rawStatus === "executing"
      ? "executing"
      : rawStatus === "approved"
      ? "approved"
      : "pending";

  const [localStatusOverride, setLocalStatusOverride] = useState<PlanExecutionState | null>(null);
  const [prevPropStatus, setPrevPropStatus] = useState<string | undefined>(planData.planStatus);

  // Sync state during render when props change, per React guidelines
  if (planData.planStatus !== prevPropStatus) {
    setPrevPropStatus(planData.planStatus);
    setLocalStatusOverride(null);
  }

  const state: PlanExecutionState = localStatusOverride || propExecutionState;
  const [localStepStates, setLocalStepStates] = useState<Record<number, "pending" | "in_progress" | "completed">>({});

  // Keyboard shortcut: Escape to dismiss
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onDismiss?.();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onDismiss]);

  const handleApprove = useCallback(() => {
    setLocalStatusOverride("executing");
    onApprovePlan?.(planData);
  }, [onApprovePlan, planData]);

  const handleExecute = useCallback(() => {
    setLocalStatusOverride("executing");
    if (onExecutePlan) {
      onExecutePlan(planData);
    } else {
      onApprovePlan?.(planData);
    }
  }, [onExecutePlan, onApprovePlan, planData]);

  const handleToggleStepLocal = (idx: number, currentStatus: "pending" | "in_progress" | "completed") => {
    const nextStatus: "pending" | "in_progress" | "completed" =
      currentStatus === "completed" ? "pending" : "completed";
    setLocalStepStates((prev) => ({ ...prev, [idx]: nextStatus }));
    onToggleStep?.(idx, nextStatus);
  };

  // Determine stage progress count
  const completedStagesCount = steps.filter((st: PlanStepItem, idx: number) => {
    const override = localStepStates[idx];
    if (override) return override === "completed";
    if (state === "completed") return true;
    if (typeof st === "object" && st?.status === "completed") return true;
    return false;
  }).length;

  return (
    <div
      role="region"
      aria-label="Execution Plan HUD"
      className="mt-2.5 w-full rounded-2xl border border-white/[0.08] bg-[#060913]/90 backdrop-blur-xl shadow-[0_16px_40px_rgba(0,0,0,0.65),inset_0_1px_0_0_rgba(255,255,255,0.08)] text-slate-100 select-none transition-all duration-200"
    >
      {/* ── Liquid Glass Specular Header ─────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.08] bg-white/[0.02] text-[11px] font-mono">
        <div className="flex items-center gap-2.5 min-w-0">
          {/* Status glyph & beacon */}
          {state === "completed" ? (
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
            </span>
          ) : state === "executing" ? (
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
            </span>
          ) : state === "approved" ? (
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
            </span>
          ) : (
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="animate-pulse relative inline-flex rounded-full h-2 w-2 bg-amber-400" />
            </span>
          )}

          {/* Status Label */}
          <span
            className={`font-semibold tracking-wider uppercase truncate text-[10.5px] ${
              state === "completed"
                ? "text-emerald-300"
                : state === "executing"
                ? "text-cyan-300"
                : state === "approved"
                ? "text-emerald-300"
                : "text-amber-300"
            }`}
          >
            {state === "completed"
              ? "COMPLETED"
              : state === "executing"
              ? "EXECUTING ARCHITECTURE"
              : state === "approved"
              ? "PLAN APPROVED"
              : "PLAN PROPOSAL"}
          </span>
        </div>

        {/* Stage counter, effort pill, and dismiss button */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-medium bg-white/[0.04] text-slate-300 border border-white/[0.08]">
            {completedStagesCount}/{steps.length} Stages
          </span>

          {effort && (
            <span className="px-2 py-0.5 rounded-md bg-white/[0.04] text-slate-300 border border-white/[0.08] text-[10px] font-mono flex items-center gap-1">
              <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{effort}</span>
            </span>
          )}

          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      {/* ── Card Content Body ───────────────────────────────────── */}
      <div className="p-4 sm:p-5 space-y-4 font-sans">
        {/* Title, summary & tech stack tags */}
        <div className="space-y-2">
          <h4 className="text-sm sm:text-base font-bold text-white tracking-tight leading-snug">
            {planData.title || "Project Execution Plan"}
          </h4>

          {planData.summary && (
            <p className="text-xs text-slate-300/90 leading-relaxed font-normal">
              {planData.summary}
            </p>
          )}

          {techStack.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-0.5 font-mono">
              {techStack.map((tech, tIdx) => (
                <span
                  key={tIdx}
                  className="px-2 py-0.5 rounded-md bg-white/[0.04] hover:bg-white/[0.07] text-slate-300 border border-white/[0.08] text-[10.5px] font-medium transition-colors"
                >
                  {tech}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* ── Stages Execution Checklist ───────────────────────────── */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[10.5px] font-mono text-slate-400">
            <span className="font-semibold uppercase tracking-wider">Execution Stages</span>
            <span className="tabular-nums">
              {completedStagesCount} of {steps.length} done
            </span>
          </div>

          <div className="space-y-1.5 max-h-[240px] overflow-y-auto custom-scrollbar pr-1 font-mono text-xs">
            {steps.map((st: PlanStepItem, idx: number) => {
              const isString = typeof st === "string";
              const rawTitle = isString ? st : (st?.title || st?.name || st?.step || "");
              const cleanTitle =
                rawTitle.replace(/^(?:Langkah\s*\d+\s*:\s*|Step\s*\d+\s*:\s*|\d+\.\s*)/i, "").trim() || rawTitle;
              const description = isString ? "" : st?.description;

              const overrideStatus = localStepStates[idx];
              const stepDone =
                overrideStatus === "completed" ||
                (!overrideStatus && (state === "completed" || (!isString && st?.status === "completed")));
              const stepInProg =
                overrideStatus === "in_progress" ||
                (!overrideStatus && !stepDone && (state === "executing" && idx === completedStagesCount));

              const currentStepState: "pending" | "in_progress" | "completed" = stepDone
                ? "completed"
                : stepInProg
                ? "in_progress"
                : "pending";

              return (
                <div
                  key={typeof st !== "string" ? st.id || idx : idx}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleToggleStepLocal(idx, currentStepState)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleToggleStepLocal(idx, currentStepState);
                    }
                  }}
                  className={`group flex items-start gap-2.5 p-2.5 rounded-xl border transition-all cursor-pointer select-none ${
                    stepDone
                      ? "bg-white/[0.015] hover:bg-white/[0.03] border-white/[0.04]"
                      : stepInProg
                      ? "bg-white/[0.035] hover:bg-white/[0.06] border-cyan-400/30"
                      : "bg-white/[0.02] hover:bg-white/[0.04] border-white/[0.06] hover:border-white/[0.12]"
                  }`}
                >
                  {/* Pure SVG Step Glyph Indicator */}
                  <div className="mt-0.5 shrink-0">
                    {stepDone ? (
                      <div className="w-4 h-4 rounded-full bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center text-emerald-300">
                        <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                    ) : stepInProg ? (
                      <div className="relative flex items-center justify-center w-4 h-4 text-cyan-300">
                        <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                          />
                        </svg>
                      </div>
                    ) : (
                      <span className="w-4 h-4 rounded-full bg-white/[0.05] border border-white/[0.12] text-slate-400 group-hover:text-slate-200 group-hover:border-white/[0.2] flex items-center justify-center text-[9px] font-mono font-medium transition-colors">
                        {idx + 1}
                      </span>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <p
                      className={`text-xs font-medium leading-snug break-words ${
                        stepDone ? "line-through text-slate-500" : "text-slate-200 group-hover:text-white"
                      }`}
                    >
                      {cleanTitle}
                    </p>
                    {description && (
                      <p className="text-[11px] text-slate-400/90 mt-0.5 leading-relaxed font-sans">
                        {description}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Related Files to Modify (Click to open in IDE) ───────── */}
        {files.length > 0 && (
          <div className="space-y-1.5 pt-2 border-t border-white/[0.08] font-mono">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Files to Modify ({files.length}):
            </p>
            <div className="flex flex-wrap gap-1.5 font-mono">
              {files.map((fp, fIdx) => (
                <button
                  key={fIdx}
                  type="button"
                  onClick={() => onOpenFile?.(fp)}
                  className="group/file px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] text-slate-300 hover:text-white border border-white/[0.08] hover:border-white/[0.16] text-[10.5px] cursor-pointer transition-all flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400/50"
                  title={`Open ${fp} in IDE`}
                >
                  <svg
                    className="w-3.5 h-3.5 text-slate-400 group-hover/file:text-cyan-300 transition-colors shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <span className="truncate max-w-[280px]">{fp}</span>
                  <svg
                    className="w-3 h-3 text-slate-500 opacity-0 group-hover/file:opacity-100 transition-opacity shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                  </svg>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── State Machine Action / Execution Bar ─────────────────── */}
        {state === "pending" && (
          <div className="pt-3 border-t border-white/[0.08] flex items-center justify-between gap-3 font-mono">
            <div className="flex items-center gap-2 text-[11px] text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              <span>Awaiting user approval</span>
            </div>
            <div className="flex items-center gap-2">
              {onRejectPlan && (
                <button
                  type="button"
                  onClick={onRejectPlan}
                  className="px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border border-white/[0.08] text-xs font-medium cursor-pointer transition-all active:scale-95"
                >
                  Dismiss
                </button>
              )}
              {onApprovePlan && (
                <button
                  type="button"
                  onClick={handleApprove}
                  className="px-3.5 py-1.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 hover:text-emerald-200 border border-emerald-400/30 text-xs font-semibold cursor-pointer transition-all active:scale-95 flex items-center gap-1.5 shadow-sm"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>Approve & Execute</span>
                </button>
              )}
            </div>
          </div>
        )}

        {state === "approved" && (
          <div className="pt-3 border-t border-white/[0.08] flex items-center justify-between gap-3 font-mono">
            <div className="flex items-center gap-2 text-[11px] text-emerald-300">
              <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span>Plan approved. Ready for execution.</span>
            </div>
            {(onExecutePlan || onApprovePlan) && (
              <button
                type="button"
                onClick={handleExecute}
                className="px-3.5 py-1.5 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 hover:text-white border border-cyan-400/30 text-xs font-semibold cursor-pointer transition-all active:scale-95 flex items-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Run Execution</span>
              </button>
            )}
          </div>
        )}

        {state === "executing" && (
          <div className="pt-3 border-t border-white/[0.08] flex items-center justify-between gap-3 text-[11px] font-mono text-cyan-300">
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 animate-spin text-cyan-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <span>Agent is actively executing architecture stages...</span>
            </div>
            <span className="text-[10px] text-slate-400 tabular-nums">
              {Math.round((completedStagesCount / (steps.length || 1)) * 100)}%
            </span>
          </div>
        )}

        {state === "completed" && (
          <div className="pt-3 border-t border-white/[0.08] flex items-center justify-between gap-2 text-[11px] font-mono text-emerald-300">
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Project architecture successfully built and verified.</span>
            </div>
            <button
              type="button"
              onClick={onDismiss}
              className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border border-white/[0.08] text-[10.5px] cursor-pointer transition-all"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
