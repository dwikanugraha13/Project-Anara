"use client";

import React from "react";

export type ApprovalMode = "plan" | "auto" | "off" | "manual" | "smart";

export function normalizeApprovalMode(raw?: string | null): "plan" | "auto" | "off" {
  const clean = (raw || "").trim().toLowerCase();
  if (clean === "plan" || clean === "manual") return "plan";
  if (clean === "off" || clean === "yolo") return "off";
  return "auto";
}

export interface ApprovalModePopoverProps {
  isOpen: boolean;
  onClose: () => void;
  mode: ApprovalMode;
  onChange: (mode: "plan" | "auto" | "off") => void;
  anchored?: boolean;
  align?: "left" | "right";
  className?: string;
}

interface ModeOption {
  id: "plan" | "auto" | "off";
  title: string;
  description: string;
}

const MODE_OPTIONS: ModeOption[] = [
  {
    id: "plan",
    title: "Plan",
    description: "Propose plans and ask before modifying files or executing commands",
  },
  {
    id: "auto",
    title: "Auto",
    description: "Execute project files autonomously with smart safety checks",
  },
  {
    id: "off",
    title: "Off",
    description: "Run without approval prompts (catastrophic commands still blocked)",
  },
];

const MODE_BADGE_STYLES: Record<string, string> = {
  plan: "text-amber-300 bg-amber-500/10 border-amber-400/25",
  manual: "text-amber-300 bg-amber-500/10 border-amber-400/25",
  auto: "text-sky-300 bg-sky-500/10 border-sky-400/25",
  smart: "text-sky-300 bg-sky-500/10 border-sky-400/25",
  off: "text-rose-300 bg-rose-500/10 border-rose-400/25",
  yolo: "text-rose-300 bg-rose-500/10 border-rose-400/25",
};

const OPTION_THEMES: Record<"plan" | "auto" | "off", { activeBg: string; activeBorder: string; activeText: string; checkColor: string }> = {
  plan: {
    activeBg: "bg-amber-500/[0.08]",
    activeBorder: "border-amber-400/30",
    activeText: "text-amber-200",
    checkColor: "text-amber-300",
  },
  auto: {
    activeBg: "bg-sky-500/[0.08]",
    activeBorder: "border-sky-400/30",
    activeText: "text-sky-200",
    checkColor: "text-sky-300",
  },
  off: {
    activeBg: "bg-rose-500/[0.08]",
    activeBorder: "border-rose-400/30",
    activeText: "text-rose-200",
    checkColor: "text-rose-300",
  },
};

export default function ApprovalModePopover({
  isOpen,
  onClose,
  mode,
  onChange,
  anchored = false,
  align = "right",
  className,
}: ApprovalModePopoverProps) {
  if (!isOpen) return null;

  const content = (
    <div
      role="dialog"
      aria-label="Approval Mode Popover"
      className={
        anchored
          ? `absolute bottom-9 ${align === "right" ? "right-0" : "left-0"} z-50 w-64 sm:w-72 max-w-[calc(100vw-2rem)] p-1.5 rounded-xl bg-[#060913]/98 backdrop-blur-2xl border border-white/15 shadow-[0_20px_50px_rgba(0,0,0,0.9)] text-slate-200 select-none animate-in fade-in zoom-in-95 duration-100 ${
              className || ""
            }`
          : "absolute bottom-8 right-32 w-64 sm:w-72 p-1.5 rounded-xl bg-[#060913]/98 backdrop-blur-2xl border border-white/15 shadow-[0_20px_50px_rgba(0,0,0,0.9)] text-slate-200 select-none animate-in fade-in zoom-in-95 duration-100"
      }
      onClick={(e) => {
        e.stopPropagation();
        e.nativeEvent?.stopImmediatePropagation?.();
      }}
    >
      {/* Header */}
      <div className="px-2.5 py-1.5 pb-2 border-b border-white/[0.08] flex items-center justify-between">
        <span className="text-[11px] font-semibold text-slate-400 font-sans tracking-tight">
          Approval mode
        </span>
        <span className={`text-[9.5px] font-mono px-1.5 py-0.5 rounded border capitalize ${MODE_BADGE_STYLES[normalizeApprovalMode(mode)] || "text-slate-300 bg-white/[0.05] border-white/[0.08]"}`}>
          {normalizeApprovalMode(mode)}
        </span>
      </div>

      {/* Options List */}
      <div className="mt-1 flex flex-col gap-0.5">
        {MODE_OPTIONS.map((opt) => {
          const isSelected = normalizeApprovalMode(mode) === opt.id;
          const theme = OPTION_THEMES[opt.id];
          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => {
                onChange(opt.id);
                onClose();
              }}
              className={`w-full flex items-start gap-2 text-left px-2.5 py-2 rounded-lg transition-all cursor-pointer border ${
                isSelected
                  ? `${theme.activeBg} ${theme.activeBorder} text-white`
                  : "hover:bg-white/[0.04] text-slate-300 hover:text-white border-transparent"
              }`}
            >
              {/* Label + Description */}
              <div className="flex flex-col min-w-0 flex-1">
                <span className={`text-xs font-semibold tracking-tight font-sans ${isSelected ? theme.activeText : "text-white"}`}>
                  {opt.title}
                </span>
                <span className="text-[10.5px] leading-tight text-slate-400 mt-0.5 font-sans">
                  {opt.description}
                </span>
              </div>

              {/* Checkmark */}
              {isSelected && (
                <div className={`shrink-0 mt-0.5 ${theme.checkColor}`}>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Hardline Floor Notice */}
      <div className="px-2.5 py-1.5 mt-1 border-t border-white/[0.08]">
        <p className="text-[9.5px] text-slate-500 leading-tight font-sans">
          Catastrophic commands (rm /, mkfs, fork bombs) are always blocked,
          even in Off mode.
        </p>
      </div>
    </div>
  );

  if (anchored) {
    return content;
  }

  return (
    <div className="fixed inset-0 z-50 pointer-events-auto" onClick={onClose}>
      {content}
    </div>
  );
}
