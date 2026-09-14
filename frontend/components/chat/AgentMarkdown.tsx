"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";

interface AgentMarkdownProps {
  content: string;
  isStreaming?: boolean;
}

function AgentMarkdown({ content, isStreaming }: AgentMarkdownProps) {
  if (!content) return null;

  // Fluid Token Stream Consumer (smooth 60fps running text interpolation)
  const [streamLength, setStreamLength] = useState(() => (!isStreaming ? content.length : Math.min(12, content.length)));
  const animRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isStreaming) {
      setStreamLength(content.length);
      if (animRef.current) cancelAnimationFrame(animRef.current);
      return;
    }

    const step = () => {
      setStreamLength((prev) => {
        if (prev >= content.length) return prev;
        const diff = content.length - prev;
        // Adaptive cadence: smooth character pacing with catch-up
        const increment = diff > 100 ? 8 : diff > 40 ? 4 : diff > 15 ? 2 : 1;
        return Math.min(content.length, prev + increment);
      });
      animRef.current = requestAnimationFrame(step);
    };

    animRef.current = requestAnimationFrame(step);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [content, isStreaming]);

  const activeContent = isStreaming && streamLength < content.length
    ? content.slice(0, streamLength)
    : content;

  // Split into tokens: code blocks vs standard markdown text (memoized)
  const tokens = useMemo(() => parseMarkdownTokens(activeContent), [activeContent]);

  return (
    <div className="space-y-2.5 text-[13.5px] leading-relaxed text-slate-200 font-sans select-text">
      {tokens.map((tok, i) => {
        const isLastToken = i === tokens.length - 1;
        if (tok.type === "codeblock") {
          return (
            <React.Fragment key={i}>
              <CodeBlock language={tok.language} code={tok.content} />
              {isLastToken && isStreaming && (
                <span className="inline-block w-2 h-4 bg-cyan-400 rounded-xs animate-pulse ml-1 align-middle shadow-[0_0_8px_rgba(34,211,238,0.7)]" />
              )}
            </React.Fragment>
          );
        }
        return (
          <FormattedParagraph
            key={i}
            raw={tok.content}
            isLast={isLastToken}
            isStreaming={isStreaming}
          />
        );
      })}
    </div>
  );
}

export default React.memo(AgentMarkdown);

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-white/10 bg-black/60 backdrop-blur-md font-mono text-xs shadow-xl">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-white/[0.04] border-b border-white/5 text-[11px] text-slate-400">
        <span className="font-semibold text-cyan-300/90 lowercase">{language || "code"}</span>
        <button
          onClick={handleCopy}
          className="text-slate-400 hover:text-white transition-colors cursor-pointer text-[10.5px] flex items-center gap-1"
        >
          {copied ? "✓ Tersalin" : "Salin"}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto custom-scrollbar text-slate-200 leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function FormattedParagraph({
  raw,
  isLast,
  isStreaming,
}: {
  raw: string;
  isLast?: boolean;
  isStreaming?: boolean;
}) {
  const lines = raw.split("\n");

  return (
    <div className="space-y-1">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        const isLastLine = idx === lines.length - 1;
        const cursorNode =
          isLast && isStreaming && isLastLine ? (
            <span
              className="inline-block w-2 h-4 bg-cyan-400 rounded-xs animate-pulse ml-1 align-text-bottom shadow-[0_0_8px_rgba(34,211,238,0.7)] select-none"
              aria-hidden="true"
            />
          ) : null;

        if (!trimmed) {
          return <div key={idx} className="h-1.5" />;
        }

        // Headings (#, ##, ###)
        if (trimmed.startsWith("### ")) {
          return (
            <h4 key={idx} className="text-sm font-bold text-white pt-2 pb-0.5 tracking-tight">
              {renderInlineMarkdown(trimmed.replace(/^###\s+/, ""))}
              {cursorNode}
            </h4>
          );
        }
        if (trimmed.startsWith("## ")) {
          return (
            <h3 key={idx} className="text-base font-bold text-cyan-200 pt-3 pb-1 tracking-tight">
              {renderInlineMarkdown(trimmed.replace(/^##\s+/, ""))}
              {cursorNode}
            </h3>
          );
        }
        if (trimmed.startsWith("# ")) {
          return (
            <h2 key={idx} className="text-lg font-extrabold text-white pt-3 pb-1 tracking-tight">
              {renderInlineMarkdown(trimmed.replace(/^#\s+/, ""))}
              {cursorNode}
            </h2>
          );
        }

        // List item bullet (- or *)
        if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
          const itemText = trimmed.replace(/^[-*]\s+/, "");
          return (
            <div key={idx} className="flex items-start gap-2 pl-2">
              <span className="text-cyan-400 mt-1 select-none text-[8px]">•</span>
              <span className="flex-1 text-slate-200 leading-relaxed">
                {renderInlineMarkdown(itemText)}
                {cursorNode}
              </span>
            </div>
          );
        }

        // Numbered list (1. , 2. )
        const numMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
        if (numMatch) {
          return (
            <div key={idx} className="flex items-start gap-2 pl-2">
              <span className="text-cyan-400/80 font-mono text-[11px] font-bold select-none pt-0.5">
                {numMatch[1]}.
              </span>
              <span className="flex-1 text-slate-200 leading-relaxed">
                {renderInlineMarkdown(numMatch[2])}
                {cursorNode}
              </span>
            </div>
          );
        }

        // Standard line
        return (
          <p key={idx} className="leading-relaxed">
            {renderInlineMarkdown(line)}
            {cursorNode}
          </p>
        );
      })}
    </div>
  );
}

function renderInlineMarkdown(text: string): React.ReactNode[] {
  // Regex for bold (**bold**), inline code (`code`), italic (*italic*)
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;

  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(text.substring(lastIdx, match.index));
    }
    const token = match[0];
    if (token.startsWith("**") && token.endsWith("**")) {
      parts.push(
        <strong key={match.index} className="font-semibold text-white">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith("`") && token.endsWith("`")) {
      parts.push(
        <code
          key={match.index}
          className="px-1.5 py-0.5 rounded-md bg-white/[0.08] text-cyan-200 border border-white/10 font-mono text-[11.5px] select-all"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith("*") && token.endsWith("*")) {
      parts.push(
        <em key={match.index} className="italic text-slate-300">
          {token.slice(1, -1)}
        </em>
      );
    }
    lastIdx = regex.lastIndex;
  }

  if (lastIdx < text.length) {
    parts.push(text.substring(lastIdx));
  }

  return parts.length > 0 ? parts : [text];
}

interface Token {
  type: "text" | "codeblock";
  content: string;
  language: string;
}

function parseMarkdownTokens(text: string): Token[] {
  const tokens: Token[] = [];
  const regex = /```(\w+)?\n([\s\S]*?)(?:```|$)/g;

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({
        type: "text",
        content: text.slice(lastIndex, match.index),
        language: "",
      });
    }

    const lang = (match[1] || "").toLowerCase();
    if (lang === "plan_card") {
      // Filter out legacy plan_card JSON blocks so raw JSON never clutters the chat
      lastIndex = regex.lastIndex;
      continue;
    }

    tokens.push({
      type: "codeblock",
      language: match[1] || "",
      content: (match[2] || "").replace(/\n$/, ""),
    });

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    tokens.push({
      type: "text",
      content: text.slice(lastIndex),
      language: "",
    });
  }

  return tokens;
}
