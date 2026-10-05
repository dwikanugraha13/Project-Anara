"use client";

import React from "react";

export type ApprovalMode = "manual" | "smart" | "off";

export interface ApprovalModePopoverProps {
  isOpen: boolean;
  onClose: () => void;
  mode: ApprovalMode;
  onChange: (mode: ApprovalMode) => void;
  anchored?: boolean;
  className?: string;
}

interface ModeOption {
  id: ApprovalMode;
  title: string;
  description: string;
  icon: React.ReactNode;
}

const ShieldIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
      d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
    />
  </svg>
);

const SparklesIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
      d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"
    />
  </svg>
);

const ZapIcon = ({ filled }: { filled?: boolean }) => (
  <svg className="w-3.5 h-3.5" fill={filled ? "currentColor" : "none"} stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={filled ? 0 : 1.8}
      d="M13 10V3L4 14h7v7l9-11h-7z"
    />
  </svg>
);

const MODE_OPTIONS: ModeOption[] = [
  {
    id: "manual",
    title: "Manual",
    description: "Ask before actions that require approval",
    icon: <ShieldIcon />,
  },
  {
    id: "smart",
    title: "Smart",
    description: "Automatically assess actions and ask when needed",
    icon: <SparklesIcon />,
  },
  {
    id: "off",
    title: "Off",
    description: "Run without approval prompts",
    icon: <ZapIcon filled />,
  },
];

const MODE_COLORS: Record<ApprovalMode, string> = {
  manual: "text-amber-400",
  smart: "text-cyan-400",
  off: "text-emerald-400",
};

export default function ApprovalModePopover({
  isOpen,
  onClose,
  mode,
  onChange,
  anchored = false,
  className,
}: ApprovalModePopoverProps) {
  if (!isOpen) return null;

  const content = (
    <div
      role="dialog"
      aria-label="Approval Mode Popover"
      className={
        anchored
          ? `absolute bottom-9 left-0 z-50 w-72 p-1.5 rounded-xl bg-[#060913]/95 backdrop-blur-2xl border border-white/15 shadow-[0_20px_50px_rgba(0,0,0,0.85)] text-slate-200 select-none animate-in fade-in zoom-in-95 duration-100 ${
              className || ""
            }`
          : "absolute bottom-8 right-32 w-72 p-1.5 rounded-xl bg-[#060913]/95 backdrop-blur-2xl border border-white/15 shadow-[0_20px_50px_rgba(0,0,0,0.85)] text-slate-200 select-none animate-in fade-in zoom-in-95 duration-100"
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
        <span className={`text-[9.5px] font-mono px-1.5 py-0.5 rounded bg-white/[0.05] border border-white/[0.08] capitalize ${MODE_COLORS[mode]}`}>
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
              className={`w-full flex items-start gap-2 text-left px-2.5 py-2 rounded-lg transition-all cursor-pointer ${
                isSelected
                  ? "bg-white/[0.08] text-white border border-white/10"
                  : "hover:bg-white/[0.04] text-slate-300 hover:text-white border border-transparent"
              }`}
            >
              {/* Icon */}
              <div className={`shrink-0 mt-0.5 ${isSelected ? MODE_COLORS[opt.id] : 'text-slate-500'}`}>
                {opt.icon}
              </div>

              {/* Label + Description */}
              <div className="flex flex-col min-w-0 flex-1">
                <span className="text-xs font-semibold tracking-tight text-white font-sans">
                  {opt.title}
                </span>
                <span className="text-[10.5px] leading-tight text-slate-400 mt-0.5 font-sans">
                  {opt.description}
                </span>
              </div>

              {/* Checkmark */}
              {isSelected && (
                <div className={`shrink-0 mt-0.5 ${MODE_COLORS[opt.id]}`}>
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
