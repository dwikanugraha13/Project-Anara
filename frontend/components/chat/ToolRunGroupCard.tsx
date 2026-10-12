"use client";

import React, { useState, useMemo } from "react";
import { AgentActionData } from "../hud/types";
import { FILE_EDIT_TOOLS, SHELL_TOOLS, SEARCH_TOOLS, WEB_SEARCH_TOOLS, READ_TOOLS, clampForDisplay } from "./toolCardUtils";
import { TerminalTranscript } from "./TerminalTranscript";
import { ReadFileView } from "./ReadFileView";
import { GrepResultView } from "./GrepResultView";
import { GlobResultView } from "./GlobResultView";
import { AgentActionCard } from "./AgentActionCard";
import { ToolRunTicker } from "./ToolRunTicker";

// ── SEARCH RESULTS STRUCTURED VIEW (Anara Standard) ───────────────────
interface SearchHit {
  title: string;
  url?: string;
  snippet?: string;
}

function parseSearchHits(raw: any): SearchHit[] {
  let data = raw;
  if (typeof raw === "string") {
    try {
      data = JSON.parse(raw);
    } catch {
      const mdLinkRegex = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
      const hits: SearchHit[] = [];
      let match;
      while ((match = mdLinkRegex.exec(raw)) !== null && hits.length < 8) {
        hits.push({ title: match[1], url: match[2] });
      }
      return hits;
    }
  }
  if (!data) return [];
  const list = Array.isArray(data)
    ? data
    : Array.isArray(data.results)
    ? data.results
    : Array.isArray(data.data?.web)
    ? data.data.web
    : Array.isArray(data.organic)
    ? data.organic
    : Array.isArray(data.items)
    ? data.items
    : [];

  return list.slice(0, 8).map((item: any) => ({
    title: item.title || item.name || item.url || "Result",
    url: item.url || item.link || item.href,
    snippet: item.snippet || item.description || item.body || item.content,
  })).filter((h: SearchHit) => h.title || h.url);
}

