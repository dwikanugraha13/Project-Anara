"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { BACKEND_URL, Conversation } from "../types";

interface BrainConversationsTabProps {
  activeSpeaker?: string | null;
  onRefreshAll?: () => void;
}

export default function BrainConversationsTab({
  activeSpeaker,
  onRefreshAll,
}: BrainConversationsTabProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationFilter, setConversationFilter] = useState<"all" | "active">("all");

  const fetchConversations = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/conversations?limit=60`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data || []);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const handleDeleteConversation = async (id: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/conversations/${id}`, { method: "DELETE" });
      if (res.ok) {
        setConversations((prev) => prev.filter((c) => c.id !== id));
        onRefreshAll?.();
      }
    } catch {}
  };

  const handleClearConversations = async () => {
    if (!confirm("Delete all episodic conversation records from the database?")) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/conversations`, { method: "DELETE" });
      if (res.ok) {
        setConversations([]);
        onRefreshAll?.();
      }
    } catch {}
  };

  const filteredConversations = useMemo(() => {
    if (conversationFilter === "active" && activeSpeaker) {
      return conversations.filter(
        (c) => (c.speaker_name || "").toLowerCase() === activeSpeaker.toLowerCase()
      );
    }
    return conversations;
  }, [conversations, conversationFilter, activeSpeaker]);

  return (
    <div className="space-y-4 font-sans select-text">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-5 rounded-2xl liquid-glass-subtle">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] uppercase tracking-wider text-cyan-300 font-bold">
              Episodic Conversation History
            </span>
            <span className="text-[10px] text-slate-400 liquid-glass-subtle px-2 py-0.5 rounded-full border border-white/10 font-mono">
              {filteredConversations.length} / {conversations.length} entri
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Multi-session dialog log records stored in SQLite database.
          </p>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-center">
          {activeSpeaker && (
            <div className="flex items-center gap-1 p-1 rounded-full bg-black/30 border border-white/10 font-mono text-xs">
              <button
                type="button"
                onClick={() => setConversationFilter("all")}
                className={`px-2.5 py-1 rounded-full text-xs transition-all cursor-pointer ${
                  conversationFilter === "all"
                    ? "bg-cyan-500/25 text-cyan-100 font-semibold border border-cyan-400/35"
                    : "text-slate-400 hover:text-white border border-transparent"
                }`}
              >
                Semua
              </button>
              <button
                type="button"
                onClick={() => setConversationFilter("active")}
                className={`px-2.5 py-1 rounded-full text-xs transition-all cursor-pointer ${
                  conversationFilter === "active"
                    ? "bg-emerald-500/25 text-emerald-100 font-semibold border border-emerald-400/35"
                    : "text-slate-400 hover:text-white border border-transparent"
                }`}
              >
                {activeSpeaker}
              </button>
            </div>
          )}

          {conversations.length > 0 && (
            <button
              type="button"
              onClick={handleClearConversations}
              className="px-3 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/25 border border-rose-400/30 text-rose-300 hover:text-rose-200 text-xs flex items-center gap-1.5 cursor-pointer transition-all font-mono"
              title="Delete all conversation history logs"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              <span>Kosongkan</span>
            </button>
          )}
        </div>
      </div>

      <div className="space-y-2.5">
        {filteredConversations.length === 0 ? (
          <div className="text-center py-16 text-slate-400 text-xs liquid-glass-subtle rounded-2xl p-8">
            No conversation history matches the current filter.
          </div>
        ) : (
          filteredConversations.map((c) => {
            const isCurrentActive = Boolean(
              c.speaker_name && activeSpeaker && c.speaker_name.toLowerCase() === activeSpeaker.toLowerCase()
            );
            const visualImg = c.visual_data?.image_url || c.media_url;

            return (
              <div
                key={c.id}
                className={`p-4 sm:p-5 rounded-2xl border text-xs sm:text-sm space-y-2.5 transition-all ${
                  isCurrentActive
                    ? "liquid-glass-subtle border-cyan-400/30 hover:border-cyan-400/50"
                    : "liquid-glass-subtle hover:border-white/25"
                }`}
              >
                <div className="flex items-center justify-between text-xs border-b border-white/[0.07] pb-2.5">
                  <div className="flex items-center gap-2 flex-wrap font-mono">
                    <span
                      className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                        isCurrentActive
                          ? "bg-emerald-500/15 text-emerald-300 border-emerald-400/35"
                          : "bg-indigo-500/15 text-indigo-300 border-indigo-400/25"
                      }`}
                    >
                      {c.speaker_name || "Tamu"}
                    </span>
                    {c.media_type && (
                      <span className="px-2 py-0.5 rounded-md bg-cyan-400/10 text-cyan-300 text-[10px] border border-cyan-400/25 uppercase font-bold">
                        {c.media_type}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2.5 shrink-0 font-mono">
                    <span className="text-slate-500 text-[11px]">
                      {new Date(c.created_at).toLocaleString("id-ID")}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleDeleteConversation(c.id)}
                      className="text-slate-500 hover:text-rose-400 p-1 rounded-md hover:bg-rose-500/10 transition-colors cursor-pointer"
                      title="Delete this conversation entry"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5 leading-relaxed">
                  <p className="text-slate-300">
                    <span className="text-slate-500 font-semibold font-mono">User:</span> {c.user_text}
                  </p>
                  <p className="text-cyan-100">
                    <span className="text-cyan-400 font-semibold font-mono">Anara:</span> {c.ai_text}
                  </p>
                </div>

                {visualImg && (
                  <div className="pt-2 flex items-center gap-2.5">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={visualImg}
                      alt="Visual Projection Thumbnail"
                      className="w-12 h-12 object-cover rounded-xl border border-cyan-400/30"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = "none";
                      }}
                    />
                    <span className="text-[11px] text-cyan-300 font-mono">
                      {c.visual_data?.image_title || "Visual Projection Image"}
                    </span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
