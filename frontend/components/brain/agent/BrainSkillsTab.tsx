"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BACKEND_URL, AgentSkillV2, CategoryIcon } from "../types";

export default function BrainSkillsTab() {
  const [skills, setSkills] = useState<AgentSkillV2[]>([]);
  const [filterStatus, setFilterStatus] = useState<"all" | "active" | "pending">("all");
  const [isAddSkillOpen, setIsAddSkillOpen] = useState(false);
  const [newSkillName, setNewSkillName] = useState("");
  const [newSkillCategory, setNewSkillCategory] = useState("coding");
  const [newSkillDesc, setNewSkillDesc] = useState("");
  const [newSkillTriggers, setNewSkillTriggers] = useState("");
  const [newSkillSteps, setNewSkillSteps] = useState("");
  const [isLoading, setIsLoading] = useState(false);

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

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

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

  const handleApproveSkill = async (slug: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}/approve`, {
        method: "POST",
      });
      if (res.ok) {
        setSkills((prev) =>
          prev.map((s) => (s.slug === slug ? { ...s, status: "active" } : s))
        );
      }
    } catch {}
  };

  const handleDeleteSkill = async (slug: string, name: string) => {
    if (!confirm(`Hapus keahlian '${name}' dari repositori skill disk?`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setSkills((prev) => prev.filter((s) => s.slug !== slug));
      }
    } catch {}
  };

  const pendingCount = skills.filter((s) => s.status === "pending").length;
  const filteredSkills = skills.filter((s) => {
    if (filterStatus === "active") return s.status === "active";
    if (filterStatus === "pending") return s.status === "pending";
    return true;
  });

  return (
    <div className="space-y-6 font-sans select-text">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 sm:p-5 rounded-2xl liquid-glass border border-white/10">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
            <h3 className="text-xs sm:text-sm font-semibold text-white tracking-wide">
              Skill Library v2 (agentskills.io)
            </h3>
            <span className="px-2 py-0.5 rounded-md text-[9px] font-mono uppercase bg-cyan-500/10 border border-cyan-400/20 text-cyan-300">
              Folder + SKILL.md
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 leading-relaxed">
            Keahlian otonom yang tersimpan dalam format berkas modular dengan YAML frontmatter &amp; alur persetujuan (FR-15 &amp; FR-16).
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setIsAddSkillOpen((v) => !v)}
            className="px-3.5 py-2 rounded-xl bg-white/[0.07] hover:bg-white/[0.12] border border-white/15 text-slate-200 hover:text-white text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
          >
            <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>Tambah Keahlian</span>
          </button>
        </div>
      </div>

      {/* Pending Approval Notice Banner */}
      {pendingCount > 0 && (
        <div className="p-3.5 px-4 rounded-xl bg-amber-500/15 border border-amber-400/30 flex items-center justify-between gap-3 text-amber-200 text-xs font-mono">
          <div className="flex items-center gap-2">
            <span className="text-amber-400 text-base">⚠️</span>
            <span>Ada <b>{pendingCount} keahlian baru</b> hasil pembelajaran otonom yang menunggu review Anda.</span>
          </div>
          <button
            type="button"
            onClick={() => setFilterStatus("pending")}
            className="px-2.5 py-1 rounded-lg bg-amber-500/30 hover:bg-amber-500/40 text-amber-100 font-bold text-[11px] transition-colors cursor-pointer"
          >
            Lihat Pending
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
          <span>Aktif ({skills.filter((s) => s.status === "active").length})</span>
        </button>
        <button
          type="button"
          onClick={() => setFilterStatus("pending")}
          className={`px-3 py-1 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
            filterStatus === "pending" ? "bg-amber-500/20 text-amber-200 font-bold border border-amber-400/30" : "text-slate-400 hover:text-white"
          }`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          <span>Menunggu Review ({pendingCount})</span>
        </button>
      </div>

      {/* Form Tambah Skill Manual Modal */}
      {isAddSkillOpen && (
        <form onSubmit={handleAddSkillSubmit} className="p-5 rounded-2xl liquid-glass border border-white/20 space-y-3.5 animate-scale-up">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <span className="text-xs font-bold font-mono text-cyan-300 uppercase">Tambah Keahlian Otonom (v2)</span>
            <button type="button" onClick={() => setIsAddSkillOpen(false)} className="text-slate-400 hover:text-white text-xs">✕</button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2 space-y-1">
              <label className="text-[11px] font-mono text-slate-400">Nama Keahlian / Skill</label>
              <input
                type="text"
                placeholder="Contoh: Analisis Laporan Keuangan Excel"
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
                <option value="architecture">Arsitektur</option>
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
              placeholder="Jelaskan apa yang dilakukan keahlian ini..."
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
                placeholder="laporan, excel, omzet, keuangan"
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
            <button type="submit" className="px-4 py-1.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/35 border border-cyan-400/40 text-xs font-semibold text-white transition-all cursor-pointer">Simpan Keahlian</button>
          </div>
        </form>
      )}

      {/* Grid Kartu Skills v2 */}
      {filteredSkills.length === 0 ? (
        <div className="p-8 text-center rounded-2xl liquid-glass border border-white/10 text-slate-400 text-xs font-mono">
          Belum ada keahlian dengan status ini.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredSkills.map((s) => {
            const isPending = s.status === "pending";
            return (
              <div
                key={s.slug}
                className={`p-5 rounded-2xl border flex flex-col justify-between transition-all space-y-3.5 ${
                  isPending
                    ? "bg-amber-950/20 border-amber-500/40 shadow-[0_0_20px_rgba(251,191,36,0.12)]"
                    : "liquid-glass border-white/15 hover:border-cyan-400/30 shadow-lg"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-3">
                      <div className={`w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 ${
                        isPending ? "bg-amber-500/20 border-amber-400/40 text-amber-300" : "bg-white/[0.05] border-white/10 text-cyan-300"
                      }`}>
                        <CategoryIcon category={s.category} className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="text-sm font-semibold text-white">{s.name}</h4>
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

                    {isPending ? (
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => handleApproveSkill(s.slug)}
                          className="px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold uppercase bg-emerald-500/20 hover:bg-emerald-500/35 border border-emerald-400/40 text-emerald-200 cursor-pointer transition-all shadow-sm"
                          title="Setujui keahlian ini agar aktif di system prompt"
                        >
                          ✓ Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteSkill(s.slug, s.name)}
                          className="px-2 py-1 rounded-lg text-[10px] font-mono text-rose-300 hover:bg-rose-500/20 border border-rose-500/30 cursor-pointer transition-all"
                          title="Tolak & hapus keahlian ini"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <span className="px-2 py-0.5 rounded-lg text-[10px] font-mono font-medium uppercase bg-emerald-500/10 text-emerald-300 border border-emerald-400/30 flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        <span>Aktif</span>
                      </span>
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
                  <span className="truncate max-w-[200px]" title={s.file_path}>
                    📁 backend/skills/{s.slug}/SKILL.md
                  </span>
                  {!isPending && (
                    <button
                      type="button"
                      onClick={() => handleDeleteSkill(s.slug, s.name)}
                      className="text-[11px] text-slate-500 hover:text-rose-400 transition-colors cursor-pointer flex items-center gap-1"
                    >
                      <span>Hapus</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
