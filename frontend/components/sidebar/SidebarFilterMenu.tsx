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

type SubmenuKey = "grouping" | "ordering" | "show" | "filters";

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
  const [activeSubmenu, setActiveSubmenu] = useState<SubmenuKey | null>(null);
  const [flyoutSide, setFlyoutSide] = useState<"right" | "left">("right");
  const menuRef = useRef<HTMLDivElement>(null);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Position detection to prevent screen clipping
  useEffect(() => {
    if (!isOpen || typeof window === "undefined") return;
    if (menuRef.current) {
      const rect = menuRef.current.getBoundingClientRect();
      if (rect.right + 230 > window.innerWidth) {
        setFlyoutSide("left");
      } else {
        setFlyoutSide("right");
      }
    }
  }, [isOpen]);

  // Click outside and Escape key handling
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  const handleSubmenuEnter = useCallback((key: SubmenuKey) => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    setActiveSubmenu(key);
  }, []);

  const handleSubmenuLeave = useCallback(() => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    closeTimerRef.current = setTimeout(() => {
      setActiveSubmenu(null);
    }, 220);
  }, []);

  const handleFlyoutMouseEnter = useCallback(() => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }, []);

  if (!isOpen) return null;

  const flyoutPosClass =
    flyoutSide === "right"
      ? "left-full top-0 ml-1.5"
      : "right-full top-0 mr-1.5";

  // Grouping options
  const groupingOptions: Array<{ id: SidebarGrouping; label: string }> = [
    { id: "project", label: "Workspace" },
    { id: "date", label: "Date" },
    { id: "status", label: "Status" },
    { id: "none", label: "None (All sessions)" },
  ];

  // Ordering options
  const orderingOptions: Array<{ id: SidebarOrdering; label: string }> = [
    { id: "updated", label: "Last updated" },
    { id: "created", label: "Date created" },
    { id: "tokens", label: "Total tokens" },
    { id: "status", label: "Status" },
  ];

  // Channel filter options
  const channelOptions: Array<{
    id: "all" | "web" | "cli" | "telegram" | "whatsapp";
    label: string;
  }> = [
    { id: "all", label: "All channels" },
    { id: "web", label: "Web" },
    { id: "cli", label: "CLI" },
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
    setActiveSubmenu(null);
  };

  return (
    <div
      ref={menuRef}
      className="absolute right-0 top-full mt-1.5 z-50 w-52 py-1.5 rounded-xl bg-[#080c14]/95 border border-white/[0.08] backdrop-blur-xl shadow-[0_16px_36px_rgba(0,0,0,0.85),0_0_1px_rgba(255,255,255,0.12)] text-slate-200 text-xs font-sans select-none animate-in fade-in zoom-in-95 duration-100"
    >
      {/* Popover Header */}
      <div className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold border-b border-white/[0.06] flex items-center justify-between">
        <span>View &amp; Filter</span>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-slate-300 transition-colors p-0.5 rounded cursor-pointer"
          title="Close menu"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="py-1">
        {/* ── Submenu 1: Grouping ── */}
        <div
          className="relative"
          onMouseEnter={() => handleSubmenuEnter("grouping")}
          onMouseLeave={handleSubmenuLeave}
        >
          <button
            type="button"
            onClick={() => setActiveSubmenu(activeSubmenu === "grouping" ? null : "grouping")}
            className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.06] rounded-md transition-colors cursor-pointer"
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
            <div className="flex items-center gap-1 text-slate-400 text-[11px] font-mono">
              <span className="capitalize">{filterState.grouping}</span>
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </button>

          {activeSubmenu === "grouping" && (
            <div
              onMouseEnter={handleFlyoutMouseEnter}
              onMouseLeave={handleSubmenuLeave}
              className={`absolute ${flyoutPosClass} w-52 py-1.5 rounded-xl bg-[#080c14]/95 border border-white/[0.08] backdrop-blur-xl shadow-[0_16px_36px_rgba(0,0,0,0.85),0_0_1px_rgba(255,255,255,0.12)] z-50 text-slate-200 animate-in fade-in duration-75`}
            >
              <div className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold border-b border-white/[0.06] mb-1">
                Group By
              </div>
              {groupingOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => {
                    onChangeFilterState({ grouping: opt.id });
                    setActiveSubmenu(null);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-1.5 text-left rounded-md transition-colors cursor-pointer ${
                    filterState.grouping === opt.id
                      ? "text-white bg-white/[0.08] font-medium"
                      : "text-slate-300 hover:text-white hover:bg-white/[0.04]"
                  }`}
                >
                  <span>{opt.label}</span>
                  {filterState.grouping === opt.id && (
                    <svg className="w-3.5 h-3.5 text-slate-100" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.4} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Submenu 2: Ordering ── */}
        <div
          className="relative"
          onMouseEnter={() => handleSubmenuEnter("ordering")}
          onMouseLeave={handleSubmenuLeave}
        >
          <button
            type="button"
            onClick={() => setActiveSubmenu(activeSubmenu === "ordering" ? null : "ordering")}
            className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.06] rounded-md transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
              </svg>
              <span>Ordering</span>
            </div>
            <div className="flex items-center gap-1 text-slate-400 text-[11px] font-mono">
              <span className="capitalize">{filterState.ordering}</span>
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </button>

          {activeSubmenu === "ordering" && (
            <div
              onMouseEnter={handleFlyoutMouseEnter}
              onMouseLeave={handleSubmenuLeave}
              className={`absolute ${flyoutPosClass} w-52 py-1.5 rounded-xl bg-[#080c14]/95 border border-white/[0.08] backdrop-blur-xl shadow-[0_16px_36px_rgba(0,0,0,0.85),0_0_1px_rgba(255,255,255,0.12)] z-50 text-slate-200 animate-in fade-in duration-75`}
            >
              <div className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold border-b border-white/[0.06] mb-1">
                Order By
              </div>
              {orderingOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => {
                    onChangeFilterState({ ordering: opt.id });
                    setActiveSubmenu(null);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-1.5 text-left rounded-md transition-colors cursor-pointer ${
                    filterState.ordering === opt.id
                      ? "text-white bg-white/[0.08] font-medium"
                      : "text-slate-300 hover:text-white hover:bg-white/[0.04]"
                  }`}
                >
                  <span>{opt.label}</span>
                  {filterState.ordering === opt.id && (
                    <svg className="w-3.5 h-3.5 text-slate-100" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.4} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Submenu 3: Show (Checkboxes) ── */}
        <div
          className="relative"
          onMouseEnter={() => handleSubmenuEnter("show")}
          onMouseLeave={handleSubmenuLeave}
        >
          <button
            type="button"
            onClick={() => setActiveSubmenu(activeSubmenu === "show" ? null : "show")}
            className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.06] rounded-md transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              <span>Show</span>
            </div>
            <div className="flex items-center gap-1 text-slate-400 text-[11px] font-mono">
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </button>

          {activeSubmenu === "show" && (
            <div
              onMouseEnter={handleFlyoutMouseEnter}
              onMouseLeave={handleSubmenuLeave}
              className={`absolute ${flyoutPosClass} w-52 py-1.5 rounded-xl bg-[#080c14]/95 border border-white/[0.08] backdrop-blur-xl shadow-[0_16px_36px_rgba(0,0,0,0.85),0_0_1px_rgba(255,255,255,0.12)] z-50 text-slate-200 animate-in fade-in duration-75`}
            >
              <div className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold border-b border-white/[0.06] mb-1">
                Visible Badges
              </div>
              <button
                type="button"
                onClick={() => onChangeFilterState({ showTokens: !filterState.showTokens })}
                className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.04] rounded-md transition-colors cursor-pointer"
              >
                <span>Tokens</span>
                <div
                  className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${
                    filterState.showTokens
                      ? "bg-white/20 border-white/40 text-white"
                      : "border-white/20 bg-white/[0.02]"
                  }`}
                >
                  {filterState.showTokens && (
                    <svg className="w-2.5 h-2.5 text-slate-100" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </button>

              <button
                type="button"
                onClick={() => onChangeFilterState({ showUpdated: !filterState.showUpdated })}
                className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.04] rounded-md transition-colors cursor-pointer"
              >
                <span>Updated</span>
                <div
                  className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${
                    filterState.showUpdated
                      ? "bg-white/20 border-white/40 text-white"
                      : "border-white/20 bg-white/[0.02]"
                  }`}
                >
                  {filterState.showUpdated && (
                    <svg className="w-2.5 h-2.5 text-slate-100" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </button>

              <button
                type="button"
                onClick={() => onChangeFilterState({ showChannel: !filterState.showChannel })}
                className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.04] rounded-md transition-colors cursor-pointer"
              >
                <span>Channel</span>
                <div
                  className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${
                    filterState.showChannel
                      ? "bg-white/20 border-white/40 text-white"
                      : "border-white/20 bg-white/[0.02]"
                  }`}
                >
                  {filterState.showChannel && (
                    <svg className="w-2.5 h-2.5 text-slate-100" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </button>
            </div>
          )}
        </div>

        {/* ── Submenu 4: Filters (Channel, Project, Archived) ── */}
        <div
          className="relative"
          onMouseEnter={() => handleSubmenuEnter("filters")}
          onMouseLeave={handleSubmenuLeave}
        >
          <button
            type="button"
            onClick={() => setActiveSubmenu(activeSubmenu === "filters" ? null : "filters")}
            className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.06] rounded-md transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" strokeWidth={1.8} />
              </svg>
              <span>Filters</span>
            </div>
            <div className="flex items-center gap-1 text-slate-400 text-[11px] font-mono">
              <span className="capitalize">{filterState.channelFilter}</span>
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </button>

          {activeSubmenu === "filters" && (
            <div
              onMouseEnter={handleFlyoutMouseEnter}
              onMouseLeave={handleSubmenuLeave}
              className={`absolute ${flyoutPosClass} w-56 py-1.5 rounded-xl bg-[#080c14]/95 border border-white/[0.08] backdrop-blur-xl shadow-[0_16px_36px_rgba(0,0,0,0.85),0_0_1px_rgba(255,255,255,0.12)] z-50 text-slate-200 animate-in fade-in duration-75 max-h-[calc(100vh-140px)] overflow-y-auto [scrollbar-width:thin]`}
            >
              {/* Channel filter (Radio) */}
              <div className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold border-b border-white/[0.06] mb-1">
                Channel
              </div>
              {channelOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onChangeFilterState({ channelFilter: opt.id })}
                  className={`w-full flex items-center justify-between px-3 py-1 text-left rounded-md transition-colors cursor-pointer ${
                    filterState.channelFilter === opt.id
                      ? "text-white bg-white/[0.08] font-medium"
                      : "text-slate-300 hover:text-white hover:bg-white/[0.04]"
                  }`}
                >
                  <span>{opt.label}</span>
                  {filterState.channelFilter === opt.id && (
                    <svg className="w-3.5 h-3.5 text-slate-100" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.4} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
              ))}

              {/* Project filter (Checkboxes) if available */}
              {availableProjects.length > 0 && (
                <>
                  <div className="my-1.5 border-t border-white/[0.06]" />
                  <div className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center justify-between">
                    <span>Projects</span>
                    {filterState.projectFilter && filterState.projectFilter.length > 0 && (
                      <button
                        type="button"
                        onClick={() => onChangeFilterState({ projectFilter: [] })}
                        className="text-[9px] text-cyan-400 hover:underline lowercase font-sans cursor-pointer"
                      >
                        Reset
                      </button>
                    )}
                  </div>
                  {availableProjects.map((p) => {
                    const isChecked = Boolean(
                      filterState.projectFilter && filterState.projectFilter.includes(p.path)
                    );
                    return (
                      <button
                        key={p.path}
                        type="button"
                        onClick={() => handleProjectToggle(p.path)}
                        className="w-full flex items-center justify-between px-3 py-1 text-left text-slate-300 hover:text-white hover:bg-white/[0.04] rounded-md transition-colors cursor-pointer"
                      >
                        <span className="truncate pr-2" title={p.path}>
                          {p.name}
                        </span>
                        <div
                          className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 transition-colors ${
                            isChecked
                              ? "bg-white/20 border-white/40 text-white"
                              : "border-white/20 bg-white/[0.02]"
                          }`}
                        >
                          {isChecked && (
                            <svg className="w-2.5 h-2.5 text-slate-100" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </>
              )}

              {/* Archived sessions toggle */}
              <div className="my-1.5 border-t border-white/[0.06]" />
              <button
                type="button"
                onClick={() => onChangeFilterState({ showArchived: !filterState.showArchived })}
                className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/[0.04] rounded-md transition-colors cursor-pointer"
              >
                <span>Archived</span>
                <div
                  className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${
                    filterState.showArchived
                      ? "bg-white/20 border-white/40 text-white"
                      : "border-white/20 bg-white/[0.02]"
                  }`}
                >
                  {filterState.showArchived && (
                    <svg className="w-2.5 h-2.5 text-slate-100" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Hairline Divider */}
      <div className="my-1 border-t border-white/[0.06]" />

      {/* ── Quick Actions ── */}
      <div className="px-1 py-0.5 space-y-0.5">
        <button
          type="button"
          onClick={() => {
            onExpandAll?.();
            onClose();
          }}
          className="w-full flex items-center gap-2 px-2.5 py-1 text-left text-[11px] text-slate-300 hover:text-white hover:bg-white/[0.06] rounded-md transition-colors cursor-pointer"
        >
          <svg className="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
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
          className="w-full flex items-center gap-2 px-2.5 py-1 text-left text-[11px] text-slate-300 hover:text-white hover:bg-white/[0.06] rounded-md transition-colors cursor-pointer"
        >
          <svg className="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 5l7 7-7 7" />
          </svg>
          <span>Collapse all</span>
        </button>

        <button
          type="button"
          onClick={handleReset}
          className="w-full flex items-center gap-2 px-2.5 py-1 text-left text-[11px] text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] rounded-md transition-colors cursor-pointer"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Reset to defaults</span>
        </button>
      </div>
    </div>
  );
}
