"use client";

import React, { useState, useMemo, useRef } from "react";
import { ChatSession, formatSmartDateTime, formatRelativeTime, resolveSessionDisplay, groupSessions, type SessionCategory, SESSION_PREVIEW_COUNT } from "./types";
import { exportSession } from "@/lib/sessionExport";

interface SessionHistoryListProps {
  sessions: ChatSession[];
  loading: boolean;
  activeSessionId: number | null;
  search: string;
  setSearch: (s: string) => void;
  onSelectSession: (id: number) => void;
  onNewSession: () => void;
  onOpenBrain?: () => void;
  onOpenArtifacts?: () => void;
  onOpenCode?: () => void;
  sessionType?: "chat" | "code";
  onPatchSession: (id: number, body: Record<string, unknown>) => Promise<void>;
  onDeleteSession: (s: ChatSession) => Promise<void> | void;
  onForkSession?: (s: ChatSession) => Promise<void>;
  onDropPin: (id: number) => void;
  onDropUnpin: (id: number) => void;
  draggedSession: ChatSession | null;
  setDraggedSession: (s: ChatSession | null) => void;
  dragOverTarget: "pin" | "unpin" | null;
  setDragOverTarget: (t: "pin" | "unpin" | null) => void;
  hoveredDropSessionId: number | null;
  setHoveredDropSessionId: React.Dispatch<React.SetStateAction<number | null>>;
}

