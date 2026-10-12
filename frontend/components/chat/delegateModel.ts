"use client";

import type { SubagentProgressItem, SubagentStatus } from "../hud/types";

/**
 * DelegateRowStatus represents the state of a delegated child task:
 * - running: live execution in progress
 * - completed: task finished successfully
 * - error: task crashed or reported an error
 * - stopped: task cancelled or interrupted
 * - dispatched: background task outlived turn, parked without active stream
 * - queued: queued awaiting worker assignment
 */
export type DelegateRowStatus =
  | SubagentStatus
  | "running"
  | "completed"
  | "error"
  | "failed"
  | "stopped"
  | "interrupted"
  | "timed_out"
  | "dispatched"
  | "queued";

/**
 * A delegation row joins the goal dispatched by the orchestrator,
 * live subagent execution progress, and settled results.
 */
export interface DelegateRow {
  id: string;
  goal: string;
  status: DelegateRowStatus;
  activity: string[];
  durationSeconds?: number;
  model?: string;
  sessionId?: string;
  keyFindings?: string[];
  referencedFiles?: string[];
  findings?: string;
  error?: string;
  depth?: number;
  startedAt?: number;
}

// ── UTILITY HELPERS ──────────────────────────────────────────────────────────

export function parseMaybeObject(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  if (typeof value !== "string" || !value.trim()) {
    return {};
  }
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export function numberValue(value: unknown): number | null {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export function firstStringField(record: Record<string, unknown>, keys: readonly string[]): string {
  for (const key of keys) {
    const val = record[key];
    if (typeof val === "string" && val.trim()) {
      return val.trim();
    }
  }
  return "";
}

export function normalize(v: unknown): string {
  if (typeof v === "string") return v.trim().toLowerCase();
  if (v == null) return "";
  return String(v).trim().toLowerCase();
}

export function isDelegateRowLive(status: DelegateRowStatus): boolean {
  return status === "running" || status === "queued";
}

export function formatElapsed(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0s";
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
}

export function formatDurationSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "";
  }
  if (seconds < 1) {
    const ms = Math.max(1, Math.round(seconds * 1000));
    return `${ms}ms`;
  }
  if (seconds < 60) {
    return `${seconds.toFixed(seconds >= 10 ? 0 : 1)}s`;
  }
  const wholeSeconds = Math.round(seconds);
  const minutes = Math.floor(wholeSeconds / 60);
  const remSeconds = wholeSeconds % 60;
  if (minutes < 60) {
    return remSeconds ? `${minutes}m ${remSeconds}s` : `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  return remMinutes ? `${hours}h ${remMinutes}m` : `${hours}h`;
}

// ── STATUS NORMALIZATION ────────────────────────────────────────────────────

export function normalizeDelegateStatus(status: string): DelegateRowStatus {
  const s = normalize(status);
  if (s === "" || s === "ok" || s === "completed" || s === "success" || s === "done") {
    return "completed";
  }
  if (s === "running" || s === "in_progress" || s === "executing") {
    return "running";
  }
  if (s === "queued" || s === "pending") {
    return "queued";
  }
  if (s === "dispatched") {
    return "dispatched";
  }
  if (s === "stopped" || s === "interrupted" || s === "cancelled") {
    return "stopped";
  }
  if (s === "timed_out" || s === "timeout") {
    return "timed_out";
  }
  if (s === "error" || s === "failed" || s === "failure") {
    return "error";
  }
  return "completed";
}

// ── PARSE GOALS FROM CALL ARGS ──────────────────────────────────────────────

export function delegateGoals(args: unknown): string[] {
  const record = parseMaybeObject(args);
  const tasks = Array.isArray(record.tasks) ? record.tasks : [];

  if (tasks.length > 0) {
    return tasks.map((task, index) => {
      const taskRecord = parseMaybeObject(task);
      return firstStringField(taskRecord, ["goal", "title", "description"]) || `Task ${index + 1}`;
    });
  }

  const singleGoal = firstStringField(record, ["goal", "title", "action", "mission"]);
  return singleGoal ? [singleGoal] : [];
}

function resultRows(result: unknown): Record<string, unknown>[] {
  const record = parseMaybeObject(result);
  const results = Array.isArray(record.results) ? record.results : [];
  return results.map(parseMaybeObject);
}

function dispatchedGoals(result: unknown): string[] {
  const record = parseMaybeObject(result);
  if (firstStringField(record, ["status"]) !== "dispatched") {
    return [];
  }
  return Array.isArray(record.goals)
    ? record.goals.filter((g): g is string => typeof g === "string")
    : [];
}

// ── BUILD ROWS FROM CALL ARGS & RESULT ──────────────────────────────────────

export function delegateRowsFromCall(
  args: unknown,
  result: unknown,
  toolCallId = ""
): DelegateRow[] {
  const goals = delegateGoals(args);
  const finished = resultRows(result);
  const dispatched = dispatchedGoals(result);
  const titles =
    goals.length > 0
      ? goals
      : dispatched.length > 0
      ? dispatched
      : finished.length > 0
      ? finished.map((_, i) => `Delegated task ${i + 1}`)
      : ["Delegated mission"];

  const idleStatus: DelegateRowStatus = result === undefined ? "running" : "dispatched";

  return titles.map((goal, index) => {
    const entry = finished[index];
    const summary = entry ? firstStringField(entry, ["summary", "findings", "executive_summary"]) : "";
    const rawStatus = entry ? firstStringField(entry, ["status"]) : "";
    const durVal = entry ? numberValue(entry.duration_seconds ?? entry.duration_sec) : null;
    const model = entry ? firstStringField(entry, ["model"]) : "";
    const err = entry ? firstStringField(entry, ["error", "error_message"]) : "";

    return {
      id: `${toolCallId || "del"}:${index}`,
      goal,
      status: entry ? normalizeDelegateStatus(rawStatus) : idleStatus,
      activity: summary ? [summary] : [],
      durationSeconds: durVal ?? undefined,
      model: model || undefined,
      error: err || undefined,
      findings: summary || undefined,
    };
  });
}

// ── MERGE LIVE PROGRESS OVER CALL ROWS ──────────────────────────────────────

export function mergeDelegateRows(
  rows: readonly DelegateRow[],
  live: readonly SubagentProgressItem[],
  toolCallId = ""
): DelegateRow[] {
  if (!live || live.length === 0) {
    return [...rows];
  }

  const unclaimed = [...live];

  const claim = (predicate: (candidate: SubagentProgressItem) => boolean): SubagentProgressItem | undefined => {
    const idx = unclaimed.findIndex(predicate);
    return idx >= 0 ? unclaimed.splice(idx, 1)[0] : undefined;
  };

  const prefix = toolCallId ? `delegate-tool:${toolCallId}:` : "";
  const byId = rows.map((_row, index) =>
    prefix ? claim((c) => c.id === `${prefix}${index}` || c.taskId === `${prefix}${index}`) : undefined
  );
  const byGoal = rows.map((row, index) =>
    byId[index] ?? claim((c) => normalize(c.goal) === normalize(row.goal) || normalize(c.title) === normalize(row.goal))
  );
  const sameShape = rows.length === live.length;

  return rows.map((row, index) => {
    const matched =
      byGoal[index] ??
      claim((c) => c.taskId === String(index) || c.taskId === String(index + 1)) ??
      (sameShape ? unclaimed.shift() : undefined);
    if (!matched) return row;

    return {
      ...row,
      id: matched.taskId || matched.id || row.id,
      goal: matched.goal || matched.title || row.goal,
      status: matched.status ? normalizeDelegateStatus(matched.status) : row.status,
      activity: matched.activity && matched.activity.length > 0 ? matched.activity : row.activity,
      durationSeconds: matched.durationSeconds ?? matched.durationSec ?? row.durationSeconds,
      model: matched.model || row.model,
      sessionId: matched.sessionId || matched.childSessionId || row.sessionId,
      keyFindings: matched.keyFindings ?? row.keyFindings,
      referencedFiles: matched.referencedFiles ?? row.referencedFiles,
      findings: matched.findings ?? row.findings,
      error: matched.error ?? row.error,
      depth: matched.depth ?? row.depth,
      startedAt: matched.startedAt ?? row.startedAt,
    };
  });
}
