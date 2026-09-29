"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { BACKEND_URL, Note, LiquidGlassSelect, SelectOption } from "../types";

interface BrainTodosTabProps {
  activeSpeaker?: string | null;
  onRefreshAll?: () => void;
}

export default function BrainTodosTab({
  activeSpeaker,
  onRefreshAll,
}: BrainTodosTabProps) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [todoFilter, setTodoFilter] = useState<"all" | "active" | "completed">("all");
  const [isAddNoteOpen, setIsAddNoteOpen] = useState(false);
  const [newNoteTitle, setNewNoteTitle] = useState("");
  const [newNoteContent, setNewNoteContent] = useState("");
  const [newNoteCategory, setNewNoteCategory] = useState("todo");

  const fetchNotes = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/notes`);
      if (res.ok) {
        const data = await res.json();
        setNotes(data || []);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchNotes();
  }, [fetchNotes]);

  const handleSaveNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNoteTitle.trim()) return;

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newNoteTitle.trim(),
          content: newNoteContent.trim(),
          category: newNoteCategory,
          speaker_name: activeSpeaker || "User",
        }),
      });

      if (res.ok) {
        setIsAddNoteOpen(false);
        setNewNoteTitle("");
        setNewNoteContent("");
        fetchNotes();
        onRefreshAll?.();
      }
    } catch (err) {
      console.error("Save note error:", err);
    }
  };

  const handleToggleTodo = async (id: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/notes/${id}/toggle`, {
        method: "PATCH",
      });
      if (res.ok) {
        setNotes((prev) =>
          prev.map((n) => (n.id === id ? { ...n, is_completed: n.is_completed ? 0 : 1 } : n))
        );
        onRefreshAll?.();
      }
    } catch (err) {
      console.error("Toggle todo error:", err);
    }
  };

  const handleDeleteNote = async (id: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/notes/${id}`, { method: "DELETE" });
      if (res.ok) {
        setNotes((prev) => prev.filter((n) => n.id !== id));
        onRefreshAll?.();
      }
    } catch (err) {
      console.error("Delete note error:", err);
    }
  };

  const currentSpeakerNotes = useMemo(() => {
    return notes;
  }, [notes]);

  const filteredNotes = useMemo(() => {
    return currentSpeakerNotes.filter((n) => {
      if (todoFilter === "active") return !n.is_completed;
      if (todoFilter === "completed") return n.is_completed;
      return true;
    });
  }, [currentSpeakerNotes, todoFilter]);

  const completedNotesCount = useMemo(
    () => currentSpeakerNotes.filter((n) => n.is_completed).length,
    [currentSpeakerNotes]
  );

  const progressPercent = useMemo(
    () => (currentSpeakerNotes.length ? Math.round((completedNotesCount / currentSpeakerNotes.length) * 100) : 0),
    [completedNotesCount, currentSpeakerNotes.length]
  );

  const noteCategoryOptions: SelectOption[] = [
    { value: "todo", label: "Tasks (To-Do)" },
    { value: "reminder", label: "Reminder" },
    { value: "idea", label: "Idea" },
    { value: "general", label: "General" },
  ];

  return (
    <div className="space-y-4 font-sans select-text">
      {/* Progress Ribbon */}
      <div className="p-3.5 rounded-xl bg-white/[0.025] border border-white/[0.08] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 font-semibold">
            Task Execution
          </span>
          <h3 className="text-sm sm:text-base font-semibold text-white mt-0.5">
            {completedNotesCount} of {currentSpeakerNotes.length} Tasks Completed ({progressPercent}%)
          </h3>
        </div>
        <div className="w-full sm:w-48 h-2 rounded-full bg-black/40 overflow-hidden border border-white/[0.08]">
          <div
            className="h-full rounded-full bg-cyan-400 transition-all duration-500 shadow-[0_0_8px_rgba(34,211,238,0.5)]"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Filter & Add Actions */}
      <div className="flex items-center justify-between gap-2.5 flex-wrap">
        <div className="flex items-center gap-1 p-0.5 rounded-lg bg-white/[0.03] border border-white/[0.08]">
          {[
            { id: "all", label: "All" },
            { id: "active", label: "Active" },
            { id: "completed", label: "Completed" },
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => setTodoFilter(f.id as any)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                todoFilter === f.id
                  ? "bg-white/[0.08] text-white border border-white/[0.12] shadow-sm"
                  : "text-slate-400 hover:text-slate-200 border border-transparent"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <button
          onClick={() => setIsAddNoteOpen(true)}
          className="px-3.5 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.12] text-slate-200 hover:text-white font-medium text-xs flex items-center gap-1.5 cursor-pointer transition-all active:scale-[0.98]"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>New Task</span>
        </button>
      </div>

      {isAddNoteOpen && (
        <form onSubmit={handleSaveNote} className="relative z-30 p-4 rounded-xl bg-[#080d1a] border border-white/[0.12] space-y-3 animate-fade-in shadow-lg">
          <h4 className="text-xs font-mono font-semibold text-cyan-400 uppercase tracking-wider">New Task / Scratchpad Item</h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <input
              type="text"
              value={newNoteTitle}
              onChange={(e) => setNewNoteTitle(e.target.value)}
              placeholder="Task Title (e.g. Audit API Endpoints)"
              className="bg-black/40 border border-white/[0.08] rounded-lg py-2 px-3 text-xs text-white placeholder-slate-500 focus:outline-none sm:col-span-2"
              required
            />
            <LiquidGlassSelect
              value={newNoteCategory}
              onChange={setNewNoteCategory}
              options={noteCategoryOptions}
            />
          </div>
          <input
            type="text"
            value={newNoteContent}
            onChange={(e) => setNewNoteContent(e.target.value)}
            placeholder="Detailed task description or checklist notes (optional)"
            className="w-full bg-black/40 border border-white/[0.08] rounded-lg py-2 px-3 text-xs text-white placeholder-slate-500 focus:outline-none"
          />
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setIsAddNoteOpen(false)}
              className="px-3 py-1.5 rounded-lg border border-white/[0.08] text-slate-300 hover:text-white text-xs cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 rounded-lg bg-white/[0.08] hover:bg-white/[0.15] border border-white/[0.14] text-white font-medium text-xs cursor-pointer transition-all"
            >
              Save Task
            </button>
          </div>
        </form>
      )}

      <div className="space-y-2">
        {filteredNotes.length === 0 ? (
          <div className="p-8 sm:p-12 rounded-xl bg-white/[0.02] border border-white/[0.08] text-center flex flex-col items-center justify-center gap-2">
            <div className="w-10 h-10 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-slate-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            </div>
            <h4 className="text-xs font-semibold text-slate-200">No tasks in this view</h4>
            <p className="text-[11px] text-slate-400 max-w-sm">
              Keep track of multi-step plans and agent instructions with tasks.
            </p>
          </div>
        ) : (
          filteredNotes.map((n) => (
            <div
              key={n.id}
              className={`p-3 px-3.5 rounded-xl border transition-all flex items-start justify-between gap-3 shadow-sm ${
                n.is_completed
                  ? "bg-white/[0.015] border-white/[0.05] opacity-50"
                  : "bg-white/[0.025] hover:bg-white/[0.04] border-white/[0.08] hover:border-white/[0.15]"
              }`}
            >
              <div className="flex items-start gap-3 min-w-0 flex-1">
                <button
                  onClick={() => handleToggleTodo(n.id)}
                  className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 mt-0.5 cursor-pointer transition-all duration-150 ${
                    n.is_completed
                      ? "bg-cyan-400 border-cyan-400 text-black shadow-[0_0_8px_rgba(34,211,238,0.4)]"
                      : "border-white/20 hover:border-white/40 hover:bg-white/[0.06] text-transparent"
                  }`}
                >
                  <svg className="w-2.5 h-2.5 stroke-[3]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </button>
                <div className="truncate min-w-0 flex-1">
                  <p className={`text-xs ${n.is_completed ? "line-through text-slate-500 font-normal" : "text-white font-medium"}`}>
                    {n.title}
                  </p>
                  {n.content && <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">{n.content}</p>}
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[10px] font-mono uppercase tracking-wide px-2 py-0.5 rounded bg-white/[0.05] text-slate-300 border border-white/[0.08]">
                  {n.category}
                </span>
                <button
                  onClick={() => handleDeleteNote(n.id)}
                  className="text-slate-500 hover:text-rose-400 p-1 cursor-pointer transition-colors"
                  title="Delete task"
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
