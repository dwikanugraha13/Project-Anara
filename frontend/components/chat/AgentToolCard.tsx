"use client";

// ── AgentToolCard — Barrel Re-export Module ─────────────────────────────────
// Decomposed from monolithic 1610-line component into focused sub-modules.
// All consumers import from this file for backward compatibility.

import React from "react";
import { AgentActionData, TodoData, SubagentTaskData } from "../hud/types";
import { AgentActionCard } from "./AgentActionCard";
import { TodoChecklistCard } from "./TodoChecklistCard";
import { SubagentCard } from "./SubagentCard";

// Re-export all sub-components for consumers
export { ThinkingCard } from "./ThinkingCard";
export { TerminalTranscript } from "./TerminalTranscript";
export { ReadFileView } from "./ReadFileView";
export { GrepResultView } from "./GrepResultView";
export { GlobResultView } from "./GlobResultView";
export { AgentActionCard, type DiffLineItem } from "./AgentActionCard";
export { ToolRunGroupCard, ExplorationGroupCard } from "./ToolRunGroupCard";
export { TodoChecklistCard } from "./TodoChecklistCard";
export { SubagentCard } from "./SubagentCard";
export { ToolRunTicker } from "./ToolRunTicker";

// Re-export shared utilities
export {
  MAX_TOOL_RENDER_CHARS,
  clampForDisplay,
  stripAnsi,
  parseAnsiToTokens,
  stripDiffFileHeaders,
  FILE_EDIT_TOOLS,
  SHELL_TOOLS,
  SEARCH_TOOLS,
  READ_TOOLS,
} from "./toolCardUtils";
export type { AnsiSpan } from "./toolCardUtils";

// ── Props interface ──
export interface AgentToolCardProps {
  action?: AgentActionData;
  todoData?: TodoData;
  subagentData?: SubagentTaskData;
  sessionId?: number;
  onOpenFile?: (filePath: string, fileName?: string) => void;
  onDismiss?: () => void;
}

// ── DEFAULT EXPORT ROUTER ────────────────────────────────────────────────
export default function AgentToolCard({
  action,
  todoData,
  subagentData,
  sessionId,
  onOpenFile,
  onDismiss,
}: AgentToolCardProps) {
  if (subagentData || action?.subagentData) {
    return <SubagentCard data={subagentData || action!.subagentData!} onOpenFile={onOpenFile} />;
  }
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
