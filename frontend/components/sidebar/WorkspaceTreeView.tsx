"use client";

import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { WorkspaceNode, WorkspaceTreeData, GitStatusData, WorkspaceFile } from "./types";
import { renderFileSvgIcon } from "./FileIcons";
import { anaraApi } from "@/lib/apiClient";

const EXPANDED_STORAGE_KEY = "anara_tree_expanded_paths";

/** Normalizes OS file paths to clean forward-slash relative/canonical paths */
function normalizePath(p: string = ""): string {
  return p.replace(/\\/g, "/").replace(/^\/+/, "").replace(/\/+$/, "");
}

/** Deep recursive checker to verify if a node or any of its descendants matches the filter query */
export function nodeHasMatch(node: WorkspaceNode, q: string): boolean {
  if (!q) return true;
  const name = (node.name || "").toLowerCase();
  if (name.includes(q)) {
    return true;
  }
  if (node.children && node.children.length > 0) {
    return node.children.some((child) => nodeHasMatch(child, q));
  }
  return false;
}

/** Rollup check to see if any descendant in a directory has an active Git status */
function getDirectoryGitRollup(
  node: WorkspaceNode,
  gitFilesMap: Record<string, string>
): "M" | "A" | "U" | "D" | null {
  if (!node.children || node.children.length === 0) return null;

  for (const child of node.children) {
    if (child.type === "file") {
      const normChildPath = normalizePath(child.path);
      const st = gitFilesMap[normChildPath];
      if (st) {
        if (st.includes("M")) return "M";
        if (st.includes("A")) return "A";
        if (st === "??" || st.includes("U")) return "U";
        if (st.includes("D")) return "D";
      }
    } else if (child.type === "directory") {
      const subRollup = getDirectoryGitRollup(child, gitFilesMap);
      if (subRollup) return subRollup;
    }
  }
  return null;
}

interface ContextMenuState {
  isOpen: boolean;
  x: number;
  y: number;
  targetNode: WorkspaceNode | null;
  targetPath: string;
  isFolder: boolean;
}

