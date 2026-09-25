"use client";

import React, { useState, useMemo, useRef } from "react";
import { ChatSession, formatFullDateTime, groupSessions } from "./types";

interface SessionHistoryListProps {
  sessions: ChatSession[];
  loading: boolean;
  activeSessionId: number | null;
  search: string;
  setSearch: (s: string) => void;
  onSelectSession: (id: number) => void;
  onNewSession: () => void;
  onOpenBrain?: () => void;
  onOpenCode?: () => void;
  sessionType?: "chat" | "code";
  onPatchSession: (id: number, body: Record<string, unknown>) => Promise<void>;
  onDeleteSession: (s: ChatSession) => Promise<void>;
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
  sessions,
  loading,
  activeSessionId,
  search,
  setSearch,
  onSelectSession,
  onNewSession,
  onOpenBrain,
  onOpenCode,
  sessionType,
  onPatchSession,
  onDeleteSession,
  onDropPin,
  onDropUnpin,
  draggedSession,
  setDraggedSession,
  dragOverTarget,
  setDragOverTarget,
  hoveredDropSessionId,
  setHoveredDropSessionId,
}: SessionHistoryListProps) {
  const [menuOpenId, setMenuOpenId] = useState<number | null>(null);
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (menuOpenId === null) return;
    const close = () => {
      setMenuOpenId(null);
    };
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [menuOpenId]);

  const submitRename = async (id: number) => {
    const val = renameValue.trim();
    setRenamingId(null);
    if (val) await onPatchSession(id, { title: val });
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter(
      (s) =>
        (s.title || "").toLowerCase().includes(q) ||
        (s.last_user_text || "").toLowerCase().includes(q)
    );
  }, [sessions, search]);

  const groups = useMemo(() => groupSessions(filtered), [filtered]);

  return (
    <>
      {/* Top Action Buttons: Anara Brain, Anara Code & Chat Baru */}
      <div className="px-3 pt-2.5 space-y-1.5 font-sans">
        <button
          onClick={onOpenBrain}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.10] border border-white/10 hover:border-white/20 text-slate-200 hover:text-white text-xs font-medium transition-all active:scale-[0.98] cursor-pointer shadow-sm"
          title="Open Anara Brain (Memory, Tasks, Projects & Providers)"
        >
          <svg className="w-3.5 h-3.5 text-indigo-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span>Anara Brain</span>
        </button>

        {sessionType === "code" ? (
          <button
            onClick={onOpenCode}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/30 hover:border-cyan-400/50 text-cyan-200 hover:text-white text-xs font-semibold transition-all active:scale-[0.98] cursor-pointer shadow-sm group"
            title="Open Workspace Editor & Terminal"
          >
            <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            <span>Open Editor ‹/›</span>
          </button>
        ) : (
          <button
            onClick={() => {
              if (typeof window !== "undefined") {
                window.open("/code", "_blank");
              }
            }}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/30 hover:border-cyan-400/50 text-cyan-200 hover:text-white text-xs font-semibold transition-all active:scale-[0.98] cursor-pointer shadow-sm group"
            title="Open Anara Code Studio in new browser tab"
          >
            <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            <span>Open Anara Code ↗</span>
          </button>
        )}

        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-white/[0.07] hover:bg-white/[0.12] border border-white/12 hover:border-white/20 text-white text-xs font-semibold transition-all active:scale-[0.98] cursor-pointer shadow-sm"
        >
          <svg className="w-3.5 h-3.5 text-slate-300 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>{sessionType === "code" ? "New Project" : "New Chat"}</span>
        </button>
      </div>

      {/* Search */}
      <div className="px-3 mt-2.5 relative">
        <svg
          className="w-3.5 h-3.5 text-slate-500 absolute left-5.5 top-1/2 -translate-y-1/2 pointer-events-none"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search conversations..."
          className="w-full py-1.5 pl-8 pr-3 rounded-xl bg-black/30 border border-white/8 text-[11.5px] text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-400/40 focus:bg-black/45 transition-all font-sans"
        />
      </div>

      {/* Session list with full datetime details & Drag-to-Pin functionality */}
      <div
        ref={listRef}
        onDragOver={(e) => {
          if (draggedSession) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            if (draggedSession.is_pinned === 1 && dragOverTarget !== "unpin") {
              setDragOverTarget("unpin");
            }
          }
        }}
        onDrop={(e) => {
          if (draggedSession && draggedSession.is_pinned === 1) {
            e.preventDefault();
            onDropUnpin(draggedSession.id);
          }
        }}
        className="flex-1 overflow-y-auto mt-2.5 px-2 pb-2 [scrollbar-width:thin] [scrollbar-color:rgba(148,163,184,0.25)_transparent] font-sans"
      >
        {/* Top Drop Zone: When dragging an unpinned session and NO pinned group exists yet */}
        {draggedSession && draggedSession.is_pinned === 0 && !sessions.some((x) => x.is_pinned === 1) && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
              setDragOverTarget("pin");
            }}
            onDragLeave={() => setDragOverTarget(null)}
            onDrop={(e) => {
              e.preventDefault();
              if (draggedSession) onDropPin(draggedSession.id);
            }}
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
        ) : groups.length === 0 ? (
          <div className="text-center py-10 px-4">
            <p className="text-xs font-semibold text-slate-300">
              {search ? "Not found" : "No history yet"}
            </p>
            <p className="text-[10.5px] text-slate-500 mt-1 leading-relaxed">
              {search ? "Try different keywords." : "Start chatting, Anara saves them here."}
            </p>
          </div>
        ) : (
          groups.map((group) => {
            const isPinnedGroup = group.label === "Pinned";
            return (
              <React.Fragment key={group.label}>
                <div
                  className={`mb-3 rounded-xl transition-all ${
                    draggedSession
                      ? isPinnedGroup && draggedSession.is_pinned === 0 && dragOverTarget === "pin"
                        ? "ring-1 ring-cyan-400/50 bg-cyan-500/5 p-1"
                        : !isPinnedGroup && draggedSession.is_pinned === 1 && dragOverTarget === "unpin"
                        ? "ring-1 ring-rose-400/50 bg-rose-500/5 p-1"
                        : ""
                      : ""
                  }`}
                  onDragOver={(e) => {
                    if (draggedSession) {
                      e.preventDefault();
                      e.dataTransfer.dropEffect = "move";
                      if (isPinnedGroup && draggedSession.is_pinned === 0) {
                        setDragOverTarget("pin");
                      } else if (!isPinnedGroup && draggedSession.is_pinned === 1) {
                        setDragOverTarget("unpin");
                      }
                    }
                  }}
                  onDrop={(e) => {
                    if (draggedSession) {
                      if (isPinnedGroup && draggedSession.is_pinned === 0) {
                        e.preventDefault();
                        onDropPin(draggedSession.id);
                      } else if (!isPinnedGroup && draggedSession.is_pinned === 1) {
                        e.preventDefault();
                        onDropUnpin(draggedSession.id);
                      }
                    }
                  }}
                >
                  <p className="px-2 mb-1 text-[9.5px] font-semibold uppercase tracking-wider text-slate-500 font-mono flex items-center justify-between">
                    <span>{group.label}</span>
                    {isPinnedGroup && (
                      <span className="text-[8.5px] font-normal lowercase opacity-70 text-slate-400">
                        (drag down to release)
                      </span>
                    )}
                  </p>
                  <div className="space-y-1">
                    {group.items.map((s) => {
                      const isActive = activeSessionId === s.id;
                      const isBeingDragged = draggedSession?.id === s.id;
                      const isHoveredTarget = hoveredDropSessionId === s.id && Boolean(draggedSession && draggedSession.id !== s.id);
                      const formattedTime = formatFullDateTime(s.updated_at || s.created_at);

                      return (
                        <div
                          key={s.id}
                          onDragOver={(e) => {
                            if (draggedSession && draggedSession.id !== s.id) {
                              e.preventDefault();
                              e.dataTransfer.dropEffect = "move";
                              e.stopPropagation();
                              setHoveredDropSessionId(s.id);
                              if (isPinnedGroup && draggedSession.is_pinned === 0) {
                                setDragOverTarget("pin");
                              } else if (!isPinnedGroup && draggedSession.is_pinned === 1) {
                                setDragOverTarget("unpin");
                              }
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
                              if (isPinnedGroup && draggedSession.is_pinned === 0) {
                                onDropPin(draggedSession.id);
                              } else if (!isPinnedGroup && draggedSession.is_pinned === 1) {
                                onDropUnpin(draggedSession.id);
                              }
                              setHoveredDropSessionId(null);
                            }
                          }}
                          className={`group/item relative rounded-xl transition-all ${
                            isBeingDragged
                              ? "opacity-30 scale-[0.98] border border-dashed border-white/25"
                              : ""
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
                              draggable={renamingId !== s.id}
                              onDragStart={(e) => {
                                e.stopPropagation();
                                e.dataTransfer.setData("text/plain", String(s.id));
                                e.dataTransfer.effectAllowed = "move";
                                setTimeout(() => {
                                  setDraggedSession(s);
                                }, 0);
                              }}
                              onDragEnd={() => {
                                setDraggedSession(null);
                                setDragOverTarget(null);
                                setHoveredDropSessionId(null);
                              }}
                              onClick={() => onSelectSession(s.id)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault();
                                  onSelectSession(s.id);
                                }
                              }}
                              title={`${s.title || `Conversation #${s.id}`} (${formattedTime}) • Hold and drag to pin/unpin`}
                              className={`w-full flex flex-col gap-0.5 text-left p-2.5 pr-7 rounded-xl transition-all border outline-none cursor-grab active:cursor-grabbing select-none ${
                                isHoveredTarget && draggedSession
                                  ? draggedSession.is_pinned === 1
                                    ? "bg-rose-950/30 border-rose-500/40 text-white shadow-sm"
                                    : "bg-cyan-950/30 border-cyan-400/40 text-white shadow-sm"
                                  : isActive
                                  ? "bg-white/[0.08] border-white/15 text-white shadow-sm"
                                  : "border-transparent bg-transparent hover:bg-white/[0.04] text-slate-300 hover:text-white"
                              }`}
                            >
                              <div className="flex items-center gap-1.5 w-full pointer-events-none">
                                {s.is_pinned === 1 && (
                                  <svg className="w-3 h-3 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                                  </svg>
                                )}
                                {s.is_archived === 1 && (
                                  <span className="text-[8.5px] font-mono text-slate-500 shrink-0">[archived]</span>
                                )}
                                <p
                                  className={`text-[12px] font-medium truncate flex-1 leading-snug ${
                                    isActive ? "text-white font-semibold" : "text-slate-300"
                                  }`}
                                >
                                  {s.title || `Conversation #${s.id}`}
                                </p>
                              </div>

                              {/* Full Datetime Display */}
                              <div className="flex items-center justify-between text-[9.5px] font-mono text-slate-400/90 pt-0.5 pointer-events-none">
                                <span className="truncate">{formattedTime}</span>
                                <span className={`shrink-0 ${isActive ? "text-slate-400" : "text-slate-500"}`}>{s.message_count} messages</span>
                              </div>
                            </div>
                          )}

                          {/* Row options menu button */}
                          {renamingId !== s.id && (
                            <div className="absolute top-2 right-1.5 z-10" onMouseDown={(e) => e.stopPropagation()}>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setMenuOpenId(menuOpenId === s.id ? null : s.id);
                                }}
                                className={`w-5 h-6 rounded flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/15 transition-all cursor-pointer ${
                                  menuOpenId === s.id ? "opacity-100" : "opacity-0 group-hover/item:opacity-100"
                                }`}
                                title="Session options"
                              >
                                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                                  <circle cx="12" cy="5" r="2" />
                                  <circle cx="12" cy="12" r="2" />
                                  <circle cx="12" cy="19" r="2" />
                                </svg>
                              </button>

                              {menuOpenId === s.id && (
                                <div
                                  className="absolute right-0 top-7 z-30 w-44 py-1 rounded-xl bg-slate-950/95 border border-white/15 backdrop-blur-xl shadow-2xl font-sans"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  {[
                                    {
                                      label: "Rename",
                                      action: () => {
                                        setRenameValue(s.title || "");
                                        setRenamingId(s.id);
                                        setMenuOpenId(null);
                                      },
                                    },
                                    {
                                      label: s.is_pinned === 1 ? "Unpin" : "Pin",
                                      action: () => {
                                        onPatchSession(s.id, { is_pinned: s.is_pinned !== 1 });
                                        setMenuOpenId(null);
                                      },
                                    },
                                  ].map((item) => (
                                    <button
                                      key={item.label}
                                      onClick={item.action}
                                      className="w-full text-left px-3 py-1.5 text-[11px] text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                                    >
                                      {item.label}
                                    </button>
                                  ))}
                                  <div className="my-1 border-t border-white/10" />
                                  <button
                                    onClick={() => {
                                      onDeleteSession(s);
                                      setMenuOpenId(null);
                                    }}
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
                    })}
                  </div>
                </div>

                {/* Dedicated Unpin Drop Zone immediately below Pinned group */}
                {isPinnedGroup && draggedSession && draggedSession.is_pinned === 1 && (
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      e.dataTransfer.dropEffect = "move";
                      setDragOverTarget("unpin");
                    }}
                    onDragLeave={(e) => {
                      e.stopPropagation();
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onDropUnpin(draggedSession.id);
                    }}
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
              </React.Fragment>
            );
          })
        )}

        {/* Bottom Drop Zone when dragging a pinned session and multiple groups exist */}
        {draggedSession && draggedSession.is_pinned === 1 && groups.length > 1 && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
              e.dataTransfer.dropEffect = "move";
              setDragOverTarget("unpin");
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onDropUnpin(draggedSession.id);
            }}
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