function SearchResultsView({ rawResult }: { rawResult: any }) {
  const hits = useMemo(() => parseSearchHits(rawResult), [rawResult]);
  if (!hits.length) {
    return (
      <div className="p-2.5 rounded border border-white/[0.06] bg-black/50 text-slate-300 text-[11px] leading-relaxed max-h-[260px] overflow-auto custom-scrollbar font-mono shadow-[0_4px_16px_rgba(0,0,0,0.4)] whitespace-pre-wrap">
        {clampForDisplay(typeof rawResult === "string" ? rawResult : JSON.stringify(rawResult, null, 2))}
      </div>
    );
  }
  return (
    <div className="p-2 rounded-lg border border-white/[0.08] bg-[#050811]/90 shadow-[0_4px_16px_rgba(0,0,0,0.4)] divide-y divide-white/[0.05]">
      {hits.map((hit, idx) => (
        <div key={idx} className="py-2 px-1.5 first:pt-1 last:pb-1 group/hit">
          <div className="flex items-center gap-1.5">
            {hit.url ? (
              <a
                href={hit.url}
                target="_blank"
                rel="noreferrer noopener"
                className="text-xs text-slate-200 hover:text-white font-medium hover:underline flex items-center gap-1 truncate"
              >
                <span className="truncate">{hit.title}</span>
                <span className="text-slate-500 text-[10px] shrink-0 font-sans">↗</span>
              </a>
            ) : (
              <span className="text-xs text-slate-200 font-medium truncate">{hit.title}</span>
            )}
          </div>
          {hit.url && (
            <div className="text-[10px] text-slate-500 font-mono truncate mt-0.5">
              {(() => {
                try {
                  const u = new URL(hit.url);
                  return u.hostname + (u.pathname.length > 1 ? u.pathname : "");
                } catch {
                  return hit.url;
                }
              })()}
            </div>
          )}
          {hit.snippet && (
            <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-relaxed">
              {hit.snippet}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

// ── TECHNICAL TOOL PAYLOAD DISCLOSURE (Anara Standard) ─────────────────
function ToolPayloadDisclosure({ sub }: { sub: AgentActionData }) {
  const [open, setOpen] = useState(false);
  const hasArgs = sub.toolArgs && Object.keys(sub.toolArgs).length > 0;
  if (!hasArgs && !sub.rawResult) return null;

  return (
    <div className="mt-1 font-mono text-[10px]">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className="flex items-center gap-1 text-slate-500 hover:text-slate-300 transition-colors py-0.5 cursor-pointer select-none"
      >
        <span className="text-[9px]">{open ? "▼" : "▶"}</span>
        <span>Tool payload</span>
      </button>
      {open && (
        <div className="mt-1 p-2 rounded border border-white/[0.06] bg-black/60 text-slate-300 max-h-48 overflow-auto custom-scrollbar select-text">
          {hasArgs && (
            <div className="mb-1.5">
              <span className="text-slate-500 uppercase font-bold text-[9px] block mb-0.5">Arguments</span>
              <pre className="text-emerald-300/90 whitespace-pre-wrap">{JSON.stringify(sub.toolArgs, null, 2)}</pre>
            </div>
          )}
          {sub.rawResult && (
            <div>
              <span className="text-slate-500 uppercase font-bold text-[9px] block mb-0.5">Raw Result</span>
              <pre className="text-slate-300 whitespace-pre-wrap">{clampForDisplay(sub.rawResult)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── TOOL RUN GROUP CARD (Anara Desktop Standard) ────────────────────────
export function ToolRunGroupCard({
  items,
  isRunning = false,
  onOpenFile,
}: {
  items: AgentActionData[];
  isRunning?: boolean;
  onOpenFile?: (filePath: string, fileName?: string) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedRowIdx, setExpandedRowIdx] = useState<number | null>(null);
  const [dismissedIndices, setDismissedIndices] = useState<Set<number>>(new Set());

  const activeItems = useMemo(
    () => (items || []).filter((_, idx) => !dismissedIndices.has(idx)),
    [items, dismissedIndices]
  );

  const summary = useMemo(() => {
    let readCount = 0;
    let searchCount = 0;
    let commandCount = 0;
    let editCount = 0;
    let webCount = 0;
    const fileSet = new Set<string>();

    for (const item of activeItems) {
      const tool = (item.toolName || "").toLowerCase();
      const isShell = SHELL_TOOLS.has(tool) || tool.includes("cli") || tool.includes("terminal") || tool.includes("exec");
      const isEdit = FILE_EDIT_TOOLS.has(tool) || tool.includes("write") || tool.includes("edit") || tool.includes("patch");
      const isRead = READ_TOOLS.has(tool) || tool.includes("read") || tool.includes("scan");
      const isWeb = WEB_SEARCH_TOOLS.has(tool) || tool.includes("web") || tool.includes("arxiv");
      const isSearch = SEARCH_TOOLS.has(tool) || tool.includes("grep") || tool.includes("glob");

      if (isShell) {
        commandCount++;
      } else if (isWeb) {
        webCount++;
      } else if (isEdit) {
        editCount++;
        const target = item.filename || item.filePath || item.detail || "";
        if (target) fileSet.add(target);
      } else if (isRead) {
        readCount++;
        const target = item.filename || item.filePath || item.detail || "";
        const cleaned = target.replace(/^(read|scan)\s+/i, "").trim();
        if (cleaned) fileSet.add(cleaned);
      } else if (isSearch) {
        searchCount++;
      }
    }

    // High polish single-tool clauses
    if (activeItems.length === 1) {
      const single = activeItems[0];
      const tool = (single.toolName || "").toLowerCase();
      const isWeb = WEB_SEARCH_TOOLS.has(tool) || tool.includes("web") || tool.includes("arxiv");
      if (isWeb) {
        const q = single.toolArgs?.query || single.query || single.detail?.replace(/^Query:\s*['"]?/i, "").replace(/['"]?$/, "").trim();
        return `${isRunning ? "Searching web for" : "Searched web for"} ${q ? `"${q}"` : "sources"}`;
      }
      if (SHELL_TOOLS.has(tool)) {
        return `${isRunning ? "Running" : "Ran"} ${single.command || single.detail || "command"}`;
      }
      if (tool.includes("read")) {
        const file = single.filename || single.filePath?.split(/[/\\]/).pop() || single.detail || "file";
        return `${isRunning ? "Reading" : "Read"} ${file}`;
      }
      if (tool.includes("grep") || tool.includes("search")) {
        const pat = single.detail?.replace(/^(\/?\s*(Regex|pattern|query)[=:]\s*)/i, "").trim() || "codebase";
        return `${isRunning ? "Searching" : "Searched"} ${pat}`;
      }
      if (tool.includes("glob") || tool.includes("list")) {
        const pat = single.detail?.replace(/^(\/?\s*(pattern|regex|query)[=:]\s*)/i, "").trim();
        return `${isRunning ? "Listing" : "Listed"} ${pat ? pat : "files"}`;
      }
      if (tool.includes("write") || tool.includes("edit")) {
        const file = single.filename || single.filePath?.split(/[/\\]/).pop() || "file";
        return `${isRunning ? "Editing" : "Edited"} ${file}`;
      }
    }

    const uniqueFiles = fileSet.size;
    const clauses: string[] = [];

    if (webCount > 0) {
      clauses.push(`${isRunning ? "Searching" : "Searched"} web (${webCount} ${webCount > 1 ? "queries" : "query"})`);
    }

    if (editCount > 0) {
      clauses.push(`${isRunning ? "Editing" : "Edited"} ${editCount} file${editCount > 1 ? "s" : ""}`);
    }

    if (uniqueFiles > 0) {
      clauses.push(`${isRunning ? "Exploring" : "Explored"} ${uniqueFiles} file${uniqueFiles > 1 ? "s" : ""}`);
    } else if (readCount > 0 || searchCount > 0) {
      const totalOps = readCount + searchCount;
      clauses.push(`${isRunning ? "Exploring" : "Explored"} ${totalOps} file${totalOps > 1 ? "s" : ""}`);
    }

    if (commandCount > 0) {
      clauses.push(`${isRunning ? "running" : "ran"} ${commandCount} command${commandCount > 1 ? "s" : ""}`);
    }

    if (clauses.length === 0) {
      clauses.push(`${isRunning ? "Running" : "Executed"} ${activeItems.length} tool${activeItems.length > 1 ? "s" : ""}`);
    }

    return clauses.join(", ");
  }, [activeItems, isRunning]);

  if (!items || items.length === 0 || activeItems.length === 0) return null;

  return (
    <div className="my-1 font-mono text-xs select-none">
      {/* Group Header Button */}
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-left text-slate-400 hover:text-slate-200 transition-colors cursor-pointer py-0.5 max-w-fit group select-none opacity-[0.67] hover:opacity-100 transition-opacity duration-150"
      >
        <span className="grid size-3.5 shrink-0 place-items-center text-slate-500 font-mono text-[11px] select-none">
          {isRunning ? (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
            </span>
          ) : (
            <span className="text-slate-500 font-mono text-[11px] leading-none">»</span>
          )}
        </span>
        <span className={`text-[11.5px] font-mono tracking-tight ${isRunning ? "shimmer font-medium" : "text-slate-400 group-hover:text-slate-200"}`}>
          {summary}
        </span>
        <svg
          className={`w-3 h-3 text-slate-500 opacity-0 group-hover:opacity-80 transition-all duration-150 shrink-0 ml-0.5 ${
            isExpanded ? "rotate-90 opacity-80" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>

      {/* Live Reel Activity Ticker while running and collapsed */}
      {isRunning && !isExpanded && activeItems.length > 0 && (
        <div className="pl-4 my-0.5">
          <ToolRunTicker isRunning inline>
            {activeItems.map((item, idx) => (
              <span key={idx}>
                {item.command || item.filename || item.filePath || item.detail || "Executing action..."}
              </span>
            ))}
          </ToolRunTicker>
        </div>
      )}

      {/* Expanded List of Tool Rows */}
      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${
          isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div className="pl-3.5 py-1 space-y-1.5 border-l border-white/[0.08] my-1 font-mono text-[11px]">
            {activeItems.map((sub, sIdx) => {
              const tool = (sub.toolName || "").toLowerCase();
              const isShell = SHELL_TOOLS.has(tool) || tool.includes("cli") || tool.includes("terminal") || tool.includes("exec");
              const isRead = READ_TOOLS.has(tool) || tool.includes("read") || tool.includes("scan");
              const isGrep = tool.includes("grep");
              const isGlob = tool.includes("glob");
              const isWrite = FILE_EDIT_TOOLS.has(tool) || tool.includes("write") || tool.includes("edit") || tool.includes("patch");
              const isWeb = WEB_SEARCH_TOOLS.has(tool) || tool.includes("web") || tool.includes("arxiv");

              const rawTarget = sub.command || sub.filePath || sub.detail || sub.actionTitle || "";
              const cmdText = sub.command || sub.detail || sub.actionTitle || "command";
              const exitCode = sub.exitCode;
              const duration = sub.durationText;

              const isRowExpanded = expandedRowIdx === sIdx;

              // Shell tool row
              if (isShell) {
                return (
                  <div key={sIdx} className="flex flex-col group/row">
                    <div className="flex items-center gap-1.5 py-0.5 px-1 rounded transition-colors text-slate-400 opacity-[0.67] hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => setExpandedRowIdx(isRowExpanded ? null : sIdx)}
                        className="flex items-center gap-1.5 max-w-fit text-left text-slate-400 hover:text-slate-200 font-mono text-[11px] cursor-pointer group/btn"
                      >
                        <span className="grid size-3.5 shrink-0 place-items-center text-slate-500 group-hover/btn:text-slate-300">
                          »
                        </span>
                        <span className="truncate">Ran {cmdText}</span>
                        <svg
                          className={`w-3 h-3 text-slate-500 opacity-0 group-hover/btn:opacity-80 transition-all duration-150 shrink-0 ml-0.5 ${
                            isRowExpanded ? "rotate-90 opacity-80" : ""
                          }`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>

                      {duration && (
                        <span className="text-[10px] text-slate-500 font-mono tabular-nums shrink-0 ml-auto">
                          {duration}
                        </span>
                      )}

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDismissedIndices((prev) => new Set([...prev, sIdx]));
                        }}
                        className="text-slate-600 hover:text-slate-300 p-0.5 rounded opacity-0 group-hover/row:opacity-100 transition-opacity shrink-0 ml-1"
                        title="Dismiss"
                      >
                        ✕
                      </button>
                    </div>

                    {isRowExpanded && (
                      <div className="pl-5 pr-1 py-1">
                        <TerminalTranscript
                          command={cmdText}
                          exitCode={exitCode ?? 0}
                          rawResult={sub.rawResult || sub.summary}
                          durationText={duration}
                        />
                      </div>
                    )}
                  </div>
                );
              }

              // File exploration or Web Search item
              const cleanTarget = rawTarget
                .replace(/^(read|scan|grep|glob|list|query)\s*[:=]?\s*/i, "")
                .replace(/^(\/?\s*(pattern|regex|query)[=:]\s*)/i, "")
                .trim();
              const lastSlash = Math.max(cleanTarget.lastIndexOf("/"), cleanTarget.lastIndexOf("\\"));
              const dir = !isWeb && lastSlash !== -1 ? cleanTarget.slice(0, lastSlash + 1) : "";
              
              const searchQuery = sub.toolArgs?.query || sub.query || (sub.detail?.startsWith("Query:") ? sub.detail.replace(/^Query:\s*['"]?/i, "").replace(/['"]?$/, "").trim() : "") || cleanTarget;
              const file = isWeb
                ? (searchQuery ? `"${searchQuery}"` : "web")
                : (sub.filename || (lastSlash !== -1 ? cleanTarget.slice(lastSlash + 1) : (cleanTarget && cleanTarget !== "Done" ? cleanTarget : sub.toolName)));
              const opVerb = isWeb ? "Searched" : isRead ? "Read" : isGrep ? "Searched" : isGlob ? "Found" : isWrite ? "Edited" : "Explored";

              return (
                <div key={sIdx} className="flex flex-col group/row">
                  <div className="flex items-center gap-1.5 py-0.5 px-1 rounded transition-colors text-slate-400 opacity-[0.67] hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      onClick={() => setExpandedRowIdx(isRowExpanded ? null : sIdx)}
                      className="flex items-center gap-1.5 max-w-fit text-left text-slate-400 hover:text-slate-200 font-mono text-[11px] cursor-pointer group/btn"
                    >
                      <span className="grid size-3.5 shrink-0 place-items-center text-slate-500 group-hover/btn:text-slate-300">
                        {isWeb ? (
                          <svg className="w-3 h-3 text-sky-400/80" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" /></svg>
                        ) : isRead ? (
                          <svg className="w-3 h-3 text-cyan-400/70" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                        ) : isGrep || isGlob ? (
                          <svg className="w-3 h-3 text-purple-400/70" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                        ) : isWrite ? (
                          <svg className="w-3 h-3 text-amber-400/70" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                        ) : (
                          <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" /></svg>
                        )}
                      </span>
                      <span>{opVerb}</span>
                      <span className="font-semibold text-slate-200 group-hover/btn:text-white truncate">
                        {file}
                      </span>
                      {dir && <span className="text-slate-500 text-[10px] truncate hidden sm:inline">{dir}</span>}
                      <svg
                        className={`w-3 h-3 text-slate-500 opacity-0 group-hover/btn:opacity-80 transition-all duration-150 shrink-0 ml-0.5 ${
                          isRowExpanded ? "rotate-90 opacity-80" : ""
                        }`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>

                    {onOpenFile && isRead && (
                      <span
                        onClick={(e) => {
                          e.stopPropagation();
                          cleanTarget && onOpenFile(cleanTarget, file);
                        }}
                        className="text-slate-500 hover:text-white text-[10px] shrink-0 opacity-0 group-hover/row:opacity-100 transition-opacity ml-1 cursor-pointer"
                        title="Open in Code Editor"
                      >
                        ↗
                      </span>
                    )}

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDismissedIndices((prev) => new Set([...prev, sIdx]));
                      }}
                      className="text-slate-600 hover:text-slate-300 p-0.5 rounded opacity-0 group-hover/row:opacity-100 transition-opacity shrink-0 ml-1"
                      title="Dismiss"
                    >
                      ✕
                    </button>
                  </div>

                  {/* Inline Dedicated Rich Viewers */}
                  {isRowExpanded && (
                    <div className="pl-4 pr-1 py-1">
                      {isWeb ? (
                        <SearchResultsView rawResult={sub.rawResult || sub.summary || sub.detail} />
                      ) : isRead ? (
                        <ReadFileView
                          filePath={sub.filePath || cleanTarget || file || ""}
                          content={sub.content || sub.rawResult || sub.summary || ""}
                          onOpenFile={onOpenFile}
                        />
                      ) : isGrep ? (
                        <GrepResultView
                          pattern={sub.detail?.replace(/^(Regex|pattern)[=:]\s*/i, "").trim() || ""}
                          rawResult={sub.rawResult || sub.summary}
                          onOpenFile={onOpenFile}
                        />
                      ) : isGlob ? (
                        <GlobResultView
                          pattern={sub.detail?.replace(/^pattern[=:]\s*/i, "").trim() || "*"}
                          rawResult={sub.rawResult || sub.summary}
                          onOpenFile={onOpenFile}
                        />
                      ) : isWrite ? (
                        <AgentActionCard
                          action={sub}
                          onOpenFile={onOpenFile}
                        />
                      ) : (
                        <pre className="p-2.5 rounded border border-white/[0.06] bg-black/50 text-slate-300 text-[10.5px] leading-relaxed max-h-[220px] overflow-x-auto overflow-y-auto custom-scrollbar whitespace-pre font-mono shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
                          {clampForDisplay((sub.rawResult && sub.rawResult !== "Done") ? sub.rawResult : (sub.content || (sub.summary && sub.summary !== "Done" ? sub.summary : sub.detail || "Completed")))}
                        </pre>
                      )}
                      <ToolPayloadDisclosure sub={sub} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// Backward-compatibility export
export const ExplorationGroupCard = ToolRunGroupCard;
