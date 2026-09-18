import React from "react";

export interface ChecklistStep {
  title: string;
  isCompleted?: boolean;
  isInProgress?: boolean;
}

export interface ChecklistData {
  title: string;
  items: ChecklistStep[];
  completedCount: number;
  total: number;
}

export interface DockPlanChecklistProps {
  checklistData: ChecklistData;
  isExpanded: boolean;
  onToggle: () => void;
}

export function DockPlanChecklist({ checklistData, isExpanded, onToggle }: DockPlanChecklistProps) {
  if (!checklistData || !checklistData.items || checklistData.items.length === 0) {
    return null;
  }

  return (
    <div className="w-full liquid-glass rounded-2xl border border-white/15 shadow-2xl shadow-black/80 pointer-events-auto backdrop-blur-3xl overflow-hidden transition-all duration-300 relative select-none animate-fade-in">
      <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-white/25 to-transparent pointer-events-none" />

      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-3.5 py-2.5 hover:bg-white/[0.04] transition-colors cursor-pointer text-left"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className={`px-1.5 py-0.5 rounded-[5px] font-mono text-[9.5px] font-bold border transition-colors shrink-0 ${
              checklistData.completedCount === checklistData.total
                ? "bg-emerald-500/15 border-emerald-400/30 text-emerald-300 shadow-[0_0_8px_rgba(52,211,153,0.15)]"
                : "bg-cyan-500/15 border-cyan-400/30 text-cyan-300"
            }`}
          >
            {checklistData.completedCount}/{checklistData.total}
          </span>
          <span className="text-[12px] font-medium text-slate-200 tracking-tight font-sans truncate">
            {checklistData.title}
          </span>
        </div>
        <div className="p-0.5 rounded text-slate-400 hover:text-white transition-colors shrink-0">
          <svg
            className={`w-3.5 h-3.5 transition-transform duration-200 ease-out ${
              isExpanded ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {isExpanded && (
        <div className="px-2.5 pb-2 pt-1 space-y-0.5 border-t border-white/[0.08] max-h-[120px] overflow-y-auto no-scrollbar">
          {checklistData.items.map((step, sIdx) => {
            const isDone = step.isCompleted;
            const isActive = step.isInProgress;
            const cleanTitle = step.title.replace(/^Langkah\s*\d+\s*:\s*/i, "");

            return (
              <div
                key={sIdx}
                className={`flex items-start gap-2.5 py-1.5 px-2 rounded-xl transition-all ${
                  isDone
                    ? "bg-white/[0.015] hover:bg-white/[0.03]"
                    : isActive
                    ? "bg-cyan-500/10 border border-cyan-400/25 shadow-[0_0_10px_rgba(34,211,238,0.1)]"
                    : "hover:bg-white/[0.03]"
                }`}
              >
                <div className="mt-0.5 shrink-0">
                  {isDone ? (
                    <div className="w-3.5 h-3.5 rounded-full bg-emerald-400/20 border border-emerald-400 flex items-center justify-center text-emerald-300">
                      <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  ) : isActive ? (
                    <div className="relative flex items-center justify-center w-3.5 h-3.5">
                      <span className="animate-ping absolute inline-flex h-2.5 w-2.5 rounded-full bg-cyan-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
                    </div>
                  ) : (
                    <div className="w-3.5 h-3.5 rounded-full border border-white/20 bg-white/5" />
                  )}
                </div>
                <span
                  className={`text-[11px] leading-snug font-sans break-words min-w-0 ${
                    isDone
                      ? "line-through text-slate-500/80"
                      : isActive
                      ? "text-cyan-200 font-medium"
                      : "text-slate-300/90"
                  }`}
                >
                  {cleanTitle}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
