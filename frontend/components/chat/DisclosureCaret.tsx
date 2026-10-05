"use client";

import React from "react";

export interface DisclosureCaretProps {
  open: boolean;
  className?: string;
  size?: number | string;
}

/**
 * DisclosureCaret — Minimal chrome caret for collapsible sections.
 * Points right when closed (▶), rotates smoothly to point down (▼) when open.
 */
export function DisclosureCaret({ open, className = "", size = 12 }: DisclosureCaretProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      className={`shrink-0 transition-transform duration-150 ${open ? "rotate-90" : ""} ${className}`}
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M9 5l7 7-7 7" />
    </svg>
  );
}

export default DisclosureCaret;
