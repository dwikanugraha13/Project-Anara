"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  SidebarFilterState,
  SidebarGrouping,
  SidebarOrdering,
  DEFAULT_SIDEBAR_FILTER_STATE,
} from "./types";

export interface SidebarFilterMenuProps {
  isOpen: boolean;
  onClose: () => void;
  filterState: SidebarFilterState;
  onChangeFilterState: (partial: Partial<SidebarFilterState>) => void;
  availableProjects?: Array<{ name: string; path: string }>;
  onExpandAll?: () => void;
  onCollapseAll?: () => void;
  onResetDefaults?: () => void;
}

type AccordionKey = "grouping" | "ordering" | "show" | "channel" | "project";

export default function SidebarFilterMenu({
  isOpen,
  onClose,
  filterState,
  onChangeFilterState,
  availableProjects = [],
  onExpandAll,
  onCollapseAll,
  onResetDefaults,
}: SidebarFilterMenuProps) {
  const [openAccordion, setOpenAccordion] = useState<AccordionKey | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Outside click & Escape listener
  useEffect(() => {
    if (!isOpen) return;

    const handlePointerDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  const toggleAccordion = useCallback((key: AccordionKey) => {
    setOpenAccordion((prev) => (prev === key ? null : key));
  }, []);

  if (!isOpen) return null;

  // Options Definitions
  const groupingOptions: Array<{ id: SidebarGrouping; label: string }> = [
    { id: "project", label: "Workspace / Project" },
    { id: "date", label: "Date (Today / Yesterday)" },
    { id: "status", label: "Status (Working / Done)" },
    { id: "none", label: "None (Flat stream)" },
  ];

  const orderingOptions: Array<{ id: SidebarOrdering; label: string }> = [
    { id: "updated", label: "Last updated" },
    { id: "created", label: "Date created" },
    { id: "tokens", label: "Total tokens" },
    { id: "status", label: "Status urgency" },
  ];

  const channelOptions: Array<{
    id: "all" | "web" | "cli" | "telegram" | "whatsapp";
    label: string;
  }> = [
    { id: "all", label: "All channels" },
    { id: "web", label: "Web Studio" },
    { id: "cli", label: "Terminal CLI" },
    { id: "telegram", label: "Telegram" },
    { id: "whatsapp", label: "WhatsApp" },
  ];

  const handleProjectToggle = (path: string) => {
    const current = filterState.projectFilter || [];
    let updated: string[];
    if (current.includes(path)) {
      updated = current.filter((p) => p !== path);
    } else {
      updated = [...current, path];
    }
    onChangeFilterState({ projectFilter: updated });
  };

  const handleReset = () => {
    if (onResetDefaults) {
      onResetDefaults();
    } else {
      onChangeFilterState(DEFAULT_SIDEBAR_FILTER_STATE);
    }
    setOpenAccordion(null);
  };

  return (
    <div
      ref={menuRef}
      role="dialog"
      aria-label="View and filter options"
      onClick={(e) => e.stopPropagation()}
      className="absolute right-0 top-full mt-1.5 z-50 w-60 py-1.5 rounded-xl bg-[#060913]/98 border border-white/[0.12] backdrop-blur-2xl shadow-[0_20px_45px_rgba(0,0,0,0.92),0_0_1px_rgba(255,255,255,0.15)] text-slate-200 text-xs font-sans select-none animate-in fade-in zoom-in-95 duration-100 max-h-[460px] overflow-y-auto [scrollbar-width:thin] [scrollbar-color:rgba(148,163,184,0.2)_transparent]"
    >
      {/* Header */}
      <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold border-b border-white/[0.08] flex items-center justify-between">
        <span>View &amp; Filter</span>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white transition-colors p-0.5 rounded cursor-pointer"
          title="Close menu (Esc)"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="py-1">
        {/* ── Section 1: Grouping ── */}
        <div>
          <button
            type="button"
            onClick={() => toggleAccordion("grouping")}
            className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <rect x="3" y="3" width="7" height="7" rx="1" strokeWidth={1.8} />
                <rect x="14" y="3" width="7" height="7" rx="1" strokeWidth={1.8} />
                <rect x="14" y="14" width="7" height="7" rx="1" strokeWidth={1.8} />
                <rect x="3" y="14" width="7" height="7" rx="1" strokeWidth={1.8} />
              </svg>
              <span>Grouping</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-mono">
              <span className="capitalize">{filterState.grouping}</span>
              <svg
                className={`w-3 h-3 text-slate-500 transition-transform ${openAccordion === "grouping" ? "rotate-90" : ""}`}
                viewBox="0 0 24 24" fill="none" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </button>

          {openAccordion === "grouping" && (
            <div className="px-2 py-1 space-y-0.5 bg-black/40 border-y border-white/[0.04]">
              {groupingOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onChangeFilterState({ grouping: opt.id })}
                  className={`w-full flex items-center justify-between px-2.5 py-1 text-left text-[11px] rounded-md transition-colors cursor-pointer ${
                    filterState.grouping === opt.id
                      ? "text-white bg-white/[0.1] font-medium"
                      : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                  }`}
                >
                  <span>{opt.label}</span>
                  {filterState.grouping === opt.id && (
                    <svg className="w-3.5 h-3.5 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.4} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Section 2: Ordering ── */}
        <div>
          <button
            type="button"
            onClick={() => toggleAccordion("ordering")}
            className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
              </svg>
              <span>Ordering</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-mono">
              <span className="capitalize">{filterState.ordering}</span>
              <svg
                className={`w-3 h-3 text-slate-500 transition-transform ${openAccordion === "ordering" ? "rotate-90" : ""}`}
                viewBox="0 0 24 24" fill="none" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </button>

          {openAccordion === "ordering" && (
            <div className="px-2 py-1 space-y-0.5 bg-black/40 border-y border-white/[0.04]">
              {orderingOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onChangeFilterState({ ordering: opt.id })}
                  className={`w-full flex items-center justify-between px-2.5 py-1 text-left text-[11px] rounded-md transition-colors cursor-pointer ${
                    filterState.ordering === opt.id
                      ? "text-white bg-white/[0.1] font-medium"
                      : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                  }`}
                >
                  <span>{opt.label}</span>
                  {filterState.ordering === opt.id && (
                    <svg className="w-3.5 h-3.5 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.4} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Section 3: Show Badges ── */}
        <div>
          <button
            type="button"
            onClick={() => toggleAccordion("show")}
            className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              <span>Show Badges</span>
            </div>
            <svg
              className={`w-3 h-3 text-slate-500 transition-transform ${openAccordion === "show" ? "rotate-90" : ""}`}
              viewBox="0 0 24 24" fill="none" stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>

          {openAccordion === "show" && (
            <div className="px-2 py-1 space-y-0.5 bg-black/40 border-y border-white/[0.04]">
              {/* Tokens Badge */}
              <button
                type="button"
                onClick={() => onChangeFilterState({ showTokens: !filterState.showTokens })}
                className="w-full flex items-center justify-between px-2.5 py-1 text-left text-[11px] text-slate-300 hover:text-white hover:bg-white/[0.04] rounded-md transition-colors cursor-pointer"
              >
                <span>Tokens count (e.g. 14k)</span>
                <div
                  className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${
                    filterState.showTokens
                      ? "bg-cyan-500 border-cyan-400 text-black font-bold"
                      : "border-white/20 bg-white/[0.02]"
                  }`}
                >
                  {filterState.showTokens && (
                    <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </button>

              {/* Updated Time */}
              <button
                type="button"
                onClick={() => onChangeFilterState({ showUpdated: !filterState.showUpdated })}
                className="w-full flex items-center justify-between px-2.5 py-1 text-left text-[11px] text-slate-300 hover:text-white hover:bg-white/[0.04] rounded-md transition-colors cursor-pointer"
              >
                <span>Relative timestamp</span>
                <div
                  className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${
                    filterState.showUpdated
                      ? "bg-cyan-500 border-cyan-400 text-black font-bold"
                      : "border-white/20 bg-white/[0.02]"
                  }`}
                >
                  {filterState.showUpdated && (
                    <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </button>

              {/* Channel Badge */}
              <button
                type="button"
                onClick={() => onChangeFilterState({ showChannel: !filterState.showChannel })}
                className="w-full flex items-center justify-between px-2.5 py-1 text-left text-[11px] text-slate-300 hover:text-white hover:bg-white/[0.04] rounded-md transition-colors cursor-pointer"
              >
                <span>Channel origin logo</span>
                <div
                  className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${
                    filterState.showChannel
                      ? "bg-cyan-500 border-cyan-400 text-black font-bold"
                      : "border-white/20 bg-white/[0.02]"
                  }`}
                >
                  {filterState.showChannel && (
                    <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </button>
            </div>
          )}
        </div>

        {/* ── Section 4: Channel Filter ── */}
        <div>
          <button
            type="button"
            onClick={() => toggleAccordion("channel")}
            className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
              <span>Channel Filter</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-mono">
              <span className="capitalize">{filterState.channelFilter}</span>
              <svg
                className={`w-3 h-3 text-slate-500 transition-transform ${openAccordion === "channel" ? "rotate-90" : ""}`}
                viewBox="0 0 24 24" fill="none" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </button>

          {openAccordion === "channel" && (
            <div className="px-2 py-1 space-y-0.5 bg-black/40 border-y border-white/[0.04]">
              {channelOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onChangeFilterState({ channelFilter: opt.id })}
                  className={`w-full flex items-center justify-between px-2.5 py-1 text-left text-[11px] rounded-md transition-colors cursor-pointer ${
                    filterState.channelFilter === opt.id
                      ? "text-white bg-white/[0.1] font-medium"
                      : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                  }`}
                >
                  <span>{opt.label}</span>
                  {filterState.channelFilter === opt.id && (
                    <svg className="w-3.5 h-3.5 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.4} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
              ))}

              {/* Show Archived Toggle */}
              <div className="my-1 border-t border-white/[0.06]" />
              <button
                type="button"
                onClick={() => onChangeFilterState({ showArchived: !filterState.showArchived })}
                className="w-full flex items-center justify-between px-2.5 py-1 text-left text-[11px] text-slate-300 hover:text-white hover:bg-white/[0.04] rounded-md transition-colors cursor-pointer"
              >
                <span>Include Archived</span>
                <div
                  className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${
                    filterState.showArchived
                      ? "bg-cyan-500 border-cyan-400 text-black font-bold"
                      : "border-white/20 bg-white/[0.02]"
                  }`}
                >
                  {filterState.showArchived && (
                    <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </button>
            </div>
          )}
        </div>

        {/* ── Section 5: Projects (if available) ── */}
        {availableProjects.length > 0 && (
          <div>
            <button
              type="button"
              onClick={() => toggleAccordion("project")}
              className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <svg className="w-3.5 h-3.5 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                <span>Projects</span>
              </div>
              <svg
                className={`w-3 h-3 text-slate-500 transition-transform ${openAccordion === "project" ? "rotate-90" : ""}`}
                viewBox="0 0 24 24" fill="none" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>

            {openAccordion === "project" && (
              <div className="px-2 py-1 space-y-0.5 bg-black/40 border-y border-white/[0.04] max-h-36 overflow-y-auto">
                {availableProjects.map((p) => {
                  const isChecked = filterState.projectFilter?.includes(p.path);
                  return (
                    <button
                      key={p.path}
                      type="button"
                      onClick={() => handleProjectToggle(p.path)}
                      className="w-full flex items-center justify-between px-2.5 py-1 text-left text-[11px] text-slate-300 hover:text-white hover:bg-white/[0.04] rounded-md transition-colors cursor-pointer"
                    >
                      <span className="truncate max-w-[170px]" title={p.path}>{p.name}</span>
                      <div
                        className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 ${
                          isChecked
                            ? "bg-cyan-500 border-cyan-400 text-black font-bold"
                            : "border-white/20 bg-white/[0.02]"
                        }`}
                      >
                        {isChecked && (
                          <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Hairline Divider */}
      <div className="my-1 border-t border-white/[0.08]" />

      {/* ── Quick Actions ── */}
      <div className="px-1.5 py-0.5 space-y-0.5">
        <div className="grid grid-cols-2 gap-1 mb-1">
          <button
            type="button"
            onClick={() => {
              onExpandAll?.();
              onClose();
            }}
            className="flex items-center justify-center gap-1.5 px-2 py-1 text-[11px] text-slate-300 hover:text-white bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] rounded-md transition-colors cursor-pointer"
          >
            <svg className="w-3 h-3 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 9l-7 7-7-7" />
            </svg>
            <span>Expand all</span>
          </button>

          <button
            type="button"
            onClick={() => {
              onCollapseAll?.();
              onClose();
            }}
            className="flex items-center justify-center gap-1.5 px-2 py-1 text-[11px] text-slate-300 hover:text-white bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] rounded-md transition-colors cursor-pointer"
          >
            <svg className="w-3 h-3 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 5l7 7-7 7" />
            </svg>
            <span>Collapse all</span>
          </button>
        </div>

        <button
          type="button"
          onClick={handleReset}
          className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1 text-[11px] text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] rounded-md transition-colors cursor-pointer"
        >
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Reset to defaults</span>
        </button>
      </div>
    </div>
  );
}
