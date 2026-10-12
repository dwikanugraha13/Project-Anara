"use client";

import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { detectArtifact } from "@/lib/artifactDetect";

// ── Types & Interfaces ────────────────────────────────────────────────────────
export interface AgentMarkdownProps {
  content: string;
  isStreaming?: boolean;
  showLineNumbersByDefault?: boolean;
  defaultWrap?: boolean;
  className?: string;
}

type BlockToken =
  | { type: "codeblock"; language: string; content: string }
  | { type: "table"; headers: string[]; aligns: ("left" | "center" | "right")[]; rows: string[][] }
  | { type: "blockquote"; content: string }
  | { type: "alert"; alertType: "note" | "tip" | "important" | "warning" | "caution"; content: string }
  | { type: "heading"; level: 1 | 2 | 3 | 4 | 5 | 6; content: string }
  | { type: "hr" }
  | { type: "list"; ordered: boolean; start?: number; items: { text: string; task?: { checked: boolean } }[] }
  | { type: "paragraph"; content: string };

// ── Syntax Highlighting Engine (Liquid Glass Palette) ─────────────────────────
interface HighlightToken {
  type:
    | "plain"
    | "keyword"
    | "function"
    | "string"
    | "number"
    | "comment"
    | "operator"
    | "type"
    | "variable"
    | "tag"
    | "attr"
    | "diff-add"
    | "diff-del"
    | "diff-hunk"
    | "prompt"
    | "flag";
  value: string;
}

