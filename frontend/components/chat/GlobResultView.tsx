"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";

// ── GLOB SEARCH RESULT VIEW (Clean Interactive File List) ───────────────
export function GlobResultView({
  pattern,
  files,
  rawResult,
  onOpenFile,
}: {
  pattern?: string;
  files?: string[];
  rawResult?: string;
  onOpenFile?: (filePath: string, fileName?: string) => void;
}) {
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
    <div className="flex flex-col gap-1 w-full my-1 font-mono text-[11px] select-text">
      {/* Header bar */}
      <div className="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-t border border-b-0 border-white/[0.08] bg-black/60">
        <div className="flex items-baseline gap-1.5 min-w-0">
          <span className="px-1.5 py-px rounded text-[9.5px] font-bold text-amber-300 bg-amber-500/10 border border-amber-400/20">
            GLOB
          </span>
          {pattern && (
            <span className="text-slate-200 font-semibold truncate text-[11px]">
              &quot;{pattern}&quot;
            </span>
          )}
          <span className="text-slate-400 text-[10.5px] tabular-nums shrink-0 ml-1">
            ({fileList.length} file{fileList.length === 1 ? "" : "s"} found)
          </span>
        </div>

        <button
          type="button"
          onClick={handleCopy}
          className="text-slate-400 hover:text-white p-1 rounded hover:bg-white/[0.05] transition-colors cursor-pointer text-[10.5px]"
          title="Copy file list"
        >
          {copied ? <span className="text-[10px] text-emerald-400 font-medium">Copied</span> : "Copy"}
        </button>
      </div>

      {/* File list */}
      <div className="rounded-b border border-white/[0.08] bg-black/50 p-2 max-h-[260px] overflow-y-auto custom-scrollbar shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
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
    </div>
  );
}
