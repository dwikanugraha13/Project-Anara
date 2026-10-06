"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { BACKEND_URL, AgentSkillV2 } from "../types";

interface HubSkillItem {
  name: string;
  slug?: string;
  description: string;
  source?: string;
  source_name?: string;
  identifier: string;
  category?: string;
  tags?: string[];
  is_installed?: boolean;
}

interface HubSource {
  id: string;
  name: string;
  skill_count?: number;
  count?: number;
}

import {
  MasterDetail,
  ListColumn,
  DetailColumn,
  CapRow,
  SortButton,
  DetailPane,
  ToolChip,
} from "../shared/MasterDetail";

export default function BrainSkillsTab() {
  const [activeTab, setActiveTab] = useState<"installed" | "hub">("installed");
  const [skills, setSkills] = useState<AgentSkillV2[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortDesc, setSortDesc] = useState(true);
  const [filterStatus, setFilterStatus] = useState<"all" | "active" | "disabled" | "pending">("all");
  const [isLoading, setIsLoading] = useState(false);
  const [togglingSlug, setTogglingSlug] = useState<string | null>(null);

  // Raw editor drawer state
  const [isEditing, setIsEditing] = useState(false);
  const [rawContent, setRawContent] = useState("");
  const [isSavingContent, setIsSavingContent] = useState(false);
  const [editNotice, setEditNotice] = useState<string | null>(null);

  // Skills Hub state
  const [hubQuery, setHubQuery] = useState("");
  const [hubSource, setHubSource] = useState("all");
  const [hubSources, setHubSources] = useState<HubSource[]>([]);
  const [hubResults, setHubResults] = useState<HubSkillItem[]>([]);
  const [hubTotal, setHubTotal] = useState(0);
  const [isSearchingHub, setIsSearchingHub] = useState(false);
  const [selectedHubItem, setSelectedHubItem] = useState<HubSkillItem | null>(null);
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
    } catch (e) {
      console.warn("[BrainSkills] Error fetching skills:", e);
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
        `${BACKEND_URL}/api/brain/skills/hub/search?q=${encodeURIComponent(query)}&source=${encodeURIComponent(source)}&limit=40`
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
    setTogglingSlug(slug);
    const newEnabled = currentStatus !== "active";
    // Optimistic UI update
    setSkills((prev) =>
      prev.map((s) =>
        s.slug === slug
          ? { ...s, status: newEnabled ? "active" : "disabled", enabled: newEnabled }
          : s
      )
    );

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}/toggle`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: newEnabled }),
      });
      if (!res.ok) {
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
        fetchSkills();
      }
    } catch {}
  };

  const handleDeleteSkill = async (slug: string) => {
    if (!confirm(`Are you sure you want to delete skill '${slug}'?`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}`, {
        method: "DELETE",
      });
      if (res.ok) {
        if (selectedSlug === slug) setSelectedSlug(null);
        fetchSkills();
      }
    } catch {}
  };

  const handleOpenEditor = async (slug: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}/content`);
      if (res.ok) {
        const data = await res.json();
        setRawContent(data.content || "");
        setIsEditing(true);
      }
    } catch (e) {
      console.warn("Failed to read raw skill content:", e);
    }
  };

  const handleSaveEditor = async () => {
    if (!selectedSlug) return;
    setIsSavingContent(true);
    setEditNotice(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${selectedSlug}/content`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: rawContent }),
      });
      if (res.ok) {
        setEditNotice("Skill saved successfully.");
        fetchSkills();
        setTimeout(() => setEditNotice(null), 3000);
      } else {
        setEditNotice("Failed to save skill.");
      }
    } catch (e) {
      setEditNotice("Network error saving skill.");
    } finally {
      setIsSavingContent(false);
    }
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
          category: item.category,
        }),
      });
      if (res.ok) {
        setInstalledNotice(`Installed '${item.name}' successfully!`);
        fetchSkills();
        setTimeout(() => setInstalledNotice(null), 4000);
      }
    } catch {
    } finally {
      setInstallingIdentifier(null);
    }
  };

  // Filter & sort visible installed skills
  const visibleSkills = useMemo(() => {
    return skills
      .filter((s) => {
        if (filterStatus !== "all" && s.status !== filterStatus) return false;
        if (!searchQuery.trim()) return true;
        const q = searchQuery.toLowerCase();
        return (
          s.name.toLowerCase().includes(q) ||
          s.category.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q) ||
          (s.trigger_keywords && s.trigger_keywords.some((t) => t.toLowerCase().includes(q)))
        );
      })
      .sort((a, b) => {
        if (sortDesc) {
          const countA = a.usage_count || 0;
          const countB = b.usage_count || 0;
          if (countA !== countB) return countB - countA;
        }
        return a.name.localeCompare(b.name);
      });
  }, [skills, filterStatus, searchQuery, sortDesc]);

  // Active selected skill
  const activeSkill = useMemo(() => {
    if (!selectedSlug && visibleSkills.length > 0) return visibleSkills[0];
    return visibleSkills.find((s) => s.slug === selectedSlug) || visibleSkills[0] || null;
  }, [selectedSlug, visibleSkills]);

  return (
    <div className="h-full w-full flex flex-col overflow-hidden select-none font-sans">
      <MasterDetail
        resizeId="brain_skills"
        pane={
          isEditing && activeSkill ? (
            <DetailPane
              id="skill_editor"
              title={`Editing ${activeSkill.name} (${activeSkill.file_path || "SKILL.md"})`}
              onClose={() => setIsEditing(false)}
              actions={
                <div className="flex items-center gap-2">
                  {editNotice && (
                    <span className="text-[11px] font-mono text-cyan-300 mr-2">{editNotice}</span>
                  )}
                  <button
                    type="button"
                    onClick={() => setIsEditing(false)}
                    className="px-2.5 py-1 rounded-md text-xs font-mono text-slate-400 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveEditor}
                    disabled={isSavingContent}
                    className="px-3 py-1 rounded-md text-xs font-mono font-medium text-black bg-cyan-400 hover:bg-cyan-300 transition-colors cursor-pointer shadow-sm disabled:opacity-50"
                  >
                    {isSavingContent ? "Saving..." : "Save (Ctrl+S)"}
                  </button>
                </div>
              }
            >
              <textarea
                value={rawContent}
                onChange={(e) => setRawContent(e.target.value)}
                placeholder="---\nname: my-skill\ndescription: ...\n---\n# Documentation"
                className="w-full h-full p-4 bg-[#04060d] text-slate-200 font-mono text-xs leading-relaxed resize-none focus:outline-none custom-scrollbar select-text"
              />
            </DetailPane>
          ) : null
        }
      >
        {/* ── LEFT COLUMN (List of Skills or Hub Catalog) ── */}
        <ListColumn
          header={
            <div className="space-y-2">
              {/* Top Sub-Tab Switcher [Installed | Hub] */}
              <div className="flex items-center p-0.5 rounded-lg bg-black/40 border border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setActiveTab("installed")}
                  className={`flex-1 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                    activeTab === "installed"
                      ? "bg-white/[0.08] text-white font-semibold shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Installed ({skills.length})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("hub")}
                  className={`flex-1 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                    activeTab === "hub"
                      ? "bg-white/[0.08] text-white font-semibold shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Skills Hub (100k+)
                </button>
              </div>

              {activeTab === "installed" ? (
                <>
                  {/* Search Bar & Sort */}
                  <div className="flex items-center gap-1.5">
                    <div className="relative flex-1 min-w-0">
                      <svg
                        className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                      <input
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search skills..."
                        className="w-full py-1 pl-8 pr-2 rounded-lg bg-black/40 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-400/40 transition-colors"
                      />
                    </div>
                    <SortButton desc={sortDesc} onToggle={() => setSortDesc((v) => !v)} label="Usage" />
                  </div>

                  {/* Filter Pills */}
                  <div className="flex items-center gap-1 text-[10px] font-mono">
                    {(["all", "active", "disabled", "pending"] as const).map((st) => (
                      <button
                        key={st}
                        onClick={() => setFilterStatus(st)}
                        className={`px-2 py-0.5 rounded capitalize transition-colors cursor-pointer ${
                          filterStatus === st
                            ? "bg-white/[0.1] text-white font-semibold"
                            : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]"
                        }`}
                      >
                        {st}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                /* Hub Search & Source Selector */
                <div className="space-y-1.5">
                  <div className="relative w-full">
                    <svg
                      className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                      value={hubQuery}
                      onChange={(e) => setHubQuery(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") searchHub(hubQuery, hubSource);
                      }}
                      placeholder="Search 100k+ Skills Hub..."
                      className="w-full py-1 pl-8 pr-2 rounded-lg bg-black/40 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-400/40 transition-colors"
                    />
                  </div>

                  <div className="flex items-center gap-1.5">
                    <select
                      value={hubSource}
                      onChange={(e) => {
                        setHubSource(e.target.value);
                        searchHub(hubQuery, e.target.value);
                      }}
                      className="flex-1 py-1 px-2 rounded-lg bg-black/40 border border-white/[0.08] text-[11px] font-mono text-slate-300 focus:outline-none"
                    >
                      <option value="all">All Repositories</option>
                      {hubSources.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name} ({s.count ? s.count.toLocaleString() : "catalog"})
                        </option>
                      ))}
                    </select>

                    <button
                      type="button"
                      onClick={() => searchHub(hubQuery, hubSource)}
                      disabled={isSearchingHub}
                      className="px-2.5 py-1 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.08] text-xs font-mono text-white transition-colors cursor-pointer"
                    >
                      {isSearchingHub ? "..." : "Search"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          }
        >
          {activeTab === "installed" ? (
            visibleSkills.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500 font-mono">
                {isLoading ? "Loading skills..." : "No skills found"}
              </div>
            ) : (
              visibleSkills.map((s) => (
                <CapRow
                  key={s.slug}
                  title={s.name}
                  subtitle={
                    <span>
                      {s.category}
                      {s.learned_from_experience && (
                        <span className="ml-1 text-[9px] text-cyan-400">· learned</span>
                      )}
                    </span>
                  }
                  active={(activeSkill?.slug || "") === s.slug}
                  enabled={s.status === "active"}
                  meta={s.usage_count ? `×${s.usage_count}` : undefined}
                  busy={togglingSlug === s.slug}
                  onSelect={() => setSelectedSlug(s.slug)}
                  onToggle={() => handleToggleSkill(s.slug, s.status)}
                />
              ))
            )
          ) : (
            /* Skills Hub Results List */
            hubResults.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500 font-mono">
                {isSearchingHub ? "Searching Hub..." : "No skills found in Hub"}
              </div>
            ) : (
              hubResults.map((item) => {
                const isInstalled = skills.some((s) => s.slug === item.identifier || s.name === item.name);
                const isSelected = selectedHubItem?.identifier === item.identifier;
                return (
                  <CapRow
                    key={item.identifier}
                    title={item.name}
                    subtitle={
                      <span>
                        {item.tags?.[0] || "community"} · <span className="text-slate-500">{item.source || "hub"}</span>
                      </span>
                    }
                    active={isSelected}
                    enabled={isInstalled}
                    onSelect={() => setSelectedHubItem(item)}
                    action={
                      isInstalled ? (
                        <span className="text-[10px] font-mono text-emerald-400 font-semibold">Installed</span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleInstallHubSkill(item)}
                          disabled={installingIdentifier === item.identifier}
                          className="px-2 py-0.5 rounded text-[10.5px] font-mono font-medium bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/25 border border-cyan-400/30 transition-colors cursor-pointer"
                        >
                          {installingIdentifier === item.identifier ? "..." : "Install"}
                        </button>
                      )
                    }
                  />
                );
              })
            )
          )}
        </ListColumn>

        {/* ── RIGHT COLUMN (Detail Inspector & Full Markdown View) ── */}
        <DetailColumn
          footer={
            activeTab === "installed"
              ? "Skill changes apply dynamically to all subsequent agent interactions."
              : "Skills from the Hub are securely quarantined and vetted by Anara AST Sentinels."
          }
        >
          {activeTab === "installed" && activeSkill ? (
            <div className="space-y-5 animate-fade-in">
              {/* Header Info */}
              <div className="border-b border-white/[0.08] pb-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-lg font-bold text-white tracking-tight font-sans">
                    {activeSkill.name}
                  </h2>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase tracking-wider ${
                        activeSkill.status === "active"
                          ? "bg-emerald-500/15 border border-emerald-400/30 text-emerald-300"
                          : activeSkill.status === "pending"
                          ? "bg-amber-500/15 border border-amber-400/30 text-amber-300"
                          : "bg-slate-800 border border-white/10 text-slate-400"
                      }`}
                    >
                      {activeSkill.status}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300">
                      {activeSkill.category}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-slate-300 mt-2 leading-relaxed font-sans">
                  {activeSkill.description || "No description provided for this skill."}
                </p>

                {/* Actions Bar */}
                <div className="flex items-center gap-2 mt-3.5">
                  <button
                    type="button"
                    onClick={() => handleOpenEditor(activeSkill.slug)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-mono text-slate-200 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors cursor-pointer"
                  >
                    <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                    <span>Edit SKILL.md</span>
                  </button>

                  {activeSkill.status === "pending" && (
                    <button
                      type="button"
                      onClick={() => handleApproveSkill(activeSkill.slug)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30 border border-emerald-400/30 transition-colors cursor-pointer"
                    >
                      ✓ Approve Skill
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => handleDeleteSkill(activeSkill.slug)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-mono text-rose-300 hover:text-rose-100 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition-colors cursor-pointer ml-auto"
                  >
                    Delete Skill
                  </button>
                </div>
              </div>

              {/* Frontmatter Metadata Table */}
              <div className="rounded-xl border border-white/[0.08] bg-[#070b16]/70 p-3.5 space-y-2 font-mono text-xs">
                <div className="flex items-start gap-3">
                  <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">Slug</span>
                  <span className="text-slate-300 font-semibold text-[11px] select-text">{activeSkill.slug}</span>
                </div>
                {activeSkill.trigger_keywords && activeSkill.trigger_keywords.length > 0 && (
                  <div className="flex items-start gap-3">
                    <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">Triggers</span>
                    <div className="flex flex-wrap gap-1">
                      {activeSkill.trigger_keywords.map((t, idx) => (
                        <ToolChip key={idx}>{t}</ToolChip>
                      ))}
                    </div>
                  </div>
                )}
                {activeSkill.file_path && (
                  <div className="flex items-start gap-3">
                    <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">Location</span>
                    <span className="text-slate-400 text-[10.5px] truncate select-text" title={activeSkill.file_path}>
                      {activeSkill.file_path}
                    </span>
                  </div>
                )}
              </div>

              {/* Full Markdown Documentation Viewer */}
              <div className="space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
                  SKILL.md Documentation
                </div>
                <div className="rounded-xl border border-white/[0.08] bg-[#050811]/90 p-4 font-mono text-xs text-slate-300 leading-relaxed overflow-x-auto select-text whitespace-pre-wrap max-h-[500px] custom-scrollbar shadow-inner">
                  {activeSkill.body || "# " + activeSkill.name + "\n\n" + activeSkill.description}
                </div>
              </div>
            </div>
          ) : activeTab === "hub" && selectedHubItem ? (
            /* Selected Hub Skill Detail */
            <div className="space-y-5 animate-fade-in">
              <div className="border-b border-white/[0.08] pb-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-lg font-bold text-white tracking-tight font-sans">
                    {selectedHubItem.name}
                  </h2>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300">
                    {selectedHubItem.tags?.[0] || "community"}
                  </span>
                </div>
                <p className="text-xs text-slate-300 mt-2 leading-relaxed font-sans">
                  {selectedHubItem.description || "Official community skill bundle."}
                </p>

                <div className="mt-4">
                  <button
                    type="button"
                    onClick={() => handleInstallHubSkill(selectedHubItem)}
                    disabled={installingIdentifier === selectedHubItem.identifier}
                    className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-cyan-400 text-black hover:bg-cyan-300 transition-colors cursor-pointer shadow-sm disabled:opacity-50"
                  >
                    {installingIdentifier === selectedHubItem.identifier ? "Installing..." : "+ Install to Anara Skills"}
                  </button>
                  {installedNotice && (
                    <span className="ml-3 text-xs font-mono text-emerald-300">{installedNotice}</span>
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-white/[0.08] bg-[#070b16]/70 p-3.5 space-y-2 font-mono text-xs">
                <div className="flex items-start gap-3">
                  <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">Identifier</span>
                  <span className="text-slate-300 text-[11px] select-text">{selectedHubItem.identifier}</span>
                </div>
                <div className="flex items-start gap-3">
                  <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">Source</span>
                  <span className="text-slate-300 text-[11px]">{selectedHubItem.source || "Community Hub"}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-12 text-center text-xs text-slate-500 font-mono">
              Select a skill from the list to inspect its documentation and configuration.
            </div>
          )}
        </DetailColumn>
      </MasterDetail>
    </div>
  );
}
