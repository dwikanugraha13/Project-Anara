"use client";

import React from "react";
import { PlanData, HudDismissButton } from "./types";

interface HudPlanCardProps {
  planData: PlanData;
  onApprovePlan?: (plan: PlanData) => void;
  onRejectPlan?: () => void;
  onOpenFile?: (filePath: string) => void;
  onDismiss?: () => void;
}

export default function HudPlanCard({
  planData,
  onApprovePlan,
  onRejectPlan,
  onOpenFile,
  onDismiss,
}: HudPlanCardProps) {
  const steps = (planData.steps || []) as any[];
  const files = planData.filesToModify || [];
  const techStack = planData.tech_stack || planData.techStack || [];
  const effort = planData.estimated_effort || planData.estimatedEffort || planData.estimatedScope;
  const pStatus = planData.planStatus || "pending";
  const isApproved = pStatus === "approved" || pStatus === "executing" || pStatus === "completed";
  const isCompleted = pStatus === "completed";

  return (
    <div
      className={`mt-2 w-full rounded-2xl overflow-hidden border bg-slate-950/70 backdrop-blur-xl shadow-lg text-white select-none ${
        isApproved ? "border-emerald-500/40" : "border-cyan-400/25"
      }`}
    >
      {/* Header */}
      <div
        className={`flex items-center justify-between px-3.5 py-2 border-b border-white/10 text-[10.5px] font-mono ${
          isApproved
            ? "bg-gradient-to-r from-emerald-950/50 via-slate-900/50 to-teal-950/50"
            : "bg-gradient-to-r from-cyan-950/40 via-slate-900/50 to-blue-950/40"
        }`}
      >
        <div className="flex items-center gap-2 min-w-0">
          {isCompleted ? (
            <span className="text-emerald-400 font-bold">✅</span>
          ) : isApproved ? (
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
          ) : (
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]" />
          )}
          <span className={`font-bold uppercase tracking-widest truncate ${isApproved ? "text-emerald-300" : "text-cyan-300"}`}>
            {isCompleted ? "✅ COMPLETED" : isApproved ? "✅ APPROVED — BUILD MODE" : "📝 PLAN MODE"}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-bold border ${
              isApproved
                ? "bg-emerald-500/15 text-emerald-200 border-emerald-400/30"
                : "bg-cyan-500/15 text-cyan-200 border-cyan-400/30"
            }`}
          >
            {steps.length} Langkah
          </span>
          {effort && (
            <span className="px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-200 border border-amber-400/30 text-[10px] font-mono">
              ⏱️ {effort}
            </span>
          )}
          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      {/* Body */}
      <div className="p-3.5 sm:p-4 space-y-3.5 font-sans">
        <div className="space-y-1.5">
          <h4 className="text-sm sm:text-base font-bold text-white tracking-wide leading-snug">
            {planData.title || "Rencana Pengerjaan Proyek"}
          </h4>
          {planData.summary && (
            <p className="text-xs text-slate-300 leading-relaxed">
              {planData.summary}
            </p>
          )}
          {techStack.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1 font-mono">
              {techStack.map((tech, tIdx) => (
                <span
                  key={tIdx}
                  className="px-2 py-0.5 rounded-md bg-cyan-500/10 text-cyan-300 border border-cyan-400/20 text-[10px] font-medium"
                >
                  {tech}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Steps Checklist */}
        <div className="space-y-1.5">
          <p className={`text-[10px] font-mono font-bold uppercase tracking-wider ${isApproved ? "text-emerald-400/80" : "text-cyan-400/80"}`}>
            Tahapan Eksekusi:
          </p>
          <div className="space-y-1.5 max-h-[220px] overflow-y-auto custom-scrollbar pr-1 font-mono">
            {steps.map((st: any, idx: number) => {
              const isString = typeof st === "string";
              const rawTitle = isString ? st : (st?.title || st?.name || st?.step || "");
              const cleanTitle = rawTitle.replace(/^(?:Langkah\s*\d+\s*:\s*|Step\s*\d+\s*:\s*|\d+\.\s*)/i, "").trim() || rawTitle;
              const description = isString ? "" : st?.description;
              const stepDone = isCompleted || (!isString && st?.status === "completed");
              const stepInProg = !isString && st?.status === "in_progress";
              return (
                <div
                  key={st?.id || idx}
                  className={`flex items-start gap-2.5 p-2.5 rounded-xl border text-xs transition-all ${
                    stepDone
                      ? "bg-emerald-950/30 border-emerald-500/40 text-emerald-200"
                      : stepInProg
                      ? "bg-amber-950/30 border-amber-500/40 text-amber-100 animate-pulse"
                      : isApproved
                      ? "bg-emerald-950/10 border-emerald-500/15 text-slate-200"
                      : "bg-black/30 border-white/5 text-slate-200 hover:border-white/15"
                  }`}
                >
                  <span className={`mt-0.5 shrink-0 font-mono text-xs font-bold ${isApproved ? "text-emerald-400/90" : "text-cyan-400/90"}`}>
                    {stepDone ? "✅" : stepInProg ? "⚡" : `[${idx + 1}]`}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className={`font-semibold leading-snug ${stepDone ? "line-through text-slate-400" : "text-white"}`}>
                      {cleanTitle}
                    </p>
                    {description && (
                      <p className="text-[10.5px] text-slate-400 mt-0.5 leading-relaxed font-sans">
                        {description}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Files to Modify / Create */}
        {files.length > 0 && (
          <div className="space-y-1 pt-1.5 border-t border-white/10 font-mono">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Berkas Terkait:
            </p>
            <div className="flex flex-wrap gap-1.5">
              {files.map((fp, fIdx) => (
                <span
                  key={fIdx}
                  onClick={() => onOpenFile?.(fp)}
                  className="px-2 py-0.5 rounded-md bg-white/5 hover:bg-cyan-500/20 text-slate-300 hover:text-cyan-200 border border-white/10 text-[10px] cursor-pointer transition-all"
                  title={`Buka ${fp}`}
                >
                  📄 {fp}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Approval Action Bar */}
        {!isApproved && (
          <div className="pt-2.5 border-t border-white/10 flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 text-[10.5px] text-slate-400 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
              <span>Menunggu persetujuan user</span>
            </div>
            <div className="flex items-center gap-2">
              {onRejectPlan && (
                <button
                  type="button"
                  onClick={onRejectPlan}
                  className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/15 text-slate-300 hover:text-white border border-white/10 text-xs font-semibold font-mono cursor-pointer transition-all active:scale-95"
                >
                  Minta Revisi
                </button>
              )}
              {onApprovePlan && (
                <button
                  type="button"
                  onClick={() => onApprovePlan(planData)}
                  className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-amber-500/30 to-amber-600/40 hover:from-amber-500/50 hover:to-amber-600/60 text-amber-100 hover:text-white border border-amber-400/60 text-xs font-bold font-mono cursor-pointer transition-all shadow-[0_0_12px_rgba(251,191,36,0.25)] active:scale-95 flex items-center gap-1.5"
                >
                  <span>⚡ Setujui &amp; Eksekusi di Build Mode</span>
                </button>
              )}
            </div>
          </div>
        )}

        {isApproved && !isCompleted && (
          <div className="pt-2.5 border-t border-emerald-500/20 flex items-center gap-2 text-[10.5px] font-mono text-emerald-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Rencana disimpan ke memori. Agent sedang mengeksekusi...</span>
          </div>
        )}

        {isCompleted && (
          <div className="pt-2.5 border-t border-emerald-500/20 flex items-center gap-2 text-[10.5px] font-mono text-emerald-300">
            <span>✅</span>
            <span>Arsitektur proyek berhasil dibangun.</span>
          </div>
        )}
      </div>
    </div>
  );
}
