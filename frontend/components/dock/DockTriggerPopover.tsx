"use client";

import React, { useMemo, useEffect, useRef } from "react";

export interface TriggerItem {
  id: string;
  category: "Files" | "Folders" | "Commands" | "Modes";
  label: string;
  value: string;
  detail?: string;
  icon?: "file" | "folder" | "command" | "mode";
}

export interface DockTriggerPopoverProps {
  isOpen: boolean;
  triggerKind: "@" | "/" | null;
  query: string;
  onSelect: (item: TriggerItem) => void;
  onClose: () => void;
  workspaceFiles?: Array<{ path: string; name: string; isDir?: boolean }>;
  selectedIndex: number;
  onSelectedIndexChange: (idx: number) => void;
}

const DEFAULT_SLASH_COMMANDS: TriggerItem[] = [
  { id: "cmd-plan", category: "Modes", label: "/plan", value: "/plan ", detail: "Switch to Architect / Planning mode", icon: "mode" },
  { id: "cmd-build", category: "Modes", label: "/build", value: "/build ", detail: "Switch to autonomous Execution mode", icon: "mode" },
  { id: "cmd-voice", category: "Modes", label: "/voice", value: "/voice", detail: "Switch to 3D Avatar Voice mode", icon: "mode" },
  { id: "cmd-chat", category: "Modes", label: "/chat", value: "/chat", detail: "Switch to standard Chat mode", icon: "mode" },
  { id: "cmd-clear", category: "Commands", label: "/clear", value: "/clear", detail: "Clear active conversation transcript", icon: "command" },
  { id: "cmd-compact", category: "Commands", label: "/compact", value: "/compact", detail: "Summarize & compact active session context", icon: "command" },
  { id: "cmd-git", category: "Commands", label: "/git", value: "/git status", detail: "Inspect Git workspace branch & diffs", icon: "command" },
  { id: "cmd-model", category: "Commands", label: "/model", value: "/model ", detail: "Switch active LLM reasoning model", icon: "command" },
];

function fuzzyMatch(text: string, query: string): { matches: boolean; score: number } {
  const t = text.toLowerCase();
  const q = query.toLowerCase().trim();
  if (!q) return { matches: true, score: 0 };
  if (t === q) return { matches: true, score: 1000 };
  if (t.startsWith(q)) return { matches: true, score: 500 };
  let qIdx = 0;
  let score = 0;
  for (let i = 0; i < t.length; i++) {
    if (t[i] === q[qIdx]) {
      qIdx++;
      score += 10;
    }
  }
  return { matches: qIdx === q.length, score };
}

export default function DockTriggerPopover({
  isOpen,
  triggerKind,
  query,
  onSelect,
  onClose,
  workspaceFiles = [],
  selectedIndex,
  onSelectedIndexChange,
}: DockTriggerPopoverProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Generate candidates based on triggerKind
  const candidates = useMemo<TriggerItem[]>(() => {
    if (!triggerKind) return [];

    if (triggerKind === "/") {
      return DEFAULT_SLASH_COMMANDS.map((cmd) => {
        const { matches, score } = fuzzyMatch(cmd.label, query);
        return { item: cmd, matches, score };
      })
        .filter((r) => r.matches)
        .sort((a, b) => b.score - a.score)
        .map((r) => r.item);
    }

    if (triggerKind === "@") {
      const fileCandidates: TriggerItem[] = workspaceFiles.slice(0, 100).map((f) => ({
        id: `file-${f.path}`,
        category: f.isDir ? "Folders" : "Files",
        label: f.name,
        value: `@${f.path} `,
        detail: f.path,
        icon: f.isDir ? "folder" : "file",
      }));

      return fileCandidates
        .map((item) => {
          const { matches, score } = fuzzyMatch(item.label + " " + item.detail, query);
          return { item, matches, score };
        })
        .filter((r) => r.matches)
        .sort((a, b) => b.score - a.score)
        .slice(0, 12)
        .map((r) => r.item);
    }

    return [];
  }, [triggerKind, query, workspaceFiles]);

  // Keep selected index within bounds
  useEffect(() => {
    if (candidates.length === 0) {
      onSelectedIndexChange(0);
    } else if (selectedIndex >= candidates.length) {
      onSelectedIndexChange(candidates.length - 1);
    }
  }, [candidates.length, selectedIndex, onSelectedIndexChange]);

  // Auto-scroll active item into view
  useEffect(() => {
    if (!containerRef.current) return;
    const activeEl = containerRef.current.querySelector(`[data-index="${selectedIndex}"]`) as HTMLElement;
    if (activeEl) {
      activeEl.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  if (!isOpen || !triggerKind || candidates.length === 0) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      className="absolute bottom-full left-0 mb-2 w-full max-w-md max-h-64 overflow-y-auto custom-scrollbar rounded-xl bg-[#060913]/95 backdrop-blur-2xl border border-white/15 shadow-[0_16px_40px_rgba(0,0,0,0.85)] z-50 p-1.5 font-mono text-xs select-none animate-fade-in"
      tabIndex={-1}
    >
      <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-white/[0.08] flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-cyan-300">
          <span>{triggerKind === "/" ? "Slash Commands & Skills" : "Workspace Files & Folders"}</span>
          <span className="text-[9px] text-slate-500 font-normal">({candidates.length})</span>
        </span>
        <span className="text-[9px] text-slate-500 font-normal">↑↓ to navigate · Enter to insert</span>
      </div>

      <div className="py-1 space-y-0.5">
        {candidates.map((item, idx) => {
          const isSelected = idx === selectedIndex;
          return (
            <button
              key={item.id}
              type="button"
              data-index={idx}
              onClick={() => onSelect(item)}
              onMouseEnter={() => onSelectedIndexChange(idx)}
              className={`w-full px-2 py-1.5 rounded-lg flex items-center justify-between text-left transition-colors cursor-pointer ${
                isSelected ? "bg-white/10 text-white shadow-sm" : "text-slate-300 hover:bg-white/[0.04]"
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                {/* Icon Indicator */}
                {item.icon === "folder" ? (
                  <svg className="w-3.5 h-3.5 text-amber-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                ) : item.icon === "file" ? (
                  <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                ) : item.icon === "mode" ? (
                  <svg className="w-3.5 h-3.5 text-purple-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                ) : (
                  <svg className="w-3.5 h-3.5 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                )}

                <span className="font-semibold text-xs truncate">{item.label}</span>
                {item.detail && (
                  <span className="text-[10px] text-slate-500 truncate max-w-[200px]">{item.detail}</span>
                )}
              </div>

              <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono shrink-0 ml-2 ${
                isSelected ? "bg-white/10 text-cyan-200" : "bg-white/[0.04] text-slate-500"
              }`}>
                {item.category}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
