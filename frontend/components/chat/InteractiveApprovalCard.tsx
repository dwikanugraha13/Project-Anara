"use client";

import React, { useState, useEffect, useRef } from "react";

export interface InteractiveApprovalCardProps {
  planId?: string;
  toolName?: string;
  commandPreview?: string;
  rationale?: string;
  riskLevel?: "low" | "medium" | "high" | "critical";
  onApprove?: (planId: string, scope: "once" | "session") => void;
  onReject?: (planId: string) => void;
}

/**
 * InteractiveApprovalCard.tsx — Anara Flat Hairline Interactive Approval Card
 *
 * Implements conversational gate approval with 3 clean actions:
 * - "Approve Once": Authorizes this single tool call execution (HotKey: Enter).
 * - "Allow for Session": Grants continuous permission for this tool within active session.
 * - "Reject": Halts the mutation safely (HotKey: Esc).
 */
export function InteractiveApprovalCard({
  planId = "default",
  toolName = "terminal",
  commandPreview,
  rationale,
  riskLevel = "medium",
  onApprove,
  onReject,
}: InteractiveApprovalCardProps) {
  const [decided, setDecided] = useState<"once" | "session" | "deny" | null>(null);
  const [copied, setCopied] = useState(false);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Capture previously active element for seamless focus restoration
  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement | null;
  }, []);

  const restoreFocus = () => {
    if (previousFocusRef.current && typeof previousFocusRef.current.focus === "function") {
      try {
        previousFocusRef.current.focus();
      } catch {
        // Safe fallback
      }
    }
  };

  // Keyboard navigation: Enter -> Approve Once, Esc -> Reject
  useEffect(() => {
    if (decided) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Guard: Ignore if user is currently typing inside an input/textarea
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      const isInput = tag === "input" || tag === "textarea" || target?.isContentEditable;
      if (isInput) return;

      if (e.key === "Enter" && !e.repeat) {
        e.preventDefault();
        setDecided("once");
        onApprove?.(planId, "once");
        restoreFocus();
      } else if (e.key === "Escape") {
        e.preventDefault();
        setDecided("deny");
        onReject?.(planId);
        restoreFocus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [decided, planId, onApprove, onReject]);

  const handleCopyPreview = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!commandPreview) return;
    navigator.clipboard.writeText(commandPreview).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const riskBadgeClass =
    riskLevel === "critical" || riskLevel === "high"
      ? "bg-rose-500/15 text-rose-300 border-rose-400/30"
      : riskLevel === "medium"
      ? "bg-amber-500/15 text-amber-300 border-amber-400/30"
      : "bg-cyan-500/15 text-cyan-300 border-cyan-400/30";

  return (
    <div className="my-2.5 w-full max-w-3xl select-none font-sans text-xs">
      <div className="rounded-xl border border-white/[0.08] bg-[#060913]/90 p-3.5 shadow-2xl backdrop-blur-2xl transition-all">
        {/* Header */}
        <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="font-semibold text-white tracking-wide">Action Requires Approval</span>
          </div>
          <span className={`rounded-md border px-2 py-0.5 text-[10px] font-mono font-medium uppercase ${riskBadgeClass}`}>
            {riskLevel}
          </span>
        </div>

        {/* Rationale / Explanation */}
        {rationale && (
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-slate-300 font-sans">
            {rationale}
          </p>
        )}

        {/* Command or Target Payload Preview */}
        {commandPreview && (
          <div className="mt-2.5 rounded-lg border border-white/[0.06] bg-black/60 p-2 font-mono text-[11px] text-cyan-300 select-text">
            <div className="flex items-center justify-between pb-1 mb-1 border-b border-white/[0.04] text-slate-500 text-[10px] select-none">
              <div className="flex items-center gap-1.5">
                <span>$</span>
                <span>{toolName}</span>
              </div>
              <button
                type="button"
                onClick={handleCopyPreview}
                className="text-slate-400 hover:text-white px-1.5 py-0.5 rounded hover:bg-white/[0.05] transition-colors cursor-pointer"
                title="Copy command"
              >
                {copied ? <span className="text-emerald-400">Copied</span> : "Copy"}
              </button>
            </div>
            <pre className="max-h-60 overflow-x-auto overflow-y-auto custom-scrollbar whitespace-pre font-mono text-[11px] text-slate-200">
              {commandPreview}
            </pre>
          </div>
        )}

        {/* Decision Actions */}
        <div className="mt-3 flex items-center justify-end gap-2 pt-1">
          {decided ? (
            <span className="text-[11px] font-mono text-slate-400 italic">
              Decision recorded: <strong className="text-cyan-300 capitalize">{decided}</strong>
            </span>
          ) : (
            <>
              <button
                type="button"
                onClick={() => {
                  setDecided("deny");
                  onReject?.(planId);
                  restoreFocus();
                }}
                className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] font-medium text-slate-300 transition-colors hover:bg-rose-500/20 hover:text-rose-200 hover:border-rose-400/30 cursor-pointer flex items-center gap-1.5"
                title="Reject this action (Esc)"
              >
                <span>Reject</span>
                <kbd className="px-1 py-px rounded bg-white/[0.06] text-[9.5px] font-mono text-slate-400">Esc</kbd>
              </button>

              <button
                type="button"
                onClick={() => {
                  setDecided("session");
                  onApprove?.(planId, "session");
                  restoreFocus();
                }}
                className="rounded-lg border border-white/[0.08] bg-white/[0.05] px-3 py-1 text-[11px] font-medium text-slate-200 transition-colors hover:bg-white/[0.1] hover:text-white cursor-pointer"
              >
                Allow for Session
              </button>

              <button
                type="button"
                onClick={() => {
                  setDecided("once");
                  onApprove?.(planId, "once");
                  restoreFocus();
                }}
                className="rounded-lg border border-cyan-400/40 bg-cyan-500/20 px-3.5 py-1 text-[11px] font-medium text-cyan-200 shadow-[0_0_12px_rgba(34,211,238,0.2)] transition-all hover:bg-cyan-500/30 hover:text-white cursor-pointer flex items-center gap-1.5"
                title="Approve Once (Enter)"
              >
                <span>Approve Once</span>
                <kbd className="px-1 py-px rounded bg-cyan-500/30 text-[9.5px] font-mono text-cyan-200">↵</kbd>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default InteractiveApprovalCard;