/** Recursive File & Directory Tree Node Component for IDE support with Git Status badges */
export function RecursiveTreeNode({
  node,
  depth = 0,
  onOpenFileIDE,
  gitFilesMap = {},
  activeFilePath,
  filterText = "",
  expandedPaths,
  onToggleExpand,
  onContextMenu,
}: {
  node: WorkspaceNode;
  depth?: number;
  onOpenFileIDE?: (filePath: string, fileName: string) => void;
  gitFilesMap?: Record<string, string>;
  activeFilePath?: string;
  filterText?: string;
  expandedPaths: Set<string>;
  onToggleExpand: (path: string) => void;
  onContextMenu: (e: React.MouseEvent, node: WorkspaceNode) => void;
}) {
  const normNodePath = normalizePath(node.path || node.name);
  const isManuallyExpanded = expandedPaths.has(normNodePath);

  // Filter check (matches by file/folder name to avoid matching whole drive paths)
  const q = filterText.toLowerCase().trim();
  const matchesSelf = !q || (node.name || "").toLowerCase().includes(q);

  // Check if any descendant matches
  const hasMatchingDescendant = useMemo(() => {
    if (!q || !node.children || node.children.length === 0) return false;
    return node.children.some((child) => nodeHasMatch(child, q));
  }, [node, q]);

  if (node.type === "directory") {
    const hasChildren = node.children && node.children.length > 0;
    if (q && !matchesSelf && !hasMatchingDescendant) {
      return null;
    }

    // Auto-expand folder when search query finds matches inside, otherwise use cached expand state
    const isFolderOpen = q ? (hasMatchingDescendant || isManuallyExpanded) : isManuallyExpanded;
    const gitRollup = !isFolderOpen ? getDirectoryGitRollup(node, gitFilesMap) : null;

    return (
      <div className="flex flex-col">
        <button
          type="button"
          onClick={() => onToggleExpand(normNodePath)}
          onContextMenu={(e) => onContextMenu(e, node)}
          className="flex items-center gap-1.5 w-full text-left py-1 px-1.5 rounded-lg hover:bg-white/[0.06] text-slate-300 hover:text-white transition-colors cursor-pointer group select-none"
          style={{ paddingLeft: `${Math.max(6, depth * 12)}px` }}
        >
          {/* Rotating vector chevron */}
          <svg
            className={`w-3 h-3 text-slate-400 group-hover:text-white transition-transform duration-150 shrink-0 ${
              isFolderOpen ? "rotate-90" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M9 5l7 7-7 7" />
          </svg>

          {/* Dynamic VS Code Folder Icon (Open vs Closed) */}
          {isFolderOpen ? (
            <svg className="w-3.5 h-3.5 text-amber-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
              <path d="M19 20H4c-1.1 0-2-.9-2-2l.01-11c0-1.1.89-2 1.99-2h5l2 2h7c1.1 0 2 .9 2 2v1h-8c-1.1 0-2 .9-2 2l-1.5 6H19v2zm1.75-8H7.38l-1.5 6h13.37l1.5-6z" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5 text-amber-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
              <path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" />
            </svg>
          )}

          <span className="truncate font-mono font-bold text-slate-200 group-hover:text-white transition-colors text-[11px]">
            {node.name}
          </span>

          {/* Collapsed folder Git rollup indicator */}
          {gitRollup && (
            <span
              className={`w-1.5 h-1.5 rounded-full shrink-0 ml-1.5 ${
                gitRollup === "M"
                  ? "bg-cyan-400"
                  : gitRollup === "A"
                  ? "bg-emerald-400"
                  : gitRollup === "D"
                  ? "bg-rose-400"
                  : "bg-amber-400"
              }`}
              title={`Contains uncommitted changes (${gitRollup})`}
            />
          )}

          {hasChildren && (
            <span className="text-[9px] text-slate-500 ml-auto font-mono group-hover:text-slate-400">
              {node.children?.length}
            </span>
          )}
        </button>

        {isFolderOpen && hasChildren && (
          <div className="flex flex-col border-l border-white/[0.06] ml-2.5">
            {node.children!.map((child, idx) => (
              <RecursiveTreeNode
                key={child.path || `${child.name}-${idx}`}
                node={child}
                depth={depth + 1}
                onOpenFileIDE={onOpenFileIDE}
                gitFilesMap={gitFilesMap}
                activeFilePath={activeFilePath}
                filterText={filterText}
                expandedPaths={expandedPaths}
                onToggleExpand={onToggleExpand}
                onContextMenu={onContextMenu}
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

  const normPath = normalizePath(node.path || node.name);
  const normActive = normalizePath(activeFilePath || "");
  const isActive = Boolean(
    normActive &&
      (normPath === normActive ||
        normPath.endsWith("/" + normActive) ||
        normActive.endsWith("/" + normPath))
  );

  // Determine git status badge (M, A, U, D) strictly by normalized relative path match
  const gitStatusRaw = gitFilesMap[normPath] || (node.path ? gitFilesMap[normalizePath(node.path)] : undefined);
  let gitBadge: { label: string; cls: string; title: string } | null = null;

  if (gitStatusRaw) {
    const s = gitStatusRaw.trim();
    if (s === "M" || s === "MM" || s === "M " || s === " M") {
      gitBadge = { label: "M", cls: "text-cyan-400 bg-cyan-950/40 border border-cyan-500/20", title: "Git: Modified" };
    } else if (s === "A" || s === "AM" || s === "A ") {
      gitBadge = { label: "A", cls: "text-emerald-400 bg-emerald-950/40 border border-emerald-500/20", title: "Git: Staged / Added" };
    } else if (s === "??" || s === "U" || s === "UU") {
      gitBadge = { label: "U", cls: "text-amber-400 bg-amber-950/40 border border-amber-500/20", title: "Git: Untracked" };
    } else if (s === "D" || s === "D ") {
      gitBadge = { label: "D", cls: "text-rose-400 bg-rose-950/40 border border-rose-500/20", title: "Git: Deleted" };
    } else if (s === "R") {
      gitBadge = { label: "R", cls: "text-purple-400 bg-purple-950/40 border border-purple-500/20", title: "Git: Renamed" };
    } else {
      gitBadge = { label: s.slice(0, 1), cls: "text-slate-300 bg-white/[0.06] border border-white/10", title: `Git: ${s}` };
    }
  }

  return (
    <div
      className={`flex items-center justify-between py-1 px-1.5 rounded-lg transition-all cursor-pointer group/file select-none border-l-2 ${
        isActive
          ? "border-cyan-400 bg-cyan-500/10 text-white font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
          : "border-transparent hover:bg-white/[0.04] text-slate-300 hover:text-white"
      }`}
      style={{ paddingLeft: `${Math.max(6, depth * 12)}px` }}
      title={`Open IDE: ${node.path} (${node.size_kb ?? 0} KB)`}
      onClick={() => onOpenFileIDE?.(node.path, node.name)}
      onContextMenu={(e) => onContextMenu(e, node)}
    >
      <div className="flex items-center gap-1.5 min-w-0 flex-1 pr-1">
        {renderFileSvgIcon(ext, isPdf, isImg, isCode, node.name)}
        <span className={`truncate font-mono text-[11px] ${isActive ? "text-white font-medium" : "group-hover/file:text-slate-200"}`}>
          {node.name}
        </span>
      </div>

      {/* Right status badge: Git status or file size */}
      {gitBadge ? (
        <span
          className={`font-mono text-[10px] font-bold shrink-0 ml-1 px-1 py-0.2 rounded ${gitBadge.cls}`}
          title={gitBadge.title}
        >
          {gitBadge.label}
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
  onRefreshWorkspace?: () => void;
  onDeleteFile?: (filePath: string) => Promise<boolean>;
  onCreateFile?: (filePath: string) => Promise<boolean>;
}

function getProjectBadge(name: string): { icon?: string; letter: string; color: string } {
  const n = (name || "").trim();
  if (/^[a-zA-Z]:[\\/]?$/i.test(n) || n === "/") {
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
  onRefreshWorkspace,
  onDeleteFile,
  onCreateFile,
}: WorkspaceTreeViewProps) {
  // ── 1. Expand/Collapse Caching ──────────────────────────────────────────
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => {
    try {
      if (typeof window !== "undefined") {
        const cached = localStorage.getItem(EXPANDED_STORAGE_KEY);
        if (cached) {
          const arr = JSON.parse(cached);
          if (Array.isArray(arr) && arr.length > 0) {
            return new Set<string>(arr);
          }
        }
      }
    } catch {}
    // Default: root directories expanded
    const initial = new Set<string>();
    if (workspaceTree?.nested_tree) {
      for (const node of workspaceTree.nested_tree) {
        if (node.type === "directory") {
          initial.add(normalizePath(node.path || node.name));
        }
      }
    }
    return initial;
  });

  const togglePathExpanded = useCallback((path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      try {
        localStorage.setItem(EXPANDED_STORAGE_KEY, JSON.stringify(Array.from(next)));
      } catch {}
      return next;
    });
  }, []);

  const expandAllFolders = useCallback(() => {
    const all = new Set<string>();
    const collect = (nodes: WorkspaceNode[]) => {
      for (const n of nodes) {
        if (n.type === "directory") {
          all.add(normalizePath(n.path || n.name));
          if (n.children) collect(n.children);
        }
      }
    };
    if (workspaceTree?.nested_tree) collect(workspaceTree.nested_tree);
    setExpandedPaths(all);
    try {
      localStorage.setItem(EXPANDED_STORAGE_KEY, JSON.stringify(Array.from(all)));
    } catch {}
  }, [workspaceTree?.nested_tree]);

  const collapseAllFolders = useCallback(() => {
    const empty = new Set<string>();
    setExpandedPaths(empty);
    try {
      localStorage.setItem(EXPANDED_STORAGE_KEY, JSON.stringify([]));
    } catch {}
  }, []);

  // ── 2. Dynamic Git Status Map ───────────────────────────────────────────
  const gitFilesMap = useMemo(() => {
    const map: Record<string, string> = {};
    const rootNorm = normalizePath(workspaceTree?.root_path || "");
    if (gitStatus?.files) {
      for (const f of gitStatus.files) {
        const relPath = normalizePath(f.path);
        map[relPath] = f.status;
        if (rootNorm) {
          map[`${rootNorm}/${relPath}`] = f.status;
        }
      }
    }
    return map;
  }, [gitStatus, workspaceTree?.root_path]);

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
    return workspaceTree.files.filter(
      (f) => (f.name || "").toLowerCase().includes(q) || (f.path || "").toLowerCase().includes(q)
    );
  }, [workspaceTree, explorerFilter]);

  // ── 3. Project Switcher State ───────────────────────────────────────────
  const [isProjectDropdownOpen, setIsProjectDropdownOpen] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");
  const [recentProjects, setRecentProjects] = useState<Array<{ name: string; path: string }>>([]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("anara_recent_projects");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setRecentProjects(parsed);
          return;
        }
      }
    } catch {}
    if (workspaceTree?.workspace_name) {
      setRecentProjects([{ name: workspaceTree.workspace_name, path: workspaceTree.root_path || "" }]);
    }
  }, [workspaceTree?.workspace_name, workspaceTree?.root_path]);

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
  }, [workspaceTree?.workspace_name, workspaceTree?.root_path]);

  useEffect(() => {
    if (!isProjectDropdownOpen) return;
    const close = () => setIsProjectDropdownOpen(false);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [isProjectDropdownOpen]);

  const currentBadge = useMemo(() => getProjectBadge(workspaceTree?.workspace_name || "Project"), [workspaceTree?.workspace_name]);

  const filteredProjects = useMemo(() => {
    const q = projectSearch.trim().toLowerCase();
    if (!q) return recentProjects;
    return recentProjects.filter((p) => p.name.toLowerCase().includes(q));
  }, [recentProjects, projectSearch]);

  const hasTreeMatches = useMemo(() => {
    if (!workspaceTree?.nested_tree || !explorerFilter.trim()) return true;
    const q = explorerFilter.toLowerCase().trim();
    return workspaceTree.nested_tree.some((node) => nodeHasMatch(node, q));
  }, [workspaceTree?.nested_tree, explorerFilter]);

  // ── 4. Drag & Drop and Upload Affordance ─────────────────────────────────
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragOver) setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleFilesUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploadStatus("Uploading...");
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append("file", file);
        formData.append("relative_path", file.name);
        await anaraApi.workspace.upload(formData);
      }
      setUploadStatus("Upload complete");
      setTimeout(() => setUploadStatus(null), 2000);
      onRefreshWorkspace?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setUploadStatus(`Error: ${msg}`);
      setTimeout(() => setUploadStatus(null), 3500);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    handleFilesUpload(e.dataTransfer.files);
  };

  // ── 5. Context Menu & New/Delete File Actions ────────────────────────────
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    isOpen: false,
    x: 0,
    y: 0,
    targetNode: null,
    targetPath: "",
    isFolder: false,
  });

  const [isNewFileDialogOpen, setIsNewFileDialogOpen] = useState(false);
  const [newFileName, setNewFileName] = useState("");
  const [newFileTargetDir, setNewFileTargetDir] = useState("");
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [fileToDelete, setFileToDelete] = useState<string | null>(null);
  const [isActionPending, setIsActionPending] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  const handleOpenContextMenu = (e: React.MouseEvent, node?: WorkspaceNode) => {
    e.preventDefault();
    e.stopPropagation();
    const x = Math.min(e.clientX, window.innerWidth - 200);
    const y = Math.min(e.clientY, window.innerHeight - 240);
    const isFolder = node ? node.type === "directory" : true;
    const targetPath = node ? normalizePath(node.path || node.name) : "";
    setContextMenu({
      isOpen: true,
      x,
      y,
      targetNode: node || null,
      targetPath,
      isFolder,
    });
  };

  useEffect(() => {
    if (!contextMenu.isOpen) return;
    const handleOutside = () => setContextMenu((prev) => ({ ...prev, isOpen: false }));
    window.addEventListener("click", handleOutside);
    window.addEventListener("contextmenu", handleOutside);
    return () => {
      window.removeEventListener("click", handleOutside);
      window.removeEventListener("contextmenu", handleOutside);
    };
  }, [contextMenu.isOpen]);

  const handlePromptNewFile = (parentDir: string = "") => {
    setNewFileTargetDir(parentDir);
    setNewFileName("");
    setIsNewFileDialogOpen(true);
    setContextMenu((prev) => ({ ...prev, isOpen: false }));
  };

  const handleConfirmCreateFile = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newFileName.trim();
    if (!trimmed) return;

    const fullRelPath = newFileTargetDir ? `${newFileTargetDir}/${trimmed}` : trimmed;
    setIsActionPending(true);
    try {
      if (onCreateFile) {
        await onCreateFile(fullRelPath);
      } else {
        await anaraApi.workspace.saveFile(fullRelPath, "");
      }
      setIsNewFileDialogOpen(false);
      setNewFileName("");
      onOpenFileIDE?.(fullRelPath, trimmed);
      onRefreshWorkspace?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create file";
      setActionFeedback(`Error: ${msg}`);
      setTimeout(() => setActionFeedback(null), 3000);
    } finally {
      setIsActionPending(false);
    }
  };

  const handlePromptDeleteFile = (filePath: string) => {
    setFileToDelete(filePath);
    setIsDeleteModalOpen(true);
    setContextMenu((prev) => ({ ...prev, isOpen: false }));
  };

  const handleConfirmDeleteFile = async () => {
    if (!fileToDelete) return;
    setIsActionPending(true);
    try {
      if (onDeleteFile) {
        await onDeleteFile(fileToDelete);
      } else {
        await anaraApi.workspace.deleteFile(fileToDelete);
      }
      setIsDeleteModalOpen(false);
      setFileToDelete(null);
      onRefreshWorkspace?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete file";
      setActionFeedback(`Error: ${msg}`);
      setTimeout(() => setActionFeedback(null), 3000);
    } finally {
      setIsActionPending(false);
    }
  };

  const handleCopyPath = (filePath: string) => {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(filePath);
    setActionFeedback("Copied path");
    setTimeout(() => setActionFeedback(null), 1800);
    setContextMenu((prev) => ({ ...prev, isOpen: false }));
  };

  return (
    <>
      {/* ── LEFT COLUMN: File Explorer & Git Changes Tree (Resizable) ── */}
      <div
        style={{ width: fullWidth ? "100%" : "var(--tree-width, 210px)", transition: "none" }}
        className={`${fullWidth ? "w-full" : "shrink-0"} h-full flex flex-col bg-[#050811]/90 backdrop-blur-xl border-r border-white/[0.08] overflow-hidden select-none relative`}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onContextMenu={(e) => handleOpenContextMenu(e)}
      >
        {/* Hidden File Input for Upload Affordance */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleFilesUpload(e.target.files)}
        />

        {/* Drag & Drop Visual Overlay */}
        {isDragOver && (
          <div className="absolute inset-0 z-40 bg-cyan-950/70 border-2 border-dashed border-cyan-400 backdrop-blur-md flex flex-col items-center justify-center p-4 text-center pointer-events-none animate-in fade-in duration-150">
            <svg className="w-8 h-8 text-cyan-400 mb-2 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-xs font-mono font-bold text-white tracking-wide">
              Drop files to import
            </p>
            <p className="text-[10px] text-cyan-200/80 mt-0.5">
              Files will be saved directly into workspace
            </p>
          </div>
        )}

        {/* Project Switcher & Git Branch Header */}
        <div
          className="relative px-2 py-1.5 bg-[#070b16]/95 border-b border-white/[0.08] font-mono text-xs shrink-0 select-none z-30"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center gap-1.5 min-w-0">
            {/* Project Picker Button (anti-scale transform discipline) */}
            <button
              type="button"
              onClick={() => setIsProjectDropdownOpen((v) => !v)}
              className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] hover:border-white/[0.16] text-slate-200 hover:text-white transition-colors cursor-pointer min-w-0 max-w-[125px] font-bold"
              title="Select or switch project workspace"
            >
              <span className={`w-4 h-4 rounded-[4px] font-mono text-[10px] font-bold flex items-center justify-center shrink-0 leading-none shadow-sm ${currentBadge.color}`}>
                {currentBadge.icon || currentBadge.letter}
              </span>
              <span className="text-[11px] truncate font-sans">
                {workspaceTree?.workspace_name || "Workspace"}
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
              className={`flex items-center gap-1 px-1.5 py-1 rounded-lg transition-colors cursor-pointer truncate min-w-0 ${
                explorerMode === "git"
                  ? "bg-cyan-500/15 border border-cyan-400/35 text-cyan-200 font-semibold"
                  : "hover:bg-white/[0.06] text-slate-400 hover:text-slate-200 border border-transparent"
              }`}
              title={gitStatus?.is_git ? `Branch: ${gitStatus.branch || "master"} (Click to toggle git/tree mode)` : "File Tree"}
            >
              <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7a3 3 0 100-6 3 3 0 000 6zm0 0v10m0 0a3 3 0 100 6 3 3 0 000-6zm8-4a3 3 0 100-6 3 3 0 000 6zm0 0v3a4 4 0 01-4 4h-4" />
              </svg>
              <span className="text-[11px] truncate font-medium">
                {gitStatus?.branch || "main"}
              </span>
            </button>

            {/* Quick Actions (Upload & Close Workspace) */}
            <div className="flex items-center gap-0.5 shrink-0 ml-auto">
              <button
                type="button"
                onClick={() => handlePromptNewFile("")}
                className="p-1 rounded hover:bg-white/[0.06] text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer"
                title="New File in Workspace Root"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 4v16m8-8H4" />
                </svg>
              </button>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="p-1 rounded hover:bg-white/[0.06] text-slate-400 hover:text-emerald-300 transition-colors cursor-pointer"
                title="Upload Files to Workspace"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
              </button>
              <button
                type="button"
                onClick={handleClearWorkspace}
                className="p-1 rounded hover:bg-white/[0.06] text-slate-400 hover:text-rose-300 transition-colors cursor-pointer"
                title="Close Workspace Folder"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Project Switcher Popover Dropdown */}
          {isProjectDropdownOpen && (
            <div
              className="absolute left-2 top-10 z-50 w-56 rounded-xl bg-[#060913]/95 backdrop-blur-2xl border border-white/[0.08] shadow-2xl p-1.5 space-y-1 font-sans text-xs animate-scale-up select-none"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Search Box with SVG Search Icon */}
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
                  const isActive = p.name.toLowerCase() === (workspaceTree?.workspace_name || "").toLowerCase();
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

              {/* Action: + Add project */}
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
          <div className="px-2.5 py-1 bg-[#060a14] border-b border-white/[0.06] flex items-center justify-between text-[10px] font-mono text-slate-300 shrink-0">
            <span className="text-cyan-300 font-bold truncate">
              {gitStatus.changed_count} changed ({gitStatus.branch || "main"})
            </span>
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-emerald-400 font-bold">+{gitStatus.insertions}</span>
              <span className="text-rose-400 font-bold">-{gitStatus.deletions}</span>
            </div>
          </div>
        )}

        {/* Explorer Filter Bar & Tree Toolbar */}
        <div className="p-1.5 border-b border-white/[0.06] bg-[#070c18]/80 shrink-0 flex items-center gap-1.5">
          <div className="relative flex-1 flex items-center min-w-0">
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
              className="w-full py-1 pl-6 pr-5 rounded-lg bg-black/40 border border-white/10 text-[10.5px] text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-white/30 font-mono"
            />
            {explorerFilter && (
              <button
                type="button"
                onClick={() => setExplorerFilter("")}
                className="absolute right-1 w-3.5 h-3.5 rounded flex items-center justify-center text-slate-400 hover:text-white transition-colors text-[9px] cursor-pointer"
                title="Clear filter (Escape)"
              >
                ✕
              </button>
            )}
          </div>

          {/* Tree Navigation Actions: Expand/Collapse All */}
          <div className="flex items-center gap-0.5 shrink-0">
            <button
              type="button"
              onClick={expandAllFolders}
              className="p-1 rounded hover:bg-white/[0.08] text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              title="Expand All Folders"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 13l-7 7-7-7m14-8l-7 7-7-7" />
              </svg>
            </button>
            <button
              type="button"
              onClick={collapseAllFolders}
              className="p-1 rounded hover:bg-white/[0.08] text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              title="Collapse All Folders"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 11l7-7 7 7M5 19l7-7 7 7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Action / Upload Toast Bar */}
        {(uploadStatus || actionFeedback) && (
          <div className="px-2 py-1 bg-cyan-950/80 border-b border-cyan-400/30 text-[10px] font-mono text-cyan-200 flex items-center justify-between shrink-0 animate-in fade-in">
            <span>{uploadStatus || actionFeedback}</span>
          </div>
        )}

        {/* Explorer Tree / Git List */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-1.5 space-y-0.5 font-mono text-xs [contain:content] [overscroll-behavior:contain] [transform:translateZ(0)]">
          {explorerMode === "git" ? (
            filteredGitFiles.length > 0 ? (
              filteredGitFiles.map((gf, gIdx) => {
                const s = (gf.status || "").trim();
                let badgeCls = "text-cyan-400 bg-cyan-950/40 border border-cyan-500/20";
                let badgeLetter = s.slice(0, 1) || "M";
                if (s === "A" || s === "AM") {
                  badgeCls = "text-emerald-400 bg-emerald-950/40 border border-emerald-500/20";
                  badgeLetter = "A";
                } else if (s === "??" || s === "U") {
                  badgeCls = "text-amber-400 bg-amber-950/40 border border-amber-500/20";
                  badgeLetter = "U";
                } else if (s === "D") {
                  badgeCls = "text-rose-400 bg-rose-950/40 border border-rose-500/20";
                  badgeLetter = "D";
                }

                return (
                  <div
                    key={gIdx}
                    onClick={() => {
                      if (gf.status !== "D") {
                        onOpenFileIDE?.(gf.path, gf.path.split(/[/\\]/).pop() || gf.path);
                      }
                    }}
                    onContextMenu={(e) =>
                      handleOpenContextMenu(e, {
                        name: gf.path.split(/[/\\]/).pop() || gf.path,
                        path: gf.path,
                        type: "file",
                      })
                    }
                    className={`flex items-center justify-between py-1 px-1.5 rounded-lg transition-colors cursor-pointer group select-none ${
                      activeFilePath === gf.path
                        ? "bg-white/[0.08] text-white font-medium"
                        : "hover:bg-white/[0.04] text-slate-300 hover:text-white"
                    }`}
                  >
                    <span className={`truncate font-mono text-[11px] ${activeFilePath === gf.path ? "text-white font-medium" : "group-hover:text-slate-200"}`}>
                      {gf.path}
                    </span>
                    <span className={`text-[10px] font-mono font-bold shrink-0 ml-1.5 px-1 py-0.2 rounded ${badgeCls}`}>
                      {badgeLetter}
                    </span>
                  </div>
                );
              })
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
          ) : workspaceTree?.nested_tree && workspaceTree.nested_tree.length > 0 ? (
            hasTreeMatches ? (
              workspaceTree.nested_tree.map((node, idx) => (
                <RecursiveTreeNode
                  key={node.path || `${node.name}-${idx}`}
                  node={node}
                  onOpenFileIDE={onOpenFileIDE}
                  gitFilesMap={gitFilesMap}
                  activeFilePath={activeFilePath}
                  filterText={explorerFilter}
                  expandedPaths={expandedPaths}
                  onToggleExpand={togglePathExpanded}
                  onContextMenu={handleOpenContextMenu}
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
          ) : filteredFlatFiles.length > 0 ? (
            filteredFlatFiles.map((file, idx) => {
              const normFilePath = normalizePath(file.path);
              const gitStatusRaw = gitFilesMap[normFilePath];
              return (
                <div
                  key={idx}
                  className={`flex items-center justify-between px-2 py-1.5 rounded-lg transition-all cursor-pointer group/file select-none border-l-2 ${
                    activeFilePath === file.path
                      ? "border-cyan-400 bg-cyan-500/10 text-white font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
                      : "border-transparent hover:bg-white/[0.04] text-slate-300 hover:text-white"
                  }`}
                  title={`Open: ${file.path} (${file.size_kb} KB)`}
                  onClick={() => onOpenFileIDE?.(file.path, file.name)}
                  onContextMenu={(e) =>
                    handleOpenContextMenu(e, {
                      name: file.name,
                      path: file.path,
                      type: "file",
                      ext: file.ext,
                      size_kb: file.size_kb,
                      is_code: file.is_code,
                      is_image: file.is_image,
                      is_pdf: file.is_pdf,
                    })
                  }
                >
                  <div className="flex items-center gap-1.5 min-w-0 flex-1 pr-1">
                    {renderFileSvgIcon(file.ext, file.is_pdf, file.is_image, file.is_code, file.name)}
                    <span className={`truncate font-mono text-[11px] ${activeFilePath === file.path ? "text-white font-medium" : "group-hover/file:text-slate-200"}`}>
                      {file.name}
                    </span>
                  </div>

                  {gitStatusRaw ? (
                    <span className="text-[10px] font-mono font-bold shrink-0 ml-1 px-1 py-0.2 rounded text-cyan-400 bg-cyan-950/40 border border-cyan-500/20">
                      {gitStatusRaw === "??" ? "U" : gitStatusRaw}
                    </span>
                  ) : (
                    <span className="text-[9px] text-slate-500 font-mono shrink-0">
                      {file.size_kb}k
                    </span>
                  )}
                </div>
              );
            })
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
          )}
        </div>

        {/* ── Context Menu (Liquid Glass popover) ── */}
        {contextMenu.isOpen && (
          <div
            style={{ top: `${contextMenu.y}px`, left: `${contextMenu.x}px` }}
            className="fixed z-50 w-48 rounded-xl bg-[#060913]/95 backdrop-blur-2xl border border-white/[0.10] shadow-[0_12px_36px_rgba(0,0,0,0.85)] p-1 text-xs font-sans text-slate-200 animate-in fade-in duration-100 select-none"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-2 py-1 text-[10px] font-mono text-slate-500 truncate border-b border-white/[0.06] mb-0.5">
              {contextMenu.targetNode ? contextMenu.targetNode.name : "Workspace"}
            </div>

            <button
              type="button"
              onClick={() => handlePromptNewFile(contextMenu.isFolder ? contextMenu.targetPath : "")}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left hover:bg-white/[0.07] hover:text-white transition-colors cursor-pointer"
            >
              <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 4v16m8-8H4" />
              </svg>
              <span>New File...</span>
            </button>

            <button
              type="button"
              onClick={() => {
                fileInputRef.current?.click();
                setContextMenu((prev) => ({ ...prev, isOpen: false }));
              }}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left hover:bg-white/[0.07] hover:text-white transition-colors cursor-pointer"
            >
              <svg className="w-3.5 h-3.5 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              <span>Upload Files...</span>
            </button>

            {contextMenu.targetPath && (
              <button
                type="button"
                onClick={() => handleCopyPath(contextMenu.targetPath)}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left hover:bg-white/[0.07] hover:text-white transition-colors cursor-pointer"
              >
                <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" />
                </svg>
                <span>Copy Path</span>
              </button>
            )}

            {contextMenu.targetNode && contextMenu.targetNode.type === "file" && (
              <>
                <div className="border-t border-white/[0.06] my-1" />
                <button
                  type="button"
                  onClick={() => handlePromptDeleteFile(contextMenu.targetPath)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-rose-300 hover:bg-rose-500/10 hover:text-rose-200 transition-colors cursor-pointer"
                >
                  <svg className="w-3.5 h-3.5 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  <span>Delete File</span>
                </button>
              </>
            )}
          </div>
        )}

        {/* ── Non-blocking Modal: New File Creation ── */}
        {isNewFileDialogOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in"
            onClick={() => setIsNewFileDialogOpen(false)}
          >
            <div
              className="w-full max-w-sm rounded-2xl border border-white/[0.10] bg-[#070b16]/95 backdrop-blur-2xl shadow-2xl p-4 flex flex-col font-sans text-xs select-none"
              onClick={(e) => e.stopPropagation()}
            >
              <h4 className="text-sm font-semibold text-white tracking-wide mb-1 flex items-center gap-2">
                <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                <span>Create New File</span>
              </h4>
              <p className="text-[11px] text-slate-400 mb-3">
                {newFileTargetDir ? `In: ${newFileTargetDir}/` : "In workspace root"}
              </p>

              <form onSubmit={handleConfirmCreateFile} className="space-y-3">
                <input
                  type="text"
                  autoFocus
                  value={newFileName}
                  onChange={(e) => setNewFileName(e.target.value)}
                  placeholder="e.g. index.ts, styles.css"
                  className="w-full py-2 px-3 rounded-xl bg-black/50 border border-white/10 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-400 font-mono"
                />

                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setIsNewFileDialogOpen(false)}
                    className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/[0.05] transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isActionPending || !newFileName.trim()}
                    className="px-3.5 py-1.5 rounded-lg bg-cyan-400 hover:bg-cyan-300 text-black font-semibold shadow-[0_0_12px_rgba(34,211,238,0.3)] transition-colors cursor-pointer disabled:opacity-50"
                  >
                    {isActionPending ? "Creating..." : "Create"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── Non-blocking Modal: Delete File Confirmation ── */}
        {isDeleteModalOpen && fileToDelete && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in"
            onClick={() => setIsDeleteModalOpen(false)}
          >
            <div
              className="w-full max-w-sm rounded-2xl border border-rose-500/25 bg-[#070b16]/95 backdrop-blur-2xl shadow-2xl p-4 flex flex-col font-sans text-xs select-none"
              onClick={(e) => e.stopPropagation()}
            >
              <h4 className="text-sm font-semibold text-rose-300 tracking-wide mb-1 flex items-center gap-2">
                <svg className="w-4 h-4 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                <span>Delete File?</span>
              </h4>
              <p className="text-[11px] text-slate-300 mb-2">
                Are you sure you want to permanently delete:
              </p>
              <div className="py-1.5 px-2.5 rounded-lg bg-black/50 border border-white/10 font-mono text-[11px] text-rose-200 truncate mb-4">
                {fileToDelete}
              </div>

              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsDeleteModalOpen(false)}
                  className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/[0.05] transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmDeleteFile}
                  disabled={isActionPending}
                  className="px-3.5 py-1.5 rounded-lg bg-rose-500 hover:bg-rose-400 text-white font-semibold shadow-[0_0_12px_rgba(244,63,94,0.3)] transition-colors cursor-pointer disabled:opacity-50"
                >
                  {isActionPending ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Single 1px Vertical Divider between Tree and Editor (only if not fullWidth) ── */}
      {!fullWidth && (
        <div
          onMouseDown={startResizingTree}
          className="relative w-px h-full cursor-col-resize shrink-0 select-none bg-white/[0.08] hover:bg-cyan-400/40 active:bg-cyan-400 transition-colors z-20"
          title="Drag to resize file tree width"
        >
          {/* Expanded invisible hit area for easy mouse grabbing */}
          <div className="absolute inset-y-0 -left-1.5 w-3 cursor-col-resize bg-transparent hover:bg-transparent active:bg-transparent" />
        </div>
      )}
    </>
  );
}
