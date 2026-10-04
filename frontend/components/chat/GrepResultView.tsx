"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import { clampForDisplay } from "./toolCardUtils";

// ── GREP SEARCH RESULT VIEW (Grouped by File & Clean Hit Badges) ─────────
export function GrepResultView({
  pattern,
  matches,
  rawResult,
  onOpenFile,
}: {
  pattern?: string;
  matches?: Array<{ file: string; line_number: number; line: string }>;
  rawResult?: string;
  onOpenFile?: (filePath: string, fileName?: string, lineNumber?: number) => void;
}) {
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
    <div className="flex flex-col gap-1 w-full my-1 font-mono text-[11px] select-text">
      {/* Header bar */}
      <div className="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-t border border-b-0 border-white/[0.08] bg-black/60">
        <div className="flex items-baseline gap-1.5 min-w-0">
          <span className="px-1.5 py-px rounded text-[9.5px] font-bold text-purple-300 bg-purple-500/10 border border-purple-400/20">
            GREP
          </span>
          {pattern && (
            <span className="text-slate-200 font-semibold truncate text-[11px]">
              &quot;{pattern}&quot;
            </span>
          )}
          <span className="text-slate-400 text-[10.5px] tabular-nums shrink-0 ml-1">
            ({totalHits} match{totalHits === 1 ? "" : "es"} across {groupedByFile.length} file{groupedByFile.length === 1 ? "" : "s"})
          </span>
        </div>

        <button
          type="button"
          onClick={handleCopy}
          className="text-slate-400 hover:text-white p-1 rounded hover:bg-white/[0.05] transition-colors cursor-pointer text-[10.5px]"
          title="Copy results"
        >
          {copied ? <span className="text-[10px] text-emerald-400 font-medium">Copied</span> : "Copy"}
        </button>
      </div>

      {/* Grouped results body */}
      <div className="rounded-b border border-white/[0.08] bg-black/50 p-2 max-h-[300px] overflow-x-auto overflow-y-auto custom-scrollbar shadow-[0_4px_16px_rgba(0,0,0,0.4)] space-y-2">
        {groupedByFile.length > 0 ? (
          groupedByFile.map(({ file, hits }, fIdx) => {
            const filename = file.split(/[/\\]/).pop() || file;
            const lastSlash = Math.max(file.lastIndexOf("/"), file.lastIndexOf("\\"));
            const dir = lastSlash !== -1 ? file.slice(0, lastSlash + 1) : "";

            return (
              <div key={fIdx} className="rounded border border-white/[0.04] bg-white/[0.015] p-2">
                <div className="flex items-center justify-between pb-1 mb-1 border-b border-white/[0.04]">
                  <div
                    onClick={() => onOpenFile?.(file, filename)}
                    className="flex items-baseline gap-1 truncate cursor-pointer group/title"
                  >
                    {dir && <span className="text-slate-500 text-[10px] truncate">{dir}</span>}
                    <span className="text-slate-200 font-medium text-[11px] group-hover/title:text-cyan-300 transition-colors truncate">
                      {filename}
                    </span>
                    <span className="text-slate-500 text-[9.5px]">({hits.length})</span>
                  </div>

                  {onOpenFile && (
                    <button
                      type="button"
                      onClick={() => onOpenFile(file, filename)}
                      className="text-slate-500 hover:text-cyan-300 text-[10px] ml-2 shrink-0 cursor-pointer"
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
                        <span className="px-1 py-px rounded text-[9px] font-mono text-purple-300 bg-purple-500/10 border border-purple-400/20 shrink-0 tabular-nums select-none group-hover/hit:bg-purple-500/20 group-hover/hit:border-purple-400/40 transition-colors">
                          L{h.line_number}
                        </span>
                        <span className="whitespace-pre font-mono text-[10.5px] text-slate-300 group-hover/hit:text-slate-100 transition-colors truncate">
                          {pattern && lineText.toLowerCase().includes(pattern.toLowerCase()) ? (
                            (() => {
                              const regex = new RegExp(`(${pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
                              const parts = lineText.split(regex);
                              return parts.map((part, pIdx) =>
                                regex.test(part) ? (
                                  <mark key={pIdx} className="bg-purple-500/30 text-purple-200 px-0.5 rounded font-bold">
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
    </div>
  );
}
