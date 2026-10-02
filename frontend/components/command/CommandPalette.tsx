"use client";

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { anaraApi } from "@/lib/apiClient";

export interface CommandItem {
  id: string;
  label: string;
  category: "Commands" | "AI Models" | "Sessions" | "Files" | string;
  sublabel?: string;
  shortcut?: string;
  icon?: React.ReactNode;
  onSelect: () => void;
  keywords?: string[];
}

export interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  commands: CommandItem[];
  sessions?: Array<{
    id: number;
    title: string | null;
    session_type?: "chat" | "code";
    message_count: number;
    updated_at?: string;
  }>;
  onSelectSession?: (id: number) => void;
  workspaceFiles?: Array<{
    name: string;
    path: string;
    ext?: string;
    size_kb?: number;
  }>;
  onOpenFile?: (filePath: string, fileName: string) => void;
  onToggleOpen?: () => void;
}

type CategoryFilter = "All" | "Commands" | "AI Models" | "Sessions" | "Files";

/** High-performance subsequence fuzzy scorer with boundary and consecutive match bonuses */
function fuzzyScore(query: string, text: string): { matches: boolean; score: number; indices: number[] } {
  const q = query.trim().toLowerCase();
  const t = text.toLowerCase();
  if (!q) return { matches: true, score: 0, indices: [] };

  // Exact match bonus
  if (t === q) {
    const indices = Array.from({ length: q.length }, (_, i) => i);
    return { matches: true, score: 1000, indices };
  }

  // Exact prefix match bonus
  if (t.startsWith(q)) {
    const indices = Array.from({ length: q.length }, (_, i) => i);
    return { matches: true, score: 800 + (100 / (t.length - q.length + 1)), indices };
  }

  // Acronym match bonus (e.g. "nt" -> "New Tab", "g3f" -> "Gemini 3.8 Flash")
  const words = text.split(/[\s_\-./\\]+/);
  const acronym = words.map((w) => w[0]?.toLowerCase() || "").join("");
  if (acronym.includes(q)) {
    return { matches: true, score: 600, indices: [] };
  }

  // Subsequence match
  let qIdx = 0;
  let tIdx = 0;
  let score = 0;
  let consecutive = 0;
  const indices: number[] = [];

  while (qIdx < q.length && tIdx < t.length) {
    if (q[qIdx] === t[tIdx]) {
      indices.push(tIdx);
      qIdx++;
      consecutive++;
      score += 10 + consecutive * 5;
      // Word boundary bonus
      if (tIdx === 0 || /[\s_\-./\\]/.test(text[tIdx - 1])) {
        score += 25;
      }
    } else {
      consecutive = 0;
    }
    tIdx++;
  }

  if (qIdx === q.length) {
    // Penalty for length gap to prefer tighter matches
    score -= (t.length - q.length) * 0.5;
    return { matches: true, score: Math.max(1, score), indices };
  }

  return { matches: false, score: -1, indices: [] };
}

/** Highlights fuzzy-matched characters with luminous cyan accents */
function HighlightFuzzyText({ text, query }: { text: string; query: string }) {
  const { matches, indices } = useMemo(() => fuzzyScore(query, text), [query, text]);
  if (!matches || !query.trim() || indices.length === 0) {
    return <span>{text}</span>;
  }

  const indexSet = new Set(indices);
  return (
    <span>
      {text.split("").map((char, i) =>
        indexSet.has(i) ? (
          <span key={i} className="text-cyan-300 font-semibold underline decoration-cyan-400/50">
            {char}
          </span>
        ) : (
          <span key={i}>{char}</span>
        )
      )}
    </span>
  );
}

