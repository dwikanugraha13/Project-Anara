"use client";

import React, { useState } from "react";
import { TodoData } from "../hud/types";

// ── TODO CHECKLIST CARD ──────────────────────────────────────────────────
export function TodoChecklistCard({
  todoData,
  onDismiss,
}: {
  todoData?: TodoData | null;
  onDismiss?: () => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!todoData || !todoData.items || todoData.items.length === 0) return null;
  const total = todoData.items.length;
  const completed = todoData.items.filter((t) => t.is_completed).length;

  return (
    <div className="my-1.5 font-mono text-xs select-none">
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        className="flex items-center gap-2 text-left text-slate-300 hover:text-white transition-colors cursor-pointer py-1 group"
      >
        <span className="relative flex h-2 w-2 shrink-0">
          <span className={`inline-flex rounded-full h-1.5 w-1.5 ${completed === total ? "bg-emerald-400" : "bg-cyan-400"}`} />
        </span>
        <span className="font-semibold text-slate-200 tracking-tight text-[11.5px]">Tasks</span>
        <span className="text-slate-400 text-[11px]">({completed} of {total} completed)</span>
        <svg
          className={`w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ${
            isExpanded ? "rotate-90" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${
          isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div className="pl-4 py-1.5 space-y-1.5 border-l border-white/[0.08] my-1 font-mono text-[11px]">
            {todoData.items.map((item: any, idx: number) => (
              <div
                key={idx}
                className={`flex items-start gap-2 p-1 rounded transition-colors ${
                  item.is_completed ? "text-slate-500 line-through" : "text-slate-200 hover:bg-white/[0.02]"
                }`}
              >
                <span
                  className={`w-3.5 h-3.5 rounded mt-0.5 flex items-center justify-center text-[9px] shrink-0 font-bold ${
                    item.is_completed
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                      : "border border-white/20 text-transparent"
                  }`}
                >
                  {item.is_completed && (
                    <svg className="w-2.5 h-2.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </span>
                <div className="flex-1 min-w-0 font-sans">
                  <p className="leading-snug">{item.title}</p>
                  {item.content && (
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5">{item.content}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
