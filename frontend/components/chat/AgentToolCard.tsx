"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import { AgentActionData, TodoData } from "../hud/types";
import { anaraApi } from "@/lib/apiClient";

export interface AgentToolCardProps {
  action?: AgentActionData;
  todoData?: TodoData;
  sessionId?: number;
  onOpenFile?: (filePath: string, fileName?: string) => void;
  onDismiss?: () => void;
}

// ── CANONICAL TOOL TAXONOMY ─────────────────────────────────────────────────
export const MAX_TOOL_RENDER_CHARS = 25_000;

export function clampForDisplay(value?: string, max = MAX_TOOL_RENDER_CHARS): string {
  if (!value) return "";
  if (value.length <= max) return value;
  const omitted = value.length - max;
  return `${value.slice(0, max)}\n\n… [${omitted.toLocaleString()} characters truncated for render performance — use Copy button for complete output]`;
}

/**
 * Strips ECMA-48 / ANSI escape sequences and carriage return noise from CLI output.
 */
export function stripAnsi(text: string): string {
  if (!text) return "";
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\x1B(?:\[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g, "")
    .replace(/\u001b\[[0-9;]*[a-zA-Z]/g, "");
}

interface AnsiSpan {
  text: string;
  className?: string;
}

/**
 * Converts terminal ANSI color codes into styled React spans.
 */
export function parseAnsiToTokens(raw: string): AnsiSpan[] {
  if (!raw) return [];
  const clean = raw.replace(/\r\n/g, "\n");
  const regex = /\x1B\[([0-9;]*)m/g;
  const spans: AnsiSpan[] = [];
  let lastIndex = 0;
  let currentClass = "";

  let match: RegExpExecArray | null;
  while ((match = regex.exec(clean)) !== null) {
    if (match.index > lastIndex) {
      spans.push({
        text: clean.slice(lastIndex, match.index),
        className: currentClass,
      });
    }
    const codes = match[1].split(";").map(Number);
    for (const code of codes) {
      if (code === 0) currentClass = "";
      else if (code === 1) currentClass += " font-bold";
      else if (code === 2) currentClass += " opacity-70";
      else if (code === 31 || code === 91) currentClass = "text-rose-400";
      else if (code === 32 || code === 92) currentClass = "text-emerald-400";
      else if (code === 33 || code === 93) currentClass = "text-amber-300";
      else if (code === 34 || code === 94) currentClass = "text-sky-400";
      else if (code === 35 || code === 95) currentClass = "text-purple-400";
      else if (code === 36 || code === 96) currentClass = "text-cyan-400";
      else if (code === 37 || code === 97) currentClass = "text-slate-100";
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < clean.length) {
    spans.push({
      text: clean.slice(lastIndex),
      className: currentClass,
    });
  }
  return spans.length > 0 ? spans : [{ text: clean }];
}

/**
 * Strips git preamble headers up to the first unified hunk or real content.
 */
export function stripDiffFileHeaders(diff: string): string {
  if (!diff) return "";
  const lines = diff.split("\n");
  let start = 0;
  const noisePrefixes = [
    "diff --git",
    "index ",
    "--- a/",
    "+++ b/",
    "--- /dev/null",
    "+++ /dev/null",
    "similarity index",
    "rename from",
    "rename to",
    "new file mode",
    "deleted file mode",
  ];

  for (; start < lines.length; start++) {
    const line = lines[start].trim();
    if (line.startsWith("@@")) break;
    const isNoise = noisePrefixes.some((p) => line.startsWith(p));
    if (!isNoise && line.length > 0 && !line.startsWith("---") && !line.startsWith("+++")) break;
  }

  return lines.slice(start).join("\n");
}

export const FILE_EDIT_TOOLS = new Set([
  "patch",
  "write_file",
  "write_local_file",
  "edit_file",
  "write",
  "edit",
  "artifact",
]);
export const SHELL_TOOLS = new Set([
  "terminal",
  "execute_cli_command",
  "execute_code",
  "bash",
  "shell",
  "command",
  "cli",
  "powershell",
]);
export const SEARCH_TOOLS = new Set([
  "search_files",
  "grep_search_code",
  "grep",
  "glob_find_files",
  "glob",
  "web_search",
  "search",
]);
export const READ_TOOLS = new Set([
  "read_file",
  "read_local_file",
  "read",
  "scan",
  "list_files",
  "list_directory",
  "scan_workspace_folder",
  "list",
]);

// ── 1. THINKING CARD (Liquid Glass Reasoning Stream) ────────────────────────
export function ThinkingCard({
  text,
  durationSec,
  isLive = false,
}: {
  text: string;
  durationSec?: number;
  isLive?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(isLive);
  const [liveElapsed, setLiveElapsed] = useState<number>(0);
  const liveStartTimeRef = useRef<number>(Date.now());

  useEffect(() => {
    if (isLive) {
      setIsExpanded(true);
    }
  }, [isLive]);

  useEffect(() => {
    if (!isLive) return;
    liveStartTimeRef.current = Date.now();
    const interval = setInterval(() => {
      setLiveElapsed(Math.round((Date.now() - liveStartTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [isLive]);

  if (!text || text.trim().length === 0) return null;

  let thoughtLabel = "Thinking";
  if (!isLive) {
    if (durationSec === undefined || durationSec === null || durationSec <= 0) {
      thoughtLabel = "Thought";
    } else if (durationSec < 1) {
      thoughtLabel = "Thought briefly";
    } else {
      thoughtLabel = `Thought for ${durationSec.toFixed(1)}s`;
    }
  }

  return (
    <div className="group/scaffold relative flex flex-col w-full my-1.5 select-none font-mono">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 text-slate-400 hover:text-slate-200 focus-visible:outline-none transition-colors cursor-pointer group py-0.5"
          aria-expanded={isExpanded}
        >
          <span className="relative flex h-2 w-2 shrink-0">
            {isLive ? (
              <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
              </>
            ) : (
              <span className="h-1.5 w-1.5 rounded-full bg-slate-500 group-hover:bg-cyan-400 transition-colors" />
            )}
          </span>

          <span className={`text-[11.5px] tracking-tight ${isLive ? "text-cyan-300 animate-pulse font-medium" : "text-slate-400 group-hover:text-slate-200"}`}>
            {thoughtLabel}
          </span>

          <svg
            className={`w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ${
              isExpanded ? "rotate-90" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {isLive && liveElapsed > 0 && (
          <span className="text-[10.5px] font-mono tabular-nums text-slate-500">
            {liveElapsed.toFixed(1)}s
          </span>
        )}
      </div>

      {isExpanded && (
        <div className="mt-1.5 w-full min-w-0 max-w-full overflow-y-auto max-h-56 border-l border-white/10 pl-3 py-1 text-slate-400 font-sans text-xs leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere] break-words select-text custom-scrollbar animate-fade-in">
          {text}
        </div>
      )}
    </div>
  );
}

// ── 2. TERMINAL TRANSCRIPT (Anara Desktop Standard) ────────────────────────
export function TerminalTranscript({
  command,
  exitCode,
  rawResult,
  stdout,
  stderr,
  durationText,
}: {
  command?: string;
  exitCode?: number;
  rawResult?: string;
  stdout?: string;
  stderr?: string;
  durationText?: string;
}) {
  const [copied, setCopied] = useState(false);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    };
  }, []);

  if (!command && exitCode === undefined && !rawResult && !stdout && !stderr) return null;

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const payload = stdout || stderr || rawResult || command || "";
    if (!payload) return;
    navigator.clipboard.writeText(stripAnsi(payload)).then(() => {
      setCopied(true);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    });
  };

  const outputPayload = rawResult || stdout || "";
  const hasSplitStreams = Boolean(stdout || stderr);

  return (
    <div className="flex flex-col gap-1.5 w-full my-1 font-mono text-[11px] select-text">
      {/* Command prompt bar */}
      {(command || exitCode !== undefined) && (
        <div className="flex min-w-0 items-center justify-between gap-2 rounded border border-white/[0.08] bg-black/60 px-2.5 py-1.5 leading-relaxed backdrop-blur-md">
          {command && (
            <div className="min-w-0 flex-1 overflow-x-auto custom-scrollbar whitespace-pre font-mono text-slate-200">
              <span className="text-cyan-400 select-none font-bold mr-1">$</span>
              {command}
            </div>
          )}
          <div className="flex items-center gap-2 shrink-0 ml-auto select-none">
            {durationText && (
              <span className="text-[10px] text-slate-500 font-mono tabular-nums">
                {durationText}
              </span>
            )}
            {exitCode !== undefined && (
              <span
                className={`shrink-0 rounded px-1.5 py-px text-[10px] font-bold tabular-nums border ${
                  exitCode === 0
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                }`}
              >
                exit {exitCode}
              </span>
            )}
            <button
              type="button"
              onClick={handleCopy}
              className="text-slate-500 hover:text-slate-300 p-1 rounded hover:bg-white/[0.05] transition-colors cursor-pointer"
              title="Copy output"
            >
              {copied ? (
                <span className="text-[10px] text-emerald-400 font-medium">Copied</span>
              ) : (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Terminal Output Surface */}
      {hasSplitStreams ? (
        <div className="flex flex-col gap-1">
          {stdout && (
            <div className="relative">
              {stderr && <div className="text-[9.5px] uppercase tracking-wider text-slate-500 mb-0.5 font-bold">stdout</div>}
              <div className="p-2.5 rounded border border-white/[0.06] bg-black/50 text-slate-300 text-[10.5px] leading-relaxed max-h-[260px] overflow-x-auto overflow-y-auto custom-scrollbar whitespace-pre font-mono shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
                {parseAnsiToTokens(clampForDisplay(stdout)).map((span, sIdx) => (
                  <span key={sIdx} className={span.className || undefined}>
                    {span.text}
                  </span>
                ))}
              </div>
            </div>
          )}
          {stderr && (
            <div className="relative">
              <div className="text-[9.5px] uppercase tracking-wider text-amber-400/80 mb-0.5 font-bold">stderr</div>
              <div className="p-2.5 rounded border border-amber-500/20 bg-amber-950/20 text-amber-200 text-[10.5px] leading-relaxed max-h-[260px] overflow-x-auto overflow-y-auto custom-scrollbar whitespace-pre font-mono shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
                {parseAnsiToTokens(clampForDisplay(stderr)).map((span, sIdx) => (
                  <span key={sIdx} className={span.className || undefined}>
                    {span.text}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : outputPayload ? (
        <div className="p-2.5 rounded border border-white/[0.06] bg-black/50 text-slate-300 text-[10.5px] leading-relaxed max-h-[260px] overflow-x-auto overflow-y-auto custom-scrollbar whitespace-pre font-mono shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
          {parseAnsiToTokens(clampForDisplay(outputPayload)).map((span, sIdx) => (
            <span key={sIdx} className={span.className || undefined}>
              {span.text}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ── 3. READ FILE VIEW (Gutter Line Numbers & Code Surface) ──────────────────
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

  const filename = filePath.split(/[\/\\]/).pop() || filePath;
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

// ── 4. GREP SEARCH RESULT VIEW (Grouped by File & Clean Hit Badges) ─────────
export function GrepResultView({
  pattern,
  matches,
  rawResult,
  onOpenFile,
}: {
  pattern?: string;
  matches?: Array<{ file: string; line_number: number; line: string }>;
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
            const filename = file.split(/[\/\\]/).pop() || file;
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
                  {hits.map((h, hIdx) => (
                    <div
                      key={hIdx}
                      onClick={() => onOpenFile?.(file, filename)}
                      className="flex items-baseline gap-2 py-0.5 px-1 rounded hover:bg-white/[0.04] cursor-pointer group/hit transition-colors"
                    >
                      <span className="px-1 py-px rounded text-[9px] font-mono text-purple-300 bg-purple-500/10 border border-purple-400/20 shrink-0 tabular-nums select-none">
                        L{h.line_number}
                      </span>
                      <span className="whitespace-pre font-mono text-[10.5px] text-slate-300 group-hover/hit:text-slate-100 transition-colors truncate">
                        {h.line}
                      </span>
                    </div>
                  ))}
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

// ── 5. GLOB SEARCH RESULT VIEW (Clean Interactive File List) ───────────────
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
            const filename = filePath.split(/[\/\\]/).pop() || filePath;
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

// ── 6. DIFF & CODE MODIFICATION CARD (Anara Desktop Standard) ──────────────
export interface DiffLineItem {
  type: "add" | "del" | "ctx" | "hunk";
  text: string;
  oldLine?: number;
  newLine?: number;
}

export function AgentActionCard({
  action,
  sessionId,
  onOpenFile,
  onDismiss,
}: {
  action?: AgentActionData;
  sessionId?: number;
  onOpenFile?: (filePath: string, fileName?: string) => void;
  onDismiss?: () => void;
}) {
  const tool = (action?.toolName || "").toLowerCase();
  const isFileEdit = Boolean(
    action?.added !== undefined ||
    action?.deleted !== undefined ||
    action?.checkpointId ||
    tool.includes("patch") ||
    tool.includes("write") ||
    tool.includes("edit")
  );
  const [isExpanded, setIsExpanded] = useState(isFileEdit);
  const [isReverting, setIsReverting] = useState(false);
  const [isReverted, setIsReverted] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);
  const [confirmRollback, setConfirmRollback] = useState(false);
  const [copied, setCopied] = useState(false);
  const confirmTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    };
  }, []);

  const rawDiff = action?.rawResult || action?.summary || "";
  const cleanedDiff = useMemo(() => stripDiffFileHeaders(rawDiff), [rawDiff]);

  const parsedDiff = useMemo(() => {
    if (!cleanedDiff) return { isRealDiff: false, added: 0, deleted: 0, lines: [] as DiffLineItem[] };
    const rawLines = cleanedDiff.split("\n");
    let added = 0;
    let deleted = 0;
    let currentOldLine = 1;
    let currentNewLine = 1;
    let hasDiffSignals = false;

    const formatted: DiffLineItem[] = [];

    for (const l of rawLines) {
      if (l.startsWith("@@")) {
        hasDiffSignals = true;
        const match = l.match(/@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@(.*)/);
        if (match) {
          currentOldLine = parseInt(match[1], 10);
          currentNewLine = parseInt(match[2], 10);
          const contextSuffix = (match[3] || "").trim();
          formatted.push({
            type: "hunk",
            text: contextSuffix ? `@@ ${contextSuffix}` : l,
          });
        } else {
          formatted.push({ type: "hunk", text: l });
        }
      } else if (l.startsWith("+") && !l.startsWith("+++")) {
        hasDiffSignals = true;
        added++;
        formatted.push({
          type: "add",
          text: l.substring(1),
          newLine: currentNewLine++,
        });
      } else if (l.startsWith("-") && !l.startsWith("---")) {
        hasDiffSignals = true;
        deleted++;
        formatted.push({
          type: "del",
          text: l.substring(1),
          oldLine: currentOldLine++,
        });
      } else {
        formatted.push({
          type: "ctx",
          text: l.startsWith(" ") ? l.substring(1) : l,
          oldLine: currentOldLine++,
          newLine: currentNewLine++,
        });
      }
    }

    return { isRealDiff: hasDiffSignals, added, deleted, lines: formatted };
  }, [cleanedDiff]);

  if (!action) return null;

  const handleCopyDiff = (e: React.MouseEvent) => {
    e.stopPropagation();
    const payload = rawDiff || action.content || "";
    navigator.clipboard.writeText(payload).then(() => {
      setCopied(true);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleRollback = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!action?.checkpointId || isReverting || isReverted) return;

    if (!confirmRollback) {
      setConfirmRollback(true);
      if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current);
      confirmTimeoutRef.current = setTimeout(() => {
        setConfirmRollback(false);
      }, 3500);
      return;
    }

    if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current);
    setConfirmRollback(false);
    setIsReverting(true);

    try {
      await anaraApi.checkpoint.revert(action.checkpointId, sessionId);
      setIsReverted(true);
      setRollbackError(null);
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("anara-brain-sync", { detail: { event: "workspace_updated" } }));
      }
    } catch (err: any) {
      console.warn("[Rollback Error]:", err);
      setRollbackError(err?.message || "Revert failed");
    } finally {
      setIsReverting(false);
    }
  };

  const isStart = (action?.eventType || "") === "agent_action_start";
  const isWrite = FILE_EDIT_TOOLS.has(tool) || tool.includes("write") || tool.includes("edit") || tool.includes("patch") || tool.includes("artifact");
  const isShell = SHELL_TOOLS.has(tool) || tool.includes("bash") || tool.includes("shell") || tool.includes("terminal") || tool.includes("command") || tool.includes("cli");
  const isSearch = SEARCH_TOOLS.has(tool) || tool.includes("glob") || tool.includes("grep") || tool.includes("search");
  const isRead = READ_TOOLS.has(tool) || tool.includes("read") || tool.includes("scan") || tool.includes("list");

  const rawTarget = action.detail || action.actionTitle || "";
  const filename = action.filename || action.filePath?.split(/[\/\\]/).pop() || rawTarget.split(" ")[0]?.split(/[\/\\]/).pop() || "file";
  const lastSlash = action.filePath ? Math.max(action.filePath.lastIndexOf("/"), action.filePath.lastIndexOf("\\")) : -1;
  const dirPath = lastSlash !== -1 && action.filePath ? action.filePath.slice(0, lastSlash) : "";

  // ── Render File Modification Diff Card ──
  if (isWrite) {
    const addCount = action.added ?? parsedDiff.added ?? 1;
    const delCount = action.deleted ?? parsedDiff.deleted ?? 0;

    return (
      <div className="my-1.5 font-mono text-xs select-none">
        {/* Header Action Row */}
        <div className="w-full flex items-center justify-between py-1 transition-colors text-left">
          <button
            type="button"
            onClick={() => setIsExpanded((v) => !v)}
            className="flex items-center gap-2 min-w-0 flex-1 text-left cursor-pointer font-mono group py-0.5"
          >
            <span className="relative flex h-2 w-2 shrink-0">
              {isStart ? (
                <>
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
                </>
              ) : (
                <span className="inline-flex rounded-full h-1.5 w-1.5 bg-slate-500 group-hover:bg-cyan-400 transition-colors" />
              )}
            </span>
            <span className="text-cyan-400 font-bold text-[11px] tracking-tight">Edit</span>
            <span className="text-slate-200 font-semibold truncate text-[11.5px] group-hover:text-white transition-colors">
              {filename}
            </span>
            {dirPath && <span className="text-slate-500 truncate text-[10.5px]">{dirPath}</span>}
            <div className="flex items-center gap-1.5 text-[10px] shrink-0 ml-1 font-bold">
              <span className="text-emerald-400">+{addCount}</span>
              <span className="text-rose-400">-{delCount}</span>
            </div>
            <svg
              className={`w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ml-1 ${
                isExpanded ? "rotate-90" : ""
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>

          <div className="flex items-center gap-2 shrink-0">
            {action.checkpointId && (
              <button
                type="button"
                onClick={handleRollback}
                disabled={isReverting || isReverted}
                className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer border ${
                  isReverted
                    ? "bg-emerald-500/15 text-emerald-300 border-emerald-400/30"
                    : confirmRollback
                    ? "bg-amber-500/20 text-amber-200 border-amber-400/40"
                    : rollbackError
                    ? "bg-rose-500/20 text-rose-300 border-rose-400/40"
                    : "bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-white border-white/[0.08]"
                }`}
                title={confirmRollback ? "Click again to confirm revert" : rollbackError || "Revert this edit"}
              >
                {isReverted ? "Reverted" : confirmRollback ? "Confirm?" : rollbackError ? "Error" : "Revert"}
              </button>
            )}

            {onOpenFile && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenFile(action.filePath || filename, filename);
                }}
                className="px-2 py-0.5 rounded text-[10px] font-mono text-cyan-300 hover:text-white bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/25 transition-all cursor-pointer"
              >
                View
              </button>
            )}

            <button
              type="button"
              onClick={handleCopyDiff}
              className="text-slate-500 hover:text-slate-300 p-1 rounded hover:bg-white/[0.05] transition-colors cursor-pointer text-[10px]"
              title="Copy diff"
            >
              {copied ? <span className="text-emerald-400 font-medium">Copied</span> : "Copy"}
            </button>
          </div>
        </div>

        {/* Dual Line Number Gutter Diff Table */}
        <div
          className={`grid transition-[grid-template-rows] duration-200 ease-out ${
            isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
          }`}
        >
          <div className="overflow-hidden">
            <div className="mt-1.5 rounded-lg border border-white/[0.08] bg-black/60 font-mono text-[11px] max-h-[340px] overflow-x-auto overflow-y-auto overscroll-x-contain overscroll-y-auto custom-scrollbar select-text tabular-nums shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
              {parsedDiff.isRealDiff ? (
                <table className="w-full border-collapse">
                  <tbody>
                    {parsedDiff.lines.map((line: DiffLineItem, idx: number) => {
                      if (line.type === "hunk") {
                        return (
                          <tr key={idx} className="bg-cyan-950/30 text-cyan-300 font-mono text-[10px] border-y border-cyan-800/20">
                            <td colSpan={4} className="px-3 py-1 select-none font-medium">
                              {line.text}
                            </td>
                          </tr>
                        );
                      }
                      return (
                        <tr
                          key={idx}
                          className={`${
                            line.type === "add"
                              ? "bg-emerald-500/[0.09] text-emerald-200 border-l-2 border-emerald-400"
                              : line.type === "del"
                              ? "bg-rose-500/[0.09] text-rose-200 border-l-2 border-rose-400"
                              : "text-slate-400 hover:bg-white/[0.015] border-l-2 border-transparent"
                          }`}
                        >
                          <td className="w-9 pr-1.5 text-right select-none text-slate-600 font-mono text-[10px] py-0.5 tabular-nums">
                            {line.type === "del" || line.type === "ctx" ? line.oldLine || "" : ""}
                          </td>
                          <td className="w-9 pr-2 text-right select-none text-slate-600 font-mono text-[10px] py-0.5 tabular-nums border-r border-white/[0.06]">
                            {line.type === "add" || line.type === "ctx" ? line.newLine || "" : ""}
                          </td>
                          <td className="w-4 text-center select-none font-bold py-0.5 text-[10px]">
                            {line.type === "add" ? (
                              <span className="text-emerald-400">+</span>
                            ) : line.type === "del" ? (
                              <span className="text-rose-400">-</span>
                            ) : (
                              " "
                            )}
                          </td>
                          <td className="pl-1.5 pr-3 py-0.5 whitespace-pre font-mono leading-relaxed text-[11px] min-h-[1.25rem]">
                            {line.text || " "}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : action.content ? (
                <table className="w-full border-collapse">
                  <tbody>
                    {action.content.split("\n").map((lineText: string, lIdx: number) => (
                      <tr key={lIdx} className="hover:bg-white/[0.02]">
                        <td className="w-10 pr-2 text-right select-none text-slate-600 font-mono text-[10px] py-0.5 border-r border-white/[0.06] tabular-nums">
                          {lIdx + 1}
                        </td>
                        <td className="pl-3 pr-3 py-0.5 whitespace-pre font-mono leading-relaxed text-[11px] text-slate-200 min-h-[1.25rem]">
                          {lineText || " "}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <pre className="text-slate-300 p-3 leading-relaxed whitespace-pre font-mono text-[11px]">
                  {rawDiff || "Modifications applied."}
                </pre>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Render Shell Execution Card ──
  if (isShell) {
    const cmd = action.command || action.detail || action.actionTitle || "command";
    const duration = action.durationText;

    return (
      <div className="my-1.5 font-mono text-xs select-none">
        <div className="flex items-center justify-between py-1 group/cmd">
          <button
            onClick={() => setIsExpanded((v) => !v)}
            className="flex items-center gap-2 text-left text-slate-300 hover:text-white transition-colors cursor-pointer flex-1 min-w-0"
          >
            <span className="relative flex h-2 w-2 shrink-0">
              {isStart ? (
                <>
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
                </>
              ) : (
                <span className="inline-flex rounded-full h-1.5 w-1.5 bg-slate-500 group-hover:bg-cyan-400 transition-colors" />
              )}
            </span>
            <span className="text-emerald-400 font-bold text-[11px] tracking-tight">Run</span>
            <span className="text-slate-300 group-hover:text-white truncate font-mono text-[11px] font-medium transition-colors">
              {cmd}
            </span>
            <svg
              className={`w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ml-1 ${
                isExpanded ? "rotate-90" : ""
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>

          {duration && (
            <span className="text-[10px] text-slate-500 font-mono tabular-nums shrink-0 ml-2">
              {duration}
            </span>
          )}
        </div>

        {isExpanded && (
          <div className="mt-1">
            <TerminalTranscript
              command={cmd}
              exitCode={action.exitCode ?? 0}
              rawResult={action.rawResult || action.summary}
              durationText={duration}
            />
          </div>
        )}
      </div>
    );
  }

  // ── Render Read File Card ──
  if (isRead) {
    const target = action.filePath || action.detail || filename;
    return (
      <ReadFileView
        filePath={target}
        content={action.content || action.rawResult || action.summary || ""}
        onOpenFile={onOpenFile}
      />
    );
  }

  // ── Render Grep Card ──
  if (tool.includes("grep") || (isSearch && !tool.includes("glob"))) {
    const pat = action.detail?.replace(/^(Regex|pattern)[=:]\s*/i, "").trim() || action.actionTitle || "";
    return (
      <GrepResultView
        pattern={pat}
        rawResult={action.rawResult || action.summary}
        onOpenFile={onOpenFile}
      />
    );
  }

  // ── Render Glob Card ──
  if (tool.includes("glob") || tool.includes("list")) {
    const pat = action.detail?.replace(/^pattern[=:]\s*/i, "").trim() || "*";
    return (
      <GlobResultView
        pattern={pat}
        rawResult={action.rawResult || action.summary}
        onOpenFile={onOpenFile}
      />
    );
  }

  // ── Fallback Generic Action Item ──
  return (
    <div className="my-1.5 font-mono text-xs select-none">
      <div className="flex items-baseline gap-2 py-0.5 text-slate-300">
        <span className="font-semibold text-slate-200 shrink-0">Action</span>
        <span className="truncate text-slate-300 font-mono">{action.detail || action.actionTitle}</span>
        {isStart && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping ml-1" />}
      </div>
    </div>
  );
}

// ── 7. TOOL RUN GROUP CARD (Anara Desktop Standard) ────────────────────────
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

  if (!items || items.length === 0) return null;

  const activeItems = useMemo(
    () => items.filter((_, idx) => !dismissedIndices.has(idx)),
    [items, dismissedIndices]
  );

  if (activeItems.length === 0) return null;

  const summary = useMemo(() => {
    let readCount = 0;
    let searchCount = 0;
    let commandCount = 0;
    let editCount = 0;
    const fileSet = new Set<string>();

    for (const item of activeItems) {
      const tool = (item.toolName || "").toLowerCase();
      const isShell = SHELL_TOOLS.has(tool) || tool.includes("cli") || tool.includes("terminal") || tool.includes("exec");
      const isEdit = FILE_EDIT_TOOLS.has(tool) || tool.includes("write") || tool.includes("edit") || tool.includes("patch");
      const isRead = READ_TOOLS.has(tool) || tool.includes("read") || tool.includes("scan");
      const isSearch = SEARCH_TOOLS.has(tool) || tool.includes("grep") || tool.includes("glob") || tool.includes("search");

      if (isShell) {
        commandCount++;
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
      if (SHELL_TOOLS.has(tool)) {
        return `${isRunning ? "Running" : "Ran"} ${single.command || single.detail || "command"}`;
      }
      if (tool.includes("read")) {
        const file = single.filename || single.filePath?.split(/[\/\\]/).pop() || single.detail || "file";
        return `${isRunning ? "Reading" : "Read"} ${file}`;
      }
      if (tool.includes("grep") || tool.includes("search")) {
        const pat = single.detail?.replace(/^(Regex|pattern)[=:]\s*/i, "").trim() || "codebase";
        return `${isRunning ? "Searching" : "Searched"} ${pat}`;
      }
      if (tool.includes("glob") || tool.includes("list")) {
        return `${isRunning ? "Listing" : "Listed"} files`;
      }
      if (tool.includes("write") || tool.includes("edit")) {
        const file = single.filename || single.filePath?.split(/[\/\\]/).pop() || "file";
        return `${isRunning ? "Editing" : "Edited"} ${file}`;
      }
    }

    const uniqueFiles = fileSet.size;
    const clauses: string[] = [];

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

  return (
    <div className="my-1.5 font-mono text-xs select-none">
      {/* Group Header Button */}
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        className="flex items-center gap-2 text-left text-slate-400 hover:text-slate-200 transition-colors cursor-pointer py-1 group"
      >
        <span className="relative flex h-2 w-2 shrink-0">
          {isRunning ? (
            <>
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
            </>
          ) : (
            <span className="inline-flex rounded-full h-1.5 w-1.5 bg-slate-500 group-hover:bg-cyan-400 transition-colors" />
          )}
        </span>
        <span className={`text-[12px] font-medium tracking-tight ${isRunning ? "text-cyan-300 animate-pulse" : "text-slate-400 group-hover:text-slate-200"}`}>
          {summary}
        </span>
        <svg
          className={`w-3.5 h-3.5 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ml-0.5 ${
            isExpanded ? "rotate-90" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>

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

              const rawTarget = sub.command || sub.filePath || sub.detail || sub.actionTitle || "";
              const cmdText = sub.command || sub.detail || sub.actionTitle || "command";
              const exitCode = sub.exitCode;
              const duration = sub.durationText;

              const isRowExpanded = expandedRowIdx === sIdx;

              // Shell tool row
              if (isShell) {
                return (
                  <div key={sIdx} className="flex flex-col group/row">
                    <div className="flex items-center gap-2 py-0.5 px-1.5 rounded hover:bg-white/[0.04] transition-colors cursor-pointer">
                      <svg className="w-3.5 h-3.5 text-slate-500 group-hover/row:text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      
                      <button
                        type="button"
                        onClick={() => setExpandedRowIdx(isRowExpanded ? null : sIdx)}
                        className="flex-1 min-w-0 text-left truncate text-slate-300 group-hover/row:text-white font-mono text-[11px]"
                      >
                        {cmdText}
                      </button>

                      {duration && (
                        <span className="text-[10px] text-slate-500 font-mono tabular-nums shrink-0 ml-auto">
                          {duration}
                        </span>
                      )}

                      <button
                        type="button"
                        onClick={() => setExpandedRowIdx(isRowExpanded ? null : sIdx)}
                        className="text-slate-500 hover:text-slate-300 p-0.5 shrink-0"
                      >
                        <svg
                          className={`w-3 h-3 transition-transform duration-150 ${isRowExpanded ? "rotate-90" : ""}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDismissedIndices((prev) => new Set([...prev, sIdx]));
                        }}
                        className="text-slate-600 hover:text-slate-300 p-0.5 rounded opacity-0 group-hover/row:opacity-100 transition-opacity shrink-0"
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

              // File exploration item (Read, Grep, Glob, Edit)
              const cleanTarget = rawTarget.replace(/^(read|scan|grep|glob|list)\s+/i, "").trim();
              const lastSlash = Math.max(cleanTarget.lastIndexOf("/"), cleanTarget.lastIndexOf("\\"));
              const dir = lastSlash !== -1 ? cleanTarget.slice(0, lastSlash + 1) : "";
              const file = sub.filename || (lastSlash !== -1 ? cleanTarget.slice(lastSlash + 1) : cleanTarget);
              const opBadge = isRead ? "READ" : isGrep ? "GREP" : isGlob ? "GLOB" : isWrite ? "EDIT" : "EXPLORE";

              return (
                <div key={sIdx} className="flex flex-col group/row">
                  <div
                    onClick={() => setExpandedRowIdx(isRowExpanded ? null : sIdx)}
                    className="flex items-center gap-2 py-0.5 px-1.5 rounded transition-colors cursor-pointer hover:bg-white/[0.04] text-slate-300"
                  >
                    <span
                      className={`px-1.5 py-px rounded text-[9.5px] font-bold shrink-0 tracking-wider border ${
                        isRead
                          ? "bg-cyan-500/10 text-cyan-300 border-cyan-400/20"
                          : isGrep
                          ? "bg-purple-500/10 text-purple-300 border-purple-400/20"
                          : isGlob
                          ? "bg-amber-500/10 text-amber-300 border-amber-400/20"
                          : "bg-emerald-500/10 text-emerald-300 border-emerald-400/20"
                      }`}
                    >
                      {opBadge}
                    </span>
                    <div className="truncate flex items-baseline gap-0.5 min-w-0 flex-1">
                      {dir && <span className="text-slate-500 truncate text-[10px]">{dir}</span>}
                      <span className="text-slate-200 font-medium group-hover/row:text-cyan-300 transition-colors truncate">
                        {file}
                      </span>
                    </div>

                    <span className="text-slate-500 hover:text-slate-300 p-0.5 shrink-0 ml-auto">
                      <svg
                        className={`w-3 h-3 transition-transform duration-150 ${isRowExpanded ? "rotate-90" : ""}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </span>

                    {onOpenFile && isRead && (
                      <span
                        onClick={(e) => {
                          e.stopPropagation();
                          cleanTarget && onOpenFile(cleanTarget, file);
                        }}
                        className="text-slate-600 hover:text-cyan-300 text-[10px] shrink-0 opacity-0 group-hover/row:opacity-100 transition-opacity ml-1"
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
                      {isRead ? (
                        <ReadFileView
                          filePath={sub.filePath || cleanTarget || file}
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
                          {clampForDisplay(sub.rawResult || sub.content || sub.summary || "")}
                        </pre>
                      )}
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

// ── 8. TODO CHECKLIST CARD ──────────────────────────────────────────────────
export function TodoChecklistCard({
  todoData,
  onDismiss,
}: {
  todoData?: TodoData | null;
  onDismiss?: () => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!todoData || !todoData.items || todoData.items.length === 0) return null;
  const total = todoData.items.length;
  const completed = todoData.items.filter((t) => t.is_completed).length;

  return (
    <div className="my-1.5 font-mono text-xs select-none">
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        className="flex items-center gap-2 text-left text-slate-300 hover:text-white transition-colors cursor-pointer py-1 group"
      >
        <span className="relative flex h-2 w-2 shrink-0">
          <span className={`inline-flex rounded-full h-1.5 w-1.5 ${completed === total ? "bg-emerald-400" : "bg-cyan-400"}`} />
        </span>
        <span className="font-semibold text-slate-200 tracking-tight text-[11.5px]">Tasks</span>
        <span className="text-slate-400 text-[11px]">({completed} of {total} completed)</span>
        <svg
          className={`w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ${
            isExpanded ? "rotate-90" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${
          isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div className="pl-4 py-1.5 space-y-1.5 border-l border-white/[0.08] my-1 font-mono text-[11px]">
            {todoData.items.map((item: any, idx: number) => (
              <div
                key={idx}
                className={`flex items-start gap-2 p-1 rounded transition-colors ${
                  item.is_completed ? "text-slate-500 line-through" : "text-slate-200 hover:bg-white/[0.02]"
                }`}
              >
                <span
                  className={`w-3.5 h-3.5 rounded mt-0.5 flex items-center justify-center text-[9px] shrink-0 font-bold ${
                    item.is_completed
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                      : "border border-white/20 text-transparent"
                  }`}
                >
                  {item.is_completed && (
                    <svg className="w-2.5 h-2.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </span>
                <div className="flex-1 min-w-0 font-sans">
                  <p className="leading-snug">{item.title}</p>
                  {item.content && (
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5">{item.content}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 9. DEFAULT EXPORT ROUTER ────────────────────────────────────────────────
export default function AgentToolCard({
  action,
  todoData,
  sessionId,
  onOpenFile,
  onDismiss,
}: AgentToolCardProps) {
  if (todoData && todoData.items && todoData.items.length > 0) {
    return <TodoChecklistCard todoData={todoData} onDismiss={onDismiss} />;
  }
  return (
    <AgentActionCard
      action={action}
      sessionId={sessionId}
      onOpenFile={onOpenFile}
      onDismiss={onDismiss}
    />
  );
}
