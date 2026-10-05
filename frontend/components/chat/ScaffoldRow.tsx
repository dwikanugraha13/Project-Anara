"use client";

import React, { ReactNode } from "react";
import { DisclosureCaret } from "./DisclosureCaret";

/**
 * Transcript scaffolding typography constants:
 * Quiet lines indicating what the agent DID rather than what it said.
 */
export const SCAFFOLD_LABEL_CLASS =
  "text-[11px] leading-relaxed text-slate-400 font-mono select-none";

/** Durations, counts, line markers trailing a scaffold label. */
export const SCAFFOLD_META_CLASS =
  "shrink-0 text-[10px] font-mono tabular-nums text-slate-500 select-none";

/** Fixed leading cell for glyphs (status dot, tool icon, spinner) so labels share a precise left edge. */
export const SCAFFOLD_GLYPH_CLASS =
  "grid h-3.5 w-3.5 shrink-0 place-items-center self-center";

export interface DisclosureRowProps {
  action?: ReactNode;
  children: ReactNode;
  onToggle?: () => void;
  open?: boolean;
  trailing?: ReactNode;
  className?: string;
}

/**
 * DisclosureRow — Shared header row for any collapsible block (thinking, tool group, tool entry).
 * Uses max-w-fit hit-target so clicking empty trailing space never triggers accidental toggles.
 */
export function DisclosureRow({
  action,
  children,
  onToggle,
  open = false,
  trailing,
  className = "",
}: DisclosureRowProps) {
  return (
    <div className={`group/disclosure-row relative flex w-full max-w-full min-w-0 items-center text-slate-400 ${className}`}>
      <button
        type="button"
        aria-expanded={onToggle ? open : undefined}
        disabled={!onToggle}
        onClick={onToggle}
        className={`flex min-w-0 max-w-fit items-center gap-1.5 text-left transition-colors select-none ${
          onToggle
            ? "cursor-pointer hover:text-slate-200 focus-visible:text-slate-100 focus-visible:outline-none"
            : "cursor-default"
        }`}
      >
        <span className="flex min-w-0 items-center gap-1.5">{children}</span>
        {onToggle && (
          <span
            className={`flex h-4 shrink-0 items-center justify-center transition-opacity duration-150 ${
              open
                ? "opacity-80 text-slate-300"
                : "opacity-40 group-hover/disclosure-row:opacity-80 group-focus-within/disclosure-row:opacity-80 text-slate-400"
            }`}
          >
            <DisclosureCaret open={open} size={11} />
          </span>
        )}
      </button>

      {action && (
        <span className="ml-auto flex h-4 shrink-0 items-center self-center pl-1.5">
          {action}
        </span>
      )}

      {trailing && (
        <span className={`${action ? "" : "ml-auto"} flex h-4 shrink-0 items-center pl-1.5`}>
          {trailing}
        </span>
      )}
    </div>
  );
}

/**
 * ScaffoldRow — 1-line standard scaffold row with leading glyph alignment.
 */
export function ScaffoldRow({
  children,
  onToggle,
  open = false,
  trailing,
  action,
  className = "",
}: {
  children: ReactNode;
  onToggle?: () => void;
  open?: boolean;
  trailing?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <DisclosureRow
      onToggle={onToggle}
      open={open}
      trailing={trailing}
      action={action}
      className={className}
    >
      <span className="flex min-w-0 items-center gap-1.5">{children}</span>
    </DisclosureRow>
  );
}

export default ScaffoldRow;
