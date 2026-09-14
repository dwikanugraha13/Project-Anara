"use client";

import React, { useState, useMemo } from "react";
import { AgentActionData, TodoData } from "../hud/types";

export interface AgentToolCardProps {
  action?: AgentActionData;
  todoData?: TodoData;
  onOpenFile?: (filePath: string, fileName: string) => void;
  onDismiss?: () => void;
}

export function ThinkingCard({ text }: { text: string }) {
  if (!text) return null;
  return (
    <div className="flex items-center gap-2 py-1 font-mono text-xs select-none animate-fade-in my-1.5">
      <span className="text-white font-bold tracking-tight">Berpikir</span>
      <span className="text-slate-400 font-sans truncate">{text}</span>
    </div>
  );
}

export function ExplorationGroupCard({
  items,
  isRunning = false,
}: {
  items: AgentActionData[];
  isRunning?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!items || items.length === 0) return null;

  const readCount = items.filter((t) => {
    const tn = (t.toolName || "").toLowerCase();
    return tn.includes("read") || tn.includes("scan");
  }).length;

  const searchCount = items.filter((t) => {
    const tn = (t.toolName || "").toLowerCase();
    return tn.includes("grep") || tn.includes("glob") || tn.includes("search") || tn.includes("list");
  }).length;

  let labelText = "";
  if (readCount > 0 && searchCount > 0) {
    labelText = `${readCount} pembacaan, ${searchCount} pencarian`;
  } else if (readCount > 0) {
    labelText = `${readCount} pembacaan`;
  } else if (searchCount > 0) {
    labelText = `${searchCount} pencarian`;
  } else {
    labelText = `${items.length} operasi`;
  }

  const prefix = isRunning ? "Menjelajah" : "Selesai menjelajah";

  return (
    <div className="my-1.5 font-mono text-xs select-none">
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        className="flex items-center gap-2 text-left text-slate-300 hover:text-white transition-colors cursor-pointer py-0.5"
      >
        <span className="font-bold text-white tracking-tight">{prefix}</span>
        <span className="text-slate-400">{labelText}</span>
        <svg
          className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-150 shrink-0 ${
            isExpanded ? "rotate-180" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div className="pl-3.5 py-1 space-y-1 border-l border-white/10 my-1 font-mono text-[11px] animate-fade-in">
          {items.map((sub, sIdx) => {
            const tool = (sub.toolName || "").toLowerCase();
            const isRead = tool.includes("read") || tool.includes("scan");
            const isGrep = tool.includes("grep");
            const isGlob = tool.includes("glob");
            const opLabel = isRead ? "Baca" : isGrep ? "Grep" : isGlob ? "Glob" : "Aksi";
            const detailText = sub.detail || sub.actionTitle || "";

            return (
              <div key={sIdx} className="flex items-baseline gap-2 py-0.5 truncate text-slate-300">
                <span className="font-bold text-white shrink-0">{opLabel}</span>
                <span className="truncate text-slate-200 font-mono">{detailText}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function AgentToolCard({ action, todoData, onOpenFile }: AgentToolCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isReverting, setIsReverting] = useState(false);
  const [isReverted, setIsReverted] = useState(false);

  const handleRollback = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!action?.checkpointId) return;
    setIsReverting(true);
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    try {
      const res = await fetch(`${backendUrl}/api/agent/checkpoint/revert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ checkpoint_id: action.checkpointId }),
      });
      if (res.ok) {
        setIsReverted(true);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "workspace_updated" } }));
        }
      }
    } catch (err) {
      console.warn("[Rollback Error]:", err);
    } finally {
      setIsReverting(false);
    }
  };

  // ── Render Checklist Widget ("0 dari 7 tugas selesai ˅") ──
  if (todoData && todoData.items && todoData.items.length > 0) {
    const total = todoData.items.length;
    const completed = todoData.items.filter((t: { is_completed?: number | boolean }) => t.is_completed).length;

    return (
      <div className="my-2.5 rounded-xl overflow-hidden border border-white/10 bg-black/60 backdrop-blur-xl select-none font-sans text-xs transition-all shadow-xl">
        <button
          onClick={() => setIsExpanded((v) => !v)}
          className="w-full flex items-center justify-between px-3.5 py-2.5 bg-white/[0.03] hover:bg-white/[0.06] transition-colors cursor-pointer text-left"
        >
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded-full border border-white/30 flex items-center justify-center text-[9px] text-cyan-300 font-mono">
              {completed === total ? "✓" : "○"}
            </span>
            <span className="font-semibold text-slate-200">
              {completed} dari {total} tugas selesai
            </span>
          </div>
          <svg
            className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${
              isExpanded ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {isExpanded && (
          <div className="p-3 pt-1 space-y-1.5 border-t border-white/5">
            {todoData.items.map((item: any, idx: number) => (
              <div
                key={idx}
                className={`flex items-start gap-2.5 p-2 rounded-lg text-[12px] transition-colors ${
                  item.is_completed
                    ? "text-slate-500 line-through bg-white/[0.01]"
                    : "text-slate-200 bg-white/[0.025] hover:bg-white/[0.05]"
                }`}
              >
                <span
                  className={`w-4 h-4 rounded mt-0.5 flex items-center justify-center text-[10px] shrink-0 font-bold ${
                    item.is_completed
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                      : "border border-white/20 text-transparent"
                  }`}
                >
                  ✓
                </span>
                <div className="flex-1 min-w-0">
                  <p className="leading-snug">{item.title}</p>
                  {item.content && (
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5">{item.content}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (!action) return null;

  const tool = (action.toolName || "").toLowerCase();
  const isStart = action.eventType === "agent_action_start";
  const isWrite = tool.includes("write") || tool.includes("edit") || tool.includes("artifact");
  const isShell = tool.includes("bash") || tool.includes("shell") || tool.includes("terminal") || tool.includes("command") || tool.includes("cli");
  const isSearch = tool.includes("glob") || tool.includes("grep") || tool.includes("search");
  const isRead = tool.includes("read") || tool.includes("scan") || tool.includes("list");

  // Extract file name and directory path
  const rawTarget = action.detail || action.actionTitle || "";
  const cleanTarget = rawTarget.replace(/^Sunting\s+/i, "").replace(/^File:\s*/i, "");
  const parts = cleanTarget.split(" ");
  const filename = action.filename || parts[0]?.split(/[/\\]/).pop() || "berkas";
  const dirPath = action.filePath ? action.filePath.replace(filename, "").replace(/[/\\]$/, "") : (parts[1] || "");

  // Compute diff lines
  const rawDiff = action.rawResult || action.summary || "";
  const parsedDiff = useMemo(() => {
    if (!rawDiff) return { added: 0, deleted: 0, lines: [] };
    const lines = rawDiff.split("\n");
    let added = 0;
    let deleted = 0;
    const formatted = lines.map((l: string, i: number) => {
      if (l.startsWith("+") && !l.startsWith("+++")) {
        added++;
        return { type: "add" as const, text: l.substring(1), lineNum: i + 1 };
      }
      if (l.startsWith("-") && !l.startsWith("---")) {
        deleted++;
        return { type: "del" as const, text: l.substring(1), lineNum: i + 1 };
      }
      return { type: "same" as const, text: l, lineNum: i + 1 };
    });
    return { added, deleted, lines: formatted };
  }, [rawDiff]);

  // ── Render Sunting (File Edit / Diff) Pill (Screenshot match) ──
  if (isWrite) {
    const addCount = action.added ?? parsedDiff.added ?? 1;
    const delCount = action.deleted ?? parsedDiff.deleted ?? 0;

    return (
      <div className="my-2 rounded-xl overflow-hidden border border-white/10 bg-black/60 backdrop-blur-xl font-sans text-xs select-none transition-all shadow-xl">
        {/* Header Pill: Sunting filename path +X -Y ▾ */}
        <div className="w-full flex items-center justify-between px-3.5 py-2 hover:bg-white/[0.04] transition-colors cursor-pointer text-left">
          <button
            type="button"
            onClick={() => setIsExpanded((v) => !v)}
            className="flex items-center gap-2 min-w-0 flex-1 text-left cursor-pointer font-mono"
          >
            <span className="text-white font-bold text-xs">Sunting</span>
            <span className="text-slate-100 font-semibold truncate text-xs">{filename}</span>
            {dirPath && <span className="text-slate-400 truncate text-[11px]">{dirPath}</span>}
            <div className="flex items-center gap-1 text-[10.5px] shrink-0 ml-1 font-bold">
              <span className="text-emerald-400">+{addCount}</span>
              <span className="text-rose-400">-{delCount}</span>
            </div>
            {isStart && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping ml-1" />}
          </button>

          <div className="flex items-center gap-2 shrink-0">
            {action.checkpointId && (
              <button
                type="button"
                onClick={handleRollback}
                disabled={isReverting || isReverted}
                className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer border ${
                  isReverted
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400/40"
                    : "bg-white/[0.06] hover:bg-white/[0.12] text-slate-300 hover:text-white border-white/10"
                }`}
                title="Batalkan perubahan berkas ke snapshot sebelum diedit agen (1-Click Rollback)"
              >
                {isReverting ? "Memulihkan..." : isReverted ? "✓ Dipulihkan" : "↺ Revert"}
              </button>
            )}

            {onOpenFile && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenFile(action.filePath || filename, filename);
                }}
                className="px-2 py-0.5 rounded text-[10px] font-mono text-cyan-300 hover:text-white bg-cyan-500/15 hover:bg-cyan-500/30 border border-cyan-400/30 transition-all cursor-pointer"
              >
                Buka di Editor
              </button>
            )}
            <button
              type="button"
              onClick={() => setIsExpanded((v) => !v)}
              className="p-0.5 text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              <svg
                className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 shrink-0 ${
                  isExpanded ? "rotate-180" : ""
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Collapsible Diff Body with Line Numbers & Green Additions */}
        {isExpanded && (
          <div className="border-t border-white/10 bg-slate-950/90 font-mono text-[11.5px]">
            <div className="flex items-center justify-between px-3 py-1.5 bg-black/40 border-b border-white/5 text-slate-400 text-[11px]">
              <span className="truncate text-slate-200 font-semibold font-mono">{filename}</span>
              <div className="flex items-center gap-1.5 font-mono text-[10.5px] shrink-0 font-bold">
                <span className="text-emerald-400">+{addCount}</span>
                <span className="text-rose-400">-{delCount}</span>
              </div>
            </div>

            <div className="max-h-[300px] overflow-auto custom-scrollbar p-2 select-text">
              {parsedDiff.lines.length > 0 ? (
                <table className="w-full border-collapse">
                  <tbody>
                    {parsedDiff.lines.map((line: { type: "add" | "del" | "same"; text: string; lineNum: number }, idx: number) => (
                      <tr
                        key={idx}
                        className={`${
                          line.type === "add"
                            ? "bg-emerald-950/40 text-emerald-200 border-l-2 border-emerald-500"
                            : line.type === "del"
                            ? "bg-rose-950/40 text-rose-300 border-l-2 border-rose-500"
                            : "text-slate-300 hover:bg-white/[0.02]"
                        }`}
                      >
                        <td className="w-9 pr-2 text-right select-none text-slate-600 font-mono text-[10px] py-0.5">
                          {line.lineNum}
                        </td>
                        <td className="w-5 text-center select-none font-bold py-0.5">
                          {line.type === "add" ? "+" : line.type === "del" ? "-" : " "}
                        </td>
                        <td className="pl-1.5 whitespace-pre leading-relaxed py-0.5 font-mono">
                          {line.text || "\u00A0"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <pre className="text-slate-300 p-2 leading-relaxed whitespace-pre-wrap font-mono">
                  {rawDiff || "Perubahan berkas telah disimpan."}
                </pre>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Render Shell Pill (Terminal command) ──
  if (isShell) {
    const cmd = action.detail || action.actionTitle || "command";

    return (
      <div className="my-2 rounded-xl overflow-hidden border border-white/10 bg-black/60 backdrop-blur-xl font-mono text-xs select-none shadow-xl">
        <button
          onClick={() => setIsExpanded((v) => !v)}
          className="w-full flex items-center justify-between px-3.5 py-2 hover:bg-white/[0.04] transition-colors cursor-pointer text-left"
        >
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-white font-bold text-[11px]">Terminal</span>
            <span className="text-slate-200 truncate font-mono text-[11px]">{cmd}</span>
          </div>
          <svg
            className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 shrink-0 ml-2 ${
              isExpanded ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {isExpanded && (action.summary || action.rawResult) && (
          <div className="border-t border-white/10 p-3 bg-black/80 font-mono text-[11px] text-slate-300 max-h-[220px] overflow-auto custom-scrollbar select-text whitespace-pre-wrap leading-relaxed">
            {action.rawResult || action.summary}
          </div>
        )}
      </div>
    );
  }

  // ── Render Standalone Search / Read ──
  const toolPrefix = isRead ? "Baca" : isSearch ? (tool.includes("glob") ? "Glob" : "Grep") : "Aksi";

  return (
    <div className="my-1.5 font-mono text-xs select-none">
      <div className="flex items-baseline gap-2 py-0.5 text-slate-300">
        <span className="font-bold text-white shrink-0">{toolPrefix}</span>
        <span className="truncate text-white/90 font-mono">{action.detail || action.actionTitle}</span>
        {isStart && <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse ml-1" />}
      </div>
    </div>
  );
}
