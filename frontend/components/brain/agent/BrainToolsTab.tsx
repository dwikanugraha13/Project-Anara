"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BACKEND_URL, ToolItem, SubagentTask, AutonomousTaskInfo } from "../types";

export default function BrainToolsTab() {
  const [toolsCatalog, setToolsCatalog] = useState<ToolItem[]>([]);
  const [subagentTasks, setSubagentTasks] = useState<SubagentTask[]>([]);
  const [autoTasks, setAutoTasks] = useState<AutonomousTaskInfo[]>([]);
  const [toolsSubTab, setToolsSubTab] = useState<"tools" | "mcp" | "subagents" | "autonomous">("tools");
  const [selectedToolCategory, setSelectedToolCategory] = useState<string>("all");
  const [expandedToolSchema, setExpandedToolSchema] = useState<string | null>(null);

  // Model Context Protocol (MCP) Connectors State
  const [mcpServers, setMcpServers] = useState<Record<string, any>>({});
  const [isConnectingMcp, setIsConnectingMcp] = useState(false);

  // New Autonomous Task Form State
  const [isAddTaskOpen, setIsAddTaskOpen] = useState(false);
  const [taskName, setTaskName] = useState("");
  const [taskPrompt, setTaskPrompt] = useState("");
  const [taskInterval, setTaskInterval] = useState(3600);
  const [taskTrust, setTaskTrust] = useState<"supervised" | "semi_autonomous" | "full_autonomous">("supervised");
  const [taskChannel, setTaskChannel] = useState("telegram");
  const [isTriggering, setIsTriggering] = useState<string | null>(null);
  const [deleteTaskConfirm, setDeleteTaskConfirm] = useState<{ id: string; name: string } | null>(null);

  const fetchMcpServers = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/mcp/servers`).then((r) => (r.ok ? r.json() : null));
      if (res && res.servers) {
        setMcpServers(res.servers);
      }
    } catch (err) {
      console.warn("[BrainToolsTab] MCP fetch error:", err);
    }
  }, []);

  const handleConnectMcp = async () => {
    setIsConnectingMcp(true);
    try {
      await fetch(`${BACKEND_URL}/api/brain/mcp/servers/connect`, { method: "POST" });
      await fetchMcpServers();
      await fetchToolsAndTasks();
    } catch (err) {
      console.warn("[BrainToolsTab] MCP connect error:", err);
    } finally {
      setIsConnectingMcp(false);
    }
  };

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
    fetchToolsAndTasks();
    fetchMcpServers();
  }, [fetchToolsAndTasks, fetchMcpServers]);

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

  const filteredTools = toolsCatalog.filter((t) => {
    if (selectedToolCategory === "all") return true;
    return t.category === selectedToolCategory;
  });

  return (
    <div className="space-y-4 font-sans select-text">
      {/* Header & Sub-Tab Switcher */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-white/[0.025] border border-white/[0.08]">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <h3 className="text-xs sm:text-sm font-semibold text-white font-mono">
              Agent Execution Instruments
            </h3>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/10 text-cyan-300 border border-cyan-400/20 font-medium">
              {toolsCatalog.length} Tools
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Physical execution instruments, background workers, and autonomous scheduler.
          </p>
        </div>

        <div className="flex items-center gap-1 p-0.5 rounded-lg bg-black/40 border border-white/[0.08] font-mono text-xs overflow-x-auto no-scrollbar">
          <button
            type="button"
            onClick={() => setToolsSubTab("tools")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border transition-all cursor-pointer select-none shrink-0 ${
              toolsSubTab === "tools"
                ? "bg-white/[0.08] text-white border-white/[0.14] shadow-sm"
                : "border-transparent text-slate-400 hover:text-white hover:bg-white/[0.03]"
            }`}
          >
            <svg className="w-3.5 h-3.5 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span>Tools Catalog ({toolsCatalog.length})</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setToolsSubTab("mcp");
              fetchMcpServers();
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border transition-all cursor-pointer select-none shrink-0 ${
              toolsSubTab === "mcp"
                ? "bg-white/[0.08] text-white border-white/[0.14] shadow-sm"
                : "border-transparent text-slate-400 hover:text-white hover:bg-white/[0.03]"
            }`}
          >
            <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span>MCP Connectors ({Object.keys(mcpServers).length})</span>
          </button>
          <button
            type="button"
            onClick={() => setToolsSubTab("autonomous")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border transition-all cursor-pointer select-none shrink-0 ${
              toolsSubTab === "autonomous"
                ? "bg-white/[0.08] text-white border-white/[0.14] shadow-sm"
                : "border-transparent text-slate-400 hover:text-white hover:bg-white/[0.03]"
            }`}
          >
            <svg className="w-3.5 h-3.5 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Autonomous Tasks ({autoTasks.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setToolsSubTab("subagents")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border transition-all cursor-pointer select-none shrink-0 ${
              toolsSubTab === "subagents"
                ? "bg-white/[0.08] text-white border-white/[0.14] shadow-sm"
                : "border-transparent text-slate-400 hover:text-white hover:bg-white/[0.03]"
            }`}
          >
            <svg className="w-3.5 h-3.5 text-indigo-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <span>Sub-Agent Swarms ({subagentTasks.length})</span>
          </button>
        </div>
      </div>

      {/* Sub-tab 1: Tools Catalog */}
      {toolsSubTab === "tools" && (
        <div className="space-y-3">
          {/* Category Filters */}
          <div className="flex items-center gap-1.5 flex-wrap font-mono text-xs">
            {[
              { id: "all", label: "All" },
              { id: "coding", label: "Coding & Files" },
              { id: "exploration", label: "Search & Navigation" },
              { id: "system", label: "Terminal & Shell" },
              { id: "intelligence", label: "Intelligence & Research" },
              { id: "connectivity", label: "Connectivity & MCP" },
            ].map((cat) => (
              <button
                key={cat.id}
                type="button"
                onClick={() => setSelectedToolCategory(cat.id)}
                className={`px-2.5 py-1 rounded-md border transition-all cursor-pointer text-[11px] ${
                  selectedToolCategory === cat.id
                    ? "bg-white/[0.08] text-white border-white/[0.14] font-medium shadow-sm"
                    : "bg-white/[0.02] text-slate-400 border-white/[0.06] hover:text-white"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 items-stretch">
            {filteredTools.map((tool) => {
              const isExpanded = expandedToolSchema === tool.name;
              return (
                <div
                  key={tool.name}
                  className="p-3.5 rounded-xl bg-white/[0.025] hover:bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all font-mono shadow-sm flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs sm:text-sm font-bold text-white tracking-tight">{tool.name}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase border font-mono ${
                          tool.is_read_only
                            ? "bg-emerald-500/15 text-emerald-300 border-emerald-400/30"
                            : "bg-cyan-500/15 text-cyan-300 border-cyan-400/30"
                        }`}
                      >
                        {tool.mode_label}
                      </span>
                    </div>

                    <p className="text-xs text-slate-300 font-sans leading-relaxed">
                      {tool.description}
                    </p>
                  </div>

                  <div className="space-y-2 mt-3 pt-2 border-t border-white/[0.06]">
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>Category: <span className="text-slate-300 font-medium">{tool.category}</span></span>
                      <button
                        type="button"
                        onClick={() => setExpandedToolSchema(isExpanded ? null : tool.name)}
                        className="text-cyan-400 hover:text-cyan-300 transition-colors cursor-pointer flex items-center gap-1 font-mono text-[10.5px]"
                      >
                        <span>{isExpanded ? "Close Schema" : "Parameters"}</span>
                        <svg className={`w-3 h-3 transition-transform ${isExpanded ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                    </div>

                    {isExpanded && tool.parameters && (
                      <div className="p-2.5 rounded-lg bg-black/60 border border-white/[0.08] text-[10.5px] space-y-1 font-mono">
                        <div className="text-slate-400 font-bold">Input Schema:</div>
                        <pre className="text-slate-300 overflow-x-auto whitespace-pre-wrap max-h-36 custom-scrollbar text-[10px]">
                          {JSON.stringify(tool.parameters, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Sub-tab: MCP Connectors (Model Context Protocol) ── */}
      {toolsSubTab === "mcp" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-white/[0.025] border border-white/[0.08]">
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse shrink-0" />
              <div>
                <h4 className="text-xs sm:text-sm font-semibold text-white font-mono">
                  Model Context Protocol (MCP) Stdio &amp; HTTP Client
                </h4>
                <p className="text-xs text-slate-400">
                  Subprocess sandboxing with env-var whitelist, stderr drain &amp; regex secret scrubbing.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={handleConnectMcp}
              disabled={isConnectingMcp}
              className="px-3 py-1.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-400/30 text-cyan-200 text-xs font-mono font-medium transition-all flex items-center gap-1.5 cursor-pointer shrink-0"
            >
              <svg className={`w-3.5 h-3.5 ${isConnectingMcp ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>{isConnectingMcp ? "Connecting..." : "Reconnect Servers"}</span>
            </button>
          </div>

          {Object.keys(mcpServers).length === 0 ? (
            <div className="p-8 rounded-xl border border-white/[0.08] bg-black/30 text-center flex flex-col items-center gap-2">
              <span className="text-xs font-medium text-slate-300">No MCP servers currently configured in config.yaml or .anara/mcp.json</span>
              <p className="text-[11px] text-slate-500 max-w-md">
                Configure your MCP servers under `mcp_servers` in config.yaml or `.anara/mcp.json` to automatically expose external tools with native sandboxing.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(mcpServers).map(([name, s]) => (
                <div key={name} className="p-3.5 rounded-xl border border-white/[0.08] bg-black/40 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 truncate">
                        <span className={`w-2 h-2 rounded-full shrink-0 ${s.connected ? "bg-emerald-400 shadow-[0_0_6px_#34d399]" : "bg-slate-500"}`} />
                        <h4 className="text-xs font-bold text-white font-mono truncate">{name}</h4>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-white/[0.05] border border-white/[0.08] text-slate-300 shrink-0 ml-2">
                        {s.transport || "stdio"}
                      </span>
                    </div>

                    <p className="mt-2 text-[11px] font-mono text-slate-400 truncate">
                      {s.command ? `$ ${s.command} ${(s.args || []).join(" ")}` : s.url}
                    </p>

                    {s.tools && s.tools.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap gap-1">
                        {s.tools.slice(0, 6).map((t: string) => (
                          <span key={t} className="px-1.5 py-0.5 rounded text-[9.5px] font-mono bg-cyan-950/40 border border-cyan-500/20 text-cyan-300">
                            {t}
                          </span>
                        ))}
                        {s.tools.length > 6 && (
                          <span className="text-[9.5px] font-mono text-slate-500">
                            +{s.tools.length - 6} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="mt-3 pt-2 flex items-center justify-between border-t border-white/[0.05] text-[10px] font-mono text-slate-500">
                    <span>{s.tools_count || 0} tools exposed</span>
                    <span className={s.connected ? "text-emerald-400 font-medium" : "text-slate-500"}>
                      {s.connected ? "Connected" : "Disconnected"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sub-tab 2: Autonomous Scheduled Tasks (Fase 5) */}
      {toolsSubTab === "autonomous" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3.5 rounded-2xl liquid-glass border border-white/10">
            <div>
              <h4 className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                Autonomous Task Scheduler (Autonomous Engine)
              </h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Scheduled background tasks with Trust-Level policy enforcement (FR-21 s/d FR-24).
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsAddTaskOpen((v) => !v)}
              className="px-3 py-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/35 border border-amber-400/40 text-amber-200 text-xs font-semibold font-mono transition-all cursor-pointer flex items-center gap-1.5"
            >
              <span>+ Add Task</span>
            </button>
          </div>

          {/* Add Task Modal */}
          {isAddTaskOpen && (
            <form onSubmit={handleCreateAutoTask} className="p-4 rounded-2xl liquid-glass border border-white/20 space-y-3 animate-scale-up font-mono text-xs">
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <span className="font-bold text-amber-300">Register New Autonomous Task</span>
                <button type="button" onClick={() => setIsAddTaskOpen(false)} className="text-slate-400 hover:text-white">✕</button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Task Name</label>
                  <input
                    type="text"
                    placeholder="Example: Daily Dependency Security Audit"
                    value={taskName}
                    onChange={(e) => setTaskName(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-white"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Trust Level Policy</label>
                  <select
                    value={taskTrust}
                    onChange={(e) => setTaskTrust(e.target.value as any)}
                    className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-white"
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
                  className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-white"
                  required
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Execution Interval</label>
                  <select
                    value={taskInterval}
                    onChange={(e) => setTaskInterval(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-white"
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
                    className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-white"
                  >
                    <option value="telegram">Telegram Bot</option>
                    <option value="web">Web Console</option>
                    <option value="cli">CLI Runner</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-1 font-mono text-xs">
                <button type="button" onClick={() => setIsAddTaskOpen(false)} className="px-3 py-1 text-slate-400 hover:text-white cursor-pointer">Cancel</button>
                <button type="submit" className="px-4 py-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/35 border border-amber-400/40 text-amber-200 font-bold cursor-pointer transition-all active:scale-95">Save Schedule</button>
              </div>
            </form>
          )}

          {/* List of Autonomous Tasks */}
          {autoTasks.length === 0 ? (
            <div className="p-8 text-center rounded-2xl liquid-glass border border-white/10 text-slate-400 text-xs font-mono">
              No autonomous tasks scheduled yet. Click &quot;Add Task&quot; above to schedule background jobs.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {autoTasks.map((t) => {
                const isWaiting = t.status === "waiting_approval";
                const isRunning = isTriggering === t.id || t.status === "running";
                return (
                  <div
                    key={t.id}
                    className={`p-4 rounded-2xl border flex flex-col justify-between space-y-3 font-mono ${
                      isWaiting
                        ? "bg-amber-950/25 border-amber-500/40 shadow-lg shadow-amber-500/10"
                        : "liquid-glass border-white/15 hover:border-white/25"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-white">{t.name}</span>
                          <span className="text-[10px] text-slate-500">#{t.id}</span>
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase border ${
                            t.trust_level === "full_autonomous"
                              ? "bg-purple-500/15 text-purple-300 border-purple-400/30"
                              : t.trust_level === "semi_autonomous"
                              ? "bg-cyan-500/15 text-cyan-300 border-cyan-400/30"
                              : "bg-amber-500/15 text-amber-300 border-amber-400/30"
                          }`}
                        >
                          {t.trust_level.replace("_", "-")}
                        </span>
                      </div>

                      <p className="text-xs text-slate-300 font-sans mt-2 leading-relaxed">
                        &quot;{t.prompt}&quot;
                      </p>

                      <div className="mt-2.5 flex items-center gap-2 text-[10px] text-slate-400 flex-wrap">
                        <span className="flex items-center gap-1 font-mono">
                          <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span>Every {Math.round(t.interval_seconds / 60)}m</span>
                        </span>
                        <span>•</span>
                        <span className="flex items-center gap-1 font-mono">
                          <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z" />
                          </svg>
                          <span>{t.target_channel.toUpperCase()}</span>
                        </span>
                        <span>•</span>
                        <span className={`font-semibold font-mono ${isWaiting ? "text-amber-400 animate-pulse" : "text-slate-400"}`}>
                          Status: {t.status}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-white/5">
                      <button
                        type="button"
                        onClick={() => handleTriggerTaskNow(t.id)}
                        disabled={isRunning}
                        className="px-3 py-1 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/30 border border-cyan-400/30 text-cyan-200 text-[11px] font-bold font-mono transition-all cursor-pointer disabled:opacity-50"
                      >
                        {isRunning ? "Executing..." : "Run Now"}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteAutoTask(t.id, t.name)}
                        className="text-[11px] text-slate-500 hover:text-rose-400 transition-colors cursor-pointer"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Sub-tab 3: Subagents */}
      {toolsSubTab === "subagents" && (
        <div className="space-y-3">
          <div className="p-3 rounded-xl bg-black/40 border border-white/10 text-xs text-slate-400 font-mono">
            List of autonomous subagent tasks delegated to run in the background.
          </div>

          {subagentTasks.length === 0 ? (
            <div className="p-8 text-center rounded-2xl liquid-glass border border-white/10 text-slate-400 text-xs font-mono">
              No active subagent tasks at this time.
            </div>
          ) : (
            <div className="space-y-2.5">
              {subagentTasks.map((t) => (
                <div
                  key={t.task_id}
                  className="p-3.5 rounded-2xl liquid-glass border border-white/10 space-y-2 font-mono"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white">#{t.task_id}</span>
                      <span className="text-xs font-semibold text-slate-200 font-sans">{t.title}</span>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
                        t.status === "completed"
                          ? "bg-emerald-500/15 text-emerald-300 border-emerald-400/30"
                          : t.status === "failed"
                          ? "bg-rose-500/15 text-rose-300 border-rose-400/30"
                          : "bg-cyan-500/15 text-cyan-300 border-cyan-400/30 animate-pulse"
                      }`}
                    >
                      {t.status}
                    </span>
                  </div>

                  <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        t.status === "completed" ? "bg-emerald-400" : "bg-cyan-400"
                      }`}
                      style={{ width: `${t.progress_percent}%` }}
                    />
                  </div>

                  {t.result && (
                    <div className="mt-2 p-2.5 rounded-xl bg-black/50 border border-white/5 text-xs text-slate-300 font-sans whitespace-pre-wrap max-h-32 overflow-y-auto custom-scrollbar">
                      {t.result}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* In-app Delete Confirmation Modal */}
      {deleteTaskConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in select-none"
        >
          <div className="w-full max-w-sm p-5 rounded-2xl bg-slate-950/95 border border-white/20 shadow-[0_0_40px_rgba(0,0,0,0.8)] text-white space-y-4 font-sans">
            <div className="flex items-center gap-2.5 text-rose-400 font-mono text-xs font-semibold">
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>Confirm Task Deletion</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              Permanently delete autonomous task schedule <b className="text-white font-mono">&apos;{deleteTaskConfirm.name}&apos;</b>?
            </p>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/10 font-mono text-xs">
              <button
                type="button"
                onClick={() => setDeleteTaskConfirm(null)}
                className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDeleteTask}
                className="px-3.5 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/40 font-semibold transition-all cursor-pointer shadow-sm active:scale-95"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
