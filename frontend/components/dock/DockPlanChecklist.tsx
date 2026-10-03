import React, { useState, useCallback, useEffect, useRef } from "react";

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
  status?: "pending_approval" | "executing" | "completed";
}

export interface DockPlanChecklistProps {
  checklistData: ChecklistData;
  isExpanded: boolean;
  onToggle: () => void;
  onApprovePlan?: () => void;
  onRejectPlan?: () => void;
  onToggleStep?: (stepIndex: number) => void;
}

export function DockPlanChecklist({
  checklistData,
  isExpanded,
  onToggle,
  onApprovePlan,
  onRejectPlan,
  onToggleStep,
}: DockPlanChecklistProps) {
  // Optimistic local toggling for instant micro-interaction
  const [localOverrides, setLocalOverrides] = useState<Record<number, boolean>>({});
  const [isLingerComplete, setIsLingerComplete] = useState(false);
  const lingerTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  if (!checklistData || !checklistData.items || checklistData.items.length === 0) {
    return null;
  }

  const effectiveItems = checklistData.items.map((step, idx) => ({
    ...step,
    isCompleted: localOverrides[idx] !== undefined ? localOverrides[idx] : !!step.isCompleted,
  }));

  const effectiveCompletedCount = effectiveItems.filter((i) => i.isCompleted).length;
  const isAllDone = effectiveCompletedCount === checklistData.total;

  // Anara Standard: Linger for 3.5s upon completion so checkmark lands, then auto-dismiss
  useEffect(() => {
    if (isAllDone && !isLingerComplete) {
      if (lingerTimeoutRef.current) clearTimeout(lingerTimeoutRef.current);
      lingerTimeoutRef.current = setTimeout(() => {
        setIsLingerComplete(true);
      }, 3500);
    } else if (!isAllDone) {
      setIsLingerComplete(false);
      if (lingerTimeoutRef.current) {
        clearTimeout(lingerTimeoutRef.current);
        lingerTimeoutRef.current = null;
      }
    }
    return () => {
      if (lingerTimeoutRef.current) clearTimeout(lingerTimeoutRef.current);
    };
  }, [isAllDone, isLingerComplete]);

  if (isLingerComplete) return null;

  const handleToggleStep = (index: number) => {
    const currentVal = effectiveItems[index]?.isCompleted ?? false;
    const newVal = !currentVal;
    setLocalOverrides((prev) => ({ ...prev, [index]: newVal }));
    onToggleStep?.(index);
  };

  const isPendingApproval = checklistData.status === "pending_approval" || (!checklistData.status && (onApprovePlan || onRejectPlan));

  return (
    <div className="w-full rounded-xl border border-white/[0.08] hover:border-white/[0.14] bg-[#060913]/90 pointer-events-auto backdrop-blur-xl overflow-hidden transition-all duration-200 relative select-none animate-fade-in shadow-lg shadow-black/40">
      <div className="w-full flex items-center justify-between px-3.5 py-2 hover:bg-white/[0.02] transition-colors">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={isExpanded}
          aria-label="Toggle plan checklist details"
          className="flex items-center gap-2.5 min-w-0 flex-1 text-left cursor-pointer"
        >
          <span
            className={`px-1.5 py-0.5 rounded-[5px] font-mono text-[9.5px] font-bold border transition-colors shrink-0 ${
              isAllDone
                ? "bg-emerald-500/15 border-emerald-400/30 text-emerald-300"
                : "bg-cyan-500/15 border-cyan-400/30 text-cyan-300"
            }`}
          >
            {effectiveCompletedCount}/{checklistData.total}
          </span>
          <span className="text-[12px] font-medium text-slate-200 tracking-tight font-sans truncate">
            {checklistData.title}
          </span>
        </button>

        <div className="flex items-center gap-2 shrink-0">
          {isPendingApproval && onRejectPlan && (
            <button
              type="button"
              onClick={onRejectPlan}
              className="px-2 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-400/25 text-[11px] font-mono font-medium flex items-center transition-all cursor-pointer"
              title="Dismiss plan"
            >
              <span>Dismiss</span>
            </button>
          )}
          {isPendingApproval && onApprovePlan && (
            <button
              type="button"
              onClick={onApprovePlan}
              className="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-400/30 text-[11px] font-mono font-bold flex items-center gap-1 transition-all cursor-pointer shadow-sm"
            >
              <span>Approve & Run</span>
            </button>
          )}
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={isExpanded}
            aria-label="Toggle plan checklist"
            className="p-1 rounded text-slate-400 hover:text-white transition-colors cursor-pointer"
          >
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
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="px-2.5 pb-2 pt-1 space-y-0.5 border-t border-white/[0.06] max-h-[260px] overflow-y-auto custom-scrollbar select-text">
          {effectiveItems.map((step, sIdx) => {
            const isDone = step.isCompleted;
            const isActive = step.isInProgress;
            const cleanTitle = step.title.replace(/^(?:\[?(?:Step|Langkah)\s*\d+\]?[\s:.-]*|\d+[\s:.-]+)/i, "").trim() || step.title;

            return (
              <div
                key={`${cleanTitle}-${sIdx}`}
                role="checkbox"
                aria-checked={isDone}
                tabIndex={0}
                onClick={() => handleToggleStep(sIdx)}
                onKeyDown={(e) => {
                  if (e.key === " " || e.key === "Enter") {
                    e.preventDefault();
                    handleToggleStep(sIdx);
                  }
                }}
                className={`group flex items-start gap-2.5 py-1.5 px-2 rounded-xl transition-colors cursor-pointer select-none border ${
                  isDone
                    ? "bg-white/[0.015] hover:bg-white/[0.04] border-transparent"
                    : isActive
                    ? "bg-cyan-500/[0.08] border-cyan-400/25"
                    : "hover:bg-white/[0.04] border-transparent"
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
                      <span className="w-2.5 h-2.5 rounded-full border border-cyan-400/60 border-t-transparent animate-spin" />
                    </div>
                  ) : (
                    <div className="w-3.5 h-3.5 rounded-full border border-white/20 bg-white/5 group-hover:border-white/40 transition-colors" />
                  )}
                </div>
                <span
                  className={`text-[11px] leading-snug font-sans break-words min-w-0 flex-1 ${
                    isDone
                      ? "line-through text-slate-500/80"
                      : isActive
                      ? "text-cyan-200 font-medium"
                      : "text-slate-300/90 group-hover:text-white"
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
