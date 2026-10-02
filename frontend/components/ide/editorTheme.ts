import { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { HighlightStyle } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { php } from "@codemirror/lang-php";
import { json } from "@codemirror/lang-json";
import { html } from "@codemirror/lang-html";
import { css } from "@codemirror/lang-css";
import { markdown } from "@codemirror/lang-markdown";
import { yaml } from "@codemirror/lang-yaml";
import { sql } from "@codemirror/lang-sql";

export function getLanguageExtension(ext: string): Extension {
  const clean = (ext || "").toLowerCase().replace(/^\./, "");
  switch (clean) {
    case "js":
    case "jsx":
    case "mjs":
    case "cjs":
      return javascript({ jsx: true, typescript: false });
    case "ts":
    case "tsx":
      return javascript({ jsx: true, typescript: true });
    case "py":
      return python();
    case "php":
      return php();
    case "json":
      return json();
    case "html":
    case "htm":
      return html();
    case "css":
    case "scss":
    case "less":
      return css();
    case "md":
    case "markdown":
    case "mdown":
      return markdown();
    case "yaml":
    case "yml":
      return yaml();
    case "sql":
      return sql();
    default:
      return [];
  }
}

// ── Anara Dark Obsidian Liquid Glass Theme for CodeMirror 6 ──
export const anaraObsidianTheme = EditorView.theme(
  {
    "&": {
      color: "#f1f5f9",
      backgroundColor: "#070b16",
      height: "100%",
      fontSize: "12.5px",
      fontFamily: "var(--font-mono), 'JetBrains Mono', Consolas, monospace",
    },
    ".cm-content": {
      caretColor: "#22d3ee",
      fontFamily: "var(--font-mono), 'JetBrains Mono', Consolas, monospace",
      lineHeight: "20px",
      padding: "8px 0",
    },
    "&.cm-focused .cm-cursor, .cm-cursor": {
      borderLeftColor: "#22d3ee !important",
      borderLeftWidth: "2px !important",
      transition: "left 60ms ease-out, top 60ms ease-out",
    },
    ".cm-dropCursor": {
      borderLeftColor: "#22d3ee !important",
      borderLeftWidth: "2px !important",
    },
    "&.cm-focused .cm-selectionBackground, ::selection": {
      backgroundColor: "rgba(34, 211, 238, 0.18) !important",
    },
    ".cm-gutters": {
      backgroundColor: "#070b16 !important",
      color: "#475569 !important",
      borderRight: "1px solid rgba(255, 255, 255, 0.08) !important",
      fontSize: "12px",
    },
    ".cm-gutter": {
      backgroundColor: "#070b16 !important",
    },
    ".cm-lineNumbers": {
      backgroundColor: "#070b16 !important",
    },
    ".cm-gutterElement": {
      color: "#475569 !important",
    },
    ".cm-activeLineGutter, .cm-activeLineGutter .cm-gutterElement": {
      backgroundColor: "rgba(255, 255, 255, 0.04) !important",
      color: "#f8fafc !important",
      fontWeight: "600 !important",
    },
    ".cm-activeLine": {
      backgroundColor: "rgba(255, 255, 255, 0.03) !important",
    },
    ".cm-foldPlaceholder": {
      backgroundColor: "rgba(255, 255, 255, 0.1)",
      border: "none",
      color: "#94a3b8",
      padding: "0 4px",
      borderRadius: "4px",
    },
    ".cm-tooltip": {
      backgroundColor: "#0b101b !important",
      border: "1px solid rgba(255, 255, 255, 0.15) !important",
      borderRadius: "8px",
      boxShadow: "0 8px 32px rgba(0,0,0,0.8)",
    },
    ".cm-searchMatch": {
      backgroundColor: "rgba(234, 179, 8, 0.3) !important",
      outline: "1px solid rgba(234, 179, 8, 0.6)",
    },
    ".cm-searchMatch.cm-searchMatch-selected": {
      backgroundColor: "rgba(34, 211, 238, 0.35) !important",
      outline: "1px solid #22d3ee",
    },
    ".cm-scroller": {
      fontFamily: "inherit",
      overflow: "auto",
    },
    ".cm-diff-inserted, .cm-insertedLine": {
      backgroundColor: "rgba(16, 185, 129, 0.15) !important",
    },
    ".cm-diff-deleted, .cm-deletedLine": {
      backgroundColor: "rgba(244, 63, 94, 0.18) !important",
    },
    ".cm-diff-chunk": {
      borderLeft: "2px solid rgba(34, 211, 238, 0.6) !important",
    },
  },
  { dark: true }
);

// ── VS Code Dark+ Highlighting Tokens ──
export const vsCodeDarkPlusHighlightStyle = HighlightStyle.define([
  { tag: t.keyword, color: "#c586c0" },
  { tag: [t.name, t.deleted, t.character, t.macroName], color: "#9cdcfe" },
  { tag: [t.propertyName], color: "#9cdcfe" },
  { tag: [t.variableName], color: "#9cdcfe" },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], color: "#dcdcaa" },
  { tag: [t.typeName, t.className, t.changed, t.annotation, t.modifier, t.self], color: "#4ec9b0" },
  { tag: [t.number], color: "#b5cea8" },
  { tag: [t.string, t.inserted, t.special(t.string)], color: "#ce9178" },
  { tag: [t.regexp, t.escape], color: "#d16969" },
  { tag: [t.operator, t.operatorKeyword], color: "#d4d4d4" },
  { tag: [t.punctuation, t.bracket], color: "#d4d4d4" },
  { tag: [t.meta, t.comment], color: "#6a9955", fontStyle: "italic" },
  { tag: t.heading, color: "#4ec9b0", fontWeight: "bold" },
  { tag: t.link, color: "#3794ff", textDecoration: "underline" },
]);