function tokenizeCode(code: string, language: string): HighlightToken[][] {
  const lang = (language || "").toLowerCase().trim();
  const lines = code.split("\n");

  // Diff Specializer
  if (lang === "diff" || lang === "patch") {
    return lines.map((line) => {
      if (line.startsWith("+++") || line.startsWith("---")) {
        return [{ type: "diff-hunk", value: line }];
      }
      if (line.startsWith("@@")) {
        return [{ type: "diff-hunk", value: line }];
      }
      if (line.startsWith("+")) {
        return [{ type: "diff-add", value: line }];
      }
      if (line.startsWith("-")) {
        return [{ type: "diff-del", value: line }];
      }
      return [{ type: "plain", value: line }];
    });
  }

  // Language Regex Grammars
  const grammars: Record<string, { patterns: [RegExp, HighlightToken["type"]][] }> = {
    python: {
      patterns: [
        [/^#.*/, "comment"],
        [/^(f?["']{3}[\s\S]*?["']{3})/, "string"],
        [/^(f?["'][^"\n]*["'])/, "string"],
        [/^\b(def|class|return|if|elif|else|while|for|in|import|from|as|try|except|finally|with|lambda|yield|async|await|pass|raise|break|continue|assert|is|not|and|or)\b/, "keyword"],
        [/^\b(True|False|None)\b/, "number"],
        [/^\b(self|cls)\b/, "variable"],
        [/^\b(int|str|float|bool|list|dict|set|tuple|object|Exception|type)\b/, "type"],
        [/^(@[a-zA-Z_]\w*)/, "function"],
        [/^([a-zA-Z_]\w*)(?=\s*\()/, "function"],
        [/^\b\d+(\.\d+)?\b/, "number"],
        [/^(=>|->|==|!=|<=|>=|[+\-*/%=<>!&|^~])/, "operator"],
      ],
    },
    javascript: {
      patterns: [
        [/^\/\/.*/, "comment"],
        [/^\/\*[\s\S]*?\*\//, "comment"],
        [/^(`(?:\\.|[^`])*`|"(?:\\.|[^"\n])*"|'(?:\\.|[^'\n])*')/, "string"],
        [/^\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|import|export|default|from|as|class|extends|new|this|typeof|instanceof|void|delete|try|catch|finally|throw|async|await|yield)\b/, "keyword"],
        [/^\b(true|false|null|undefined|NaN)\b/, "number"],
        [/^\b(string|number|boolean|any|void|never|unknown|Promise|Array|Record|Partial)\b/, "type"],
        [/^([a-zA-Z_$][\w$]*)(?=\s*\()/, "function"],
        [/^\b\d+(\.\d+)?\b/, "number"],
        [/^(=>|===|!==|==|!=|<=|>=|[+\-*/%=<>!&|^~?])/, "operator"],
      ],
    },
    bash: {
      patterns: [
        [/^#.*/, "comment"],
        [/^(\$|>|#)\s/, "prompt"],
        [/^(--[a-zA-Z0-9_-]+|-[a-zA-Z0-9])/, "flag"],
        [/^(".*?"|'.*?')/, "string"],
        [/^\b(cd|ls|mkdir|rm|cp|mv|cat|grep|chmod|chown|curl|wget|git|npm|pnpm|yarn|bun|node|python|docker|sudo|echo|export|source|alias)\b/, "function"],
        [/^\b(if|then|else|elif|fi|case|esac|for|while|until|do|done|in)\b/, "keyword"],
        [/^(\$[a-zA-Z_]\w*|\$\{[^}]+\})/, "variable"],
        [/^(\|{1,2}|&{1,2}|>>?|<)/, "operator"],
      ],
    },
    sql: {
      patterns: [
        [/^--.*/, "comment"],
        [/^('(''|[^'])*')/, "string"],
        [/^\b(SELECT|FROM|WHERE|INSERT|INTO|UPDATE|DELETE|JOIN|LEFT|RIGHT|INNER|OUTER|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|CREATE|TABLE|ALTER|DROP|INDEX|UNION|ALL|AS|DISTINCT|COUNT|SUM|AVG|MIN|MAX|AND|OR|NOT|NULL|IS|IN|LIKE|BETWEEN|CASE|WHEN|THEN|ELSE|END)\b/i, "keyword"],
        [/^\b\d+(\.\d+)?\b/, "number"],
        [/^(=|!=|<>|<=|>=|[+\-*/%<>])/, "operator"],
      ],
    },
    json: {
      patterns: [
        [/^"(\\.|[^"\n])*"(?=\s*:)/, "tag"],
        [/^"(\\.|[^"\n])*"/, "string"],
        [/^\b(true|false|null)\b/, "keyword"],
        [/^-?\b\d+(\.\d+)?([eE][+-]?\d+)?\b/, "number"],
        [/^[:,\{\}\[\]]/, "operator"],
      ],
    },
    yaml: {
      patterns: [
        [/^#.*/, "comment"],
        [/^([a-zA-Z0-9_-]+)(?=\s*:)/, "tag"],
        [/^(".*?"|'.*?')/, "string"],
        [/^\b(true|false|null|yes|no)\b/i, "number"],
        [/^\b\d+(\.\d+)?\b/, "number"],
        [/^[-:|]/, "operator"],
      ],
    },
  };

  // Language Aliases
  let grammar = grammars[lang];
  if (!grammar) {
    if (["ts", "tsx", "jsx", "typescript"].includes(lang)) grammar = grammars.javascript;
    else if (["py", "python3"].includes(lang)) grammar = grammars.python;
    else if (["sh", "zsh", "shell"].includes(lang)) grammar = grammars.bash;
    else if (["yml"].includes(lang)) grammar = grammars.yaml;
  }

  return lines.map((line) => {
    if (!grammar) return [{ type: "plain", value: line }];
    const tokens: HighlightToken[] = [];
    let remaining = line;

    while (remaining.length > 0) {
      let matched = false;
      for (const [regex, type] of grammar.patterns) {
        const match = remaining.match(regex);
        if (match && match.index === 0) {
          tokens.push({ type, value: match[0] });
          remaining = remaining.slice(match[0].length);
          matched = true;
          break;
        }
      }

      if (!matched) {
        const nextSpecial = remaining.search(/[^a-zA-Z0-9_]/);
        if (nextSpecial > 0) {
          tokens.push({ type: "plain", value: remaining.slice(0, nextSpecial) });
          remaining = remaining.slice(nextSpecial);
        } else {
          tokens.push({ type: "plain", value: remaining.slice(0, 1) });
          remaining = remaining.slice(1);
        }
      }
    }
    return tokens;
  });
}

function getTokenColor(type: HighlightToken["type"]): string {
  switch (type) {
    case "keyword":
      return "text-purple-400 font-semibold";
    case "function":
      return "text-sky-300 font-medium";
    case "string":
      return "text-emerald-300";
    case "number":
      return "text-amber-400";
    case "comment":
      return "text-slate-500 italic";
    case "operator":
      return "text-sky-300/80";
    case "type":
      return "text-teal-300 font-medium";
    case "variable":
      return "text-slate-200";
    case "tag":
      return "text-rose-400";
    case "attr":
      return "text-amber-300";
    case "flag":
      return "text-amber-300";
    case "prompt":
      return "text-slate-400 font-bold select-none";
    case "diff-add":
      return "text-emerald-300 bg-emerald-500/10 block w-full px-1 rounded-xs";
    case "diff-del":
      return "text-rose-300 bg-rose-500/10 block w-full px-1 rounded-xs";
    case "diff-hunk":
      return "text-slate-400 font-mono bg-white/[0.04] border-y border-white/[0.06] block w-full px-1 rounded-xs";
    default:
      return "text-slate-200";
  }
}

// ── CodeBlock Component (Obsidian Liquid Glass) ───────────────────────────────
function CodeBlock({
  language,
  code,
  showLineNumbers = true,
  isStreamingLeaf = false,
}: {
  language: string;
  code: string;
  showLineNumbers?: boolean;
  isStreamingLeaf?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const [wrap, setWrap] = useState(false);
  const [linesActive, setLinesActive] = useState(showLineNumbers);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const handleCopy = useCallback(() => {
    const fallbackCopy = (text: string) => {
      try {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        textarea.style.pointerEvents = "none";
        document.body.appendChild(textarea);
        textarea.select();
        const success = document.execCommand("copy");
        document.body.removeChild(textarea);
        return success;
      } catch {
        return false;
      }
    };

    const markSuccess = () => {
      setCopied(true);
      setCopyFailed(false);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), 2000);
    };

    const markError = () => {
      setCopyFailed(true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopyFailed(false), 2500);
    };

    if (navigator?.clipboard?.writeText) {
      navigator.clipboard
        .writeText(code)
        .then(markSuccess)
        .catch(() => {
          if (fallbackCopy(code)) markSuccess();
          else markError();
        });
    } else {
      if (fallbackCopy(code)) markSuccess();
      else markError();
    }
  }, [code]);

  const tokenizedLines = useMemo(() => tokenizeCode(code, language), [code, language]);
  const artifact = useMemo(() => detectArtifact(language, code), [language, code]);

  const cleanLang = (language || "code").toLowerCase();
  const langLabel =
    {
      ts: "TypeScript",
      tsx: "React TSX",
      js: "JavaScript",
      jsx: "React JSX",
      py: "Python",
      sh: "Bash",
      bash: "Bash",
      sql: "SQL",
      json: "JSON",
      yaml: "YAML",
      yml: "YAML",
      html: "HTML",
      css: "CSS",
      diff: "Diff",
      md: "Markdown",
    }[cleanLang] || cleanLang.toUpperCase();

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-white/10 bg-[#060913]/90 backdrop-blur-xl shadow-2xl transition-all">
      {/* Chrome Header */}
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-white/[0.03] border-b border-white/5 text-[11px]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-slate-400/60" />
          <span className="font-mono font-semibold tracking-wide text-slate-300 text-[10.5px]">
            {langLabel}
          </span>
          <span className="text-[10px] text-slate-500 font-mono">
            {tokenizedLines.length} {tokenizedLines.length === 1 ? "line" : "lines"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {artifact && (
            <button
              type="button"
              onClick={() => {
                if (typeof window !== "undefined") {
                  window.dispatchEvent(
                    new CustomEvent("anara-open-code-viewer", {
                      detail: {
                        title: artifact.title,
                        language: artifact.language,
                        content: code,
                      },
                    })
                  );
                }
              }}
              className="cursor-pointer flex items-center gap-1 px-2 py-0.5 rounded text-[10.5px] font-medium text-slate-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-all mr-1"
              title="Open in Right Split View (Studio)"
            >
              <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
              <span>Split View</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => setLinesActive(!linesActive)}
            className={`cursor-pointer px-1.5 py-0.5 rounded text-[10.5px] font-mono transition-colors ${
              linesActive ? "text-white bg-white/[0.08]" : "text-slate-400 hover:text-slate-200"
            }`}
            title="Toggle line numbers"
          >
            #
          </button>
          <button
            type="button"
            onClick={() => setWrap(!wrap)}
            className={`cursor-pointer px-1.5 py-0.5 rounded text-[10.5px] transition-colors ${
              wrap ? "text-white bg-white/[0.08]" : "text-slate-400 hover:text-slate-200"
            }`}
            title="Toggle line wrap"
          >
            wrap
          </button>
          <button
            type="button"
            onClick={handleCopy}
            className={`cursor-pointer flex items-center gap-1 px-2 py-0.5 rounded text-[10.5px] font-medium transition-all ${
              copied
                ? "text-emerald-300 bg-emerald-950/40 border border-emerald-500/30"
                : copyFailed
                ? "text-rose-300 bg-rose-950/40 border border-rose-500/30"
                : "text-slate-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08]"
            }`}
          >
            {copied ? (
              <>
                <svg className="w-3 h-3 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>Copied</span>
              </>
            ) : copyFailed ? (
              <span>Error</span>
            ) : (
              <>
                <svg className="w-3 h-3 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Code Scroller */}
      <pre
        className={`p-3.5 custom-scrollbar text-[12px] font-mono leading-relaxed overflow-x-auto ${
          wrap ? "whitespace-pre-wrap break-words" : "whitespace-pre"
        }`}
      >
        <code>
          {tokenizedLines.map((lineTokens, lineIdx) => {
            const isLastLine = lineIdx === tokenizedLines.length - 1;
            return (
              <div key={lineIdx} className="table-row">
                {linesActive && (
                  <span className="table-cell pr-4 text-right text-slate-600 select-none text-[11px] font-mono align-top w-8">
                    {lineIdx + 1}
                  </span>
                )}
                <span className="table-cell align-top">
                  {lineTokens.map((t, tokIdx) => (
                    <span key={tokIdx} className={getTokenColor(t.type)}>
                      {t.value}
                    </span>
                  ))}
                  {isStreamingLeaf && isLastLine && (
                    <span className="streaming-caret inline-block w-[2px] h-[1.15em] bg-white/80 animate-pulse ml-0.5 align-middle" />
                  )}
                </span>
              </div>
            );
          })}
        </code>
      </pre>
    </div>
  );
}

// ── Auto-Graph Table Component (Oh My Pi / Harness Parity) ───────────────────
interface AutoGraphTableProps {
  headers: string[];
  aligns: ("left" | "center" | "right")[];
  rows: string[][];
  renderInlineText: (text: string, isLast?: boolean, isStreaming?: boolean) => React.ReactNode;
  isLastBlock?: boolean;
  isStreaming?: boolean;
}

function parseNumericValue(val: string): number | null {
  if (!val) return null;
  const clean = val.replace(/,/g, "").trim();
  const m = clean.match(/[-+]?\d*\.?\d+/);
  if (m) {
    const n = parseFloat(m[0]);
    return isNaN(n) ? null : n;
  }
  return null;
}

function AutoGraphTable({
  headers,
  aligns,
  rows,
  renderInlineText,
  isLastBlock,
  isStreaming,
}: AutoGraphTableProps) {
  const [viewMode, setViewMode] = useState<"table" | "chart">("table");

  // Detect measure columns with numeric values (Pass rate, tokens, latency, numbers)
  const numericColumns = useMemo(() => {
    if (rows.length < 2 || headers.length < 2) return [];
    const valid: { colIdx: number; header: string; values: number[] }[] = [];

    for (let c = 1; c < headers.length; c++) {
      let numCount = 0;
      const vals: number[] = [];
      for (const row of rows) {
        const parsed = parseNumericValue(row[c] || "");
        if (parsed !== null) {
          numCount++;
          vals.push(parsed);
        } else {
          vals.push(0);
        }
      }
      if (numCount >= Math.ceil(rows.length * 0.5)) {
        valid.push({ colIdx: c, header: headers[c] || `Metric ${c}`, values: vals });
      }
    }
    return valid;
  }, [headers, rows]);

  const [activeMetricIdx, setActiveMetricIdx] = useState<number>(0);
  const currentMetric = numericColumns[activeMetricIdx] || numericColumns[0];

  const maxVal = useMemo(() => {
    if (!currentMetric || currentMetric.values.length === 0) return 1;
    const max = Math.max(...currentMetric.values, 0);
    return max > 0 ? max : 1;
  }, [currentMetric]);

  const canChart = numericColumns.length > 0 && rows.length >= 2;

  return (
    <div className="my-3 rounded-xl border border-white/10 bg-[#060913]/70 backdrop-blur-md shadow-lg overflow-hidden transition-all font-mono">
      {/* Top Header Toolbar if chart is eligible */}
      {canChart && (
        <div className="px-3.5 py-2 border-b border-white/[0.06] bg-white/[0.02] flex items-center justify-between gap-2 text-xs select-none">
          {/* Metric Selector Pills if in Chart mode */}
          <div className="flex items-center gap-1.5 overflow-x-auto custom-scrollbar min-w-0">
            {viewMode === "chart" && (
              <span className="text-[10px] text-slate-400 font-sans uppercase tracking-wider shrink-0 mr-1">
                Metric:
              </span>
            )}
            {viewMode === "chart" &&
              numericColumns.map((col, idx) => (
                <button
                  key={col.colIdx}
                  type="button"
                  onClick={() => setActiveMetricIdx(idx)}
                  className={`px-2 py-0.5 rounded text-[10.5px] transition-all cursor-pointer truncate ${
                    activeMetricIdx === idx
                      ? "bg-cyan-500/15 text-cyan-300 border border-cyan-400/30 font-semibold"
                      : "bg-white/[0.03] text-slate-400 hover:text-white border border-transparent"
                  }`}
                >
                  {col.header}
                </button>
              ))}
          </div>

          {/* Mode Switcher */}
          <div className="flex items-center gap-1 bg-black/40 p-0.5 rounded-lg border border-white/[0.06] shrink-0">
            <button
              type="button"
              onClick={() => setViewMode("table")}
              className={`px-2 py-0.5 rounded text-[10px] font-sans font-medium transition-all cursor-pointer ${
                viewMode === "table"
                  ? "bg-white/10 text-white shadow-xs font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Table
            </button>
            <button
              type="button"
              onClick={() => setViewMode("chart")}
              className={`px-2 py-0.5 rounded text-[10px] font-sans font-medium transition-all cursor-pointer flex items-center gap-1 ${
                viewMode === "chart"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 font-semibold shadow-xs"
                  : "text-slate-400 hover:text-cyan-300"
              }`}
            >
              <span>Auto-Graph</span>
            </button>
          </div>
        </div>
      )}

      {/* Main View Container */}
      {viewMode === "chart" && canChart && currentMetric ? (
        <div className="p-4 space-y-3 animate-fade-in select-none">
          {rows.map((row, rIdx) => {
            const rawLabel = row[0] || `Row ${rIdx + 1}`;
            const numVal = currentMetric.values[rIdx] ?? 0;
            const rawText = row[currentMetric.colIdx] || `${numVal}`;
            const pct = Math.min(100, Math.max(0, (numVal / maxVal) * 100));

            return (
              <div key={rIdx} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-200 truncate pr-2 max-w-[65%]" title={rawLabel}>
                    {rawLabel}
                  </span>
                  <span className="text-[11px] font-mono text-cyan-300 font-bold shrink-0">
                    {rawText}
                  </span>
                </div>
                {/* Horizontal Progress Bar */}
                <div className="h-2 w-full bg-white/[0.06] rounded-full overflow-hidden p-0.5 border border-white/[0.04]">
                  <div
                    style={{ width: `${Math.max(4, pct)}%` }}
                    className="h-full rounded-full bg-gradient-to-r from-cyan-500/80 to-purple-500/80 transition-all duration-500 shadow-xs shadow-cyan-500/20"
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse font-sans">
            <thead>
              <tr className="border-b border-white/10 bg-white/[0.04]">
                {headers.map((h, hIdx) => (
                  <th
                    key={hIdx}
                    style={{ textAlign: aligns[hIdx] || "left" }}
                    className="px-3.5 py-2 font-semibold text-slate-100 tracking-wide font-mono text-[11px]"
                  >
                    {renderInlineText(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 font-mono text-xs">
              {rows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-white/[0.02] transition-colors">
                  {row.map((cell, cIdx) => (
                    <td
                      key={cIdx}
                      style={{ textAlign: aligns[cIdx] || "left" }}
                      className="px-3.5 py-2 text-slate-300"
                    >
                      {renderInlineText(
                        cell,
                        isLastBlock && isStreaming && rIdx === rows.length - 1 && cIdx === row.length - 1,
                        isStreaming
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Inline Markdown Renderer ──────────────────────────────────────────────────
function renderInlineText(text: string, isLast?: boolean, isStreaming?: boolean): React.ReactNode {
  if (!text) {
    if (isLast && isStreaming) {
      return (
        <span className="inline-block w-[1.5px] h-[1.1em] bg-cyan-400/90 ml-0.5 align-middle rounded-full animate-pulse pointer-events-none" aria-hidden="true" />
      );
    }
    return null;
  }

  // Regex handles: Markdown Links, Bare URLs, Inline Code, Bold-Italic, Bold (with nested support), Italic, Strikethrough
  const inlineRegex =
    /(\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]+|mailto:[^\s)]+)\)|(https?:\/\/[^\s<)]+)|`([^`]+)`|\*\*\*([^*]+)\*\*\*|\*\*(.+?)\*\*|\*([^*]+)\*|~~([^~]+)~~)/g;

  const elements: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = inlineRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      elements.push(text.substring(lastIndex, match.index));
    }

    const [, , linkText, linkHref, bareUrl, codeText, boldItalic, boldText, italicText, strikeText] = match;

    if (linkText && linkHref) {
      elements.push(
        <a
          key={match.index}
          href={linkHref}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyan-300 hover:text-cyan-200 underline underline-offset-2 decoration-cyan-400/40 hover:decoration-cyan-400 transition-colors inline-flex items-center gap-0.5"
          title={linkHref}
        >
          <span>{linkText}</span>
          <svg className="w-2.5 h-2.5 opacity-70" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </a>
      );
    } else if (bareUrl) {
      elements.push(
        <a
          key={match.index}
          href={bareUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyan-300 hover:text-cyan-200 underline underline-offset-2 decoration-cyan-400/40 hover:decoration-cyan-400 transition-colors inline-flex items-center gap-0.5 break-all"
          title={bareUrl}
        >
          <span>{bareUrl}</span>
          <svg className="w-2.5 h-2.5 opacity-70 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </a>
      );
    } else if (codeText) {
      elements.push(
        <code
          key={match.index}
          className="px-1.5 py-0.5 rounded-[0.25rem] bg-white/[0.06] text-slate-100 border border-white/[0.08] font-mono text-[11.5px] select-all tracking-tight"
        >
          {codeText}
        </code>
      );
    } else if (boldItalic) {
      elements.push(
        <strong key={match.index} className="font-bold text-white">
          <em className="italic text-slate-100">{boldItalic}</em>
        </strong>
      );
    } else if (boldText) {
      const hasInnerItalic = /\*([^*]+)\*/.test(boldText);
      elements.push(
        <strong key={match.index} className="font-semibold text-white">
          {hasInnerItalic ? renderInlineText(boldText) : boldText}
        </strong>
      );
    } else if (italicText) {
      elements.push(
        <em key={match.index} className="italic text-slate-300">
          {italicText}
        </em>
      );
    } else if (strikeText) {
      elements.push(
        <del key={match.index} className="line-through text-slate-500 decoration-slate-500">
          {strikeText}
        </del>
      );
    }

    lastIndex = inlineRegex.lastIndex;
  }

  if (lastIndex < text.length) {
    elements.push(text.substring(lastIndex));
  }

  return (
    <>
      {elements}
      {isLast && isStreaming && (
        <span className="inline-block w-[1.5px] h-[1.1em] bg-cyan-400/90 ml-0.5 align-middle rounded-full animate-pulse pointer-events-none" aria-hidden="true" />
      )}
    </>
  );
}

// ── GFM Block Parser ──────────────────────────────────────────────────────────
// ── Incremental Block Cache (Streaming Performance) ───────────────────────────
// Two-layer cache adapted from reference desktop agent pattern:
// Layer 1: Exact-string cache — same text returns same array by identity
// Layer 2: Streaming-append cache — reuses settled blocks, only re-parses suffix
const _exactBlockCache = new Map<string, BlockToken[]>();
const _EXACT_CACHE_MAX = 128;
const _appendBlockCache: { blocks: BlockToken[]; text: string }[] = [];
const _APPEND_CACHE_MAX = 4;
const _APPEND_MIN_LEN = 512;

function _blockContentLength(blocks: BlockToken[]): number {
  let len = 0;
  for (const b of blocks) {
    if (b.type === "hr") { len += 3; continue; }
    if (b.type === "codeblock") { len += b.language.length + b.content.length + 8; continue; }
    if (b.type === "table") { len += b.headers.join("").length + b.rows.reduce((s, r) => s + r.join("").length, 0); continue; }
    if (b.type === "list") { len += b.items.reduce((s, it) => s + it.text.length, 0); continue; }
    if ("content" in b) { len += b.content.length; }
  }
  return len;
}

function _lexBlocksIncrementally(text: string): BlockToken[] | null {
  const entry = _appendBlockCache.find(
    (c) => text.length > c.text.length && text.startsWith(c.text)
  );
  if (!entry) return null;

  // Drop last 2 content blocks (boundary merging safety)
  let keep = entry.blocks.length;
  for (let dropped = 0; dropped < 2 && keep > 0; dropped++) {
    if (keep > 0) keep--;
  }
  if (keep === 0) return null;

  const settled = entry.blocks.slice(0, keep);
  const settledLen = _blockContentLength(settled);
  // Approximate: re-parse from where settled blocks end
  // For safety, back up a bit in the raw text
  const backupChars = Math.min(200, settledLen);
  const reparseFrom = Math.max(0, text.lastIndexOf("\n", text.length - (text.length - entry.text.length) - backupChars));
  const suffixBlocks = _parseMarkdownBlocksRaw(text.slice(reparseFrom));
  return [...settled, ...suffixBlocks];
}

function parseMarkdownBlocksCached(rawMarkdown: string): BlockToken[] {
  // Layer 1: exact match
  const hit = _exactBlockCache.get(rawMarkdown);
  if (hit) {
    _exactBlockCache.delete(rawMarkdown);
    _exactBlockCache.set(rawMarkdown, hit);
    return hit;
  }

  // Layer 2: incremental lex (streaming append)
  const incremental = _lexBlocksIncrementally(rawMarkdown);
  const blocks = incremental ?? _parseMarkdownBlocksRaw(rawMarkdown);

  // Update append cache
  if (rawMarkdown.length >= _APPEND_MIN_LEN) {
    const idx = _appendBlockCache.findIndex((e) => rawMarkdown.startsWith(e.text));
    if (idx !== -1) _appendBlockCache.splice(idx, 1);
    _appendBlockCache.push({ blocks, text: rawMarkdown });
    if (_appendBlockCache.length > _APPEND_CACHE_MAX) _appendBlockCache.shift();
  }

  // Update exact cache
  _exactBlockCache.set(rawMarkdown, blocks);
  if (_exactBlockCache.size > _EXACT_CACHE_MAX) {
    _exactBlockCache.delete(_exactBlockCache.keys().next().value as string);
  }

  return blocks;
}

function _parseMarkdownBlocksRaw(rawMarkdown: string): BlockToken[] {
  const blocks: BlockToken[] = [];
  const lines = rawMarkdown.split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // 1. CodeBlock Fences (```lang)
    const codeMatch = line.match(/^```([a-zA-Z0-9_+#.-]*)/);
    if (codeMatch) {
      const language = (codeMatch[1] || "").toLowerCase();
      i++;
      const codeLines: string[] = [];
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      if (i < lines.length && lines[i].startsWith("```")) {
        i++; // skip closing ```
      }

      if (language !== "plan_card") {
        blocks.push({
          type: "codeblock",
          language,
          content: codeLines.join("\n"),
        });
      }
      continue;
    }

    // 2. Horizontal Rule (---, ***, ___)
    if (/^(---|___|\*\*\*)$/.test(trimmed)) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }

    // 3. Headings (# H1 to ###### H6)
    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      blocks.push({
        type: "heading",
        level: headingMatch[1].length as 1 | 2 | 3 | 4 | 5 | 6,
        content: headingMatch[2],
      });
      i++;
      continue;
    }

    // 4. Blockquotes (> quote) & GitHub-style Alerts (> [!NOTE], > [!TIP], etc.)
    if (line.startsWith(">")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        quoteLines.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      const fullQuote = quoteLines.join("\n");
      const alertMatch = fullQuote.match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\](?:\s*\n)?([\s\S]*)$/i);
      if (alertMatch) {
        const alertType = alertMatch[1].toLowerCase() as "note" | "tip" | "important" | "warning" | "caution";
        blocks.push({
          type: "alert",
          alertType,
          content: alertMatch[2].trim(),
        });
      } else {
        blocks.push({
          type: "blockquote",
          content: fullQuote,
        });
      }
      continue;
    }

    // 5. GFM Tables (| Col 1 | Col 2 |)
    if (line.includes("|") && i + 1 < lines.length && lines[i + 1].includes("|")) {
      const delimiterLine = lines[i + 1].trim();
      const isTable = /^\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?$/.test(delimiterLine);

      if (isTable) {
        const rawHeaders = line.split("|").map((h) => h.trim());
        if (rawHeaders[0] === "") rawHeaders.shift();
        if (rawHeaders[rawHeaders.length - 1] === "") rawHeaders.pop();

        const rawAligns = delimiterLine.split("|").map((d) => d.trim());
        if (rawAligns[0] === "") rawAligns.shift();
        if (rawAligns[rawAligns.length - 1] === "") rawAligns.pop();

        const aligns = rawAligns.map((d) => {
          const left = d.startsWith(":");
          const right = d.endsWith(":");
          if (left && right) return "center";
          if (right) return "right";
          return "left";
        });

        i += 2; // skip header + delimiter
        const rows: string[][] = [];

        while (i < lines.length && lines[i].includes("|")) {
          const rawRow = lines[i].split("|").map((c) => c.trim());
          if (rawRow[0] === "") rawRow.shift();
          if (rawRow[rawRow.length - 1] === "") rawRow.pop();
          rows.push(rawRow);
          i++;
        }

        blocks.push({
          type: "table",
          headers: rawHeaders,
          aligns,
          rows,
        });
        continue;
      }
    }

    // 6. Lists (Task Lists, Ordered, Unordered)
    const listMatch = line.match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
    if (listMatch) {
      const ordered = /^\d+\./.test(listMatch[2]);
      const items: { text: string; task?: { checked: boolean } }[] = [];

      while (i < lines.length) {
        const currentLine = lines[i];
        const matchItem = currentLine.match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
        if (!matchItem) break;

        let itemText = matchItem[3];
        let task: { checked: boolean } | undefined;

        const taskMatch = itemText.match(/^\[([ xX])\]\s+(.*)$/);
        if (taskMatch) {
          task = { checked: taskMatch[1].toLowerCase() === "x" };
          itemText = taskMatch[2];
        }

        items.push({ text: itemText, task });
        i++;
      }

      blocks.push({
        type: "list",
        ordered,
        items,
      });
      continue;
    }

    // 7. Regular Paragraphs
    if (trimmed.length > 0) {
      const pLines: string[] = [];
      while (
        i < lines.length &&
        lines[i].trim().length > 0 &&
        !lines[i].startsWith("#") &&
        !lines[i].startsWith(">") &&
        !lines[i].startsWith("```") &&
        !/^(\s*)([-*]|\d+\.)\s+/.test(lines[i]) &&
        !/^(---|___|\*\*\*)$/.test(lines[i].trim())
      ) {
        pLines.push(lines[i]);
        i++;
      }
      blocks.push({
        type: "paragraph",
        content: pLines.join(" "),
      });
      continue;
    }

    i++;
  }

  return blocks;
}

// Helper to safely remend open fences during streaming (Anara Streamdown Standard)
function remendStream(content: string, isStreaming?: boolean): string {
  if (!isStreaming || !content) return content;
  const fenceMatches = content.match(/```/g);
  if (fenceMatches && fenceMatches.length % 2 !== 0) {
    return content + "\n```";
  }
  return content;
}

// ── AgentMarkdown Master Component ────────────────────────────────────────────
function AgentMarkdown({
  content = "",
  isStreaming = false,
  showLineNumbersByDefault = true,
  className = "",
}: AgentMarkdownProps) {
  const safeContent = content || "";

  const activeContent = useMemo(
    () => remendStream(safeContent, isStreaming),
    [safeContent, isStreaming]
  );

  const blocks = useMemo(() => parseMarkdownBlocksCached(activeContent), [activeContent]);

  if (!safeContent) return null;

  return (
    <div
      className={`space-y-3 text-[13.5px] leading-relaxed text-slate-200 font-sans select-text ${className}`}
    >
      {blocks.map((block, idx) => {
        const isLastBlock = idx === blocks.length - 1;

        switch (block.type) {
          case "codeblock":
            return (
              <CodeBlock
                key={`code-${idx}`}
                language={block.language}
                code={block.content}
                showLineNumbers={showLineNumbersByDefault}
                isStreamingLeaf={isLastBlock && isStreaming}
              />
            );

          case "table":
            return (
              <AutoGraphTable
                key={`table-${idx}`}
                headers={block.headers}
                aligns={block.aligns}
                rows={block.rows}
                renderInlineText={renderInlineText}
                isLastBlock={isLastBlock}
                isStreaming={isStreaming}
              />
            );

          case "blockquote":
            return (
              <blockquote
                key={`quote-${idx}`}
                className="my-2 pl-3.5 py-0.5 border-l-2 border-white/20 text-slate-300/90 italic text-[13px]"
              >
                {renderInlineText(block.content, isLastBlock, isStreaming)}
              </blockquote>
            );

          case "alert": {
            const alertConfigs = {
              note: {
                label: "Note",
                border: "border-cyan-500/40",
                bg: "bg-cyan-500/[0.06]",
                text: "text-cyan-300",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" strokeWidth="1.8" />
                    <line x1="12" y1="16" x2="12" y2="12" strokeWidth="2" strokeLinecap="round" />
                    <circle cx="12" cy="8" r="1" fill="currentColor" />
                  </svg>
                ),
              },
              tip: {
                label: "Tip",
                border: "border-emerald-500/40",
                bg: "bg-emerald-500/[0.06]",
                text: "text-emerald-300",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                ),
              },
              important: {
                label: "Important",
                border: "border-purple-500/40",
                bg: "bg-purple-500/[0.06]",
                text: "text-purple-300",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                  </svg>
                ),
              },
              warning: {
                label: "Warning",
                border: "border-amber-500/40",
                bg: "bg-amber-500/[0.06]",
                text: "text-amber-300",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                ),
              },
              caution: {
                label: "Caution",
                border: "border-rose-500/40",
                bg: "bg-rose-500/[0.06]",
                text: "text-rose-300",
                icon: (
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ),
              },
            }[block.alertType] || {
              label: "Note",
              border: "border-cyan-500/40",
              bg: "bg-cyan-500/[0.06]",
              text: "text-cyan-300",
              icon: (
                <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" strokeWidth="1.8" />
                  <line x1="12" y1="16" x2="12" y2="12" strokeWidth="2" strokeLinecap="round" />
                  <circle cx="12" cy="8" r="1" fill="currentColor" />
                </svg>
              ),
            };

            return (
              <div
                key={`alert-${idx}`}
                className={`my-3 p-3 rounded-xl border ${alertConfigs.border} ${alertConfigs.bg} backdrop-blur-md transition-all`}
              >
                <div className={`flex items-center gap-2 mb-1.5 font-semibold text-[12px] ${alertConfigs.text}`}>
                  {alertConfigs.icon}
                  <span className="uppercase tracking-wider text-[11px] font-mono">{alertConfigs.label}</span>
                </div>
                <div className="text-[13px] text-slate-200 pl-6 leading-relaxed">
                  {renderInlineText(block.content, isLastBlock, isStreaming)}
                </div>
              </div>
            );
          }

          case "heading": {
            const headingClasses = {
              1: "text-lg font-extrabold text-white pt-3 pb-1 border-b border-white/10 tracking-tight",
              2: "text-base font-bold text-slate-100 pt-3 pb-0.5 tracking-tight",
              3: "text-sm font-bold text-white pt-2 pb-0.5 tracking-tight",
              4: "text-xs font-semibold uppercase tracking-wider text-slate-300 pt-1.5",
              5: "text-xs font-semibold text-slate-300 pt-1",
              6: "text-xs font-medium text-slate-400 pt-1",
            }[block.level];

            const headingChildren = renderInlineText(block.content, isLastBlock, isStreaming);
            if (block.level === 1) return <h1 key={`head-${idx}`} className={headingClasses}>{headingChildren}</h1>;
            if (block.level === 2) return <h2 key={`head-${idx}`} className={headingClasses}>{headingChildren}</h2>;
            if (block.level === 3) return <h3 key={`head-${idx}`} className={headingClasses}>{headingChildren}</h3>;
            if (block.level === 4) return <h4 key={`head-${idx}`} className={headingClasses}>{headingChildren}</h4>;
            if (block.level === 5) return <h5 key={`head-${idx}`} className={headingClasses}>{headingChildren}</h5>;
            return <h6 key={`head-${idx}`} className={headingClasses}>{headingChildren}</h6>;
          }

          case "hr":
            return <div key={`hr-${idx}`} aria-hidden className="my-3" />;

          case "list":
            return (
              <div key={`list-${idx}`} className="space-y-1 my-1.5 pl-2">
                {block.items.map((item, itemIdx) => {
                  const isLastItem = isLastBlock && itemIdx === block.items.length - 1;
                  return (
                    <div key={itemIdx} className="flex items-start gap-2.5">
                      {item.task ? (
                        <span
                          className={`mt-0.5 w-3.5 h-3.5 rounded flex items-center justify-center border transition-all ${
                            item.task.checked
                              ? "bg-emerald-500/20 border-emerald-400/60 text-emerald-400"
                              : "border-white/20 bg-white/5"
                          }`}
                        >
                          {item.task.checked && (
                            <svg className="w-2.5 h-2.5 stroke-[3]" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          )}
                        </span>
                      ) : block.ordered ? (
                        <span className="text-slate-400 font-mono text-[11px] font-bold select-none pt-0.5">
                          {itemIdx + 1}.
                        </span>
                      ) : (
                        <span className="text-slate-400 mt-1 select-none text-[8px]">•</span>
                      )}

                      <span
                        className={`flex-1 text-slate-200 leading-relaxed ${
                          item.task?.checked ? "line-through text-slate-400 decoration-slate-500" : ""
                        }`}
                      >
                        {renderInlineText(item.text, isLastItem, isStreaming)}
                      </span>
                    </div>
                  );
                })}
              </div>
            );

          case "paragraph":
          default: {
            return (
              <p
                key={`p-${idx}`}
                className="leading-relaxed text-slate-100 selection:bg-cyan-500/20"
              >
                {renderInlineText(block.content, isLastBlock, isStreaming)}
              </p>
            );
          }
        }
      })}
    </div>
  );
}

export default React.memo(AgentMarkdown);

