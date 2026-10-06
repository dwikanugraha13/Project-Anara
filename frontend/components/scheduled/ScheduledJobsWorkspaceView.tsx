"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BACKEND_URL, AutonomousTaskInfo } from "@/components/brain/types";

export interface ScheduledJobsWorkspaceViewProps {
  onClose?: () => void;
}

export default function ScheduledJobsWorkspaceView({ onClose }: ScheduledJobsWorkspaceViewProps) {
  const [autoTasks, setAutoTasks] = useState<AutonomousTaskInfo[]>([]);
  const [isAddTaskOpen, setIsAddTaskOpen] = useState(false);
  const [taskName, setTaskName] = useState("");
  const [taskPrompt, setTaskPrompt] = useState("");
  const [taskInterval, setTaskInterval] = useState(3600);
  const [taskTrust, setTaskTrust] = useState<"supervised" | "semi_autonomous" | "full_autonomous">("supervised");
  const [taskChannel, setTaskChannel] = useState("telegram");
  const [isTriggering, setIsTriggering] = useState<string | null>(null);
  const [deleteTaskConfirm, setDeleteTaskConfirm] = useState<{ id: string; name: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchTasks = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/agent/autonomous/tasks`).then((r) => (r.ok ? r.json() : null));
      if (res && res.tasks) {
        setAutoTasks(res.tasks || []);
      }
    } catch (e) {
      console.warn("[ScheduledJobs] Fetch error:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

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
        fetchTasks();
      }
    } catch {}
  };

  const handleTriggerTaskNow = async (taskId: string) => {
    setIsTriggering(taskId);
    try {
      await fetch(`${BACKEND_URL}/api/agent/autonomous/tasks/${taskId}/trigger`, {
        method: "POST",
      });
      fetchTasks();
    } catch {
    } finally {
      setIsTriggering(null);
    }
  };

  const handleDeleteTask = async () => {
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

  return (
    <div className="flex-1 min-w-0 h-full flex flex-col overflow-hidden bg-[#060913] select-none font-sans relative">
      {/* ── Top Workspace Header ── */}
      <header className="h-[44px] px-4 border-b border-white/[0.08] bg-[#070c18]/90 backdrop-blur-2xl flex items-center justify-between shrink-0 z-20">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_#fbbf24]" />
            <h3 className="text-xs sm:text-sm font-semibold text-white font-mono tracking-tight">
              Scheduled Jobs &amp; Autonomous Scheduler
            </h3>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300 hidden sm:inline">
            {autoTasks.length} Active Jobs
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsAddTaskOpen((v) => !v)}
            className="px-3 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-400/30 text-amber-200 text-xs font-mono font-medium transition-colors cursor-pointer"
          >
            + New Schedule
          </button>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-mono text-slate-300 hover:text-white transition-all cursor-pointer"
              title="Return to Chat Conversation"
            >
              <span>Back to Chat</span>
              <span className="text-slate-500 font-bold">✕</span>
            </button>
          )}
        </div>
      </header>

      {/* ── Main Content Area ── */}
      <main className="flex-1 min-h-0 overflow-y-auto p-6 select-text custom-scrollbar space-y-4">
        <div className="max-w-5xl mx-auto space-y-4">
          {/* Add Task Modal Form */}
          {isAddTaskOpen && (
            <form onSubmit={handleCreateAutoTask} className="p-5 rounded-2xl bg-[#080d1a] border border-white/[0.12] space-y-3 font-mono text-xs animate-scale-up shadow-2xl">
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <span className="font-bold text-amber-300 text-sm">Register Scheduled Job</span>
                <button type="button" onClick={() => setIsAddTaskOpen(false)} className="text-slate-400 hover:text-white">✕</button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Job Title</label>
                  <input
                    type="text"
                    placeholder="Example: Daily Security & Dependency Audit"
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
                  placeholder="Example: Inspect codebase, run tests, and report summary..."
                  value={taskPrompt}
                  onChange={(e) => setTaskPrompt(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg bg-black/60 border border-white/15 text-white"
                  required
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Interval</label>
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
                    <option value="web">Web Studio</option>
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
            <div className="p-12 text-center rounded-2xl bg-white/[0.02] border border-white/[0.08] text-slate-400 text-xs font-mono">
              {isLoading ? "Loading scheduled jobs..." : "No scheduled jobs registered. Click '+ New Schedule' to register autonomous background tasks."}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {autoTasks.map((t) => (
                <div key={t.id} className="p-4 rounded-xl border border-white/[0.08] bg-[#070b16]/80 space-y-3 font-mono shadow-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-white">{t.name}</span>
                    <span className="px-2 py-0.5 rounded text-[9px] uppercase bg-white/[0.05] border border-white/10 text-slate-300">
                      {t.trust_level.replace("_", "-")}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 font-sans leading-relaxed">&quot;{t.prompt}&quot;</p>
                  <div className="flex items-center justify-between pt-2 border-t border-white/5 text-[10px] text-slate-500">
                    <div className="flex items-center gap-2">
                      <span>Every {Math.round(t.interval_seconds / 60)}m</span>
                      <span>•</span>
                      <span>{t.target_channel.toUpperCase()}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleTriggerTaskNow(t.id)}
                        disabled={isTriggering === t.id}
                        className="px-2.5 py-1 rounded bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-200 border border-cyan-400/30 text-xs font-bold cursor-pointer"
                      >
                        {isTriggering === t.id ? "Running..." : "Run Now"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleteTaskConfirm({ id: t.id, name: t.name })}
                        className="text-slate-400 hover:text-rose-400 cursor-pointer"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Delete Confirmation Modal */}
      {deleteTaskConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
          <div className="w-full max-w-sm p-5 rounded-2xl bg-slate-950/95 border border-white/20 text-white space-y-4 font-sans">
            <span className="text-xs font-bold font-mono text-rose-400">Confirm Job Deletion</span>
            <p className="text-xs text-slate-300">Delete scheduled job &apos;{deleteTaskConfirm.name}&apos;?</p>
            <div className="flex justify-end gap-2 font-mono text-xs">
              <button type="button" onClick={() => setDeleteTaskConfirm(null)} className="px-3 py-1 rounded text-slate-400 hover:text-white">Cancel</button>
              <button type="button" onClick={handleDeleteTask} className="px-3 py-1 rounded bg-rose-500/20 text-rose-200 border border-rose-500/40">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