export default function CommandPalette({
  isOpen,
  onClose,
  commands,
  sessions: propSessions,
  onSelectSession,
  workspaceFiles: propFiles,
  onOpenFile,
  onToggleOpen,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>("All");
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Fallback internal sessions and files state
  const [internalSessions, setInternalSessions] = useState<Array<{ id: number; title: string | null; message_count: number; session_type?: "chat" | "code" }>>([]);
  const [internalFiles, setInternalFiles] = useState<Array<{ name: string; path: string; size_kb?: number }>>([]);

  // ── 1. Global Keyboard Shortcut Registration (Cmd/Ctrl+K / Cmd/Ctrl+P) ──
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "p")) {
        e.preventDefault();
        e.stopPropagation();
        if (onToggleOpen) {
          onToggleOpen();
        } else if (isOpen) {
          onClose();
        }
      }
    };

    const handleCustomOpen = () => {
      if (onToggleOpen) onToggleOpen();
    };

    window.addEventListener("keydown", handleGlobalKeyDown);
    window.addEventListener("anara:open-command-palette", handleCustomOpen);
    return () => {
      window.removeEventListener("keydown", handleGlobalKeyDown);
      window.removeEventListener("anara:open-command-palette", handleCustomOpen);
    };
  }, [isOpen, onClose, onToggleOpen]);

  // Fetch background sessions & files for rich search if not provided via props
  useEffect(() => {
    if (!isOpen) return;

    if (!propSessions || propSessions.length === 0) {
      anaraApi.sessions
        .list({ includeArchived: false })
        .then((res) => {
          if (Array.isArray(res)) setInternalSessions(res);
        })
        .catch(() => {});
    }

    if (!propFiles || propFiles.length === 0) {
      anaraApi.workspace
        .getTree()
        .then((tree) => {
          if (tree?.files && Array.isArray(tree.files)) {
            setInternalFiles(tree.files);
          }
        })
        .catch(() => {});
    }
  }, [isOpen, propSessions, propFiles]);

  // Reset focus and states upon opening
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setActiveCategory("All");
      setTimeout(() => inputRef.current?.focus(), 40);
    }
  }, [isOpen]);

  // ── 2. Unified Multi-Domain Items Collection ────────────────────────────
  const unifiedItems: CommandItem[] = useMemo(() => {
    const list: CommandItem[] = [...commands];

    // Enrich with Sessions
    const activeSessions = propSessions && propSessions.length > 0 ? propSessions : internalSessions;
    activeSessions.slice(0, 15).forEach((s) => {
      const isCode = s.session_type === "code";
      list.push({
        id: `session-${s.id}`,
        label: s.title || (isCode ? `Coding Workspace #${s.id}` : `Chat Session #${s.id}`),
        category: "Sessions",
        sublabel: `${s.message_count} messages • ${isCode ? "Code Studio" : "Chat"}`,
        shortcut: `#${s.id}`,
        icon: (
          <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        ),
        onSelect: () => {
          if (onSelectSession) {
            onSelectSession(s.id);
          } else if (typeof window !== "undefined") {
            localStorage.setItem("anara_active_session_id", String(s.id));
            window.location.reload();
          }
        },
      });
    });

    // Enrich with Workspace Files
    const activeFiles = propFiles && propFiles.length > 0 ? propFiles : internalFiles;
    activeFiles.slice(0, 40).forEach((f) => {
      list.push({
        id: `file-${f.path}`,
        label: f.name,
        category: "Files",
        sublabel: f.path,
        shortcut: f.size_kb ? `${f.size_kb} KB` : undefined,
        icon: (
          <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        ),
        onSelect: () => {
          if (onOpenFile) {
            onOpenFile(f.path, f.name);
          } else if (typeof window !== "undefined") {
            window.open(`/code?file=${encodeURIComponent(f.path)}`, "_blank");
          }
        },
      });
    });

    return list;
  }, [commands, propSessions, internalSessions, propFiles, internalFiles, onSelectSession, onOpenFile]);

  // Support quick search prefixes (e.g. "> " for Commands, "@" for Files, "~" for Sessions)
  const effectiveFilter = useMemo(() => {
    let cleanQuery = query.trim();
    let overrideCategory: CategoryFilter | null = null;

    if (cleanQuery.startsWith(">")) {
      overrideCategory = "Commands";
      cleanQuery = cleanQuery.slice(1).trim();
    } else if (cleanQuery.startsWith("@") || cleanQuery.startsWith("#/")) {
      overrideCategory = "Files";
      cleanQuery = cleanQuery.slice(1).trim();
    } else if (cleanQuery.startsWith("~")) {
      overrideCategory = "Sessions";
      cleanQuery = cleanQuery.slice(1).trim();
    } else if (cleanQuery.startsWith("#")) {
      overrideCategory = "AI Models";
      cleanQuery = cleanQuery.slice(1).trim();
    }

    return {
      query: cleanQuery,
      category: overrideCategory || activeCategory,
    };
  }, [query, activeCategory]);

  // ── 3. Search Filtering with Fuzzy Ranking ───────────────────────────────
  const filteredCommands = useMemo(() => {
    const { query: q, category } = effectiveFilter;

    let candidates = unifiedItems;
    if (category !== "All") {
      candidates = candidates.filter((c) => {
        if (category === "Commands") return c.category === "Commands" || c.category === "Workstation" || c.category === "Context Panes" || c.category === "Chat" || c.category === "Navigation";
        return c.category.toLowerCase() === category.toLowerCase();
      });
    }

    if (!q) {
      return candidates;
    }

    const scored = candidates
      .map((cmd) => {
        const labelScore = fuzzyScore(q, cmd.label);
        const subScore = cmd.sublabel ? fuzzyScore(q, cmd.sublabel) : { matches: false, score: -1, indices: [] };
        const catScore = fuzzyScore(q, cmd.category);
        const bestScore = Math.max(labelScore.score, subScore.score * 0.8, catScore.score * 0.5);
        const hasMatch = labelScore.matches || subScore.matches || catScore.matches;

        return {
          cmd,
          score: bestScore,
          hasMatch,
        };
      })
      .filter((item) => item.hasMatch)
      .sort((a, b) => b.score - a.score)
      .map((item) => item.cmd);

    return scored;
  }, [unifiedItems, effectiveFilter]);

  // Reset selected index when filtered list changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [filteredCommands]);

  // Auto-scroll active item into viewport
  useEffect(() => {
    if (!listRef.current) return;
    const activeItem = listRef.current.querySelector(`[data-index="${selectedIndex}"]`) as HTMLElement;
    if (activeItem) {
      activeItem.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  // ── 4. Full Keyboard Navigation ─────────────────────────────────────────
  const categories: CategoryFilter[] = ["All", "Commands", "AI Models", "Sessions", "Files"];

  const cycleCategory = useCallback((forward = true) => {
    const curIdx = categories.indexOf(activeCategory);
    const nextIdx = forward
      ? (curIdx + 1) % categories.length
      : (curIdx - 1 + categories.length) % categories.length;
    setActiveCategory(categories[nextIdx]);
  }, [activeCategory, categories]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (filteredCommands.length > 0 ? (prev + 1) % filteredCommands.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        filteredCommands.length > 0 ? (prev - 1 + filteredCommands.length) % filteredCommands.length : 0
      );
    } else if (e.key === "Home") {
      e.preventDefault();
      setSelectedIndex(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setSelectedIndex(Math.max(0, filteredCommands.length - 1));
    } else if (e.key === "Tab") {
      e.preventDefault();
      cycleCategory(!e.shiftKey);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredCommands[selectedIndex]) {
        filteredCommands[selectedIndex].onSelect();
        onClose();
      }
    }
  };

  if (!isOpen) return null;

  // Group filtered items by category for clean section headers
  const grouped = filteredCommands.reduce((acc, cmd, idx) => {
    const cat = cmd.category || "General";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push({ cmd, flatIndex: idx });
    return acc;
  }, {} as Record<string, Array<{ cmd: CommandItem; flatIndex: number }>>);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command Palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] px-4 bg-black/75 backdrop-blur-2xl animate-in fade-in duration-150 select-none"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl rounded-2xl border border-white/[0.10] bg-[#060913]/95 backdrop-blur-2xl shadow-[0_24px_64px_rgba(0,0,0,0.85),0_0_24px_rgba(34,211,238,0.08)] overflow-hidden flex flex-col font-sans transition-all"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Specular Top Hairline */}
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-cyan-400/30 to-transparent pointer-events-none" />

        {/* Search Input Bar with Hairline Bottom */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.08] bg-white/[0.02]">
          <svg className="w-4 h-4 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command, search models, files, or sessions... (Esc to close)"
            className="flex-1 bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none font-sans"
          />
          <div className="flex items-center gap-1.5 shrink-0">
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="p-1 rounded text-slate-400 hover:text-white text-xs cursor-pointer"
                title="Clear query"
              >
                ✕
              </button>
            )}
            <kbd className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/10 text-[10px] font-mono text-slate-400">
              ESC
            </kbd>
          </div>
        </div>

        {/* Domain Filter Pills Rail */}
        <div className="px-3 py-1.5 border-b border-white/[0.06] bg-black/30 flex items-center gap-1.5 overflow-x-auto no-scrollbar text-xs font-mono shrink-0">
          <span className="text-[10px] text-slate-500 uppercase font-semibold mr-1 shrink-0">Filter:</span>
          {categories.map((cat) => {
            const isActive = activeCategory === cat;
            return (
              <button
                key={cat}
                type="button"
                onClick={() => setActiveCategory(cat)}
                className={`px-2 py-0.5 rounded-lg text-[10.5px] transition-colors cursor-pointer shrink-0 ${
                  isActive
                    ? "bg-cyan-500/15 border border-cyan-400/40 text-cyan-200 font-semibold"
                    : "hover:bg-white/[0.05] text-slate-400 hover:text-slate-200 border border-transparent"
                }`}
              >
                {cat}
              </button>
            );
          })}
          <span className="ml-auto text-[10px] text-slate-500 shrink-0 font-mono">
            {filteredCommands.length} matches
          </span>
        </div>

        {/* Command List Area with Flat Liquid Glass Rows (Zero Card-itis) */}
        <div ref={listRef} className="max-h-[380px] overflow-y-auto custom-scrollbar p-1.5 space-y-2">
          {filteredCommands.length === 0 ? (
            <div className="py-12 text-center flex flex-col items-center justify-center gap-1.5 text-xs font-mono text-slate-500">
              <svg className="w-6 h-6 text-slate-600 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>No matching commands, models, files, or sessions found.</span>
              <span className="text-[10.5px] text-slate-600">Try searching with a broader keyword or switch filters.</span>
            </div>
          ) : (
            Object.entries(grouped).map(([category, items]) => (
              <div key={category} className="space-y-0.5">
                <p className="px-2.5 py-1 text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-500 flex items-center justify-between">
                  <span>{category}</span>
                  <span className="text-[9px] text-slate-600">{items.length}</span>
                </p>
                {items.map(({ cmd, flatIndex }) => {
                  const isSelected = selectedIndex === flatIndex;
                  return (
                    <button
                      key={cmd.id}
                      type="button"
                      data-index={flatIndex}
                      onClick={() => {
                        cmd.onSelect();
                        onClose();
                      }}
                      onMouseEnter={() => setSelectedIndex(flatIndex)}
                      className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-left transition-colors cursor-pointer font-sans border-l-2 ${
                        isSelected
                          ? "border-cyan-400 bg-cyan-500/10 text-white font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
                          : "border-transparent hover:bg-white/[0.04] text-slate-300 hover:text-white"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0 flex-1 pr-2">
                        {cmd.icon ? (
                          <div className={`w-4 h-4 shrink-0 ${isSelected ? "text-cyan-300" : "text-slate-400"}`}>
                            {cmd.icon}
                          </div>
                        ) : (
                          <div className="w-4 h-4 shrink-0 flex items-center justify-center text-slate-500">
                            ●
                          </div>
                        )}
                        <div className="truncate flex-1 min-w-0">
                          <p className={`text-xs truncate ${isSelected ? "text-white font-medium" : "text-slate-200"}`}>
                            <HighlightFuzzyText text={cmd.label} query={effectiveFilter.query} />
                          </p>
                          {cmd.sublabel && (
                            <p className="text-[10px] text-slate-400 truncate font-mono">
                              <HighlightFuzzyText text={cmd.sublabel} query={effectiveFilter.query} />
                            </p>
                          )}
                        </div>
                      </div>

                      {cmd.shortcut && (
                        <kbd className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/10 text-[10px] font-mono text-slate-400 shrink-0 ml-2">
                          {cmd.shortcut}
                        </kbd>
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer Hint Bar */}
        <div className="px-4 py-2 border-t border-white/[0.06] bg-[#050811] flex items-center justify-between text-[10px] font-mono text-slate-500 select-none">
          <div className="flex items-center gap-3">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>Tab Cycle filter</span>
            <span>Esc Close</span>
          </div>
          <span className="text-cyan-400/80 font-semibold tracking-wide">Anara Studio</span>
        </div>
      </div>
    </div>
  );
}
