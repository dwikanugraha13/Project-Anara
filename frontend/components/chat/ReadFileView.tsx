"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";

// ── READ FILE VIEW (Gutter Line Numbers & Code Surface) ──────────────────
export function ReadFileView({
  filePath,
  content,
  onOpenFile,
}: {
  filePath: string;
  content: string;
  onOpenFile?: (filePath: string, fileName?: string) => void;
}) {
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
    <div className="flex flex-col gap-1 w-full my-1 font-mono text-[11px] select-text">
      <div className="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-t border border-b-0 border-white/[0.08] bg-black/60">
        <div className="flex items-baseline gap-1.5 min-w-0">
          <span className="px-1.5 py-px rounded text-[9.5px] font-bold text-cyan-300 bg-cyan-500/10 border border-cyan-400/20">
            READ
          </span>
          <span className="text-slate-200 font-semibold truncate text-[11.5px]">{filename}</span>
          {dirPath && <span className="text-slate-500 text-[10px] truncate">{dirPath}</span>}
          <span className="text-slate-500 text-[10px] tabular-nums shrink-0 ml-1">
            ({lines.length} lines)
          </span>
        </div>

        <div className="flex items-center gap-1.5 shrink-0 ml-auto">
          {onOpenFile && (
            <button
              type="button"
              onClick={() => onOpenFile(filePath, filename)}
              className="text-cyan-300 hover:text-white px-2 py-0.5 rounded text-[10.5px] bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/25 transition-all cursor-pointer"
              title="Open file in IDE"
            >
              View in Editor ↗
            </button>
          )}
          <button
            type="button"
            onClick={handleCopy}
            className="text-slate-400 hover:text-white p-1 rounded hover:bg-white/[0.05] transition-colors cursor-pointer text-[10.5px]"
            title="Copy content"
          >
            {copied ? <span className="text-[10px] text-emerald-400 font-medium">Copied</span> : "Copy"}
          </button>
        </div>
      </div>

      <div className="rounded-b border border-white/[0.08] bg-black/50 max-h-[300px] overflow-x-auto overflow-y-auto custom-scrollbar shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
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
    </div>
  );
}
