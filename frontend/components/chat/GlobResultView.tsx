"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";

// ── GLOB SEARCH RESULT VIEW (Clean Interactive File List) ───────────────
export function GlobResultView({
  pattern,
  files,
  rawResult,
  onOpenFile,
  defaultExpanded = false,
}: {
  pattern?: string;
  files?: string[];
  rawResult?: string;
  onOpenFile?: (filePath: string, fileName?: string) => void;
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

  const fileList = useMemo(() => {
    if (files && files.length > 0) return files;
    if (!rawResult) return [];
    return rawResult.split("\n").map((f) => f.trim()).filter(Boolean);
  }, [files, rawResult]);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const payload = fileList.join("\n");
    navigator.clipboard.writeText(payload).then(() => {
      setCopied(true);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="flex flex-col gap-1 w-full my-0.5 font-mono text-xs select-text">
      {/* 1-Line Clean Scaffold Row (Desktop Reference Parity) */}
      <div className="flex items-center justify-between py-0.5 transition-colors group/globrow opacity-[0.67] hover:opacity-100 transition-opacity duration-150">
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="flex items-center gap-1.5 max-w-fit text-left cursor-pointer group/btn select-none py-0.5"
        >
          <span className="grid size-3.5 shrink-0 place-items-center text-slate-500 group-hover/btn:text-slate-300 text-[11px] font-mono">
            »
          </span>
          <span className="text-slate-400 group-hover/btn:text-slate-200 transition-colors text-[11.5px] font-mono">
            Found {fileList.length} file{fileList.length === 1 ? "" : "s"} {pattern ? <span>matching <span className="font-semibold text-slate-200 group-hover/btn:text-white">&quot;{pattern}&quot;</span></span> : ""}
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
            title="Copy file list"
          >
            {copied ? <span className="text-[10px] text-emerald-400 font-medium">Copied</span> : "Copy"}
          </button>
        </div>
      </div>

      {/* File list (Expanded Surface) */}
      {isExpanded && (
        <div className="rounded-lg border border-white/[0.08] bg-black/60 p-2.5 max-h-[260px] overflow-y-auto overscroll-y-auto custom-scrollbar shadow-[0_4px_16px_rgba(0,0,0,0.4)] animate-fade-in">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
            {fileList.map((filePath, fIdx) => {
              const filename = filePath.split(/[/\\]/).pop() || filePath;
              const lastSlash = Math.max(filePath.lastIndexOf("/"), filePath.lastIndexOf("\\"));
              const dir = lastSlash !== -1 ? filePath.slice(0, lastSlash + 1) : "";
              const ext = filename.includes(".") ? filename.split(".").pop()?.toUpperCase() : "FILE";

              return (
                <div
                  key={fIdx}
                  onClick={() => onOpenFile?.(filePath, filename)}
                  className="flex items-center justify-between gap-1.5 py-1 px-2 rounded hover:bg-white/[0.04] transition-colors cursor-pointer border border-transparent hover:border-white/[0.06] group"
                >
                  <div className="flex items-baseline gap-1.5 min-w-0 truncate">
                    <span className="text-[9px] px-1 py-px rounded bg-white/[0.05] text-slate-400 font-mono shrink-0">
                      {ext}
                    </span>
                    <div className="truncate flex items-baseline gap-0.5">
                      {dir && <span className="text-slate-500 text-[10px] truncate">{dir}</span>}
                      <span className="text-slate-200 font-medium text-[11px] group-hover:text-cyan-300 transition-colors truncate">
                        {filename}
                      </span>
                    </div>
                  </div>

                  {onOpenFile && (
                    <span className="text-slate-500 group-hover:text-cyan-300 text-[10px] shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                      ↗
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
