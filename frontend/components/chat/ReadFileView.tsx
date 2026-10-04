"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";

// ── READ FILE VIEW (Gutter Line Numbers & Code Surface) ──────────────────
export function ReadFileView({
  filePath,
  content,
  onOpenFile,
  defaultExpanded = false,
}: {
  filePath: string;
  content: string;
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

  const filename = filePath.split(/[/\\]/).pop() || filePath;
  const lastSlash = Math.max(filePath.lastIndexOf("/"), filePath.lastIndexOf("\\"));
  const dirPath = lastSlash !== -1 ? filePath.slice(0, lastSlash + 1) : "";

  // Parse lines: handle pre-numbered output "1: import..." or raw code
  const lines = useMemo(() => {
    if (!content) return [];
    const rawLines = content.split("\n");
    return rawLines.map((line, idx) => {
      const match = /^(\d+)[:|]\s*(.*)$/.exec(line);
      if (match) {
        return { lineNo: parseInt(match[1], 10), text: match[2] };
      }
      return { lineNo: idx + 1, text: line };
    });
  }, [content]);

  // Compute line range label (e.g. L1-45 or L12)
  const lineRangeLabel = useMemo(() => {
    if (lines.length === 0) return "";
    const start = lines[0].lineNo;
    const end = lines[lines.length - 1].lineNo;
    return start === end ? `L${start}` : `L${start}-${end}`;
  }, [lines]);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const cleanCode = lines.map((l) => l.text).join("\n");
    navigator.clipboard.writeText(cleanCode).then(() => {
      setCopied(true);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="flex flex-col gap-1 w-full my-0.5 font-mono text-xs select-text">
      {/* 1-Line Clean Scaffold Row (Desktop Reference Parity) */}
      <div className="flex items-center justify-between py-0.5 transition-colors group/readrow opacity-[0.67] hover:opacity-100 transition-opacity duration-150">
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="flex items-center gap-1.5 max-w-fit text-left cursor-pointer group/btn select-none py-0.5"
        >
          <span className="grid size-3.5 shrink-0 place-items-center text-slate-500 group-hover/btn:text-slate-300 text-[11px] font-mono">
            »
          </span>
          <span className="text-slate-400 group-hover/btn:text-slate-200 transition-colors text-[11.5px] font-mono">
            Read <span className="font-semibold text-slate-200 group-hover/btn:text-white">{filename}</span>
          </span>
          {lineRangeLabel && (
            <span className="text-[10px] text-slate-500 font-mono tabular-nums shrink-0">
              {lineRangeLabel}
            </span>
          )}
          {dirPath && <span className="text-slate-500 text-[10px] truncate hidden sm:inline">{dirPath}</span>}
          <span className="text-slate-500 text-[10px] tabular-nums shrink-0">
            ({lines.length} lines)
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
          {onOpenFile && (
            <button
              type="button"
              onClick={() => onOpenFile(filePath, filename)}
              className="text-slate-400 hover:text-white px-1 py-0.5 rounded text-[10.5px] transition-colors cursor-pointer"
              title="Open file in IDE"
            >
              ↗
            </button>
          )}
          <button
            type="button"
            onClick={handleCopy}
            className="text-slate-500 hover:text-slate-300 p-0.5 rounded hover:bg-white/[0.05] transition-colors cursor-pointer text-[10px]"
            title="Copy content"
          >
            {copied ? <span className="text-[10px] text-emerald-400 font-medium">Copied</span> : "Copy"}
          </button>
        </div>
      </div>

      {/* Expanded Table Gutter Surface */}
      {isExpanded && (
        <div className="rounded-lg border border-white/[0.08] bg-black/60 max-h-[300px] overflow-x-auto overflow-y-auto overscroll-x-contain overscroll-y-auto custom-scrollbar shadow-[0_4px_16px_rgba(0,0,0,0.4)] animate-fade-in">
          <table className="w-full border-collapse">
            <tbody>
              {lines.map((l, idx) => (
                <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                  <td className="w-10 pr-2 text-right select-none text-slate-600 font-mono text-[10px] py-0.5 border-r border-white/[0.06] tabular-nums">
                    {l.lineNo}
                  </td>
                  <td className="pl-3 pr-3 py-0.5 whitespace-pre font-mono leading-relaxed text-[11px] text-slate-200 min-h-[1.25rem]">
                    {l.text || " "}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
