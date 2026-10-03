"use client";

import React, { useState, useEffect, useRef } from "react";

export interface FindBarProps {
  isOpen: boolean;
  onClose: () => void;
  onSearch: (query: string) => number; // returns total match count
  onNext: () => void;
  onPrevious: () => void;
  activeMatchIndex: number;
  totalMatches: number;
}

/**
 * FindBar.tsx — Anara In-Conversation Find Bar (Ctrl+F)
 *
 * Implements conversational transcript search:
 * - Pops up via Ctrl+F / Cmd+F with auto-focused search input.
 * - Live match counter (`1 of 5` or `No matches`).
 * - Step next / previous with Enter / Shift+Enter or Up/Down buttons.
 * - Escape closes cleanly and clears search highlights.
 * - Styled with Anara Liquid Glass Flat Hairlines.
 */
export function FindBar({
  isOpen,
  onClose,
  onSearch,
  onNext,
  onPrevious,
  activeMatchIndex,
  totalMatches,
}: FindBarProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      const id = requestAnimationFrame(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      });
      return () => cancelAnimationFrame(id);
    } else {
      setQuery("");
    }
  }, [isOpen]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    onSearch(val);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (e.shiftKey) {
        onPrevious();
      } else {
        onNext();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  if (!isOpen) return null;

  const matchLabel =
    query.trim() === ""
      ? ""
      : totalMatches > 0
      ? `${activeMatchIndex + 1} of ${totalMatches}`
      : "0 matches";

  return (
    <div
      role="search"
      aria-label="Find in transcript"
      className="pointer-events-auto fixed right-6 top-16 z-50 flex items-center gap-1.5 rounded-xl border border-white/[0.12] bg-[#060913]/95 px-3 py-1.5 font-sans text-xs shadow-2xl backdrop-blur-2xl animate-fade-in"
    >
      <div className="flex items-center gap-2">
        <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>

        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="Find in chat..."
          className="h-6 w-36 sm:w-48 bg-transparent text-xs text-slate-100 placeholder-slate-500 outline-none"
        />
      </div>

      {matchLabel && (
        <span className="min-w-[4rem] text-center font-mono text-[10.5px] text-slate-400 select-none">
          {matchLabel}
        </span>
      )}

      {/* Previous Button */}
      <button
        type="button"
        onClick={onPrevious}
        disabled={totalMatches === 0}
        aria-label="Previous match"
        className="flex h-6 w-6 items-center justify-center rounded text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors disabled:opacity-30 disabled:pointer-events-none cursor-pointer"
        title="Previous (Shift+Enter)"
      >
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
        </svg>
      </button>

      {/* Next Button */}
      <button
        type="button"
        onClick={onNext}
        disabled={totalMatches === 0}
        aria-label="Next match"
        className="flex h-6 w-6 items-center justify-center rounded text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors disabled:opacity-30 disabled:pointer-events-none cursor-pointer"
        title="Next (Enter)"
      >
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Close Button */}
      <button
        type="button"
        onClick={onClose}
        aria-label="Close find bar"
        className="flex h-6 w-6 items-center justify-center rounded text-slate-400 hover:text-rose-300 hover:bg-white/[0.08] transition-colors cursor-pointer ml-1"
        title="Close (Esc)"
      >
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export default FindBar;