export default function SessionHistoryList({
  sessions, loading, activeSessionId, search, setSearch,
  onSelectSession, onNewSession, onOpenBrain, onOpenArtifacts, onOpenCode, sessionType,
  onPatchSession, onDeleteSession, onForkSession,
  onDropPin, onDropUnpin,
  draggedSession, setDraggedSession, dragOverTarget, setDragOverTarget,
  hoveredDropSessionId, setHoveredDropSessionId,
}: SessionHistoryListProps) {
  const [menuOpenId, setMenuOpenId] = useState<number | null>(null);
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const isSubmittingRenameRef = useRef(false);
  const dragTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [collapsedCategories, setCollapsedCategories] = useState<Record<string, boolean>>({});
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({});

  React.useEffect(() => {
    if (menuOpenId === null) return;
    const close = () => setMenuOpenId(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [menuOpenId]);

  const submitRename = async (id: number) => {
    if (isSubmittingRenameRef.current) return;
    isSubmittingRenameRef.current = true;
    const val = renameValue.trim();
    setRenamingId(null);
    try {
      if (val) await onPatchSession(id, { title: val });
    } finally {
      isSubmittingRenameRef.current = false;
    }
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let res = sessions;
    if (!q) {
      res = res.filter((s) => {
        const isCli = (s.title || "").toLowerCase().includes("cli");
        if (isCli && s.message_count === 0 && s.id !== activeSessionId) return false;
        return true;
      });
    } else {
      res = res.filter(
        (s) =>
          (s.title || "").toLowerCase().includes(q) ||
          (s.last_user_text || "").toLowerCase().includes(q)
      );
    }
    return res;
  }, [sessions, search, activeSessionId]);

  const categories = useMemo(() => groupSessions(filtered), [filtered]);

  const categoryIcon = (cat: SessionCategory) => {
    if (cat.category === "pinned") return (
      <svg className="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
      </svg>
    );
    if (cat.category === "home") return (
      <svg className="w-3 h-3 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    );
    // Project category — folder icon
    return (
      <svg className="w-3 h-3 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
      </svg>
    );
  };

  /* ── Session row renderer (extracted to reduce nesting) ──────────── */
  const renderSessionRow = (s: ChatSession, isPinnedCategory: boolean) => {
    const isActive = activeSessionId === s.id;
    const isBeingDragged = draggedSession?.id === s.id;
    const isHoveredTarget = hoveredDropSessionId === s.id && Boolean(draggedSession && draggedSession.id !== s.id);
    const display = resolveSessionDisplay(s);
    const smartTime = formatSmartDateTime(s.updated_at || s.created_at);
    const relTime = formatRelativeTime(s.updated_at || s.created_at);

    return (
      <div
        key={s.id}
        onDragOver={(e) => {
          if (draggedSession && draggedSession.id !== s.id) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            e.stopPropagation();
            setHoveredDropSessionId(s.id);
            if (isPinnedCategory && draggedSession.is_pinned === 0) setDragOverTarget("pin");
            else if (!isPinnedCategory && draggedSession.is_pinned === 1) setDragOverTarget("unpin");
          }
        }}
        onDragLeave={(e) => {
          e.stopPropagation();
          setHoveredDropSessionId((prev) => (prev === s.id ? null : prev));
        }}
        onDrop={(e) => {
          if (draggedSession && draggedSession.id !== s.id) {
            e.preventDefault();
            e.stopPropagation();
            if (isPinnedCategory && draggedSession.is_pinned === 0) onDropPin(draggedSession.id);
            else if (!isPinnedCategory && draggedSession.is_pinned === 1) onDropUnpin(draggedSession.id);
            setHoveredDropSessionId(null);
          }
        }}
        className={`group/item relative rounded-xl transition-all ${
          isBeingDragged ? "opacity-30 scale-[0.98] border border-dashed border-white/25" : ""
        }`}
      >
        {/* Floating Pill on Drag Hover */}
        {isHoveredTarget && draggedSession && (
          <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-50 pointer-events-none animate-scale-up">
            {draggedSession.is_pinned === 1 ? (
              <div className="px-3 py-1.5 rounded-xl bg-[#2d0a11]/95 border border-rose-500/50 text-rose-200 text-[11px] font-sans font-medium shadow-[0_8px_24px_rgba(0,0,0,0.85),0_0_16px_rgba(244,63,94,0.3)] backdrop-blur-xl flex items-center gap-1.5 whitespace-nowrap select-none">
                <span>Release to unpin</span>
              </div>
            ) : (
              <div className="px-3 py-1.5 rounded-xl bg-[#08202f]/95 border border-cyan-400/50 text-cyan-200 text-[11px] font-sans font-medium shadow-[0_8px_24px_rgba(0,0,0,0.85),0_0_16px_rgba(34,211,238,0.3)] backdrop-blur-xl flex items-center gap-1.5 whitespace-nowrap select-none">
                <span>Release to pin</span>
              </div>
            )}
          </div>
        )}

        {renamingId === s.id ? (
          <div className="p-1.5">
            <input
              autoFocus
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitRename(s.id);
                if (e.key === "Escape") setRenamingId(null);
              }}
              onBlur={() => submitRename(s.id)}
              className="w-full py-1.5 px-2 rounded-lg bg-black/60 border border-cyan-400/50 text-xs text-white focus:outline-none font-sans"
            />
          </div>
        ) : (
          <div
            role="button"
            tabIndex={0}
            draggable
            onDragStart={(e) => {
              e.stopPropagation();
              e.dataTransfer.setData("text/plain", String(s.id));
              e.dataTransfer.effectAllowed = "move";
              if (dragTimeoutRef.current) clearTimeout(dragTimeoutRef.current);
              dragTimeoutRef.current = setTimeout(() => {
                setDraggedSession(s);
                dragTimeoutRef.current = null;
              }, 0);
            }}
            onDragEnd={() => {
              if (dragTimeoutRef.current) { clearTimeout(dragTimeoutRef.current); dragTimeoutRef.current = null; }
              setDraggedSession(null);
              setDragOverTarget(null);
              setHoveredDropSessionId(null);
            }}
            onClick={() => onSelectSession(s.id)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectSession(s.id); } }}
            title={`${display.title}${display.subtitle ? ` — ${display.subtitle}` : ""} (${smartTime} • ${s.message_count} msgs)`}
            className={`w-full flex items-center gap-2 text-left py-1.5 px-2.5 rounded-lg transition-all outline-none cursor-grab active:cursor-grabbing select-none ${
              isHoveredTarget && draggedSession
                ? draggedSession.is_pinned === 1
                  ? "bg-rose-950/30 border border-rose-500/40 text-white shadow-sm"
                  : "bg-cyan-950/30 border border-cyan-400/40 text-white shadow-sm"
                : isActive
                ? "bg-cyan-500/10 text-white shadow-sm font-medium border-l-[3px] border-cyan-400 rounded-l-none pl-2"
                : "bg-transparent hover:bg-white/[0.04] text-slate-300 hover:text-white"
            }`}
          >
            {/* Lead icon */}
            <div className="shrink-0 flex items-center justify-center pointer-events-none">
              {s.is_pinned === 1 ? (
                <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                </svg>
              ) : display.channel === "telegram" ? (
                <span className="w-3.5 h-3.5 rounded bg-sky-500/15 border border-sky-400/30 flex items-center justify-center text-sky-400" title="Telegram">
                  <svg className="w-2 h-2" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.52 2.77-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .26z" />
                  </svg>
                </span>
              ) : display.channel === "whatsapp" ? (
                <span className="w-3.5 h-3.5 rounded bg-emerald-500/15 border border-emerald-400/30 flex items-center justify-center text-emerald-400" title="WhatsApp">
                  <svg className="w-2 h-2" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.816 9.816 0 0012.04 2z" />
                  </svg>
                </span>
              ) : display.channel === "cli" ? (
                <span className="w-3.5 h-3.5 rounded bg-emerald-500/15 border border-emerald-400/30 flex items-center justify-center text-emerald-400" title="CLI">
                  <svg className="w-2 h-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M8 9l3 3-3 3m5 0h3" />
                  </svg>
                </span>
              ) : s.session_type === "code" ? (
                <span className="w-3.5 h-3.5 rounded bg-violet-500/15 border border-violet-400/30 flex items-center justify-center text-violet-400" title="Code Studio">
                  <svg className="w-2 h-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                  </svg>
                </span>
              ) : (
                <span className={`w-1.5 h-1.5 rounded-full ${isActive ? "bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.5)]" : "bg-slate-500/60"}`} />
              )}
            </div>

            <span className={`text-[12px] truncate flex-1 tracking-tight font-sans ${isActive ? "text-white font-medium" : "text-slate-300 group-hover/item:text-white"}`}>
              {display.title}
            </span>

            <span className="text-[10px] font-mono text-slate-500 shrink-0 pointer-events-none group-hover/item:opacity-0 transition-opacity tabular-nums">
              {relTime || smartTime}
            </span>
          </div>
        )}

        {/* Row options menu */}
        {renamingId !== s.id && (
          <div className="absolute top-1/2 -translate-y-1/2 right-1.5 z-10" onMouseDown={(e) => e.stopPropagation()}>
            <button
              onClick={(e) => { e.stopPropagation(); setMenuOpenId(menuOpenId === s.id ? null : s.id); }}
              className={`w-5 h-6 rounded flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/15 transition-all cursor-pointer ${menuOpenId === s.id ? "opacity-100" : "opacity-0 group-hover/item:opacity-100"}`}
              title="Session options"
            >
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                <circle cx="12" cy="5" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="12" cy="19" r="2" />
              </svg>
            </button>

            {menuOpenId === s.id && (
              <div className="absolute right-0 top-7 z-30 w-44 py-1 rounded-xl bg-slate-950/95 border border-white/15 backdrop-blur-xl shadow-2xl font-sans" onClick={(e) => e.stopPropagation()}>
                {[
                  { label: "Rename", action: () => { setRenameValue(s.title || ""); setRenamingId(s.id); setMenuOpenId(null); } },
                  { label: s.is_pinned === 1 ? "Unpin" : "Pin", action: () => { onPatchSession(s.id, { is_pinned: s.is_pinned !== 1 }); setMenuOpenId(null); } },
                  { label: "Branch / Fork", action: () => { onForkSession?.(s); setMenuOpenId(null); } },
                  { label: "Export as Markdown", action: () => { exportSession({ sessionId: s.id, title: s.title, format: "markdown" }); setMenuOpenId(null); } },
                  { label: "Export as JSON", action: () => { exportSession({ sessionId: s.id, title: s.title, format: "json" }); setMenuOpenId(null); } },
                ].map((item) => (
                  <button key={item.label} onClick={item.action} className="w-full text-left px-3 py-1.5 text-[11px] text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer">
                    {item.label}
                  </button>
                ))}
                <div className="my-1 border-t border-white/10" />
                <button
                  onClick={() => { onDeleteSession(s); setMenuOpenId(null); }}
                  className="w-full text-left px-3 py-1.5 text-[11px] text-rose-300 hover:text-white hover:bg-rose-500/25 transition-colors cursor-pointer"
                >
                  Delete session
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      {/* Action Bar */}
      <div className="px-2.5 pt-2 flex flex-col gap-1.5 font-sans">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] hover:border-white/[0.16] text-slate-200 hover:text-white text-xs font-medium transition-all active:scale-[0.98] cursor-pointer shadow-sm group backdrop-blur-md"
          title="Start new conversation (Ctrl+N)"
        >
          <div className="flex items-center gap-2">
            <svg className="w-3.5 h-3.5 text-cyan-400 group-hover:text-cyan-300 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M12 4v16m8-8H4" />
            </svg>
            <span className="font-semibold tracking-tight">{sessionType === "code" ? "New Project" : "New session"}</span>
          </div>
          <div className="flex items-center gap-1 font-mono text-[10px] text-slate-400">
            <span className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/10">Ctrl</span>
            <span className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/10">N</span>
          </div>
        </button>

        <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-sans">
          <button
            type="button"
            onClick={onOpenBrain}
            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] hover:border-white/10 hover:text-white transition-all cursor-pointer shadow-sm active:scale-95"
            title="Brain Capabilities & Memory"
          >
            <svg className="w-3.5 h-3.5 text-indigo-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span className="truncate font-medium">Capabilities</span>
          </button>
          <button
            type="button"
            onClick={onOpenArtifacts}
            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] hover:border-white/10 hover:text-white transition-all cursor-pointer shadow-sm active:scale-95"
            title="Artifacts Gallery & Outputs"
          >
            <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="truncate font-medium">Artifacts</span>
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="px-2.5 mt-1.5 relative">
        <svg className="w-3.5 h-3.5 text-slate-500 absolute left-5 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search sessions..."
          className="w-full py-1.5 pl-7 pr-2.5 rounded-lg bg-black/30 border border-white/[0.08] focus:border-cyan-400/40 text-[11px] text-slate-200 placeholder:text-slate-500 focus:outline-none focus:bg-black/50 transition-all font-sans"
        />
      </div>

      {/* Session list */}
      <div
        ref={listRef}
        onDragOver={(e) => {
          if (draggedSession) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            if (draggedSession.is_pinned === 1 && dragOverTarget !== "unpin") setDragOverTarget("unpin");
          }
        }}
        onDrop={(e) => {
          if (draggedSession && draggedSession.is_pinned === 1) { e.preventDefault(); onDropUnpin(draggedSession.id); }
        }}
        className="flex-1 overflow-y-auto mt-2.5 px-2 pb-2 [scrollbar-width:thin] [scrollbar-color:rgba(148,163,184,0.25)_transparent] font-sans"
      >
        {/* Top Drop Zone: pin when no pinned group exists */}
        {draggedSession && draggedSession.is_pinned === 0 && !sessions.some((x) => x.is_pinned === 1) && (
          <div
            onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setDragOverTarget("pin"); }}
            onDragLeave={() => setDragOverTarget(null)}
            onDrop={(e) => { e.preventDefault(); e.stopPropagation(); if (draggedSession) onDropPin(draggedSession.id); }}
            className={`mb-2 p-2.5 rounded-xl border border-dashed text-center transition-all cursor-pointer ${
              dragOverTarget === "pin"
                ? "border-cyan-400/60 bg-cyan-500/15 text-cyan-200 shadow-[0_0_15px_rgba(34,211,238,0.2)]"
                : "border-white/15 bg-white/[0.03] text-slate-400"
            }`}
          >
            <div className="flex items-center justify-center gap-2 text-xs font-mono">
              <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              <span>Release to pin</span>
            </div>
          </div>
        )}

        {loading && sessions.length === 0 ? (
          <p className="text-[11px] text-slate-500 text-center py-8 font-mono">Loading history...</p>
        ) : categories.length === 0 ? (
          <div className="text-center py-10 px-4">
            <p className="text-xs font-semibold text-slate-300">{search ? "Not found" : "No history yet"}</p>
            <p className="text-[10.5px] text-slate-500 mt-1 leading-relaxed">{search ? "Try different keywords." : "Start chatting, Anara saves them here."}</p>
          </div>
        ) : (
          categories.map((category) => {
            const isPinned = category.category === "pinned";
            // Use workspace path as unique key for project categories
            const categoryKey = category.workspacePath || category.category;
            const isCollapsed = collapsedCategories[categoryKey] ?? false;
            const isExpanded = expandedCategories[categoryKey] ?? false;
            const totalCount = category.items.length;
            const accentClass = category.category === "pinned" ? "text-cyan-400/90" : category.category === "home" ? "text-indigo-400/90" : "text-violet-400/90";
            // Session pattern: preview SESSION_PREVIEW_COUNT, "Show all N sessions" to expand
            const visibleItems = isExpanded || isPinned ? category.items : category.items.slice(0, SESSION_PREVIEW_COUNT);
            const hiddenCount = totalCount - visibleItems.length;

            return (
              <div key={categoryKey} className="mb-3">
                {/* Category Header — Category Header style */}
                <button
                  type="button"
                  onClick={() => setCollapsedCategories((prev) => ({ ...prev, [categoryKey]: !prev[categoryKey] }))}
                  className="w-full px-2 mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider font-mono cursor-pointer hover:opacity-90 transition-opacity select-none group/cat-header"
                >
                  <svg
                    className={`w-2.5 h-2.5 text-slate-500 transition-transform ${isCollapsed ? "-rotate-90" : ""}`}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                  </svg>
                  {categoryIcon(category)}
                  <span className={accentClass}>{category.label}</span>
                  <span className="text-[9px] font-normal text-slate-500 ml-auto tabular-nums">{totalCount}</span>
                  {isPinned && (
                    <span className="text-[9px] font-normal lowercase opacity-0 group-hover/cat-header:opacity-70 text-slate-400 transition-opacity">
                      Shift-click to pin
                    </span>
                  )}
                </button>

                {/* Category body */}
                {!isCollapsed && (
                  <div
                    className={`rounded-xl transition-all ${
                      draggedSession
                        ? isPinned && draggedSession.is_pinned === 0 && dragOverTarget === "pin"
                          ? "ring-1 ring-cyan-400/50 bg-cyan-500/5 p-1"
                          : !isPinned && draggedSession.is_pinned === 1 && dragOverTarget === "unpin"
                          ? "ring-1 ring-rose-400/50 bg-rose-500/5 p-1"
                          : ""
                        : ""
                    }`}
                    onDragOver={(e) => {
                      if (draggedSession) {
                        e.preventDefault();
                        e.dataTransfer.dropEffect = "move";
                        if (isPinned && draggedSession.is_pinned === 0) setDragOverTarget("pin");
                        else if (!isPinned && draggedSession.is_pinned === 1) setDragOverTarget("unpin");
                      }
                    }}
                    onDrop={(e) => {
                      if (draggedSession) {
                        e.stopPropagation();
                        if (isPinned && draggedSession.is_pinned === 0) { e.preventDefault(); onDropPin(draggedSession.id); }
                        else if (!isPinned && draggedSession.is_pinned === 1) { e.preventDefault(); onDropUnpin(draggedSession.id); }
                      }
                    }}
                  >
                    <div className="space-y-0.5">
                      {visibleItems.map((s) => renderSessionRow(s, isPinned))}
                    </div>

                    {/* "Show all N sessions" — Preview count pattern */}
                    {hiddenCount > 0 && (
                      <button
                        type="button"
                        onClick={() => setExpandedCategories((prev) => ({ ...prev, [categoryKey]: true }))}
                        className="w-full mt-1 px-3 py-1.5 text-[11px] text-slate-400 hover:text-white font-mono cursor-pointer hover:bg-white/[0.04] rounded-lg transition-colors text-left flex items-center gap-1.5"
                      >
                        <svg className="w-3 h-3 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                        <span>Show all {totalCount} sessions</span>
                      </button>
                    )}
                  </div>
                )}

                {/* Unpin drop zone below Pinned */}
                {isPinned && !isCollapsed && draggedSession && draggedSession.is_pinned === 1 && (
                  <div
                    onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect = "move"; setDragOverTarget("unpin"); }}
                    onDragLeave={(e) => e.stopPropagation()}
                    onDrop={(e) => { e.preventDefault(); e.stopPropagation(); onDropUnpin(draggedSession.id); }}
                    className={`mb-3 p-3 rounded-xl border border-dashed text-center transition-all cursor-pointer select-none ${
                      dragOverTarget === "unpin"
                        ? "border-rose-400/80 bg-rose-500/20 text-rose-200 shadow-[0_0_18px_rgba(244,63,94,0.35)] scale-[1.01]"
                        : "border-rose-500/40 bg-rose-500/10 text-rose-300 hover:border-rose-400/60"
                    }`}
                  >
                    <div className="flex items-center justify-center gap-2 text-xs font-mono font-medium">
                      <svg className="w-3.5 h-3.5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                      </svg>
                      <span>Release here to unpin</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}

        {/* Bottom unpin drop zone */}
        {draggedSession && draggedSession.is_pinned === 1 && categories.length > 1 && (
          <div
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect = "move"; setDragOverTarget("unpin"); }}
            onDrop={(e) => { e.preventDefault(); e.stopPropagation(); onDropUnpin(draggedSession.id); }}
            className={`my-2 p-2.5 rounded-xl border border-dashed text-center transition-all cursor-pointer select-none ${
              dragOverTarget === "unpin"
                ? "border-rose-400/80 bg-rose-500/20 text-rose-200 shadow-[0_0_15px_rgba(244,63,94,0.3)]"
                : "border-white/15 bg-white/[0.03] text-slate-400 hover:border-rose-400/40"
            }`}
          >
            <div className="flex items-center justify-center gap-2 text-xs font-mono">
              <svg className="w-3.5 h-3.5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
              <span>Release here to unpin</span>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
