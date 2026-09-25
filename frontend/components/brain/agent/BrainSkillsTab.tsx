"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BACKEND_URL, AgentSkillV2, CategoryIcon } from "../types";

interface HubSkillItem {
  name: string;
  slug: string;
  description: string;
  source: string;
  identifier: string;
  trust_level?: string;
  repo?: string;
  path?: string;
  tags?: string[];
  is_installed?: boolean;
}

interface HubSource {
  id: string;
  name: string;
  count: number;
  description: string;
}

export default function BrainSkillsTab() {
  const [activeTab, setActiveTab] = useState<"installed" | "hub">("installed");
  const [skills, setSkills] = useState<AgentSkillV2[]>([]);
  const [filterStatus, setFilterStatus] = useState<"all" | "active" | "disabled" | "pending">("all");
  const [isAddSkillOpen, setIsAddSkillOpen] = useState(false);
  const [newSkillName, setNewSkillName] = useState("");
  const [newSkillCategory, setNewSkillCategory] = useState("coding");
  const [newSkillDesc, setNewSkillDesc] = useState("");
  const [newSkillTriggers, setNewSkillTriggers] = useState("");
  const [newSkillSteps, setNewSkillSteps] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [togglingSlug, setTogglingSlug] = useState<string | null>(null);

  // ── Skills Hub state ──
  const [hubQuery, setHubQuery] = useState("");
  const [hubSource, setHubSource] = useState("all");
  const [hubSources, setHubSources] = useState<HubSource[]>([]);
  const [hubResults, setHubResults] = useState<HubSkillItem[]>([]);
  const [hubTotal, setHubTotal] = useState(0);
  const [isSearchingHub, setIsSearchingHub] = useState(false);
  const [installingIdentifier, setInstallingIdentifier] = useState<string | null>(null);
  const [installedNotice, setInstalledNotice] = useState<string | null>(null);

  const fetchSkills = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2`);
      if (res.ok) {
        const data = await res.json();
        setSkills(data || []);
      }
    } catch {
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchHubSources = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/hub/sources`);
      if (res.ok) {
        const data = await res.json();
        setHubSources(data || []);
      }
    } catch {}
  }, []);

  const searchHub = useCallback(async (query: string, source: string) => {
    setIsSearchingHub(true);
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/brain/skills/hub/search?q=${encodeURIComponent(query)}&source=${encodeURIComponent(source)}&limit=36`
      );
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setHubResults(data);
          setHubTotal(data.length);
        } else {
          setHubResults(data.results || []);
          setHubTotal(data.total || 0);
        }
      }
    } catch {
    } finally {
      setIsSearchingHub(false);
    }
  }, []);

  useEffect(() => {
    fetchSkills();
    fetchHubSources();
  }, [fetchSkills, fetchHubSources]);

  // Initial featured search when switching to hub tab
  useEffect(() => {
    if (activeTab === "hub" && hubResults.length === 0) {
      searchHub("", hubSource);
    }
  }, [activeTab, hubSource, hubResults.length, searchHub]);

  const handleToggleSkill = async (slug: string, currentStatus: string) => {
    const isCurrentlyActive = currentStatus === "active";
    const nextStatus = isCurrentlyActive ? "disabled" : "active";
    const nextEnabled = !isCurrentlyActive;

    // Optimistic UI update
    setTogglingSlug(slug);
    setSkills((prev) =>
      prev.map((s) =>
        s.slug === slug
          ? { ...s, status: nextStatus as any, enabled: nextEnabled }
          : s
      )
    );

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}/toggle`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: nextEnabled }),
      });
      if (!res.ok) {
        // Revert on failure
        fetchSkills();
      }
    } catch {
      fetchSkills();
    } finally {
      setTogglingSlug(null);
    }
  };

  const handleApproveSkill = async (slug: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}/approve`, {
        method: "POST",
      });
      if (res.ok) {
        setSkills((prev) =>
          prev.map((s) => (s.slug === slug ? { ...s, status: "active", enabled: true } : s))
        );
      }
    } catch {}
  };

  const handleDeleteSkill = async (slug: string, name: string) => {
    if (!confirm(`Permanently delete skill '${name}' from Anara runtime disk?`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setSkills((prev) => prev.filter((s) => s.slug !== slug));
      }
    } catch {}
  };

  const handleInstallHubSkill = async (item: HubSkillItem) => {
    setInstallingIdentifier(item.identifier);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/hub/install`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          identifier: item.identifier,
          name: item.name,
          category: item.tags?.[0] || "community",
        }),
      });
      if (res.ok) {
        setHubResults((prev) =>
          prev.map((r) =>
            r.identifier === item.identifier ? { ...r, is_installed: true } : r
          )
        );
        setInstalledNotice(`Skill '${item.name}' successfully downloaded and active!`);
        setTimeout(() => setInstalledNotice(null), 4000);
        fetchSkills();
      } else {
        const err = await res.json().catch(() => ({ detail: "Failed to download" }));
        alert(`Failed to install skill: ${err.detail || "Error"}`);
      }
    } catch (e: any) {
      alert(`Failed to install: ${e.message}`);
    } finally {
      setInstallingIdentifier(null);
    }
  };

  const handleAddSkillSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSkillName.trim() || !newSkillDesc.trim()) return;
    try {
      const triggers = newSkillTriggers
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const steps = newSkillSteps
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);

      const res = await fetch(`${BACKEND_URL}/api/agent/skills`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newSkillName.trim(),
          category: newSkillCategory,
          description: newSkillDesc.trim(),
          trigger_keywords: triggers,
          procedure_steps: steps,
        }),
      });
      if (res.ok) {
        setNewSkillName("");
        setNewSkillDesc("");
        setNewSkillTriggers("");
        setNewSkillSteps("");
        setIsAddSkillOpen(false);
        fetchSkills();
      }
    } catch {}
  };

  const pendingCount = skills.filter((s) => s.status === "pending").length;
  const activeCount = skills.filter((s) => s.status === "active").length;
  const disabledCount = skills.filter((s) => s.status === "disabled").length;

  const filteredSkills = skills.filter((s) => {
    if (filterStatus === "active") return s.status === "active";
    if (filterStatus === "disabled") return s.status === "disabled";
    if (filterStatus === "pending") return s.status === "pending";
    return true;
  });

  return (
    <div className="space-y-6 font-sans select-text">
      {/* Top Banner Navigation: Installed vs Skills Hub */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 sm:p-5 rounded-2xl liquid-glass border border-white/10 shadow-lg">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <h3 className="text-xs sm:text-sm font-semibold text-white tracking-wide">
              Anara Skill Ecosystem (Hermes Parity)
            </h3>
            <span className="px-2 py-0.5 rounded-md text-[9px] font-mono uppercase bg-cyan-500/10 border border-cyan-400/20 text-cyan-300">
              100.000+ Skills Hub
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 leading-relaxed">
            Manage active runtime skills or download on-demand from the global community catalog.
          </p>
        </div>

        {/* View Switcher Tabs & Actions */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center p-1 rounded-xl bg-black/50 border border-white/10 text-xs font-mono">
            <button
              type="button"
              onClick={() => setActiveTab("installed")}
              className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === "installed"
                  ? "bg-cyan-500/25 text-cyan-200 font-bold border border-cyan-400/30 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <span>Terpasang</span>
              <span className="px-1.5 py-0.2 rounded text-[10px] bg-white/10 text-slate-200">
                {skills.length}
              </span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("hub")}
              className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === "hub"
                  ? "bg-cyan-500/25 text-cyan-200 font-bold border border-cyan-400/30 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <span>Skills Hub</span>
              <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-400/30">
                100k+
              </span>
            </button>
          </div>

          {activeTab === "installed" && (
            <button
              type="button"
              onClick={() => setIsAddSkillOpen((v) => !v)}
              className="px-3 py-2 rounded-xl bg-white/[0.07] hover:bg-white/[0.12] border border-white/15 text-slate-200 hover:text-white text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
              title="Create your own custom skill"
            >
              <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span>Create New</span>
            </button>
          )}
        </div>
      </div>

      {/* Global Success Notification */}
      {installedNotice && (
        <div className="p-3.5 px-4 rounded-xl bg-emerald-500/15 border border-emerald-400/30 flex items-center gap-3 text-emerald-200 text-xs font-mono animate-scale-up">
          <span className="text-emerald-400 text-base">✓</span>
          <span>{installedNotice}</span>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 1: INSTALLED SKILLS VIEW                                          */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === "installed" && (
        <>
          {/* Pending Approval Notice Banner */}
          {pendingCount > 0 && (
            <div className="p-3.5 px-4 rounded-xl bg-amber-500/15 border border-amber-400/30 flex items-center justify-between gap-3 text-amber-200 text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="text-amber-400 text-base">⚠️</span>
                <span>There are <b>{pendingCount} new skills</b> from autonomous learning awaiting your review.</span>
              </div>
              <button
                type="button"
                onClick={() => setFilterStatus("pending")}
                className="px-2.5 py-1 rounded-lg bg-amber-500/30 hover:bg-amber-500/40 text-amber-100 font-bold text-[11px] transition-colors cursor-pointer"
              >
                View Pending
              </button>
            </div>
          )}

          {/* Status Filter Tabs */}
          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-black/40 border border-white/10 w-fit text-xs font-mono">
            <button
              type="button"
              onClick={() => setFilterStatus("all")}
              className={`px-3 py-1 rounded-lg transition-colors cursor-pointer ${
                filterStatus === "all" ? "bg-white/15 text-white font-bold" : "text-slate-400 hover:text-white"
              }`}
            >
              Semua ({skills.length})
            </button>
            <button
              type="button"
              onClick={() => setFilterStatus("active")}
              className={`px-3 py-1 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
                filterStatus === "active" ? "bg-emerald-500/20 text-emerald-200 font-bold border border-emerald-400/30" : "text-slate-400 hover:text-white"
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Active ({activeCount})</span>
            </button>
            <button
              type="button"
              onClick={() => setFilterStatus("disabled")}
              className={`px-3 py-1 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
                filterStatus === "disabled" ? "bg-slate-700/50 text-slate-200 font-bold border border-white/20" : "text-slate-400 hover:text-white"
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
              <span>Inactive ({disabledCount})</span>
            </button>
            {pendingCount > 0 && (
              <button
                type="button"
                onClick={() => setFilterStatus("pending")}
                className={`px-3 py-1 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
                  filterStatus === "pending" ? "bg-amber-500/20 text-amber-200 font-bold border border-amber-400/30" : "text-slate-400 hover:text-white"
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                <span>Pending Review ({pendingCount})</span>
              </button>
            )}
          </div>

          {/* Form Tambah Skill Manual Modal */}
          {isAddSkillOpen && (
            <form onSubmit={handleAddSkillSubmit} className="p-5 rounded-2xl liquid-glass border border-white/20 space-y-3.5 animate-scale-up">
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <span className="text-xs font-bold font-mono text-cyan-300 uppercase">Tambah Keahlian Mandiri (agentskills.io v2)</span>
                <button type="button" onClick={() => setIsAddSkillOpen(false)} className="text-slate-400 hover:text-white text-xs">✕</button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2 space-y-1">
                  <label className="text-[11px] font-mono text-slate-400">Nama Keahlian / Skill</label>
                  <input
                    type="text"
                    placeholder="Example: Excel Financial Report Analysis"
                    value={newSkillName}
                    onChange={(e) => setNewSkillName(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-400 font-sans"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-mono text-slate-400">Kategori</label>
                  <select
                    value={newSkillCategory}
                    onChange={(e) => setNewSkillCategory(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-xs text-white focus:outline-none focus:border-cyan-400 font-mono"
                  >
                    <option value="coding">Coding &amp; Software</option>
                    <option value="architecture">Architecture</option>
                    <option value="devops">DevOps &amp; Infra</option>
                    <option value="research">Riset &amp; Web</option>
                    <option value="document">Dokumen &amp; PDF</option>
                    <option value="communication">Komunikasi</option>
                    <option value="general">Umum</option>
                  </select>
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-mono text-slate-400">Deskripsi Keahlian</label>
                <input
                  type="text"
                   placeholder="Describe what this skill does..."
                  value={newSkillDesc}
                  onChange={(e) => setNewSkillDesc(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-400"
                  required
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] font-mono text-slate-400">Kata Kunci Pemicu (pisahkan koma)</label>
                  <input
                    type="text"
                    placeholder="report, excel, revenue, finance"
                    value={newSkillTriggers}
                    onChange={(e) => setNewSkillTriggers(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-400 font-mono"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-mono text-slate-400">Langkah Prosedur (1 langkah per baris)</label>
                  <textarea
                    rows={2}
                    placeholder={"1. Baca file excel\n2. Hitung rasio\n3. Buat ringkasan"}
                    value={newSkillSteps}
                    onChange={(e) => setNewSkillSteps(e.target.value)}
                    className="w-full px-3 py-1 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-400 font-mono"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <button type="button" onClick={() => setIsAddSkillOpen(false)} className="px-3 py-1.5 rounded-xl text-xs text-slate-400 hover:text-white">Batal</button>
                <button type="submit" className="px-4 py-1.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/35 border border-cyan-400/40 text-xs font-semibold text-white transition-all cursor-pointer">Save Skill</button>
              </div>
            </form>
          )}

          {/* Grid Kartu Skills v2 */}
          {filteredSkills.length === 0 ? (
            <div className="p-8 text-center rounded-2xl liquid-glass border border-white/10 text-slate-400 text-xs font-mono">
               No skills with this status.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredSkills.map((s) => {
                const isPending = s.status === "pending";
                const isActive = s.status === "active";
                const isDisabled = s.status === "disabled";
                const isToggling = togglingSlug === s.slug;

                return (
                  <div
                    key={s.slug}
                    className={`p-5 rounded-2xl border flex flex-col justify-between transition-all space-y-3.5 ${
                      isPending
                        ? "bg-amber-950/20 border-amber-500/40 shadow-[0_0_20px_rgba(251,191,36,0.12)]"
                        : isDisabled
                        ? "bg-white/[0.02] border-white/5 opacity-70 hover:opacity-90"
                        : "liquid-glass border-white/15 hover:border-cyan-400/30 shadow-lg"
                    }`}
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-3">
                          <div className={`w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 ${
                            isPending
                              ? "bg-amber-500/20 border-amber-400/40 text-amber-300"
                              : isDisabled
                              ? "bg-slate-800/60 border-white/10 text-slate-400"
                              : "bg-white/[0.05] border-white/10 text-cyan-300"
                          }`}>
                            <CategoryIcon category={s.category} className="w-4 h-4" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <h4 className={`text-sm font-semibold ${isDisabled ? "text-slate-300 line-through decoration-slate-500" : "text-white"}`}>
                                {s.name}
                              </h4>
                              {s.learned_from_experience && (
                                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-cyan-500/10 text-cyan-300 border border-cyan-400/25">
                                  Otomatis
                                </span>
                              )}
                              {isPending && (
                                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-400/40 animate-pulse">
                                  Pending Review
                                </span>
                              )}
                            </div>
                            <span className="text-[10px] text-slate-500 font-mono">
                              {s.category.toUpperCase()} • {s.slug}
                            </span>
                          </div>
                        </div>

                        {/* Top Right Action: Toggle Switch or Approve */}
                        {isPending ? (
                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleApproveSkill(s.slug)}
                              className="px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold uppercase bg-emerald-500/20 hover:bg-emerald-500/35 border border-emerald-400/40 text-emerald-200 cursor-pointer transition-all shadow-sm"
                              title="Approve this skill to activate"
                            >
                              ✓ Approve
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteSkill(s.slug, s.name)}
                              className="px-2 py-1 rounded-lg text-[10px] font-mono text-rose-300 hover:bg-rose-500/20 border border-rose-500/30 cursor-pointer transition-all"
                              title="Reject & delete skill"
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            {/* Toggle ON/OFF Switch */}
                            <label className="flex items-center gap-2 cursor-pointer select-none" title={isActive ? "Disable this skill (save context)" : "Enable this skill"}>
                              <span className={`text-[10px] font-mono font-semibold uppercase ${isActive ? "text-emerald-300" : "text-slate-500"}`}>
                                {isActive ? "Active" : "Inactive"}
                              </span>
                              <div
                                onClick={() => !isToggling && handleToggleSkill(s.slug, s.status)}
                                className={`w-9 h-5 rounded-full p-0.5 transition-colors duration-200 ease-in-out relative ${
                                  isActive ? "bg-emerald-500" : "bg-slate-700"
                                } ${isToggling ? "opacity-50" : ""}`}
                              >
                                <div
                                  className={`w-4 h-4 rounded-full bg-white transition-transform duration-200 ease-in-out ${
                                    isActive ? "translate-x-4" : "translate-x-0"
                                  }`}
                                />
                              </div>
                            </label>
                          </div>
                        )}
                      </div>

                      <p className="text-xs text-slate-300 mt-2.5 leading-relaxed">{s.description}</p>

                      {s.trigger_keywords && s.trigger_keywords.length > 0 && (
                        <div className="mt-2.5 flex items-center gap-1.5 flex-wrap">
                          <span className="text-[10px] font-mono text-slate-500">Pemicu:</span>
                          {s.trigger_keywords.map((kw, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/8 text-[10px] font-mono text-slate-300">
                              {kw}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {s.body && (
                      <div className="p-3 rounded-xl bg-black/50 border border-white/10 space-y-1 text-[11px] font-mono text-slate-300 max-h-40 overflow-y-auto custom-scrollbar">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                          Dokumen SKILL.md:
                        </span>
                        <pre className="whitespace-pre-wrap font-mono text-[10.5px] leading-relaxed text-slate-300">
                          {s.body}
                        </pre>
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-1 border-t border-white/5 text-[10px] font-mono text-slate-500">
                      <span className="truncate max-w-[220px]" title={s.file_path}>
                        📁 skills/{s.slug}/SKILL.md
                      </span>
                      {!isPending && (
                        <button
                          type="button"
                          onClick={() => handleDeleteSkill(s.slug, s.name)}
                          className="text-[11px] text-slate-500 hover:text-rose-400 transition-colors cursor-pointer flex items-center gap-1"
                        >
                          <span>Delete</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 2: SKILLS HUB (100,000+ KOMUNITAS) EXPLORER                      */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === "hub" && (
        <div className="space-y-4">
          {/* Hub Search & Source Filter Bar */}
          <div className="p-4 rounded-2xl liquid-glass border border-white/10 space-y-3">
            <div className="flex flex-col sm:flex-row gap-3">
              {/* Search input */}
              <div className="relative flex-1">
                <svg className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  placeholder="Search from 100,621+ skills (e.g. crypto, excel, blender, docker, seo, react)..."
                  value={hubQuery}
                  onChange={(e) => setHubQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") searchHub(hubQuery, hubSource);
                  }}
                  className="w-full pl-10 pr-4 py-2 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-400 font-sans"
                />
              </div>

              {/* Source registry dropdown */}
              <select
                value={hubSource}
                onChange={(e) => {
                  setHubSource(e.target.value);
                  searchHub(hubQuery, e.target.value);
                }}
                className="px-3 py-2 rounded-xl bg-black/60 border border-white/15 text-xs text-cyan-300 focus:outline-none focus:border-cyan-400 font-mono shrink-0"
              >
                <option value="all">Semua Registry (100k+)</option>
                {hubSources.filter((s) => s.id !== "all").map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.count.toLocaleString()})
                  </option>
                ))}
              </select>

              {/* Search button */}
              <button
                type="button"
                onClick={() => searchHub(hubQuery, hubSource)}
                disabled={isSearchingHub}
                className="px-4 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/35 border border-cyan-400/40 text-cyan-200 text-xs font-semibold transition-all cursor-pointer flex items-center justify-center gap-1.5 shrink-0"
              >
                {isSearchingHub ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                    <span>Searching...</span>
                  </>
                ) : (
                  <span>Search Catalog</span>
                )}
              </button>
            </div>

            {/* Quick tags pills */}
            <div className="flex items-center gap-1.5 flex-wrap pt-1 text-[11px] font-mono text-slate-400">
              <span className="text-slate-500">Popular Searches:</span>
              {["crypto", "docker", "blender", "excel", "security", "scraping", "github", "react", "fastapi"].map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => {
                    setHubQuery(tag);
                    searchHub(tag, hubSource);
                  }}
                  className="px-2 py-0.5 rounded-md bg-white/[0.04] hover:bg-white/[0.1] border border-white/10 text-slate-300 text-[10px] transition-all cursor-pointer"
                >
                  #{tag}
                </button>
              ))}
            </div>
          </div>

          {/* Search Result Summary */}
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 px-1">
            <span>
              Menemukan <b className="text-white">{hubTotal.toLocaleString()}</b> keahlian di Skills Hub.
            </span>
            <span className="text-[11px] text-slate-500">
              Catalog updated on-demand &amp; verified
            </span>
          </div>

          {/* Hub Results Grid */}
          {isSearchingHub ? (
            <div className="p-12 text-center rounded-2xl liquid-glass border border-white/10 text-slate-400 text-xs font-mono flex flex-col items-center justify-center gap-3">
              <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
              <span>Menelusuri database 100.621 keahlian komunitas...</span>
            </div>
          ) : hubResults.length === 0 ? (
            <div className="p-12 text-center rounded-2xl liquid-glass border border-white/10 text-slate-400 text-xs font-mono">
              No skills found matching that keyword. Try different keywords or select &apos;All Registry&apos;.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {hubResults.map((item, idx) => {
                const isInstalling = installingIdentifier === item.identifier;
                const isInstalled = Boolean(item.is_installed);

                return (
                  <div
                    key={`${item.identifier}-${idx}`}
                    className="p-5 rounded-2xl liquid-glass border border-white/15 hover:border-cyan-400/30 transition-all flex flex-col justify-between space-y-3 shadow-md"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <h4 className="text-sm font-semibold text-white tracking-wide">
                              {item.name}
                            </h4>
                            {/* Source Badge */}
                            <span className={`px-2 py-0.5 rounded-md text-[9px] font-mono font-bold uppercase border ${
                              item.source === "official"
                                ? "bg-cyan-500/20 text-cyan-200 border-cyan-400/30"
                                : item.source === "github"
                                ? "bg-purple-500/20 text-purple-200 border-purple-400/30"
                                : item.source === "skills.sh"
                                ? "bg-emerald-500/20 text-emerald-200 border-emerald-400/30"
                                : item.source === "clawhub"
                                ? "bg-amber-500/20 text-amber-200 border-amber-400/30"
                                : "bg-white/10 text-slate-300 border-white/15"
                            }`}>
                              {item.source}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono block mt-0.5 truncate max-w-[280px]" title={item.identifier}>
                            {item.identifier}
                          </span>
                        </div>

                        {/* Install Button */}
                        <div className="shrink-0">
                          {isInstalled ? (
                            <span className="px-3 py-1 rounded-xl bg-emerald-500/10 text-emerald-300 border border-emerald-400/30 text-xs font-mono font-semibold flex items-center gap-1">
              <span>Installed</span>
                              <span>✓</span>
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleInstallHubSkill(item)}
                              disabled={isInstalling}
                              className="px-3.5 py-1.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/35 border border-cyan-400/40 text-cyan-200 text-xs font-semibold transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
                            >
                              {isInstalling ? (
                                <>
                                  <span className="w-3 h-3 border-2 border-cyan-300 border-t-transparent rounded-full animate-spin" />
                                  <span>Mengunduh...</span>
                                </>
                              ) : (
                                <>
                                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                  </svg>
                                  <span>Install</span>
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      </div>

                      <p className="text-xs text-slate-300 mt-2.5 leading-relaxed line-clamp-3">
                        {item.description || "No detailed description available for this skill."}
                      </p>

                      {item.tags && item.tags.length > 0 && (
                        <div className="mt-2.5 flex items-center gap-1.5 flex-wrap">
                          {item.tags.slice(0, 5).map((t, ti) => (
                            <span key={ti} className="px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/8 text-[9px] font-mono text-slate-400">
                              #{t}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-white/5 text-[10px] font-mono text-slate-500">
                      <span>Trust: {item.trust_level || "community"}</span>
                      {item.repo && (
                        <span className="truncate max-w-[180px]" title={item.repo}>
                          Repo: {item.repo}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
