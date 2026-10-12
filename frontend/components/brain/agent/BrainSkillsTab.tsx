"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { BACKEND_URL, AgentSkillV2 } from "../types";
import {
  MasterDetail,
  ListColumn,
  DetailColumn,
  CapRow,
  SortButton,
  ToolChip,
} from "../shared/MasterDetail";

export interface OfficialCatalogSkill {
  name: string;
  category: string;
  identifier: string;
  description: string;
  platforms?: string[] | null;
  version?: string;
  author?: string;
  license?: string;
  tags?: string[];
  setup?: any;
  installed?: boolean;
}

export interface OfficialSkillPreviewData {
  name: string;
  identifier: string;
  category: string;
  description: string;
  version: string;
  author: string;
  license: string;
  platforms?: string[] | null;
  tags: string[];
  setup?: any;
  metadata?: any;
  skill_md: string;
  files: string[];
}

export default function BrainSkillsTab() {
  const [skillsTab, setSkillsTab] = useState<"installed" | "available">("installed");
  const [skills, setSkills] = useState<AgentSkillV2[]>([]);
  const [officialCatalog, setOfficialCatalog] = useState<OfficialCatalogSkill[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [selectedOfficial, setSelectedOfficial] = useState<string | null>(null);
  const [officialPreview, setOfficialPreview] = useState<OfficialSkillPreviewData | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [sortDesc, setSortDesc] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [togglingSlug, setTogglingSlug] = useState<string | null>(null);
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [installNotice, setInstallNotice] = useState<string | null>(null);

  // Raw editor drawer state for installed learned skills
  const [isEditing, setIsEditing] = useState(false);
  const [rawContent, setRawContent] = useState("");
  const [isSavingContent, setIsSavingContent] = useState(false);
  const [editNotice, setEditNotice] = useState<string | null>(null);

  // Fetch installed skills
  const fetchSkills = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2`);
      if (res.ok) {
        const data = await res.json();
        setSkills(data || []);
      }
    } catch (e) {
      console.warn("[BrainSkills] Error fetching installed skills:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch official catalog skills
  const fetchOfficialCatalog = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/hub/official`);
      if (res.ok) {
        const data = await res.json();
        setOfficialCatalog(data.skills || []);
      }
    } catch (e) {
      console.warn("[BrainSkills] Error fetching official catalog:", e);
    }
  }, []);

  useEffect(() => {
    fetchSkills();
    fetchOfficialCatalog();
  }, [fetchSkills, fetchOfficialCatalog]);

  // Load preview when an available catalog skill is selected
  useEffect(() => {
    if (!selectedOfficial) {
      setOfficialPreview(null);
      return;
    }
    let isMounted = true;
    setIsPreviewLoading(true);

    fetch(`${BACKEND_URL}/api/brain/skills/hub/preview?identifier=${encodeURIComponent(selectedOfficial)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (isMounted && data) {
          setOfficialPreview(data);
        }
      })
      .catch((err) => {
        console.warn("[BrainSkills] Preview error:", err);
      })
      .finally(() => {
        if (isMounted) setIsPreviewLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedOfficial]);

  const installedNames = useMemo(() => {
    return new Set(skills.map((s) => s.name.toLowerCase()));
  }, [skills]);

  // Filter & sort installed skills
  const visibleInstalled = useMemo(() => {
    return skills
      .filter((s) => {
        if (!searchQuery.trim()) return true;
        const q = searchQuery.toLowerCase();
        return (
          s.name.toLowerCase().includes(q) ||
          s.slug.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q) ||
          s.category.toLowerCase().includes(q) ||
          (s.trigger_keywords && s.trigger_keywords.some((k) => k.toLowerCase().includes(q)))
        );
      })
      .sort((a, b) => {
        if (sortDesc) {
          const usesA = a.usage_count || 0;
          const usesB = b.usage_count || 0;
          if (usesA !== usesB) return usesB - usesA;
        }
        return a.name.localeCompare(b.name);
      });
  }, [skills, searchQuery, sortDesc]);

  // Filter available (uninstalled) catalog skills
  const visibleAvailable = useMemo(() => {
    return officialCatalog
      .filter((item) => {
        if (installedNames.has(item.name.toLowerCase())) return false;
        if (!searchQuery.trim()) return true;
        const q = searchQuery.toLowerCase();
        return (
          item.name.toLowerCase().includes(q) ||
          item.category.toLowerCase().includes(q) ||
          item.description.toLowerCase().includes(q) ||
          (item.tags && item.tags.some((t) => t.toLowerCase().includes(q)))
        );
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [officialCatalog, installedNames, searchQuery]);

  // Set initial selected item when tab changes or data loads
  useEffect(() => {
    if (skillsTab === "installed") {
      if (!selectedSlug && visibleInstalled.length > 0) {
        setSelectedSlug(visibleInstalled[0].slug);
      }
    } else {
      if (!selectedOfficial && visibleAvailable.length > 0) {
        setSelectedOfficial(visibleAvailable[0].identifier);
      }
    }
  }, [skillsTab, visibleInstalled, visibleAvailable, selectedSlug, selectedOfficial]);

  // Active installed skill
  const activeInstalledSkill = useMemo(() => {
    if (selectedSlug) {
      return visibleInstalled.find((s) => s.slug === selectedSlug) || null;
    }
    return visibleInstalled[0] || null;
  }, [selectedSlug, visibleInstalled]);

  // Parsed frontmatter metadata pairs for active installed skill
  const activeInstalledFrontmatterPairs = useMemo(() => {
    if (!activeInstalledSkill) return [];
    if (activeInstalledSkill.is_learned) {
      // 1:1 Reference standard: learned skills only show name & description
      return [
        ["name", activeInstalledSkill.name],
        ["description", activeInstalledSkill.description],
      ] as [string, string][];
    }

    // For non-learned skills (e.g. anara-agent), show full structured metadata
    const meta = (activeInstalledSkill as any).metadata || {};
    const pairs: [string, string][] = [
      ["name", activeInstalledSkill.name],
      ["description", activeInstalledSkill.description],
    ];

    if (activeInstalledSkill.version || meta.version) {
      pairs.push(["version", activeInstalledSkill.version || meta.version]);
    }
    if (activeInstalledSkill.author || meta.author) {
      pairs.push(["author", activeInstalledSkill.author || meta.author]);
    }
    if (activeInstalledSkill.license || meta.license) {
      pairs.push(["license", activeInstalledSkill.license || meta.license]);
    }

    const plats = activeInstalledSkill.platforms || meta.platforms;
    if (plats) {
      pairs.push([
        "platforms",
        `[${Array.isArray(plats) ? plats.join(", ") : plats}]`,
      ]);
    }

    if (meta.metadata) {
      const nested = meta.metadata;
      const anaraBlock = nested.anara || nested;
      const lines: string[] = ["anara:"];
      if (anaraBlock.tags) {
        lines.push(`  tags: [${Array.isArray(anaraBlock.tags) ? anaraBlock.tags.join(", ") : anaraBlock.tags}]`);
      }
      if (anaraBlock.hero) {
        lines.push(`  hero: [${Array.isArray(anaraBlock.hero) ? anaraBlock.hero.join(", ") : anaraBlock.hero}]`);
      }
      if (anaraBlock.related_skills) {
        lines.push(`  related_skills: [${Array.isArray(anaraBlock.related_skills) ? anaraBlock.related_skills.join(", ") : anaraBlock.related_skills}]`);
      }
      if (anaraBlock.homepage) {
        lines.push(`  homepage: ${anaraBlock.homepage}`);
      }
      pairs.push(["metadata", lines.join("\n")]);
    } else if (activeInstalledSkill.tags && activeInstalledSkill.tags.length > 0) {
      pairs.push(["tags", `[${activeInstalledSkill.tags.join(", ")}]`]);
    }

    return pairs;
  }, [activeInstalledSkill]);

  // Toggle skill active/disabled
  const handleToggleSkill = async (slug: string, currentEnabled: boolean) => {
    setTogglingSlug(slug);
    const newEnabled = !currentEnabled;
    setSkills((prev) =>
      prev.map((s) =>
        s.slug === slug
          ? { ...s, enabled: newEnabled, status: newEnabled ? "active" : "disabled" }
          : s
      )
    );

    try {
      const endpoint = newEnabled ? "enable" : "disable";
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}/${endpoint}`, {
        method: "POST",
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

  // Archive learned skill
  const handleArchiveSkill = async (slug: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}/archive`, {
        method: "POST",
      });
      if (res.ok) {
        setInstallNotice(`✓ Successfully archived ${slug}!`);
        await fetchSkills();
        setSelectedSlug(null);
        setTimeout(() => setInstallNotice(null), 3000);
      }
    } catch (err) {
      console.warn("[BrainSkills] Archive error:", err);
    }
  };

  // Install available catalog skill
  const handleInstallOfficialSkill = async (item: OfficialCatalogSkill | OfficialSkillPreviewData) => {
    setInstallingId(item.identifier);
    setInstallNotice(null);
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
        setInstallNotice(`✓ Successfully installed ${item.name}!`);
        await fetchSkills();
        await fetchOfficialCatalog();
        // Switch view to installed tab with newly installed skill selected
        setSkillsTab("installed");
        setSelectedSlug(item.name);
        setTimeout(() => setInstallNotice(null), 4000);
      }
    } catch (err) {
      console.warn("[BrainSkills] Install failed:", err);
    } finally {
      setInstallingId(null);
    }
  };

  // Open raw editor
  const handleOpenEditor = async (slug: string) => {
    setIsEditing(true);
    setEditNotice(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}/content`);
      if (res.ok) {
        const data = await res.json();
        setRawContent(data.content || "");
      }
    } catch {
      setRawContent(activeInstalledSkill?.body || "");
    }
  };

  // Save raw content
  const handleSaveContent = async (slug: string) => {
    setIsSavingContent(true);
    setEditNotice(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/skills/v2/${slug}/content`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: rawContent }),
      });
      if (res.ok) {
        setEditNotice("Saved successfully!");
        fetchSkills();
        setTimeout(() => {
          setIsEditing(false);
          setEditNotice(null);
        }, 1200);
      }
    } catch (err) {
      setEditNotice("Error saving content.");
    } finally {
      setIsSavingContent(false);
    }
  };

  return (
    <div className="h-full w-full flex flex-col overflow-hidden select-none font-sans bg-[#060913]">
      <div className="flex-1 min-h-0 overflow-hidden">
        <MasterDetail resizeId="brain_skills">
          {/* ── LEFT COLUMN: Skills List Filtered by [Installed | Available] ── */}
          <ListColumn
            header={
              <div className="space-y-2">
                {/* Search Bar & Sort Button */}
                <div className="flex items-center gap-1.5">
                  <div className="relative flex-1 min-w-0">
                    <svg
                      className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                      />
                    </svg>
                    <input
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder={
                        skillsTab === "installed"
                          ? "Search installed skills..."
                          : "Search available catalog..."
                      }
                      className="w-full py-1 pl-7 pr-2 rounded-md bg-black/40 border border-white/[0.08] text-[11.5px] text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-white/20 transition-colors font-sans"
                    />
                  </div>
                  <SortButton
                    desc={sortDesc}
                    onToggle={() => setSortDesc((v) => !v)}
                    label={sortDesc ? "Usage" : "A-Z"}
                  />
                </div>

                {/* Sub-header Strip: Micro-compact Tabs [Installed | Available] */}
                <div className="flex items-center justify-between px-0.5 text-[10px] font-mono">
                  <div className="flex items-center p-0.5 rounded bg-black/60 border border-white/[0.08] h-6">
                    <button
                      type="button"
                      onClick={() => setSkillsTab("installed")}
                      className={`px-2 h-full rounded text-[10px] font-mono transition-colors cursor-pointer flex items-center gap-1 ${
                        skillsTab === "installed"
                          ? "bg-white/[0.08] text-white font-medium border border-white/[0.1] shadow-sm"
                          : "text-slate-400 hover:text-slate-200 border border-transparent"
                      }`}
                    >
                      <span>Installed</span>
                      <span className="text-[9px] text-slate-400 font-mono">
                        ({skills.length})
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setSkillsTab("available")}
                      className={`px-2 h-full rounded text-[10px] font-mono transition-colors cursor-pointer flex items-center gap-1 ${
                        skillsTab === "available"
                          ? "bg-white/[0.08] text-white font-medium border border-white/[0.1] shadow-sm"
                          : "text-slate-400 hover:text-slate-200 border border-transparent"
                      }`}
                    >
                      <span>Available</span>
                      <span className="text-[9px] text-slate-400 font-mono">
                        ({visibleAvailable.length})
                      </span>
                    </button>
                  </div>

                  <span className="text-[9px] font-mono text-slate-400 whitespace-nowrap pr-1 tracking-tight">
                    {skillsTab === "installed"
                      ? `${visibleInstalled.length} active`
                      : `${visibleAvailable.length} in catalog`}
                  </span>
                </div>
              </div>
            }
          >
            {/* VIEW 1: INSTALLED SKILLS */}
            {skillsTab === "installed" && (
              <>
                {visibleInstalled.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500 font-mono">
                    {isLoading ? "Loading skills..." : "No installed skills found"}
                  </div>
                ) : (
                  visibleInstalled.map((s) => (
                    <CapRow
                      key={`installed-${s.slug}`}
                      title={s.name}
                      subtitle={
                        <div className="flex items-center gap-1.5 truncate">
                          <span className="truncate">{s.category}</span>
                          {s.is_learned && (
                            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-medium bg-blue-500/15 border border-blue-400/30 text-blue-300">
                              learned
                            </span>
                          )}
                        </div>
                      }
                      active={(activeInstalledSkill?.slug || "") === s.slug}
                      enabled={Boolean(s.enabled)}
                      busy={togglingSlug === s.slug}
                      onSelect={() => setSelectedSlug(s.slug)}
                      onToggle={() => handleToggleSkill(s.slug, Boolean(s.enabled))}
                    />
                  ))
                )}
              </>
            )}

            {/* VIEW 2: AVAILABLE CATALOG SKILLS */}
            {skillsTab === "available" && (
              <>
                {visibleAvailable.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500 font-mono">
                    No available skills match query
                  </div>
                ) : (
                  visibleAvailable.map((item) => {
                    const isInstalling = installingId === item.identifier;
                    const isSelected = selectedOfficial === item.identifier;

                    return (
                      <CapRow
                        key={`available-${item.identifier}`}
                        title={item.name}
                        subtitle={<span className="capitalize">{item.category}</span>}
                        active={isSelected}
                        enabled={false}
                        onSelect={() => setSelectedOfficial(item.identifier)}
                        action={
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleInstallOfficialSkill(item);
                            }}
                            disabled={isInstalling}
                            className="px-2.5 py-0.5 rounded text-[11px] font-mono bg-white/[0.06] hover:bg-white/[0.12] text-slate-200 hover:text-white border border-white/[0.1] transition-all flex items-center gap-1 cursor-pointer disabled:opacity-50"
                          >
                            {isInstalling ? (
                              <>
                                <svg className="w-3 h-3 animate-spin text-cyan-300" viewBox="0 0 24 24" fill="none">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                </svg>
                                <span>Installing...</span>
                              </>
                            ) : (
                              <span>Install</span>
                            )}
                          </button>
                        }
                      />
                    );
                  })
                )}
              </>
            )}
          </ListColumn>

          {/* ── RIGHT COLUMN: Detail Pane ── */}
          <DetailColumn>
            {/* DETAIL VIEW FOR AVAILABLE SKILLS */}
            {skillsTab === "available" && selectedOfficial && officialPreview ? (
              <div className="h-full w-full flex flex-col min-h-0 space-y-2 animate-fade-in">
                {/* Header Banner */}
                <div className="shrink-0 border-b border-white/[0.08] pb-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-[14.5px] font-semibold text-white tracking-tight font-sans">
                      {officialPreview.name}
                    </h2>
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300 capitalize">
                        {officialPreview.category}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/10 border border-cyan-400/25 text-cyan-300 font-semibold uppercase">
                        Official
                      </span>
                    </div>
                  </div>
                  <p className="text-[11.5px] text-slate-400 mt-1 leading-normal font-sans">
                    {officialPreview.description || "Official modular skill from Project Anara catalog."}
                  </p>

                  <div className="mt-1.5 flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => handleInstallOfficialSkill(officialPreview)}
                      disabled={installingId === officialPreview.identifier}
                      className="px-3 py-1 rounded-md text-[11px] font-mono font-semibold bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 border border-cyan-400/30 transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                    >
                      {installingId === officialPreview.identifier ? (
                        <>
                          <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                          </svg>
                          <span>Installing Skill...</span>
                        </>
                      ) : (
                        <span>Install Skill</span>
                      )}
                    </button>
                    {installNotice && (
                      <span className="text-xs font-mono text-emerald-300 animate-fade-in">
                        {installNotice}
                      </span>
                    )}
                  </div>
                </div>

                {/* Metadata Card (Matching Reference Standard 1:1) */}
                <div className="shrink-0 rounded-lg border border-white/[0.08] bg-[#070b16]/70 p-2 space-y-1 font-mono text-[11px]">
                  <div className="flex items-start gap-3">
                    <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">name</span>
                    <span className="text-slate-200 select-text font-semibold">{officialPreview.name}</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">version</span>
                    <span className="text-slate-300 select-text">{officialPreview.version}</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">author</span>
                    <span className="text-slate-300 select-text">{officialPreview.author}</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">license</span>
                    <span className="text-slate-300 select-text">{officialPreview.license}</span>
                  </div>
                  {officialPreview.platforms && (
                    <div className="flex items-start gap-3">
                      <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">platforms</span>
                      <span className="text-slate-300 select-text">
                        [{Array.isArray(officialPreview.platforms) ? officialPreview.platforms.join(", ") : officialPreview.platforms}]
                      </span>
                    </div>
                  )}
                  {officialPreview.tags && officialPreview.tags.length > 0 && (
                    <div className="flex items-start gap-3">
                      <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">tags</span>
                      <div className="flex flex-wrap gap-1">
                        {officialPreview.tags.map((t, idx) => (
                          <ToolChip key={idx}>{t}</ToolChip>
                        ))}
                      </div>
                    </div>
                  )}
                  {officialPreview.setup && (
                    <div className="flex items-start gap-3 pt-1 border-t border-white/[0.04]">
                      <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">setup</span>
                      <div className="text-slate-300 text-[10.5px] whitespace-pre-wrap">
                        {JSON.stringify(officialPreview.setup, null, 2)}
                      </div>
                    </div>
                  )}
                </div>

                {/* Monospace Markdown Documentation Viewer */}
                <div className="rounded-lg border border-white/[0.08] bg-[#050811]/90 p-2.5 font-mono text-[11px] text-slate-300 leading-relaxed overflow-x-auto select-text whitespace-pre-wrap flex-1 min-h-[160px] overflow-y-auto custom-scrollbar shadow-inner">
                  {officialPreview.skill_md}
                </div>
              </div>
            ) : skillsTab === "available" && isPreviewLoading ? (
              <div className="p-12 text-center text-xs text-slate-500 font-mono">
                Loading skill documentation &amp; metadata...
              </div>
            ) : skillsTab === "installed" && activeInstalledSkill && isEditing ? (
              /* DEDICATED FULL-BLEED RAW CODE/MARKDOWN EDITOR (1:1 REFERENCE PARITY) */
              <div className="h-full w-full flex flex-col min-h-0 rounded-lg border border-white/[0.08] bg-[#050811]/95 overflow-hidden animate-fade-in shadow-inner">
                {/* Editor Header Bar */}
                <div className="shrink-0 flex items-center justify-between px-3 py-2 border-b border-white/[0.08] bg-white/[0.02]">
                  <div className="flex items-center gap-2 text-xs font-mono">
                    <span className="text-white font-medium">{activeInstalledSkill.slug}/SKILL.md</span>
                    <span className="text-[10px] text-slate-500 font-sans">Raw Editor</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {editNotice && (
                      <span className="text-[11px] font-mono text-slate-300 mr-2 animate-fade-in">
                        {editNotice}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => setIsEditing(false)}
                      className="px-2.5 py-1 rounded text-xs font-mono text-slate-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => handleSaveContent(activeInstalledSkill.slug)}
                      disabled={isSavingContent}
                      className="px-3 py-1 rounded text-xs font-mono bg-white/[0.12] hover:bg-white/[0.18] text-white border border-white/20 font-medium transition-colors cursor-pointer disabled:opacity-50"
                    >
                      {isSavingContent ? "Saving..." : "Save Changes"}
                    </button>
                  </div>
                </div>
                {/* Full-Height Textarea */}
                <textarea
                  value={rawContent}
                  onChange={(e) => setRawContent(e.target.value)}
                  className="flex-1 w-full min-h-0 p-3.5 bg-transparent border-0 text-xs font-mono text-slate-100 leading-relaxed focus:outline-none focus:ring-0 resize-none whitespace-pre-wrap break-words custom-scrollbar select-text"
                  placeholder="SKILL.md content..."
                  spellCheck={false}
                />
              </div>
            ) : skillsTab === "installed" && activeInstalledSkill ? (
              /* DETAIL VIEW FOR INSTALLED SKILLS */
              <div className="h-full w-full flex flex-col min-h-0 space-y-2 animate-fade-in">
                {/* Header Banner */}
                <div className="shrink-0 border-b border-white/[0.08] pb-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-[14.5px] font-semibold text-white tracking-tight font-sans">
                      {activeInstalledSkill.name}
                    </h2>
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300 capitalize">
                        {activeInstalledSkill.category}
                      </span>
                      {activeInstalledSkill.is_learned && (
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-blue-500/15 border border-blue-400/30 text-blue-300 font-semibold">
                          learned
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-[11.5px] text-slate-400 mt-1 leading-normal font-sans">
                    {activeInstalledSkill.description || "Active agent skill."}
                  </p>

                  {/* ACTION BUTTONS: Only Learned skills can be Edited and Archived (1:1 Reference Standard) */}
                  {activeInstalledSkill.is_learned && (
                    <div className="mt-1.5 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleOpenEditor(activeInstalledSkill.slug)}
                        className="px-2.5 py-1 rounded text-xs font-mono text-slate-200 hover:text-white bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.08] transition-colors cursor-pointer"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleArchiveSkill(activeInstalledSkill.slug)}
                        className="px-2.5 py-1 rounded text-xs font-mono text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors cursor-pointer"
                      >
                        Archive
                      </button>
                      {editNotice && (
                        <span className="text-xs font-mono text-slate-300 ml-2 animate-fade-in">
                          {editNotice}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* METADATA BOX:
                    - If learned: ONLY name and description (1:1 Reference Standard)
                    - If NOT learned: Full metadata (name, description, version, author, license, platforms, metadata)
                */}
                <div className="shrink-0 rounded-lg border border-white/[0.08] bg-[#070b16]/70 p-2 space-y-1 font-mono text-[11px]">
                  {activeInstalledFrontmatterPairs.map(([k, v]) => (
                    <div key={k} className="flex items-start gap-3">
                      <span className="w-24 shrink-0 font-medium text-slate-500 text-[11px]">{k}</span>
                      <span className="min-w-0 select-text text-slate-200 text-[11px] whitespace-pre-wrap break-words leading-relaxed">
                        {v}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Markdown Documentation Viewer */}
                <div className="rounded-lg border border-white/[0.08] bg-[#050811]/90 p-2.5 font-mono text-[11px] text-slate-300 leading-relaxed overflow-x-auto select-text whitespace-pre-wrap break-words flex-1 min-h-[160px] overflow-y-auto custom-scrollbar shadow-inner">
                  {activeInstalledSkill.body || `# ${activeInstalledSkill.name}\n\n${activeInstalledSkill.description}`}
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
    </div>
  );
}