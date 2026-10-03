"use client";

import React from "react";

export type ApprovalMode = "manual" | "smart" | "off";

export interface ApprovalModePopoverProps {
  isOpen: boolean;
  onClose: () => void;
  mode: ApprovalMode;
  onChange: (mode: ApprovalMode) => void;
}

interface ModeOption {
  id: ApprovalMode;
  title: string;
  description: string;
}

const MODE_OPTIONS: ModeOption[] = [
  {
    id: "manual",
    title: "Manual",
    description: "Ask before actions that require approval",
  },
  {
    id: "smart",
    title: "Smart",
    description: "Automatically assess actions and ask when needed",
  },
  {
    id: "off",
    title: "Off",
    description: "Run without approval prompts",
  },
];

export default function ApprovalModePopover({
  isOpen,
  onClose,
  mode,
  onChange,
}: ApprovalModePopoverProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 pointer-events-auto" onClick={onClose}>
      <div
        className="absolute bottom-8 right-32 w-72 p-1.5 rounded-xl bg-[#060913]/95 backdrop-blur-2xl border border-white/15 shadow-[0_20px_50px_rgba(0,0,0,0.85)] text-slate-200 select-none animate-in fade-in zoom-in-95 duration-100"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-2.5 py-1.5 pb-2 border-b border-white/[0.08] flex items-center justify-between">
          <span className="text-[11px] font-semibold text-slate-400 font-sans tracking-tight">
            Approval mode
          </span>
          <span className="text-[9.5px] font-mono px-1.5 py-0.5 rounded bg-white/[0.05] border border-white/[0.08] text-cyan-400 capitalize">
            {mode}
          </span>
        </div>

        {/* Options List */}
        <div className="mt-1 flex flex-col gap-0.5">
          {MODE_OPTIONS.map((opt) => {
            const isSelected = mode === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => {
                  onChange(opt.id);
                  onClose();
                }}
                className={`w-full flex items-start justify-between text-left px-2.5 py-2 rounded-lg transition-all cursor-pointer ${
                  isSelected
                    ? "bg-white/[0.08] text-white border border-white/10"
                    : "hover:bg-white/[0.04] text-slate-300 hover:text-white border border-transparent"
                }`}
              >
                <div className="flex flex-col min-w-0 pr-2">
                  <span className="text-xs font-semibold tracking-tight text-white font-sans">
                    {opt.title}
                  </span>
                  <span className="text-[10.5px] leading-tight text-slate-400 mt-0.5 font-sans">
                    {opt.description}
                  </span>
                </div>

                {isSelected && (
                  <div className="shrink-0 mt-0.5 text-cyan-400">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2.2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
