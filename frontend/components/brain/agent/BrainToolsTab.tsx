"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { BACKEND_URL, ToolItem, SubagentTask, AutonomousTaskInfo } from "../types";
import {
  MasterDetail,
  ListColumn,
  DetailColumn,
  CapRow,
  SortButton,
  ToolChip,
} from "../shared/MasterDetail";

export interface ToolsetInfo {
  id: string;
  title: string;
  description: string;
  icon: string;
  category: string;
  default_enabled: boolean;
  tools: string[];
  enabled: boolean;
  tool_count: number;
  total_calls?: number;
  tool_calls?: Record<string, number>;
  configured?: boolean;
}

export default function BrainToolsTab() {
  const [toolsets, setToolsets] = useState<ToolsetInfo[]>([]);
  const [toolsCatalog, setToolsCatalog] = useState<ToolItem[]>([]);
  const [subagentTasks, setSubagentTasks] = useState<SubagentTask[]>([]);
  const [autoTasks, setAutoTasks] = useState<AutonomousTaskInfo[]>([]);
  const [toolsSubTab, setToolsSubTab] = useState<"toolsets" | "autonomous" | "subagents">("toolsets");
  const [selectedToolsetId, setSelectedToolsetId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortDesc, setSortDesc] = useState(true);
  const [expandedToolSchema, setExpandedToolSchema] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // New Autonomous Task Form State
  const [isAddTaskOpen, setIsAddTaskOpen] = useState(false);
  const [taskName, setTaskName] = useState("");
  const [taskPrompt, setTaskPrompt] = useState("");
  const [taskInterval, setTaskInterval] = useState(3600);
  const [taskTrust, setTaskTrust] = useState<"supervised" | "semi_autonomous" | "full_autonomous">("supervised");
  const [taskChannel, setTaskChannel] = useState("telegram");
  const [isTriggering, setIsTriggering] = useState<string | null>(null);
  const [deleteTaskConfirm, setDeleteTaskConfirm] = useState<{ id: string; name: string } | null>(null);

  const fetchToolsets = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/toolsets`);
      if (res.ok) {
        const data = await res.json();
        setToolsets(data.toolsets || []);
      }
    } catch (e) {
      console.warn("[BrainTools] Error fetching toolsets:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchToolsAndTasks = useCallback(async () => {
    try {
      const [toolsRes, tasksRes, autoRes] = await Promise.allSettled([
        fetch(`${BACKEND_URL}/api/agent/tools`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${BACKEND_URL}/api/agent/subagent/tasks`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${BACKEND_URL}/api/agent/autonomous/tasks`).then((r) => (r.ok ? r.json() : null)),
      ]);
      if (toolsRes.status === "fulfilled" && toolsRes.value) {
        setToolsCatalog(toolsRes.value.tools || []);
      }
      if (tasksRes.status === "fulfilled" && tasksRes.value) {
        setSubagentTasks(tasksRes.value.tasks || []);
      }
      if (autoRes.status === "fulfilled" && autoRes.value) {
        setAutoTasks(autoRes.value.tasks || []);
      }
    } catch (err) {
      console.warn("[BrainToolsTab] Fetch error:", err);
    }
  }, []);

  useEffect(() => {
    fetchToolsets();
    fetchToolsAndTasks();
  }, [fetchToolsets, fetchToolsAndTasks]);

  const handleToggleToolset = async (toolsetId: string, currentEnabled: boolean) => {
    setTogglingId(toolsetId);
    const newEnabled = !currentEnabled;
    // Optimistic UI update
    setToolsets((prev) =>
      prev.map((ts) => (ts.id === toolsetId ? { ...ts, enabled: newEnabled } : ts))
    );

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/toolsets/${toolsetId}/toggle`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: newEnabled }),
      });
      if (!res.ok) {
        fetchToolsets();
      }
    } catch {
      fetchToolsets();
    } finally {
      setTogglingId(null);
    }
  };

  const handleCreateAutoTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskName.trim() || !taskPrompt.trim()) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/agent/autonomous/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: taskName.trim(),
          prompt: taskPrompt.trim(),
          interval_seconds: Number(taskInterval),
          trust_level: taskTrust,
          target_channel: taskChannel,
        }),
      });
      if (res.ok) {
        setTaskName("");
        setTaskPrompt("");
        setIsAddTaskOpen(false);
        fetchToolsAndTasks();
      }
    } catch {}
  };

  const handleTriggerTaskNow = async (taskId: string) => {
    setIsTriggering(taskId);
    try {
      await fetch(`${BACKEND_URL}/api/agent/autonomous/tasks/${taskId}/trigger`, {
        method: "POST",
      });
      fetchToolsAndTasks();
    } catch {
    } finally {
      setIsTriggering(null);
    }
  };

  const handleDeleteAutoTask = (taskId: string, name: string) => {
    setDeleteTaskConfirm({ id: taskId, name });
  };

  const handleConfirmDeleteTask = async () => {
    if (!deleteTaskConfirm) return;
    const { id } = deleteTaskConfirm;
    setDeleteTaskConfirm(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/agent/autonomous/tasks/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setAutoTasks((prev) => prev.filter((t) => t.id !== id));
      }
    } catch {}
  };

  // Filter & sort visible toolsets
  const visibleToolsets = useMemo(() => {
    return toolsets
      .filter((ts) => {
        if (!searchQuery.trim()) return true;
        const q = searchQuery.toLowerCase();
        return (
          ts.title.toLowerCase().includes(q) ||
          ts.description.toLowerCase().includes(q) ||
          ts.category.toLowerCase().includes(q) ||
          ts.tools.some((t) => t.toLowerCase().includes(q))
        );
      })
      .sort((a, b) => {
        if (sortDesc) {
          const callsA = a.total_calls || 0;
          const callsB = b.total_calls || 0;
          if (callsA !== callsB) return callsB - callsA;
        }
        return a.title.localeCompare(b.title);
      });
  }, [toolsets, searchQuery, sortDesc]);

  // Active selected toolset
  const activeToolset = useMemo(() => {
    if (!selectedToolsetId && visibleToolsets.length > 0) return visibleToolsets[0];
    return visibleToolsets.find((ts) => ts.id === selectedToolsetId) || visibleToolsets[0] || null;
  }, [selectedToolsetId, visibleToolsets]);

  // Map tools in active toolset to their parameter schemas
  const activeMemberTools = useMemo(() => {
    if (!activeToolset) return [];
    return activeToolset.tools.map((toolName) => {
      const found = toolsCatalog.find((tc) => tc.name === toolName);
      return {
        name: toolName,
        calls: activeToolset.tool_calls?.[toolName] || 0,
        description: found?.description || "Executable agent tool.",
        parameters: found?.parameters,
        mode_label: found?.mode_label || (found?.is_read_only ? "READ-ONLY" : "ACTION"),
        is_read_only: found?.is_read_only,
      };
    });
  }, [activeToolset, toolsCatalog]);

  return (
    <div className="h-full w-full flex flex-col overflow-hidden select-none font-sans">
      {/* Top Secondary View Switcher */}
      <div className="px-4 py-2 border-b border-white/[0.06] bg-[#050811]/95 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-1.5 p-0.5 rounded-lg bg-black/40 border border-white/[0.08] text-xs font-mono">
          <button
            type="button"
            onClick={() => setToolsSubTab("toolsets")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              toolsSubTab === "toolsets"
                ? "bg-white/[0.08] text-white font-medium border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Toolsets</span>
            <span className="px-1.5 py-0.2 rounded text-[10px] bg-white/10 text-slate-300">
              {toolsets.length}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setToolsSubTab("autonomous")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              toolsSubTab === "autonomous"
                ? "bg-white/[0.08] text-white font-medium border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Autonomous Tasks</span>
            <span className="px-1.5 py-0.2 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-400/30">
              {autoTasks.length}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setToolsSubTab("subagents")}
            className={`px-3 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              toolsSubTab === "subagents"
                ? "bg-white/[0.08] text-white font-medium border border-white/[0.14] shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Sub-Agent Swarms</span>
            <span className="px-1.5 py-0.2 rounded text-[10px] bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
              {subagentTasks.length}
            </span>
          </button>
        </div>

        {toolsSubTab === "autonomous" && (
          <button
            type="button"
            onClick={() => setIsAddTaskOpen((v) => !v)}
            className="px-2.5 py-1 rounded-md bg-amber-500/15 hover:bg-amber-500/25 border border-amber-400/30 text-amber-200 text-xs font-mono font-medium transition-colors cursor-pointer"
          >
            + New Schedule
          </button>
        )}
      </div>

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* SUB-TAB 1: TOOLSETS MASTER-DETAIL VIEW (1:1 Reference Standard)     */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {toolsSubTab === "toolsets" && (
        <div className="flex-1 min-h-0 overflow-hidden">
          <MasterDetail resizeId="brain_toolsets">
            {/* ── LEFT COLUMN: List of 31 Toolsets ── */}
            <ListColumn
              header={
                <div className="flex items-center gap-1.5">
                  <div className="relative flex-1 min-w-0">
                    <svg
                      className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search toolsets..."
                      className="w-full py-1 pl-8 pr-2 rounded-lg bg-black/40 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-400/40 transition-colors"
                    />
                  </div>
                  <SortButton desc={sortDesc} onToggle={() => setSortDesc((v) => !v)} label="Usage" />
                </div>
              }
            >
              {visibleToolsets.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-500 font-mono">
                  {isLoading ? "Loading toolsets..." : "No toolsets match filter"}
                </div>
              ) : (
                visibleToolsets.map((ts) => (
                  <CapRow
                    key={ts.id}
                    title={ts.title}
                    subtitle={<span>{ts.tools.length} tools · {ts.category}</span>}
                    active={(activeToolset?.id || "") === ts.id}
                    enabled={ts.enabled}
                    meta={ts.total_calls ? `×${ts.total_calls >= 1000 ? `${(ts.total_calls / 1000).toFixed(1)}k` : ts.total_calls}` : undefined}
                    busy={togglingId === ts.id}
                    onSelect={() => setSelectedToolsetId(ts.id)}
                    onToggle={() => handleToggleToolset(ts.id, ts.enabled)}
                  />
                ))
              )}
            </ListColumn>

            {/* ── RIGHT COLUMN: Toolset Breakdown, Sub-Tools & Parameters ── */}
            <DetailColumn
              footer="Enabled toolsets are automatically exposed to the LLM agent reasoning loop."
            >
              {activeToolset ? (
                <div className="space-y-5 animate-fade-in">
                  {/* Toolset Header */}
                  <div className="border-b border-white/[0.08] pb-4">
                    <div className="flex items-center justify-between gap-3">
                      <h2 className="text-lg font-bold text-white tracking-tight font-sans">
                        {activeToolset.title}
                      </h2>
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase tracking-wider ${
                            activeToolset.enabled
                              ? "bg-emerald-500/15 border border-emerald-400/30 text-emerald-300"
                              : "bg-slate-800 border border-white/10 text-slate-400"
                          }`}
                        >
                          {activeToolset.enabled ? "Enabled" : "Disabled"}
                        </span>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300">
                          {activeToolset.category}
                        </span>
                      </div>
                    </div>
                    <p className="text-xs text-slate-300 mt-2 leading-relaxed font-sans">
                      {activeToolset.description}
                    </p>
                  </div>

                  {/* Sub-tools Breakdown Chips */}
                  <div className="space-y-2">
                    <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
                      Member Tools ({activeToolset.tools.length})
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {activeMemberTools.map((m) => (
                        <ToolChip key={m.name} count={m.calls > 0 ? m.calls : undefined}>
                          {m.name}
                        </ToolChip>
                      ))}
                    </div>
                  </div>

                  {/* Parameter Schema Cards */}
                  <div className="space-y-2.5 pt-2">
                    <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
                      Tool Specifications &amp; Parameters
                    </div>
                    <div className="space-y-2">
                      {activeMemberTools.map((m) => {
                        const isExpanded = expandedToolSchema === m.name;
                        return (
                          <div
                            key={m.name}
                            className="rounded-xl border border-white/[0.08] bg-[#070b16]/70 p-3 space-y-2 font-mono text-xs transition-colors"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-white select-text">{m.name}</span>
                                <span
                                  className={`px-1.5 py-0.2 rounded text-[9px] font-mono uppercase ${
                                    m.is_read_only
                                      ? "bg-emerald-500/15 text-emerald-300 border border-emerald-400/25"
                                      : "bg-cyan-500/15 text-cyan-300 border border-cyan-400/25"
                                  }`}
                                >
                                  {m.mode_label}
                                </span>
                              </div>
                              <button
                                type="button"
                                onClick={() => setExpandedToolSchema(isExpanded ? null : m.name)}
                                className="text-cyan-400 hover:text-cyan-300 text-[11px] flex items-center gap-1 cursor-pointer"
                              >
                                <span>{isExpanded ? "Hide Schema" : "Inspect Schema"}</span>
                                <svg
                                  className={`w-3 h-3 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
                                >
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                              </button>
                            </div>
                            <p className="text-xs text-slate-300 font-sans leading-relaxed select-text">
                              {m.description}
                            </p>
                            {isExpanded && m.parameters && (
                              <div className="p-3 rounded-lg bg-[#04060d] border border-white/[0.06] text-[10.5px] font-mono text-slate-300 overflow-x-auto select-text whitespace-pre-wrap max-h-48 custom-scrollbar">
                                {JSON.stringify(m.parameters, null, 2)}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-12 text-center text-xs text-slate-500 font-mono">
                  Select a toolset from the left rail to view sub-tools and parameters.
                </div>
              )}
            </DetailColumn>
          </MasterDetail>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* SUB-TAB 2: AUTONOMOUS SCHEDULED TASKS                                 */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {toolsSubTab === "autonomous" && (
        <div className="p-6 overflow-y-auto space-y-4">
          {/* Add Task Form Modal */}
          {isAddTaskOpen && (
            <form onSubmit={handleCreateAutoTask} className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.12] space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <span className="font-bold text-amber-300">Register New Autonomous Task</span>
                <button type="button" onClick={() => setIsAddTaskOpen(false)} className="text-slate-400 hover:text-white">✕</button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Task Name</label>
                  <input
                    type="text"
                    placeholder="Example: Daily Security Audit"
                    value={taskName}
                    onChange={(e) => setTaskName(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-black/60 border border-white/15 text-white"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Trust Level Policy</label>
                  <select
                    value={taskTrust}
                    onChange={(e) => setTaskTrust(e.target.value as any)}
                    className="w-full px-3 py-1.5 rounded-lg bg-black/60 border border-white/15 text-white"
                  >
                    <option value="supervised">Supervised (Pause &amp; Ask User)</option>
                    <option value="semi_autonomous">Semi-Autonomous (Auto Safe Actions)</option>
                    <option value="full_autonomous">Full-Autonomous (Full Auto Mutating)</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-slate-400">Autonomous Prompt Instructions</label>
                <textarea
                  rows={2}
                  placeholder="Example: Check project dependencies via terminal and report findings..."
                  value={taskPrompt}
                  onChange={(e) => setTaskPrompt(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg bg-black/60 border border-white/15 text-white"
                  required
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Execution Interval</label>
                  <select
                    value={taskInterval}
                    onChange={(e) => setTaskInterval(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg bg-black/60 border border-white/15 text-white"
                  >
                    <option value={1800}>Every 30 Minutes</option>
                    <option value={3600}>Every 1 Hour</option>
                    <option value={21600}>Every 6 Hours</option>
                    <option value={86400}>Daily (24 Hours)</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Notification Channel</label>
                  <select
                    value={taskChannel}
                    onChange={(e) => setTaskChannel(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-black/60 border border-white/15 text-white"
                  >
                    <option value="telegram">Telegram Bot</option>
                    <option value="web">Web Console</option>
                    <option value="cli">CLI Runner</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-1 font-mono text-xs">
                <button type="button" onClick={() => setIsAddTaskOpen(false)} className="px-3 py-1 text-slate-400 hover:text-white cursor-pointer">Cancel</button>
                <button type="submit" className="px-4 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/35 border border-amber-400/40 text-amber-200 font-bold cursor-pointer transition-all active:scale-95">Save Schedule</button>
              </div>
            </form>
          )}

          {/* List of Tasks */}
          {autoTasks.length === 0 ? (
            <div className="p-8 text-center rounded-xl bg-white/[0.02] border border-white/[0.08] text-slate-400 text-xs font-mono">
              No autonomous tasks scheduled yet.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {autoTasks.map((t) => (
                <div key={t.id} className="p-4 rounded-xl border border-white/[0.08] bg-[#070b16]/70 space-y-3 font-mono">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-white">{t.name}</span>
                    <span className="px-2 py-0.5 rounded text-[9px] uppercase bg-white/[0.05] border border-white/10 text-slate-300">
                      {t.trust_level.replace("_", "-")}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 font-sans leading-relaxed">&quot;{t.prompt}&quot;</p>
                  <div className="flex items-center justify-between pt-2 border-t border-white/5 text-[10px] text-slate-500">
                    <button
                      type="button"
                      onClick={() => handleTriggerTaskNow(t.id)}
                      disabled={isTriggering === t.id}
                      className="px-2.5 py-1 rounded bg-cyan-500/15 text-cyan-200 border border-cyan-400/30 text-xs font-bold cursor-pointer"
                    >
                      {isTriggering === t.id ? "Running..." : "Run Now"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteAutoTask(t.id, t.name)}
                      className="text-slate-400 hover:text-rose-400 cursor-pointer"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* SUB-TAB 3: SUBAGENT SWARMS                                            */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {toolsSubTab === "subagents" && (
        <div className="p-6 overflow-y-auto space-y-3">
          {subagentTasks.length === 0 ? (
            <div className="p-8 text-center rounded-xl bg-white/[0.02] border border-white/[0.08] text-slate-400 text-xs font-mono">
              No active subagent tasks at this time.
            </div>
          ) : (
            <div className="space-y-2.5">
              {subagentTasks.map((t) => (
                <div key={t.task_id} className="p-3.5 rounded-xl border border-white/[0.08] bg-[#070b16]/70 space-y-2 font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white">#{t.task_id} — {t.title}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] uppercase bg-white/[0.05] border border-white/10 text-slate-300">
                      {t.status}
                    </span>
                  </div>
                  {t.result && (
                    <div className="p-2.5 rounded-lg bg-black/50 border border-white/5 text-xs text-slate-300 font-sans whitespace-pre-wrap max-h-32 overflow-y-auto custom-scrollbar">
                      {t.result}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteTaskConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
          <div className="w-full max-w-sm p-5 rounded-2xl bg-slate-950/95 border border-white/20 text-white space-y-4 font-sans">
            <span className="text-xs font-bold font-mono text-rose-400">Confirm Task Deletion</span>
            <p className="text-xs text-slate-300">Delete task schedule &apos;{deleteTaskConfirm.name}&apos;?</p>
            <div className="flex justify-end gap-2 font-mono text-xs">
              <button type="button" onClick={() => setDeleteTaskConfirm(null)} className="px-3 py-1 rounded text-slate-400 hover:text-white">Cancel</button>
              <button type="button" onClick={handleConfirmDeleteTask} className="px-3 py-1 rounded bg-rose-500/20 text-rose-200 border border-rose-500/40">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
