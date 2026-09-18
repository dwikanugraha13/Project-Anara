"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BACKEND_URL, ToolItem, SubagentTask, AutonomousTaskInfo } from "../types";

export default function BrainToolsTab() {
  const [toolsCatalog, setToolsCatalog] = useState<ToolItem[]>([]);
  const [subagentTasks, setSubagentTasks] = useState<SubagentTask[]>([]);
  const [autoTasks, setAutoTasks] = useState<AutonomousTaskInfo[]>([]);
  const [toolsSubTab, setToolsSubTab] = useState<"tools" | "subagents" | "autonomous">("tools");
  const [selectedToolCategory, setSelectedToolCategory] = useState<string>("all");
  const [expandedToolSchema, setExpandedToolSchema] = useState<string | null>(null);

  // New Autonomous Task Form State
  const [isAddTaskOpen, setIsAddTaskOpen] = useState(false);
  const [taskName, setTaskName] = useState("");
  const [taskPrompt, setTaskPrompt] = useState("");
  const [taskInterval, setTaskInterval] = useState(3600);
  const [taskTrust, setTaskTrust] = useState<"supervised" | "semi_autonomous" | "full_autonomous">("supervised");
  const [taskChannel, setTaskChannel] = useState("telegram");
  const [isTriggering, setIsTriggering] = useState<string | null>(null);

  const fetchToolsAndTasks = useCallback(async () => {
    try {
      const [toolsRes, tasksRes, autoRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/agent/tools`),
        fetch(`${BACKEND_URL}/api/agent/subagent/tasks`),
        fetch(`${BACKEND_URL}/api/agent/autonomous/tasks`),
      ]);
      if (toolsRes.ok) {
        const d = await toolsRes.json();
        setToolsCatalog(d.tools || []);
      }
      if (tasksRes.ok) {
        const d = await tasksRes.json();
        setSubagentTasks(d.tasks || []);
      }
      if (autoRes.ok) {
        const d = await autoRes.json();
        setAutoTasks(d.tasks || []);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchToolsAndTasks();
  }, [fetchToolsAndTasks]);

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

  const handleDeleteAutoTask = async (taskId: string, name: string) => {
    if (!confirm(`Hapus jadwal tugas '${name}'?`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/agent/autonomous/tasks/${taskId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setAutoTasks((prev) => prev.filter((t) => t.id !== taskId));
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
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-2xl liquid-glass border border-white/10">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-white font-mono">
              Katalog Alat, Sub-Agent &amp; Otonom
            </h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/15 text-cyan-300 border border-cyan-400/30 font-semibold">
              {toolsCatalog.length || 24} Tools
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Instrumen fisik, pekerja latar belakang, dan scheduler otonom (Anara Standard &amp; OpenCode).
          </p>
        </div>

        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-black/40 border border-white/10 font-mono text-xs flex-wrap">
          <button
            type="button"
            onClick={() => setToolsSubTab("tools")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors duration-150 ease-out cursor-pointer select-none ${
              toolsSubTab === "tools"
                ? "bg-white/[0.12] text-white border-white/20 shadow-sm"
                : "border-transparent text-slate-400 hover:text-white hover:bg-white/[0.04]"
            }`}
          >
            <svg className="w-3.5 h-3.5 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span>Katalog Alat ({toolsCatalog.length || 24})</span>
          </button>
          <button
            type="button"
            onClick={() => setToolsSubTab("autonomous")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors duration-150 ease-out cursor-pointer select-none ${
              toolsSubTab === "autonomous"
                ? "bg-white/[0.12] text-white border-white/20 shadow-sm"
                : "border-transparent text-slate-400 hover:text-white hover:bg-white/[0.04]"
            }`}
          >
            <svg className="w-3.5 h-3.5 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Tugas Otonom ({autoTasks.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setToolsSubTab("subagents")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors duration-150 ease-out cursor-pointer select-none ${
              toolsSubTab === "subagents"
                ? "bg-white/[0.12] text-white border-white/20 shadow-sm"
                : "border-transparent text-slate-400 hover:text-white hover:bg-white/[0.04]"
            }`}
          >
            <svg className="w-3.5 h-3.5 text-indigo-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <span>Misi Sub-Agent ({subagentTasks.length})</span>
          </button>
        </div>
      </div>

      {/* Sub-tab 1: Tools Catalog */}
      {toolsSubTab === "tools" && (
        <div className="space-y-3">
          {/* Category Filters */}
          <div className="flex items-center gap-1.5 flex-wrap font-mono text-xs">
            {[
              { id: "all", label: "Semua" },
              { id: "coding", label: "Koding & Berkas" },
              { id: "exploration", label: "Pencarian & Eksplorasi" },
              { id: "system", label: "Terminal & Sistem" },
              { id: "intelligence", label: "Intelijen & Riset" },
              { id: "connectivity", label: "Konektivitas" },
            ].map((cat) => (
              <button
                key={cat.id}
                type="button"
                onClick={() => setSelectedToolCategory(cat.id)}
                className={`px-3 py-1 rounded-lg border transition-all cursor-pointer text-[11px] ${
                  selectedToolCategory === cat.id
                    ? "bg-cyan-500/20 text-cyan-200 border-cyan-400/40 font-bold"
                    : "bg-white/[0.03] text-slate-400 border-white/5 hover:text-white"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filteredTools.map((tool) => {
              const isExpanded = expandedToolSchema === tool.name;
              return (
                <div
                  key={tool.name}
                  className="p-3.5 rounded-2xl liquid-glass border border-white/10 space-y-2 hover:border-white/20 transition-all font-mono"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-white">{tool.name}</span>
                      <span
                        className={`px-2 py-0.5 rounded-md text-[9px] font-bold uppercase border ${
                          tool.is_read_only
                            ? "bg-emerald-500/15 text-emerald-300 border-emerald-400/30"
                            : "bg-amber-500/15 text-amber-300 border-amber-400/30"
                        }`}
                      >
                        {tool.mode_label}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-400 font-sans leading-relaxed">
                    {tool.description}
                  </p>

                  <div className="pt-1 flex items-center justify-between border-t border-white/5 text-[10px] text-slate-500">
                    <span>Kategori: {tool.category}</span>
                    <button
                      type="button"
                      onClick={() => setExpandedToolSchema(isExpanded ? null : tool.name)}
                      className="text-cyan-400 hover:text-cyan-300 transition-colors cursor-pointer"
                    >
                      {isExpanded ? "Tutup Skema ▲" : "Lihat Parameter ▼"}
                    </button>
                  </div>

                  {isExpanded && tool.parameters && (
                    <div className="p-2.5 rounded-xl bg-black/60 border border-white/10 text-[10px] space-y-1">
                      <div className="text-slate-400 font-bold">Parameter Input:</div>
                      <pre className="text-slate-300 overflow-x-auto whitespace-pre-wrap max-h-36 custom-scrollbar">
                        {JSON.stringify(tool.parameters, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Sub-tab 2: Autonomous Scheduled Tasks (Fase 5) */}
      {toolsSubTab === "autonomous" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3.5 rounded-2xl liquid-glass border border-white/10">
            <div>
              <h4 className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                Penjadwal Tugas Otonom (Autonomous Engine)
              </h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Tugas background terjadwal dengan penegakan kebijakan Trust-Level (FR-21 s/d FR-24).
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsAddTaskOpen((v) => !v)}
              className="px-3 py-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/35 border border-amber-400/40 text-amber-200 text-xs font-semibold font-mono transition-all cursor-pointer flex items-center gap-1.5"
            >
              <span>+ Tambah Tugas</span>
            </button>
          </div>

          {/* Add Task Modal */}
          {isAddTaskOpen && (
            <form onSubmit={handleCreateAutoTask} className="p-4 rounded-2xl liquid-glass border border-white/20 space-y-3 animate-scale-up font-mono text-xs">
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <span className="font-bold text-amber-300">Daftarkan Tugas Otonom Baru</span>
                <button type="button" onClick={() => setIsAddTaskOpen(false)} className="text-slate-400 hover:text-white">✕</button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Nama Tugas</label>
                  <input
                    type="text"
                    placeholder="Contoh: Audit Keamanan Dependensi Harian"
                    value={taskName}
                    onChange={(e) => setTaskName(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-white"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Kebijakan Trust Level</label>
                  <select
                    value={taskTrust}
                    onChange={(e) => setTaskTrust(e.target.value as any)}
                    className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-white"
                  >
                    <option value="supervised">Supervised (Pause &amp; Tanya User)</option>
                    <option value="semi_autonomous">Semi-Autonomous (Auto Aksi Ringan)</option>
                    <option value="full_autonomous">Full-Autonomous (Auto Mutating)</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-slate-400">Instruksi Prompt Otonom</label>
                <textarea
                  rows={2}
                  placeholder="Contoh: Periksa dependensi proyek via terminal dan laporkan ke Telegram..."
                  value={taskPrompt}
                  onChange={(e) => setTaskPrompt(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-white"
                  required
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Interval Eksekusi</label>
                  <select
                    value={taskInterval}
                    onChange={(e) => setTaskInterval(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-white"
                  >
                    <option value={1800}>Setiap 30 Menit</option>
                    <option value={3600}>Setiap 1 Jam</option>
                    <option value={21600}>Setiap 6 Jam</option>
                    <option value={86400}>Harian (24 Jam)</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-400">Channel Notifikasi</label>
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

              <div className="flex justify-end gap-2 pt-1">
                <button type="button" onClick={() => setIsAddTaskOpen(false)} className="px-3 py-1 text-slate-400 hover:text-white">Batal</button>
                <button type="submit" className="px-4 py-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/35 border border-amber-400/40 text-amber-200 font-bold cursor-pointer">Simpan Jadwal</button>
              </div>
            </form>
          )}

          {/* List of Autonomous Tasks */}
          {autoTasks.length === 0 ? (
            <div className="p-8 text-center rounded-2xl liquid-glass border border-white/10 text-slate-400 text-xs font-mono">
              Belum ada tugas otonom terjadwal. Klik &quot;Tambah Tugas&quot; di atas untuk menjadwalkan pekerjaan background.
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
                        <span>⏱️ Setiap {Math.round(t.interval_seconds / 60)} m</span>
                        <span>•</span>
                        <span>📢 {t.target_channel.toUpperCase()}</span>
                        <span>•</span>
                        <span className={`font-semibold ${isWaiting ? "text-amber-400 animate-pulse" : "text-slate-400"}`}>
                          Status: {t.status}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-white/5">
                      <button
                        type="button"
                        onClick={() => handleTriggerTaskNow(t.id)}
                        disabled={isRunning}
                        className="px-3 py-1 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/30 border border-cyan-400/30 text-cyan-200 text-[11px] font-bold transition-all cursor-pointer disabled:opacity-50"
                      >
                        {isRunning ? "⚡ Mengeksekusi..." : "⚡ Jalankan Sekarang"}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteAutoTask(t.id, t.name)}
                        className="text-[11px] text-slate-500 hover:text-rose-400 transition-colors cursor-pointer"
                      >
                        Hapus
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
            Daftar tugas subagent otonom yang didelegasikan untuk berjalan di latar belakang.
          </div>

          {subagentTasks.length === 0 ? (
            <div className="p-8 text-center rounded-2xl liquid-glass border border-white/10 text-slate-400 text-xs font-mono">
              Belum ada subagent task yang aktif saat ini.
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
    </div>
  );
}
