"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { anaraApi, BACKEND_URL } from "@/lib/apiClient";

export type ArtifactCategory = "all" | "images" | "files" | "code";

export interface ArtifactItem {
  id: string;
  title: string;
  kind: "image" | "file" | "code";
  url: string;
  sourceSessionId?: number | string;
  sourceSessionTitle?: string;
  createdAt: number;
  sizeKb?: number;
  snippet?: string;
}

export interface ArtifactsGalleryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenSession?: (sessionId: number) => void;
  onOpenFileInEditor?: (path: string, fileName?: string) => void;
}

/**
 * ArtifactsGalleryModal.tsx — Anara Universal Artifacts Gallery (/artifacts Parity)
 *
 * Provides a dedicated gallery interface for all generated artifacts, files,
 * diagrams, images, and code documents produced across all conversation sessions.
 * Follows the Anara Liquid Glass Flat Hairline design standard.
 */
export function ArtifactsGalleryModal({
  isOpen,
  onClose,
  onOpenSession,
  onOpenFileInEditor,
}: ArtifactsGalleryModalProps) {
  const [activeFilter, setActiveFilter] = useState<ArtifactCategory>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Load all artifacts across sessions and workspace
  const fetchArtifacts = useCallback(async () => {
    setLoading(true);
    try {
      const items: ArtifactItem[] = [];

      // 1. Fetch workspace files tree
      try {
        const treeRes = await fetch(`${BACKEND_URL}/api/agent/workspace/tree`);
        if (treeRes.ok) {
          const treeData = await treeRes.json();
          const scanFiles = (node: any) => {
            if (!node) return;
            if (node.type === "file") {
              const name: string = node.name || "";
              const path: string = node.path || name;
              const isImg = /\.(png|jpe?g|gif|webp|svg)$/i.test(name);
              const isCode = /\.(ts|tsx|js|jsx|py|html|css|json|md|rs|go|sh)$/i.test(name);
              const size = typeof node.size === "number" ? Math.round(node.size / 1024) : undefined;

              items.push({
                id: `ws_${path}`,
                title: name,
                kind: isImg ? "image" : isCode ? "code" : "file",
                url: path,
                createdAt: Date.now() - 3600000,
                sizeKb: size,
              });
            }
            if (Array.isArray(node.children)) {
              node.children.forEach(scanFiles);
            }
          };
          scanFiles(treeData);
        }
      } catch (err) {
        console.warn("[ArtifactsGallery] Workspace tree load error:", err);
      }

      // 2. Fetch recent sessions and extract image/code artifacts from messages
      try {
        const sessionsRes: any = await anaraApi.sessions.list();
        const sessionList: any[] = Array.isArray(sessionsRes) ? sessionsRes : sessionsRes?.sessions || [];

        // Sample up to 10 most recent sessions to extract artifacts
        const sampleSessions = sessionList.slice(0, 10);
        for (const s of sampleSessions) {
          try {
            const sDetail = await anaraApi.sessions.get(s.id);
            const messages = sDetail?.messages || [];
            for (const m of messages) {
              const text = m.content || m.text || "";

              // Check for markdown image tags ![alt](url)
              const imgMatches = text.matchAll(/!\[([^\]]*)\]\((https?:\/\/[^\s)]+|\/[^\s)]+)\)/g);
              for (const match of imgMatches) {
                const alt = match[1] || "Generated Visual";
                const url = match[2];
                items.push({
                  id: `img_${s.id}_${url.slice(-16)}`,
                  title: alt,
                  kind: "image",
                  url: url,
                  sourceSessionId: s.id,
                  sourceSessionTitle: s.title || `Session ${s.id}`,
                  createdAt: s.updated_at ? new Date(s.updated_at).getTime() : Date.now(),
                });
              }

              // Check for code blocks > 30 lines
              const codeBlocks = text.matchAll(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g);
              for (const cMatch of codeBlocks) {
                const lang = cMatch[1] || "code";
                const codeContent = cMatch[2] || "";
                const lines = codeContent.split("\n").length;
                if (lines >= 25) {
                  const firstLine = codeContent.trim().split("\n")[0] || "";
                  const title = firstLine.replace(/^(?:\/\/|#|<!--|\/\*)\s*/, "").slice(0, 40) || `snippet.${lang}`;
                  items.push({
                    id: `code_${s.id}_${title}`,
                    title: title,
                    kind: "code",
                    url: title,
                    sourceSessionId: s.id,
                    sourceSessionTitle: s.title || `Session ${s.id}`,
                    createdAt: s.updated_at ? new Date(s.updated_at).getTime() : Date.now(),
                    snippet: codeContent.slice(0, 240),
                    sizeKb: Math.round(codeContent.length / 1024),
                  });
                }
              }
            }
          } catch {}
        }
      } catch (err) {
        console.warn("[ArtifactsGallery] Session scan error:", err);
      }

      // Deduplicate items by ID
      const unique = Array.from(new Map(items.map((i) => [i.id, i])).values());
      setArtifacts(unique);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchArtifacts();
    }
  }, [isOpen, fetchArtifacts]);

  // Filter and search
  const filteredArtifacts = useMemo(() => {
    return artifacts.filter((item) => {
      if (activeFilter === "images" && item.kind !== "image") return false;
      if (activeFilter === "files" && item.kind !== "file") return false;
      if (activeFilter === "code" && item.kind !== "code") return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = item.title.toLowerCase().includes(q);
        const matchesSession = item.sourceSessionTitle?.toLowerCase().includes(q) || false;
        const matchesSnippet = item.snippet?.toLowerCase().includes(q) || false;
        return matchesTitle || matchesSession || matchesSnippet;
      }
      return true;
    });
  }, [artifacts, activeFilter, searchQuery]);

  const handleCopyLink = (item: ArtifactItem) => {
    navigator.clipboard.writeText(item.url);
    setCopiedId(item.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Artifacts Gallery"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-xl animate-fade-in"
    >
      <div className="relative w-full max-w-5xl h-[85vh] flex flex-col rounded-2xl border border-white/[0.12] bg-[#060913]/95 shadow-[0_16px_60px_rgba(0,0,0,0.9)] overflow-hidden font-sans">
        {/* Top Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08] bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-cyan-500/15 border border-cyan-400/30 text-cyan-300">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </span>
            <div>
              <h2 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
                Artifacts Library
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-cyan-950/60 border border-cyan-500/30 text-cyan-300">
                  {filteredArtifacts.length}
                </span>
              </h2>
              <p className="text-xs text-slate-400 font-sans">
                Documents, images, visual diagrams, and code artifacts generated across all sessions
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={fetchArtifacts}
              disabled={loading}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
              title="Refresh artifacts"
            >
              <svg className={`w-4 h-4 ${loading ? "animate-spin text-cyan-400" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-lg text-slate-400 hover:text-rose-300 hover:bg-white/[0.06] transition-colors cursor-pointer"
              title="Close (Esc)"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Filter Tabs & Search Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 px-6 py-3 border-b border-white/[0.06] bg-black/40">
          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-white/[0.04] border border-white/[0.06]">
            {(["all", "images", "files", "code"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveFilter(tab)}
                className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition-all cursor-pointer ${
                  activeFilter === tab
                    ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30 shadow-[0_0_10px_rgba(34,211,238,0.2)]"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-72">
            <svg className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by title, path, or session..."
              className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/[0.08] focus:border-cyan-400/40 text-xs text-slate-200 placeholder-slate-500 outline-none transition-all"
            />
          </div>
        </div>

        {/* Artifacts Grid */}
        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
          {loading ? (
            <div className="h-full flex flex-col items-center justify-center gap-3 text-slate-400">
              <div className="w-8 h-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
              <span className="text-xs font-mono">Scanning artifacts across workspace &amp; sessions...</span>
            </div>
          ) : filteredArtifacts.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-slate-500">
              <svg className="w-10 h-10 stroke-[1.2] text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              <span className="text-sm font-medium text-slate-400">No artifacts found</span>
              <p className="text-xs text-slate-500 max-w-sm text-center">
                Artifacts like images, diagrams, documents, and code files generated during chat turns will appear here automatically.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {filteredArtifacts.map((item) => (
                <div
                  key={item.id}
                  className="flex flex-col justify-between rounded-xl border border-white/[0.08] bg-black/40 hover:bg-white/[0.03] hover:border-white/[0.16] p-3.5 transition-all group shadow-md backdrop-blur-md"
                >
                  <div>
                    {/* Kind Icon + Title */}
                    <div className="flex items-start gap-2.5">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/[0.05] border border-white/[0.08] text-cyan-300">
                        {item.kind === "image" ? (
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        ) : item.kind === "code" ? (
                          <svg className="w-3.5 h-3.5 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                          </svg>
                        ) : (
                          <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        )}
                      </span>

                      <div className="min-w-0 flex-1">
                        <h4 className="text-xs font-semibold text-slate-200 group-hover:text-white truncate font-mono">
                          {item.title}
                        </h4>
                        {item.sourceSessionTitle && (
                          <p className="text-[10px] text-slate-500 truncate mt-0.5">
                            From: {item.sourceSessionTitle}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Code Snippet or Info */}
                    {item.snippet && (
                      <pre className="mt-2.5 p-2 rounded-lg bg-black/60 border border-white/[0.05] text-[10px] text-slate-400 font-mono leading-relaxed line-clamp-3 select-text overflow-hidden">
                        {item.snippet}
                      </pre>
                    )}
                  </div>

                  {/* Footer Actions */}
                  <div className="mt-3 pt-2 flex items-center justify-between border-t border-white/[0.06] text-[10.5px] font-mono">
                    <span className="text-slate-500 tabular-nums">
                      {item.sizeKb !== undefined ? `${item.sizeKb} KB` : item.kind}
                    </span>

                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleCopyLink(item)}
                        className="px-2 py-0.5 rounded text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
                        title="Copy file path or URL"
                      >
                        {copiedId === item.id ? "Copied" : "Copy"}
                      </button>

                      {item.kind === "code" || item.kind === "file" ? (
                        <button
                          type="button"
                          onClick={() => {
                            if (onOpenFileInEditor) {
                              onOpenFileInEditor(item.url, item.title);
                              onClose();
                            }
                          }}
                          className="px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/25 border border-cyan-400/30 transition-all cursor-pointer font-medium"
                          title="Open in Code Studio"
                        >
                          Studio →
                        </button>
                      ) : (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          className="px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/25 border border-cyan-400/30 transition-all cursor-pointer font-medium"
                        >
                          View ↗
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ArtifactsGalleryModal;
