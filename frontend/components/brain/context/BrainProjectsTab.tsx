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
          speaker_name: activeSpeaker || "User",
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
    return projects;
  }, [projects]);

  return (
    <div className="space-y-4 font-sans select-text">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 font-semibold">
            Tracked Workspaces
          </span>
          <h3 className="text-sm sm:text-base font-semibold text-white mt-0.5">
            {currentSpeakerProjects.length} Active Contexts
          </h3>
        </div>

        <button
          onClick={() => setIsAddProjectOpen(true)}
          className="px-3.5 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.12] text-slate-200 hover:text-white font-medium text-xs flex items-center gap-1.5 cursor-pointer transition-all active:scale-[0.98]"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>New Project</span>
        </button>
      </div>

      {isAddProjectOpen && (
        <form onSubmit={handleSaveProject} className="p-4 rounded-xl bg-[#080d1a] border border-white/[0.12] space-y-3 animate-fade-in shadow-lg">
          <h4 className="text-xs font-mono font-semibold text-cyan-400 uppercase tracking-wider">New Project / Work Context</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <input
              type="text"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              placeholder="Project Name (e.g. Project Anara)"
              className="bg-black/40 border border-white/[0.08] rounded-lg py-2 px-3 text-xs text-white placeholder-slate-500 focus:outline-none"
              required
            />
            <input
              type="text"
              value={newProjectStack}
              onChange={(e) => setNewProjectStack(e.target.value)}
              placeholder="Tech Stack (e.g. Next.js, FastAPI, SQLite)"
              className="bg-black/40 border border-white/[0.08] rounded-lg py-2 px-3 text-xs text-white placeholder-slate-500 focus:outline-none"
            />
          </div>
          <input
            type="text"
            value={newProjectGoal}
            onChange={(e) => setNewProjectGoal(e.target.value)}
            placeholder="Primary Goal / Deliverable"
            className="w-full bg-black/40 border border-white/[0.08] rounded-lg py-2 px-3 text-xs text-white placeholder-slate-500 focus:outline-none"
          />
          <input
            type="text"
            value={newProjectNotes}
            onChange={(e) => setNewProjectNotes(e.target.value)}
            placeholder="Architectural notes, constraints, or guidelines (optional)"
            className="w-full bg-black/40 border border-white/[0.08] rounded-lg py-2 px-3 text-xs text-white placeholder-slate-500 focus:outline-none"
          />
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setIsAddProjectOpen(false)}
              className="px-3 py-1.5 rounded-lg border border-white/[0.08] text-slate-300 hover:text-white text-xs cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 rounded-lg bg-white/[0.08] hover:bg-white/[0.15] border border-white/[0.14] text-white font-medium text-xs cursor-pointer transition-all"
            >
              Save Project
            </button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {currentSpeakerProjects.length === 0 ? (
          <div className="col-span-2 p-8 sm:p-12 rounded-xl bg-white/[0.02] border border-white/[0.08] text-center flex flex-col items-center justify-center gap-2">
            <div className="w-10 h-10 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-slate-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
            </div>
            <h4 className="text-xs font-semibold text-slate-200">No project workspaces tracked yet</h4>
            <p className="text-[11px] text-slate-400 max-w-sm">
              Click 'New Project' or discuss your project in chat to provide Anara with deep repository context.
            </p>
          </div>
        ) : (
          currentSpeakerProjects.map((p) => (
            <div
              key={p.id}
              className="p-3.5 rounded-xl bg-white/[0.025] hover:bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] flex flex-col justify-between gap-2.5 transition-all shadow-sm"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-white truncate">{p.name}</span>
                  <span className="text-[10px] font-mono uppercase tracking-wide px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-400/20 shrink-0">
                    {p.status}
                  </span>
                </div>
                {p.tech_stack && (
                  <p className="text-[11px] font-mono text-cyan-400/90 mt-1">Stack: {p.tech_stack}</p>
                )}
                {p.goal && (
                  <p className="text-xs text-slate-200 mt-1.5 leading-relaxed">{p.goal}</p>
                )}
                {p.notes && (
                  <p className="text-[11px] text-slate-400 mt-1 italic">{p.notes}</p>
                )}
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-white/[0.05] text-[10px] font-mono text-slate-500">
                <span>Updated: {new Date(p.updated_at).toLocaleDateString("id-ID")}</span>
                <button
                  onClick={() => handleDeleteProject(p.id)}
                  className="text-slate-500 hover:text-rose-400 transition-colors p-1 cursor-pointer"
                  title="Delete project"
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
    </div>
  );
}
