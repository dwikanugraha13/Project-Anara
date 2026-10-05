"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import { clampForDisplay } from "./toolCardUtils";

// ── GREP SEARCH RESULT VIEW (Grouped by File & Clean Hit Badges) ─────────
export function GrepResultView({
  pattern,
  matches,
  rawResult,
  onOpenFile,
  defaultExpanded = false,
}: {
  pattern?: string;
  matches?: Array<{ file: string; line_number: number; line: string }>;
  rawResult?: string;
  onOpenFile?: (filePath: string, fileName?: string, lineNumber?: number) => void;
  defaultExpanded?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    };
  }, []);

  const parsedMatches = useMemo(() => {
    if (matches && matches.length > 0) return matches;
    if (!rawResult) return [];
    const results: Array<{ file: string; line_number: number; line: string }> = [];
    const rawLines = rawResult.split("\n");
    for (const r of rawLines) {
      const match = /^([^:\n]+):(\d+):(.*)$/.exec(r);
      if (match) {
        results.push({
          file: match[1].trim(),
          line_number: parseInt(match[2], 10),
          line: match[3],
        });
      }
    }
    return results;
  }, [matches, rawResult]);

  // Group matches by file
  const groupedByFile = useMemo(() => {
    const map = new Map<string, Array<{ line_number: number; line: string }>>();
    for (const m of parsedMatches) {
      if (!map.has(m.file)) map.set(m.file, []);
      map.get(m.file)!.push({ line_number: m.line_number, line: m.line });
    }
    return Array.from(map.entries()).map(([file, hits]) => ({ file, hits }));
  }, [parsedMatches]);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const payload = rawResult || parsedMatches.map((m) => `${m.file}:${m.line_number}: ${m.line}`).join("\n");
    navigator.clipboard.writeText(payload).then(() => {
      setCopied(true);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    });
  };

  const totalHits = parsedMatches.length;

  return (
    <div className="flex flex-col gap-1 w-full my-0.5 font-mono text-xs select-text">
      {/* 1-Line Clean Scaffold Row (Desktop Reference Parity) */}
      <div className="flex items-center justify-between py-0.5 transition-colors group/greprow opacity-[0.67] hover:opacity-100 transition-opacity duration-150">
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="flex items-center gap-1.5 max-w-fit text-left cursor-pointer group/btn select-none py-0.5"
        >
          <span className="grid size-3.5 shrink-0 place-items-center text-slate-400">
            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </span>
          <span className="text-slate-400 group-hover/btn:text-slate-200 transition-colors text-[11.5px] font-mono">
            Searched {pattern ? <span className="font-semibold text-slate-200 group-hover/btn:text-white">&quot;{pattern}&quot;</span> : "codebase"}
          </span>
          <span className="text-slate-500 text-[10px] tabular-nums shrink-0 ml-0.5">
            ({totalHits} match{totalHits === 1 ? "" : "es"} across {groupedByFile.length} file{groupedByFile.length === 1 ? "" : "s"})
          </span>

          {/* Affordance Caret on Right (Hover Only) */}
          <svg
            className={`w-3 h-3 text-slate-500 opacity-0 group-hover/btn:opacity-80 transition-all duration-150 shrink-0 ml-0.5 ${
              isExpanded ? "rotate-90 opacity-80" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        <div className="flex items-center gap-1.5 shrink-0 ml-auto select-none">
          <button
            type="button"
            onClick={handleCopy}
            className="text-slate-500 hover:text-slate-300 p-0.5 rounded hover:bg-white/[0.05] transition-colors cursor-pointer text-[10px]"
            title="Copy results"
          >
            {copied ? <span className="text-[10px] text-emerald-400 font-medium">Copied</span> : "Copy"}
          </button>
        </div>
      </div>

      {/* Grouped results body (Expanded Surface) */}
      {isExpanded && (
        <div className="rounded-lg border border-white/[0.08] bg-black/60 p-2.5 max-h-[300px] overflow-x-auto overflow-y-auto overscroll-x-contain overscroll-y-auto custom-scrollbar shadow-[0_4px_16px_rgba(0,0,0,0.4)] space-y-2 animate-fade-in">
          {groupedByFile.length > 0 ? (
            groupedByFile.map(({ file, hits }, fIdx) => {
              const filename = file.split(/[/\\]/).pop() || file;
              const lastSlash = Math.max(file.lastIndexOf("/"), file.lastIndexOf("\\"));
              const dir = lastSlash !== -1 ? file.slice(0, lastSlash + 1) : "";

              return (
                <div key={fIdx} className="border-t border-white/[0.06] first:border-t-0 pt-1.5 first:pt-0">
                  <div className="flex items-center justify-between pb-1">
                    <div
                      onClick={() => onOpenFile?.(file, filename)}
                      className="flex items-baseline gap-1 truncate cursor-pointer group/title"
                    >
                      {dir && <span className="text-slate-500 text-[10px] truncate">{dir}</span>}
                      <span className="text-slate-200 font-medium text-[11px] group-hover/title:text-white transition-colors truncate">
                        {filename}
                      </span>
                      <span className="text-slate-500 text-[9.5px]">({hits.length})</span>
                    </div>

                    {onOpenFile && (
                      <button
                        type="button"
                        onClick={() => onOpenFile(file, filename)}
                        className="text-slate-500 hover:text-white text-[10px] ml-2 shrink-0 cursor-pointer"
                        title="Open file"
                      >
                        ↗
                      </button>
                    )}
                  </div>

                  <div className="space-y-0.5">
                  {hits.map((h, hIdx) => {
                    const lineText = h.line;
                    return (
                      <div
                        key={hIdx}
                        onClick={() => onOpenFile?.(file, filename, h.line_number)}
                        className="flex items-baseline gap-2 py-0.5 px-1 rounded hover:bg-white/[0.04] cursor-pointer group/hit transition-colors"
                      >
                        <span className="px-1 py-px rounded text-[9px] font-mono text-slate-400 bg-white/[0.04] border border-white/[0.08] shrink-0 tabular-nums select-none group-hover/hit:text-slate-200 transition-colors">
                          L{h.line_number}
                        </span>
                        <span className="whitespace-pre font-mono text-[10.5px] text-slate-300 group-hover/hit:text-slate-100 transition-colors truncate">
                          {pattern && lineText.toLowerCase().includes(pattern.toLowerCase()) ? (
                            (() => {
                              const regex = new RegExp(`(${pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
                              const parts = lineText.split(regex);
                              return parts.map((part, pIdx) =>
                                regex.test(part) ? (
                                  <mark key={pIdx} className="bg-white/[0.12] text-white px-0.5 rounded font-semibold">
                                    {part}
                                  </mark>
                                ) : (
                                  part
                                )
                              );
                            })()
                          ) : (
                            lineText
                          )}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })
        ) : (
          <pre className="text-slate-300 text-[10.5px] leading-relaxed whitespace-pre font-mono">
            {clampForDisplay(rawResult || "No matches found.")}
          </pre>
        )}
      </div>
    )}
  </div>
);
}
