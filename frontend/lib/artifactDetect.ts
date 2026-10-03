"use client";

/**
 * artifactDetect.ts — Anara Artifact & Document Detection Engine
 *
 * Decides when a fenced code block or document in an assistant message is
 * substantial, self-contained content that deserves promotion to the right
 * contextual split-pane rather than remaining trapped as a giant inline block.
 *
 * Thresholds:
 * - HTML Documents (with <html>, <head>, or <body>): >= 160 characters
 * - Standalone SVG Graphics: >= 1500 characters
 * - Code files: >= 48 lines OR >= 2500 characters
 */

export type ArtifactKind = "code" | "html" | "svg";

export interface ArtifactDetection {
  kind: ArtifactKind;
  language: string;
  title: string;
  lineCount: number;
}

const HTML_DOC_RE = /<!doctype\s+html|<html[\s>]|<head[\s>]|<body[\s>]/i;
const SVG_TAG_RE = /<svg[\s>]/i;

const CODE_DECLARATION_RE =
  /(?:^|\n)\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|struct|interface|enum|trait|impl|def|fn)\s+([A-Za-z_$][\w$]*)/;

const FILENAME_COMMENT_RE =
  /^\s*(?:\/\/|#|--|<!--|\/\*)\s*([\w./-]+\.[a-z0-9]{1,8})\b/i;

const NON_ARTIFACT_LANGUAGES = new Set([
  "",
  "text",
  "txt",
  "plain",
  "plaintext",
  "stdout",
  "stderr",
  "console",
  "output",
  "log",
  "logs",
  "diff",
  "patch",
  "mermaid",
]);

export function countCodeLines(text: string): number {
  let lines = 1;
  let index = text.indexOf("\n");
  while (index !== -1) {
    lines += 1;
    index = text.indexOf("\n", index + 1);
  }
  return lines;
}

export function detectArtifact(
  language?: string,
  code?: string
): ArtifactDetection | null {
  const trimmed = (code ?? "").trim();
  if (!trimmed) return null;

  const cleanLang = (language || "").trim().toLowerCase();
  if (NON_ARTIFACT_LANGUAGES.has(cleanLang)) return null;

  const lines = countCodeLines(trimmed);
  const chars = trimmed.length;

  // 1. HTML Documents
  if (cleanLang === "html" || cleanLang === "htm" || cleanLang === "xhtml") {
    if (HTML_DOC_RE.test(trimmed) && chars >= 160) {
      const titleMatch = /<title[^>]*>([\s\S]*?)<\/title>/i.exec(trimmed);
      const title = titleMatch ? titleMatch[1].trim().slice(0, 60) : "index.html";
      return { kind: "html", language: "html", title, lineCount: lines };
    }
  }

  // 2. Standalone SVG
  if (cleanLang === "svg" || (SVG_TAG_RE.test(trimmed) && chars >= 1500)) {
    return { kind: "svg", language: "svg", title: "graphic.svg", lineCount: lines };
  }

  // 3. Substantial Source Code (> 48 lines or > 2500 chars)
  if (lines >= 48 || chars >= 2500) {
    const head = trimmed.slice(0, 1500);
    const filenameMatch = FILENAME_COMMENT_RE.exec(head);
    let title = filenameMatch ? filenameMatch[1] : "";

    if (!title) {
      const declMatch = CODE_DECLARATION_RE.exec(head);
      if (declMatch) {
        title = `${declMatch[1]}.${cleanLang || "ts"}`;
      } else {
        title = `snippet.${cleanLang || "code"}`;
      }
    }

    return { kind: "code", language: cleanLang, title, lineCount: lines };
  }

  return null;
}

export default detectArtifact;
