"use client";

import React, { useState, useRef, useEffect } from "react";
import { clampForDisplay, parseAnsiToTokens, stripAnsi } from "./toolCardUtils";

// ── TERMINAL TRANSCRIPT (Anara Desktop Standard) ────────────────────────
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

  // Pinned auto-tailing ref (Desktop Reference Standard)
  const stdoutScrollRef = useRef<HTMLDivElement>(null);
  const stderrScrollRef = useRef<HTMLDivElement>(null);
  const mergedScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = stdoutScrollRef.current || mergedScrollRef.current;
    if (el) {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
      if (nearBottom) {
        el.scrollTop = el.scrollHeight;
      }
    }
  }, [stdout, outputPayload]);

  useEffect(() => {
    const el = stderrScrollRef.current;
    if (el) {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
      if (nearBottom) {
        el.scrollTop = el.scrollHeight;
      }
    }
  }, [stderr]);

  return (
    <div className="flex flex-col gap-1.5 w-full my-1 font-mono text-[11px] select-text">
      {/* Command prompt bar (Desktop Reference Standard) */}
      {(command || exitCode !== undefined) && (
        <div className="flex min-w-0 items-center justify-between gap-2 rounded-[0.25rem] border border-white/[0.08] bg-black/50 px-2 py-1 leading-relaxed">
          {command && (
            <div className="min-w-0 flex-1 overflow-x-auto custom-scrollbar whitespace-pre font-mono text-slate-200 text-[11px]">
              <span className="text-cyan-400 select-none font-bold mr-1.5">$</span>
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
                className={`shrink-0 rounded px-1 py-px text-[9.5px] font-bold tabular-nums border ${
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
              className="text-slate-500 hover:text-slate-300 p-0.5 rounded hover:bg-white/[0.05] transition-colors cursor-pointer"
              title="Copy output"
            >
              {copied ? (
                <span className="text-[9.5px] text-emerald-400 font-medium">Copied</span>
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
              <div
                ref={stdoutScrollRef}
                className="p-2.5 rounded border border-white/[0.06] bg-black/50 text-slate-300 text-[10.5px] leading-relaxed max-h-[260px] overflow-x-auto overflow-y-auto overscroll-x-contain overscroll-y-auto custom-scrollbar whitespace-pre font-mono shadow-[0_4px_16px_rgba(0,0,0,0.4)]"
              >
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
              <div
                ref={stderrScrollRef}
                className="p-2.5 rounded border border-amber-500/20 bg-amber-950/20 text-amber-200 text-[10.5px] leading-relaxed max-h-[260px] overflow-x-auto overflow-y-auto overscroll-x-contain overscroll-y-auto custom-scrollbar whitespace-pre font-mono shadow-[0_4px_16px_rgba(0,0,0,0.4)]"
              >
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
        <div
          ref={mergedScrollRef}
          className="p-2.5 rounded border border-white/[0.06] bg-black/50 text-slate-300 text-[10.5px] leading-relaxed max-h-[260px] overflow-x-auto overflow-y-auto overscroll-x-contain overscroll-y-auto custom-scrollbar whitespace-pre font-mono shadow-[0_4px_16px_rgba(0,0,0,0.4)]"
        >
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
