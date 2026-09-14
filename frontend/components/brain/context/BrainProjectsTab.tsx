"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { BACKEND_URL, Project } from "../types";

interface BrainProjectsTabProps {
  activeSpeaker?: string | null;
  onRefreshAll?: () => void;
}

export default function BrainProjectsTab({
  activeSpeaker,
  onRefreshAll,
}: BrainProjectsTabProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isAddProjectOpen, setIsAddProjectOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectStack, setNewProjectStack] = useState("");
  const [newProjectGoal, setNewProjectGoal] = useState("");
  const [newProjectNotes, setNewProjectNotes] = useState("");

  const fetchProjects = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/projects`);
      if (res.ok) {
        const data = await res.json();
        setProjects(data || []);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleSaveProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newProjectName.trim(),
          speaker_name: activeSpeaker || "Agnan",
          tech_stack: newProjectStack.trim(),
          goal: newProjectGoal.trim(),
          notes: newProjectNotes.trim(),
          status: "active",
        }),
      });

      if (res.ok) {
        setIsAddProjectOpen(false);
        setNewProjectName("");
        setNewProjectStack("");
        setNewProjectGoal("");
        setNewProjectNotes("");
        fetchProjects();
        onRefreshAll?.();
      }
    } catch (err) {
      console.error("Save project error:", err);
    }
  };

  const handleDeleteProject = async (id: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/projects/${id}`, { method: "DELETE" });
      if (res.ok) {
        setProjects((prev) => prev.filter((p) => p.id !== id));
        onRefreshAll?.();
      }
    } catch (err) {
      console.error("Delete project error:", err);
    }
  };

  const currentSpeakerProjects = useMemo(() => {
    if (!activeSpeaker) return projects;
    return projects.filter((p) => (p.speaker_name || "").toLowerCase() === activeSpeaker.toLowerCase());
  }, [projects, activeSpeaker]);

  return (
    <div className="space-y-5 font-sans select-text">
      {!activeSpeaker ? (
        <div className="p-10 sm:p-14 rounded-3xl liquid-glass-subtle text-center flex flex-col items-center justify-center gap-3 animate-fade-in">
          <div className="w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-400/30 flex items-center justify-center text-cyan-300 shadow-[0_0_24px_rgba(34,211,238,0.2)]">
            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
          </div>
          <h4 className="text-sm sm:text-base font-bold text-white uppercase tracking-wider">
            Menunggu Identifikasi Pengguna
          </h4>
          <p className="text-xs sm:text-sm text-slate-300 max-w-lg leading-relaxed">
            Proyek kerja dan riwayat target disimpan khusus per profil. Silakan bicara atau pilih profil Anda agar Anara memuat konteks proyek Anda.
          </p>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <span className="text-[10px] uppercase tracking-wider text-cyan-300 font-semibold">
                Konteks Proyek • {activeSpeaker}
              </span>
              <h3 className="text-base sm:text-lg font-bold text-white mt-0.5">
                {currentSpeakerProjects.length} Proyek Terdaftar
              </h3>
            </div>

            <button
              onClick={() => setIsAddProjectOpen(true)}
              className="px-4 py-2 rounded-2xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white font-semibold text-xs flex items-center gap-1.5 cursor-pointer shadow-[0_4px_20px_rgba(34,211,238,0.25)] transition-all hover:opacity-90 active:scale-[0.98]"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Proyek Baru
            </button>
          </div>

          {isAddProjectOpen && (
            <form onSubmit={handleSaveProject} className="p-5 rounded-2xl liquid-glass space-y-3.5 animate-fade-in">
              <h4 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">Proyek / Konteks Kerja Baru</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="Nama Proyek (cth: Sistem Asisten Anara)"
                  className="liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                  required
                />
                <input
                  type="text"
                  value={newProjectStack}
                  onChange={(e) => setNewProjectStack(e.target.value)}
                  placeholder="Tech Stack (cth: Next.js, FastAPI, SQLite)"
                  className="liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                />
              </div>
              <input
                type="text"
                value={newProjectGoal}
                onChange={(e) => setNewProjectGoal(e.target.value)}
                placeholder="Target / Sasaran Utama Proyek Ini"
                className="w-full liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
              />
              <input
                type="text"
                value={newProjectNotes}
                onChange={(e) => setNewProjectNotes(e.target.value)}
                placeholder="Catatan tambahan untuk Anara (opsional)"
                className="w-full liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
              />
              <div className="flex justify-end gap-2.5 pt-1">
                <button
                  type="button"
                  onClick={() => setIsAddProjectOpen(false)}
                  className="px-4 py-2 rounded-xl liquid-glass-subtle border border-white/10 text-slate-300 text-xs cursor-pointer"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-slate-950 font-bold text-xs cursor-pointer shadow-[0_4px_16px_rgba(245,158,11,0.3)] transition-all hover:opacity-90"
                >
                  Simpan
                </button>
              </div>
            </form>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {currentSpeakerProjects.length === 0 ? (
              <p className="col-span-2 text-xs text-slate-400 text-center py-16 rounded-2xl liquid-glass-subtle">Belum ada catatan proyek kerja untuk {activeSpeaker}. Klik 'Proyek Baru' atau ceritakan proyek Anda saat mengobrol.</p>
            ) : (
              currentSpeakerProjects.map((p) => (
                <div
                  key={p.id}
                  className="p-5 rounded-2xl liquid-glass-subtle hover:border-amber-400/40 flex flex-col justify-between gap-3 transition-all duration-300"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-white truncate">{p.name}</span>
                      <span className="text-[10px] uppercase tracking-wide px-2.5 py-1 rounded-full bg-amber-400/15 text-amber-300 border border-amber-400/25 shrink-0">
                        {p.status}
                      </span>
                    </div>
                    {p.tech_stack && (
                      <p className="text-[11px] text-cyan-300 mt-1.5">Tech: {p.tech_stack}</p>
                    )}
                    {p.goal && (
                      <p className="text-xs text-slate-200 mt-2 leading-relaxed">Target: {p.goal}</p>
                    )}
                    {p.notes && (
                      <p className="text-xs text-slate-400 mt-1 italic">{p.notes}</p>
                    )}
                  </div>

                  <div className="flex items-center justify-between pt-2.5 border-t border-white/[0.07] text-[10px] text-slate-500">
                    <span>Diperbarui: {new Date(p.updated_at).toLocaleDateString("id-ID")}</span>
                    <button
                      onClick={() => handleDeleteProject(p.id)}
                      className="text-slate-500 hover:text-rose-400 transition-colors p-1 cursor-pointer"
                      title="Hapus proyek"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
