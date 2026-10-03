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
      return "text-cyan-300 drop-shadow-[0_0_8px_rgba(34,211,238,0.2)]";
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
      return "text-cyan-400/90 font-bold select-none";
    case "diff-add":
      return "text-emerald-300 bg-emerald-500/10 block w-full px-1 rounded-xs";
    case "diff-del":
      return "text-rose-300 bg-rose-500/10 block w-full px-1 rounded-xs";
    case "diff-hunk":
      return "text-cyan-400 font-bold bg-cyan-950/30 block w-full px-1 rounded-xs";
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
          <span className="w-2 h-2 rounded-full bg-cyan-400/60 shadow-[0_0_6px_rgba(34,211,238,0.5)]" />
          <span className="font-mono font-semibold tracking-wide text-cyan-300/90 text-[10.5px]">
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
              className="cursor-pointer flex items-center gap-1 px-2 py-0.5 rounded text-[10.5px] font-medium text-cyan-300 hover:text-white bg-cyan-950/40 hover:bg-cyan-900/50 border border-cyan-500/30 transition-all shadow-[0_0_8px_rgba(34,211,238,0.15)] mr-1"
              title="Open in Right Split View (Studio)"
            >
              <svg className="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
              <span>Split View</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => setLinesActive(!linesActive)}
            className={`cursor-pointer px-1.5 py-0.5 rounded text-[10.5px] font-mono transition-colors ${
              linesActive ? "text-cyan-300 bg-cyan-950/40" : "text-slate-400 hover:text-slate-200"
            }`}
            title="Toggle line numbers"
          >
            #
          </button>
          <button
            type="button"
            onClick={() => setWrap(!wrap)}
            className={`cursor-pointer px-1.5 py-0.5 rounded text-[10.5px] transition-colors ${
              wrap ? "text-cyan-300 bg-cyan-950/40" : "text-slate-400 hover:text-slate-200"
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
                    <span className="inline-block w-2 h-3.5 bg-cyan-400 rounded-xs animate-pulse ml-1 align-middle shadow-[0_0_8px_rgba(34,211,238,0.7)]" />
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

// ── Inline Markdown Renderer ──────────────────────────────────────────────────
function renderInlineText(text: string, isLast?: boolean, isStreaming?: boolean): React.ReactNode {
  if (!text) {
    if (isLast && isStreaming) {
      return (
        <span className="inline-block w-2 h-4 bg-cyan-400 rounded-xs animate-pulse ml-1 align-text-bottom shadow-[0_0_8px_rgba(34,211,238,0.7)]" />
      );
    }
    return null;
  }

  // Regex handles: Links, Bold-Italic, Bold, Italic, Strikethrough, Inline Code
  const inlineRegex =
    /(\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]+|mailto:[^\s)]+)\)|`([^`]+)`|\*\*\*([^*]+)\*\*\*|\*\*([^*]+)\*\*|\*([^*]+)\*|~~([^~]+)~~)/g;

  const elements: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = inlineRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      elements.push(text.substring(lastIndex, match.index));
    }

    const [, , linkText, linkHref, codeText, boldItalic, boldText, italicText, strikeText] = match;

    if (linkText && linkHref) {
      elements.push(
        <a
          key={match.index}
          href={linkHref}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyan-400 hover:text-cyan-300 underline underline-offset-2 decoration-cyan-500/40 hover:decoration-cyan-300 transition-colors inline-flex items-center gap-0.5"
        >
          {linkText}
          <svg className="w-2.5 h-2.5 opacity-70" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
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
          className="px-1.5 py-0.5 rounded-md bg-white/[0.08] text-cyan-200 border border-white/10 font-mono text-[11.5px] select-all"
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
      elements.push(
        <strong key={match.index} className="font-semibold text-white">
          {boldText}
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
        <span className="inline-block w-2 h-4 bg-cyan-400 rounded-xs animate-pulse ml-1 align-text-bottom shadow-[0_0_8px_rgba(34,211,238,0.7)]" />
      )}
    </>
  );
}

// ── GFM Block Parser ──────────────────────────────────────────────────────────
function parseMarkdownBlocks(rawMarkdown: string): BlockToken[] {
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

    // 4. Blockquotes (> quote)
    if (line.startsWith(">")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        quoteLines.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      blocks.push({
        type: "blockquote",
        content: quoteLines.join("\n"),
      });
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

  const blocks = useMemo(() => parseMarkdownBlocks(activeContent), [activeContent]);

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
              <div
                key={`table-${idx}`}
                className="my-3 overflow-x-auto rounded-xl border border-white/10 bg-[#060913]/60 backdrop-blur-md shadow-lg"
              >
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/10 bg-white/[0.04]">
                      {block.headers.map((h, hIdx) => (
                        <th
                          key={hIdx}
                          style={{ textAlign: block.aligns[hIdx] || "left" }}
                          className="px-3.5 py-2 font-semibold text-cyan-200 tracking-wide"
                        >
                          {renderInlineText(h)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {block.rows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-white/[0.02] transition-colors">
                        {row.map((cell, cIdx) => (
                          <td
                            key={cIdx}
                            style={{ textAlign: block.aligns[cIdx] || "left" }}
                            className="px-3.5 py-2 text-slate-300"
                          >
                            {renderInlineText(
                              cell,
                              isLastBlock && isStreaming && rIdx === block.rows.length - 1 && cIdx === row.length - 1,
                              isStreaming
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );

          case "blockquote":
            return (
              <blockquote
                key={`quote-${idx}`}
                className="my-3 pl-3.5 py-1 border-l-2 border-cyan-400/70 bg-cyan-950/20 rounded-r-lg text-slate-300 italic text-[13px]"
              >
                {renderInlineText(block.content, isLastBlock, isStreaming)}
              </blockquote>
            );

          case "heading": {
            const headingClasses = {
              1: "text-lg font-extrabold text-white pt-3 pb-1 border-b border-white/10 tracking-tight",
              2: "text-base font-bold text-cyan-200 pt-3 pb-0.5 tracking-tight",
              3: "text-sm font-bold text-white pt-2 pb-0.5 tracking-tight",
              4: "text-xs font-semibold uppercase tracking-wider text-cyan-300/90 pt-1.5",
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
            return <hr key={`hr-${idx}`} className="my-4 border-t border-white/10" />;

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
                        <span className="text-cyan-400/80 font-mono text-[11px] font-bold select-none pt-0.5">
                          {itemIdx + 1}.
                        </span>
                      ) : (
                        <span className="text-cyan-400 mt-1 select-none text-[8px]">•</span>
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
          default:
            return (
              <p key={`p-${idx}`} className="leading-relaxed">
                {renderInlineText(block.content, isLastBlock, isStreaming)}
              </p>
            );
        }
      })}
    </div>
  );
}

export default React.memo(AgentMarkdown);

