"use client";

import React, { useState, useMemo, useEffect } from "react";
import { WorkspaceNode, WorkspaceTreeData, GitStatusData } from "./types";
import { renderFileSvgIcon } from "./FileIcons";

/** Deep recursive checker to verify if a node or any of its descendants matches the filter query */
export function nodeHasMatch(node: WorkspaceNode, q: string): boolean {
  if (!q) return true;
  const name = (node.name || "").toLowerCase();
  const path = (node.path || "").toLowerCase();
  if (name.includes(q) || path.includes(q)) {
    return true;
  }
  if (node.children && node.children.length > 0) {
    return node.children.some((child) => nodeHasMatch(child, q));
  }
  return false;
}

/** Recursive File & Directory Tree Node Component for IDE support with Git Status badges */
export function RecursiveTreeNode({
  node,
  depth = 0,
  onOpenFileIDE,
  gitFilesMap = {},
  activeFilePath,
  filterText = "",
}: {
  node: WorkspaceNode;
  depth?: number;
  onOpenFileIDE?: (filePath: string, fileName: string) => void;
  gitFilesMap?: Record<string, string>;
  activeFilePath?: string;
  filterText?: string;
}) {
  // Only root directories start expanded by default; sub-folders collapsed for instant 60 FPS performance
  const [isExpanded, setIsExpanded] = useState(depth === 0);

  // Filter check
  const q = filterText.toLowerCase().trim();
  const matchesSelf = !q || (node.name || "").toLowerCase().includes(q) || ((node.path || "").toLowerCase().includes(q));

  // Check if any descendant matches
  const hasMatchingDescendant = useMemo(() => {
    if (!q || !node.children || node.children.length === 0) return false;
    return node.children.some((child) => nodeHasMatch(child, q));
  }, [node, q]);

  // Auto-expand folder when search query matches any child item
  useEffect(() => {
    if (q && hasMatchingDescendant) {
      setIsExpanded(true);
    }
  }, [q, hasMatchingDescendant]);

  if (node.type === "directory") {
    const hasChildren = node.children && node.children.length > 0;
    // If filter is active and neither this folder nor any nested child matches, hide
    if (q && !matchesSelf && !hasMatchingDescendant) {
      return null;
    }

    // Auto-expand folder when search query finds matches inside
    const isFolderOpen = q ? (hasMatchingDescendant || isExpanded) : isExpanded;

    return (
      <div className="flex flex-col">
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="flex items-center gap-1.5 w-full text-left py-1 px-1.5 rounded-lg hover:bg-white/[0.07] text-slate-300 hover:text-white transition-colors cursor-pointer group select-none"
          style={{ paddingLeft: `${Math.max(6, depth * 12)}px` }}
        >
          {/* Smooth rotating vector chevron */}
          <svg
            className={`w-3 h-3 text-slate-400 group-hover:text-white transition-transform duration-150 shrink-0 ${
              isFolderOpen ? "rotate-90" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
          </svg>

          {/* Dynamic VS Code Folder Icon (Open vs Closed) */}
          {isFolderOpen ? (
            <svg className="w-3.5 h-3.5 text-amber-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
              <path d="M19 20H4c-1.1 0-2-.9-2-2l.01-11c0-1.1.89-2 1.99-2h5l2 2h7c1.1 0 2 .9 2 2v1h-8c-1.1 0-2 .9-2 2l-1.5 6H19v2zm1.75-8H7.38l-1.5 6h13.37l1.5-6z"/>
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5 text-amber-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
              <path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
            </svg>
          )}

          <span className="truncate font-mono font-bold text-slate-200 group-hover:text-white transition-colors">
            {node.name}
          </span>
          {hasChildren && (
            <span className="text-[9px] text-slate-500 ml-auto font-mono group-hover:text-slate-300">
              {node.children?.length}
            </span>
          )}
        </button>

        {isFolderOpen && hasChildren && (
          <div className="flex flex-col border-l border-white/[0.06] ml-2.5">
            {node.children!.map((child, idx) => (
              <RecursiveTreeNode
                key={idx}
                node={child}
                depth={depth + 1}
                onOpenFileIDE={onOpenFileIDE}
                gitFilesMap={gitFilesMap}
                activeFilePath={activeFilePath}
                filterText={filterText}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  // File Item Filter
  if (q && !matchesSelf) {
    return null;
  }

  const isCode = node.is_code;
  const isPdf = node.is_pdf;
  const isImg = node.is_image;
  const ext = (node.ext || "").toLowerCase();
  const isActive = activeFilePath && (node.path === activeFilePath || activeFilePath.endsWith(node.name));

  // Determine git status badge (A, M, D, U)
  const normPath = (node.path || "").replace(/\\/g, "/");
  const gitStatus = gitFilesMap[normPath] || gitFilesMap[node.name] || Object.entries(gitFilesMap).find(([k]) => normPath.endsWith(k))?.[1];

  return (
    <div
      className={`flex items-center justify-between py-1 px-1.5 rounded-lg transition-all cursor-pointer group/file select-none border-l-2 ${
        isActive
          ? "border-cyan-400 bg-cyan-500/10 text-white font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]"
          : "border-transparent hover:bg-white/[0.04] text-slate-300 hover:text-white"
      }`}
      style={{ paddingLeft: `${Math.max(6, depth * 12)}px` }}
      title={`Open IDE: ${node.path} (${node.size_kb ?? 0} KB)`}
      onClick={() => onOpenFileIDE?.(node.path, node.name)}
    >
      <div className="flex items-center gap-1.5 min-w-0 flex-1 pr-1">
        {renderFileSvgIcon(ext, isPdf, isImg, isCode, node.name)}
        <span className={`truncate font-mono text-[11px] ${isActive ? "text-white font-medium" : "group-hover/file:text-slate-200"}`}>
          {node.name}
        </span>
      </div>

      {/* Right status badge: Git letter A / M / D or size */}
      {gitStatus ? (
        <span
          className={`font-mono text-[10.5px] font-bold shrink-0 ml-1 px-1 rounded ${
            gitStatus === "M"
              ? "text-cyan-400 bg-cyan-950/40"
              : gitStatus === "A" || gitStatus === "??"
              ? "text-emerald-400 bg-emerald-950/40"
              : gitStatus === "D"
              ? "text-rose-400 bg-rose-950/40"
              : "text-amber-400 bg-amber-950/40"
          }`}
          title={`Status Git: ${gitStatus}`}
        >
          {gitStatus === "??" ? "U" : gitStatus}
        </span>
      ) : typeof node.size_kb === "number" ? (
        <span className="text-[9px] text-slate-500 font-mono shrink-0">
          {node.size_kb}k
        </span>
      ) : null}
    </div>
  );
}

interface WorkspaceTreeViewProps {
  workspaceTree: WorkspaceTreeData;
  gitStatus: GitStatusData | null;
  explorerMode: "tree" | "git";
  setExplorerMode: React.Dispatch<React.SetStateAction<"tree" | "git">>;
  explorerFilter: string;
  setExplorerFilter: (s: string) => void;
  activeFilePath?: string;
  onOpenFileIDE?: (filePath: string, fileName: string) => void;
  handlePickLocalFolder: (targetPath?: string) => void;
  handleClearWorkspace: () => void;
  startResizingTree: (e: React.MouseEvent) => void;
  fullWidth?: boolean;
}

function getProjectBadge(name: string): { icon?: string; letter: string; color: string } {
  const n = (name || "").trim();
  if (n.toUpperCase() === "C:" || n.startsWith("C:\\") || n.startsWith("C:/")) {
    return { icon: "▲", letter: "", color: "bg-black text-white border border-white/25" };
  }
  const firstChar = (n[0] || "P").toUpperCase();
  const colors: Record<string, string> = {
    P: "bg-purple-600/90 text-purple-100",
    J: "bg-pink-600/90 text-pink-100",
    D: "bg-slate-600/90 text-slate-100",
    C: "bg-black text-white border border-white/20",
    A: "bg-cyan-600/90 text-cyan-100",
    G: "bg-emerald-600/90 text-emerald-100",
  };
  const color = colors[firstChar] || "bg-indigo-600/90 text-indigo-100";
  return { letter: firstChar, color };
}

export default function WorkspaceTreeView({
  workspaceTree,
  gitStatus,
  explorerMode,
  setExplorerMode,
  explorerFilter,
  setExplorerFilter,
  activeFilePath,
  onOpenFileIDE,
  handlePickLocalFolder,
  handleClearWorkspace,
  startResizingTree,
  fullWidth = false,
}: WorkspaceTreeViewProps) {
  const gitFilesMap = useMemo(() => {
    const map: Record<string, string> = {};
    if (gitStatus?.files) {
      for (const f of gitStatus.files) {
        map[f.path.replace(/\\/g, "/")] = f.status;
        const fname = f.path.split(/[/\\]/).pop();
        if (fname) map[fname] = f.status;
      }
    }
    return map;
  }, [gitStatus]);

  const filteredGitFiles = useMemo(() => {
    if (!gitStatus?.files) return [];
    if (!explorerFilter.trim()) return gitStatus.files;
    const q = explorerFilter.toLowerCase().trim();
    return gitStatus.files.filter((gf) => (gf.path || "").toLowerCase().includes(q));
  }, [gitStatus, explorerFilter]);

  const filteredFlatFiles = useMemo(() => {
    if (!workspaceTree?.files) return [];
    if (!explorerFilter.trim()) return workspaceTree.files;
    const q = explorerFilter.toLowerCase().trim();
    return workspaceTree.files.filter((f) => (f.name || "").toLowerCase().includes(q) || (f.path || "").toLowerCase().includes(q));
  }, [workspaceTree, explorerFilter]);

  const [isProjectDropdownOpen, setIsProjectDropdownOpen] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");
  const [recentProjects, setRecentProjects] = useState<Array<{ name: string; path: string }>>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("anara_recent_projects");
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) return parsed;
        }
      } catch {}
    }
    return [
      { name: "Project Anara", path: "" },
      { name: "jiofarm", path: "" },
      { name: "Default Project", path: "" },
    ];
  });

  // Sync active workspaceTree to recentProjects
  useEffect(() => {
    if (!workspaceTree?.workspace_name) return;
    const currentName = workspaceTree.workspace_name;
    const currentPath = workspaceTree.root_path || "";
    setRecentProjects((prev) => {
      const filtered = prev.filter((p) => p.name.toLowerCase() !== currentName.toLowerCase());
      const updated = [{ name: currentName, path: currentPath }, ...filtered];
      try {
        localStorage.setItem("anara_recent_projects", JSON.stringify(updated.slice(0, 15)));
      } catch {}
      return updated;
    });
  }, [workspaceTree]);

  // Click-outside listener for project dropdown
  useEffect(() => {
    if (!isProjectDropdownOpen) return;
    const close = () => setIsProjectDropdownOpen(false);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [isProjectDropdownOpen]);

  const currentBadge = useMemo(() => getProjectBadge(workspaceTree.workspace_name), [workspaceTree.workspace_name]);

  const filteredProjects = useMemo(() => {
    const q = projectSearch.trim().toLowerCase();
    if (!q) return recentProjects;
    return recentProjects.filter((p) => p.name.toLowerCase().includes(q));
  }, [recentProjects, projectSearch]);

  const hasTreeMatches = useMemo(() => {
    if (!workspaceTree?.nested_tree || !explorerFilter.trim()) return true;
    const q = explorerFilter.toLowerCase().trim();
    return workspaceTree.nested_tree.some((node) => nodeHasMatch(node, q));
  }, [workspaceTree, explorerFilter]);

  return (
    <>
      {/* ── LEFT COLUMN: File Explorer & Git Changes Tree (Resizable) ── */}
      <div
        style={{ width: fullWidth ? "100%" : "var(--tree-width, 210px)", transition: "none" }}
        className={`${fullWidth ? "w-full" : "shrink-0"} h-full flex flex-col bg-black/40 overflow-hidden select-none`}
      >
        {/* Project Switcher & Git Branch Header (Screenshot match: [P] Project Anara ▾ / ⑂ master) */}
        <div
          className="relative px-2 py-1.5 bg-black/60 border-b border-white/10 font-mono text-xs shrink-0 select-none z-30"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center gap-1.5 min-w-0">
            {/* Project Picker Button */}
            <button
              type="button"
              onClick={() => setIsProjectDropdownOpen((v) => !v)}
              className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.12] border border-white/10 hover:border-white/20 text-slate-200 hover:text-white transition-all cursor-pointer min-w-0 max-w-[125px] font-bold active:scale-95 shadow-sm"
              title="Select or switch project"
            >
              <span className={`w-4 h-4 rounded-[4px] font-mono text-[10px] font-bold flex items-center justify-center shrink-0 leading-none shadow-sm ${currentBadge.color}`}>
                {currentBadge.icon || currentBadge.letter}
              </span>
              <span className="text-[11px] truncate font-sans">
                {workspaceTree.workspace_name}
              </span>
              <svg className={`w-3 h-3 text-slate-400 transition-transform duration-150 shrink-0 ${isProjectDropdownOpen ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Separator */}
            <span className="text-slate-600 text-xs shrink-0 select-none">/</span>

            {/* Git Branch Button */}
            <button
              type="button"
              onClick={() => setExplorerMode((m) => (m === "tree" ? "git" : "tree"))}
              className={`flex items-center gap-1 px-1.5 py-1 rounded-lg transition-all cursor-pointer truncate min-w-0 ${
                explorerMode === "git"
                  ? "bg-cyan-500/15 border border-cyan-400/35 text-cyan-200"
                  : "hover:bg-white/[0.06] text-slate-400 hover:text-slate-200"
              }`}
              title={gitStatus?.is_git ? `Branch: ${gitStatus.branch || "master"} (Click to toggle git/tree mode)` : "File Tree"}
            >
              <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7a3 3 0 100-6 3 3 0 000 6zm0 0v10m0 0a3 3 0 100 6 3 3 0 000-6zm8-4a3 3 0 100-6 3 3 0 000 6zm0 0v3a4 4 0 01-4 4h-4" />
              </svg>
              <span className="text-[11px] truncate font-medium">
                {gitStatus?.branch || "master"}
              </span>
            </button>

            {/* Close Workspace Button */}
            <div className="flex items-center gap-0.5 shrink-0 ml-auto">
              <button
                type="button"
                onClick={handleClearWorkspace}
                className="p-1 rounded text-slate-400 hover:text-rose-300 transition-colors cursor-pointer"
                title="Close Workspace Folder"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Project Switcher Popover Dropdown (Screenshot match) */}
          {isProjectDropdownOpen && (
            <div
              className="absolute left-2 top-10 z-50 w-56 rounded-xl bg-[#18181b] border border-white/15 shadow-2xl p-1.5 space-y-1 font-sans text-xs animate-scale-up select-none"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Search Box with SVG Search Icon (No emoji) */}
              <div className="relative flex items-center mb-1">
                <svg className="w-3.5 h-3.5 text-slate-400 absolute left-2 pointer-events-none shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  autoFocus
                  value={projectSearch}
                  onChange={(e) => setProjectSearch(e.target.value)}
                  placeholder="Search project"
                  className="w-full py-1.5 pl-7 pr-2 rounded-lg bg-black/40 border border-white/10 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-white/30 font-sans"
                />
              </div>

              {/* Projects List */}
              <div className="max-h-48 overflow-y-auto custom-scrollbar space-y-0.5">
                {filteredProjects.map((p, idx) => {
                  const isActive = p.name.toLowerCase() === workspaceTree.workspace_name.toLowerCase();
                  const b = getProjectBadge(p.name);
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        handlePickLocalFolder(p.path);
                        setIsProjectDropdownOpen(false);
                        setProjectSearch("");
                      }}
                      className={`w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg text-left transition-colors cursor-pointer group ${
                        isActive
                          ? "bg-white/10 text-white font-medium"
                          : "hover:bg-white/[0.05] text-slate-300 hover:text-white"
                      }`}
                    >
                      <span className={`w-4 h-4 rounded-[4px] text-[10px] font-mono font-bold flex items-center justify-center shrink-0 leading-none shadow-sm ${b.color}`}>
                        {b.icon || b.letter}
                      </span>
                      <span className="truncate flex-1 font-sans text-xs">
                        {p.name}
                      </span>
                      {isActive && (
                        <svg className="w-3.5 h-3.5 text-slate-300 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Divider */}
              <div className="border-t border-white/10 my-1" />

              {/* Action: + Add project (SVG plus, No emoji) */}
              <button
                type="button"
                onClick={() => {
                  setIsProjectDropdownOpen(false);
                  handlePickLocalFolder();
                }}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer font-sans text-xs font-medium"
              >
                <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                <span>Add project</span>
              </button>
            </div>
          )}
        </div>

        {/* Git Changes Pill Header (+X -Y) */}
        {gitStatus && gitStatus.is_git && gitStatus.changed_count > 0 && (
          <div className="px-2.5 py-1 bg-black/40 border-b border-white/5 flex items-center justify-between text-[10px] font-mono text-slate-300 shrink-0">
            <span className="text-cyan-300 font-bold truncate">{gitStatus.changed_count} files ({gitStatus.branch || "main"})</span>
            <div className="flex items-center gap-1 shrink-0">
              <span className="text-emerald-400 font-bold">+{gitStatus.insertions}</span>
              <span className="text-rose-400 font-bold">-{gitStatus.deletions}</span>
            </div>
          </div>
        )}

        {/* Filter Files */}
        <div className="p-1.5 border-b border-white/5 bg-black/20 shrink-0">
          <div className="relative flex items-center">
            <svg className="w-3 h-3 text-slate-500 absolute left-2 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={explorerFilter}
              onChange={(e) => setExplorerFilter(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  setExplorerFilter("");
                }
              }}
              placeholder="Filter files..."
              className="w-full py-1 pl-6 pr-6 rounded-lg bg-black/40 border border-white/10 text-[10.5px] text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-white/40 font-mono"
            />
            {explorerFilter && (
              <button
                type="button"
                onClick={() => setExplorerFilter("")}
                className="absolute right-1.5 w-4 h-4 rounded flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-colors text-[10px] cursor-pointer"
                title="Clear filter (Escape)"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Explorer Tree / Git List */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-1.5 space-y-0.5 font-mono text-xs [contain:content] [overscroll-behavior:contain] [transform:translateZ(0)]">
          {explorerMode === "git" ? (
            filteredGitFiles.length > 0 ? (
              filteredGitFiles.map((gf, gIdx) => (
                <div
                  key={gIdx}
                  onClick={() => onOpenFileIDE?.(gf.path, gf.path.split(/[/\\]/).pop() || gf.path)}
                  className={`flex items-center justify-between py-1 px-1.5 rounded-lg transition-colors cursor-pointer group select-none ${
                    activeFilePath === gf.path
                      ? "bg-white/[0.08] text-white font-medium"
                      : "hover:bg-white/[0.04] text-slate-300 hover:text-white"
                  }`}
                >
                  <span className={`truncate font-mono text-[11px] ${activeFilePath === gf.path ? "text-white font-medium" : "group-hover:text-slate-200"}`}>
                    {gf.path}
                  </span>
                  <span className={`text-[10px] font-mono font-bold shrink-0 ml-1.5 px-1 rounded ${
                    gf.status === "M"
                      ? "text-cyan-400 bg-cyan-950/40"
                      : gf.status === "A" || gf.status === "??"
                      ? "text-emerald-400 bg-emerald-950/40"
                      : gf.status === "D"
                      ? "text-rose-400 bg-rose-950/40"
                      : "text-amber-400 bg-amber-950/40"
                  }`}>
                    {gf.status === "??" ? "U" : gf.status}
                  </span>
                </div>
              ))
            ) : (
              <div className="py-6 px-3 text-center flex flex-col items-center justify-center text-slate-500 font-mono text-[11px] gap-1">
                <span>No matching files</span>
                {explorerFilter && (
                  <button
                    type="button"
                    onClick={() => setExplorerFilter("")}
                    className="text-cyan-400 hover:underline text-[10px] cursor-pointer mt-1"
                  >
                    Clear filter
                  </button>
                )}
              </div>
            )
          ) : workspaceTree.nested_tree && workspaceTree.nested_tree.length > 0 ? (
            hasTreeMatches ? (
              workspaceTree.nested_tree.map((node, idx) => (
                <RecursiveTreeNode
                  key={idx}
                  node={node}
                  onOpenFileIDE={onOpenFileIDE}
                  gitFilesMap={gitFilesMap}
                  activeFilePath={activeFilePath}
                  filterText={explorerFilter}
                />
              ))
            ) : (
              <div className="py-6 px-3 text-center flex flex-col items-center justify-center text-slate-500 font-mono text-[11px] gap-1">
                <span>No matching files</span>
                {explorerFilter && (
                  <button
                    type="button"
                    onClick={() => setExplorerFilter("")}
                    className="text-cyan-400 hover:underline text-[10px] cursor-pointer mt-1"
                  >
                    Clear filter
                  </button>
                )}
              </div>
            )
          ) : (
            filteredFlatFiles.length > 0 ? (
              filteredFlatFiles.map((file, idx) => (
                <div
                  key={idx}
                  className={`flex items-center justify-between px-2 py-1.5 rounded-lg transition-all cursor-pointer group/file select-none border-l-2 ${
                    activeFilePath === file.path
                      ? "border-cyan-400 bg-cyan-500/10 text-white font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]"
                      : "border-transparent hover:bg-white/[0.04] text-slate-300 hover:text-white"
                  }`}
                  title={`Open: ${file.path} (${file.size_kb} KB)`}
                  onClick={() => onOpenFileIDE?.(file.path, file.name)}
                >
                  <div className="flex items-center gap-1.5 min-w-0 flex-1 pr-1">
                    {renderFileSvgIcon(file.ext, file.is_pdf, file.is_image, file.is_code, file.name)}
                    <span className={`truncate font-mono text-[11px] ${activeFilePath === file.path ? "text-white font-medium" : "group-hover/file:text-slate-200"}`}>
                      {file.name}
                    </span>
                  </div>
                  <span className="text-[9px] text-slate-500 font-mono shrink-0">
                    {file.size_kb}k
                  </span>
                </div>
              ))
            ) : (
              <div className="py-6 px-3 text-center flex flex-col items-center justify-center text-slate-500 font-mono text-[11px] gap-1">
                <span>No matching files</span>
                {explorerFilter && (
                  <button
                    type="button"
                    onClick={() => setExplorerFilter("")}
                    className="text-cyan-400 hover:underline text-[10px] cursor-pointer mt-1"
                  >
                    Clear filter
                  </button>
                )}
              </div>
            )
          )}
        </div>
      </div>

      {/* ── Single 1px Vertical Divider between Tree and Editor (only if not fullWidth) ── */}
      {!fullWidth && (
        <div
          onMouseDown={startResizingTree}
          className="relative w-px h-full cursor-col-resize shrink-0 select-none bg-white/10 hover:bg-white/20 transition-colors z-20"
          title="Drag to resize file tree width"
        >
          {/* Expanded invisible hit area so mouse can grab easily without adding visual thickness */}
          <div className="absolute inset-y-0 -left-1.5 w-3 cursor-col-resize bg-transparent hover:bg-transparent active:bg-transparent" />
        </div>
      )}
    </>
  );
}
