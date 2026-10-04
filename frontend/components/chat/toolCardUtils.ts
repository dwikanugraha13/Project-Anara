"use client";

// ── CANONICAL TOOL TAXONOMY ─────────────────────────────────────────────────
// Shared utilities and constants for all agent tool card sub-components.

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
    .replace(/\x1B(?:\[@-Z\\\\-_]|\[[0-?]*[ -/]*[@-~])/g, "")
    .replace(/\u001b\[[0-9;]*[a-zA-Z]/g, "");
}

export interface AnsiSpan {
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
