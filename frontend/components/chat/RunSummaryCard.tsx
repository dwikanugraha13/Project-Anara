"use client";

import React, { useMemo } from "react";
import { AgentActionData } from "../hud/types";

export interface RunSummaryCardProps {
  actions: AgentActionData[];
  durationSec?: number;
  modelName?: string;
  totalTokens?: number;
}

/**
 * RunSummaryCard.tsx — Turn Run Summary & Execution Metrics Card
 *
 * Synthesizes multi-step tool runs into clean grammatical clauses:
 * "Edited 2 files · Ran 3 commands · Explored 4 files (2.4s)"
 * Following the Anara Flat Hairline Liquid Glass design system.
 */
export function RunSummaryCard({
  actions,
  durationSec,
  modelName,
  totalTokens,
}: RunSummaryCardProps) {
  const summaryClause = useMemo(() => {
    if (!actions || actions.length === 0) return null;

    let editCount = 0;
    let runCount = 0;
    let exploreCount = 0;
    let searchCount = 0;

    const editedFiles = new Set<string>();

    for (const a of actions) {
      const tool = (a.toolName || "").toLowerCase();
      if (tool.includes("write") || tool.includes("edit") || tool.includes("patch")) {
        editCount++;
        if (a.filePath) editedFiles.add(a.filePath.split(/[/\\]/).pop() || a.filePath);
      } else if (tool.includes("terminal") || tool.includes("shell") || tool.includes("cli") || tool.includes("code")) {
        runCount++;
      } else if (tool.includes("search") || tool.includes("grep")) {
        searchCount++;
      } else if (tool.includes("read") || tool.includes("scan") || tool.includes("list")) {
        exploreCount++;
      }
    }

    const clauses: string[] = [];

    if (editCount > 0) {
      const filesCount = editedFiles.size || editCount;
      clauses.push(`Edited ${filesCount} file${filesCount > 1 ? "s" : ""}`);
    }
    if (runCount > 0) {
      clauses.push(`Ran ${runCount} command${runCount > 1 ? "s" : ""}`);
    }
    if (exploreCount > 0) {
      clauses.push(`Explored ${exploreCount} file${exploreCount > 1 ? "s" : ""}`);
    }
    if (searchCount > 0) {
      clauses.push(`Searched ${searchCount} quer${searchCount > 1 ? "ies" : "y"}`);
    }

    if (clauses.length === 0) {
      clauses.push(`Completed ${actions.length} action${actions.length > 1 ? "s" : ""}`);
    }

    return clauses.join(" · ");
  }, [actions]);

  if (!summaryClause) return null;

  return (
    <div className="my-1.5 flex items-center justify-between rounded-lg border border-white/[0.06] bg-black/30 px-3 py-1.5 font-mono text-[11px] text-slate-400 backdrop-blur-md">
      <div className="flex items-center gap-2 truncate">
        <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-400/80 shrink-0" />
        <span className="truncate text-slate-300 font-medium">{summaryClause}</span>
      </div>

      <div className="flex items-center gap-2.5 text-[10px] text-slate-500 shrink-0 ml-3">
        {durationSec !== undefined && durationSec > 0 && (
          <span className="tabular-nums">
            {durationSec < 1 ? `${Math.round(durationSec * 1000)}ms` : `${durationSec.toFixed(1)}s`}
          </span>
        )}
        {modelName && (
          <span className="rounded bg-white/[0.04] px-1.5 py-0.5 text-slate-400">
            {modelName}
          </span>
        )}
        {totalTokens !== undefined && totalTokens > 0 && (
          <span className="tabular-nums">
            {totalTokens.toLocaleString()} tokens
          </span>
        )}
      </div>
    </div>
  );
}

export default RunSummaryCard;
