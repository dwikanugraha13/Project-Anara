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
          speaker_name: activeSpeaker || "Agnan",
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
    if (!activeSpeaker) return notes;
    return notes.filter((n) => (n.speaker_name || "").toLowerCase() === activeSpeaker.toLowerCase());
  }, [notes, activeSpeaker]);

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
    { value: "todo", label: "Tugas (To-Do)" },
    { value: "reminder", label: "Pengingat" },
    { value: "idea", label: "Ide" },
    { value: "general", label: "Umum" },
  ];

  return (
    <div className="space-y-5 font-sans select-text">
      {!activeSpeaker ? (
        <div className="p-10 sm:p-14 rounded-3xl liquid-glass-subtle text-center flex flex-col items-center justify-center gap-3 animate-fade-in">
          <div className="w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-400/30 flex items-center justify-center text-cyan-300 shadow-[0_0_24px_rgba(34,211,238,0.2)]">
            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
          </div>
          <h4 className="text-sm sm:text-base font-bold text-white uppercase tracking-wider">
            Menunggu Identifikasi Pengguna
          </h4>
          <p className="text-xs sm:text-sm text-slate-300 max-w-lg leading-relaxed">
            Daftar to-do dan catatan personal disimpan berdasarkan profil pengguna. Silakan bicara atau perkenalkan diri agar Anara memuat tugas Anda.
          </p>
        </div>
      ) : (
        <>
          {/* Progress Ribbon */}
          <div className="p-5 rounded-2xl liquid-glass-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <span className="text-[10px] uppercase tracking-wider text-cyan-300 font-semibold">
                Penyelesaian Tugas • {activeSpeaker}
              </span>
              <h3 className="text-base font-bold text-white mt-0.5">
                {completedNotesCount} dari {currentSpeakerNotes.length} Tugas Selesai ({progressPercent}%)
              </h3>
            </div>
            <div className="w-full sm:w-48 h-2 rounded-full bg-black/40 overflow-hidden border border-white/10">
              <div
                className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-indigo-500 transition-all duration-500 shadow-[0_0_10px_rgba(34,211,238,0.3)]"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Filter & Add Actions */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-1 p-1 rounded-full liquid-glass-subtle">
              {[
                { id: "all", label: "Semua" },
                { id: "active", label: "Aktif" },
                { id: "completed", label: "Selesai" },
              ].map((f) => (
                <button
                  key={f.id}
                  onClick={() => setTodoFilter(f.id as any)}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer ${
                    todoFilter === f.id
                      ? "bg-cyan-500/20 text-cyan-100 border border-cyan-400/35"
                      : "text-slate-400 hover:text-slate-200 border border-transparent"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

            <button
              onClick={() => setIsAddNoteOpen(true)}
              className="px-4 py-2 rounded-2xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white font-semibold text-xs flex items-center gap-1.5 cursor-pointer shadow-[0_4px_20px_rgba(34,211,238,0.25)] transition-all hover:opacity-90 active:scale-[0.98]"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Tugas Baru
            </button>
          </div>

          {isAddNoteOpen && (
            <form onSubmit={handleSaveNote} className="relative z-30 p-5 rounded-2xl liquid-glass space-y-3.5 animate-fade-in">
              <h4 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">Tambah Tugas / Catatan</h4>
              <div className="relative z-40 grid grid-cols-1 sm:grid-cols-3 gap-3">
                <input
                  type="text"
                  value={newNoteTitle}
                  onChange={(e) => setNewNoteTitle(e.target.value)}
                  placeholder="Judul Tugas (cth: Evaluasi Laporan)"
                  className="liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none sm:col-span-2"
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
                placeholder="Deskripsi detail tugas (opsional)"
                className="w-full liquid-glass-input rounded-xl py-2.5 px-3.5 text-xs text-white placeholder-slate-500 focus:outline-none"
              />
              <div className="flex justify-end gap-2.5 pt-1">
                <button
                  type="button"
                  onClick={() => setIsAddNoteOpen(false)}
                  className="px-4 py-2 rounded-xl liquid-glass-subtle border border-white/10 text-slate-300 text-xs cursor-pointer"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-500 text-white font-semibold text-xs cursor-pointer shadow-[0_4px_16px_rgba(168,85,247,0.3)] transition-all hover:opacity-90"
                >
                  Simpan
                </button>
              </div>
            </form>
          )}

          <div className="space-y-2.5">
            {filteredNotes.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-16 rounded-2xl liquid-glass-subtle">Belum ada tugas atau catatan untuk {activeSpeaker}.</p>
            ) : (
              filteredNotes.map((n) => (
                <div
                  key={n.id}
                  className={`p-4 px-5 rounded-2xl border transition-all duration-300 flex items-start justify-between gap-4 ${
                    n.is_completed
                      ? "liquid-glass-subtle border-white/[0.06] opacity-50"
                      : "liquid-glass-subtle hover:border-purple-400/40"
                  }`}
                >
                  <div className="flex items-start gap-3.5 min-w-0 flex-1">
                    <button
                      onClick={() => handleToggleTodo(n.id)}
                      className={`w-[22px] h-[22px] rounded-lg border flex items-center justify-center shrink-0 mt-0.5 cursor-pointer transition-all duration-200 ${
                        n.is_completed
                          ? "bg-gradient-to-tr from-emerald-500 to-teal-400 border-emerald-300/60 text-black shadow-[0_0_12px_rgba(52,211,153,0.35)]"
                          : "border-white/25 hover:border-purple-300 hover:bg-purple-500/20 text-transparent"
                      }`}
                    >
                      <svg className="w-3 h-3 stroke-[3]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </button>
                    <div className="truncate min-w-0 flex-1">
                      <p className={`text-xs sm:text-sm ${n.is_completed ? "line-through text-slate-500 font-normal" : "text-white font-semibold"}`}>
                        {n.title}
                      </p>
                      {n.content && <p className="text-xs text-slate-400 mt-1 leading-relaxed">{n.content}</p>}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] uppercase tracking-wide px-2.5 py-1 rounded-full bg-purple-500/15 text-purple-300 border border-purple-400/25">
                      {n.category}
                    </span>
                    <button
                      onClick={() => handleDeleteNote(n.id)}
                      className="text-slate-500 hover:text-rose-400 p-1.5 text-xs cursor-pointer transition-colors"
                      title="Hapus tugas"
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
