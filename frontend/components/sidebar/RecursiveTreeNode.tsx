"use client";

import React, { useMemo } from "react";
import { WorkspaceNode } from "./types";
import { renderFileSvgIcon } from "./FileIcons";
import { normalizePath, nodeHasMatch, getDirectoryGitRollup } from "./treeUtils";

export interface RecursiveTreeNodeProps {
  node: WorkspaceNode;
  depth?: number;
  onOpenFileIDE?: (filePath: string, fileName: string) => void;
  gitFilesMap?: Record<string, string>;
  activeFilePath?: string;
  filterText?: string;
  expandedPaths: Set<string>;
  onToggleExpand: (path: string) => void;
  onContextMenu: (e: React.MouseEvent, node: WorkspaceNode) => void;
  onLoadChildren: (dirPath: string) => void;
}

/**
 * Recursive File & Directory Tree Node Component with Git Status badges & lazy expand.
 */
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
  onLoadChildren,
}: RecursiveTreeNodeProps) {
  const normNodePath = normalizePath(node.path || node.name);
  const isManuallyExpanded = expandedPaths.has(normNodePath);

  // Filter check
  const q = filterText.toLowerCase().trim();
  const matchesSelf = !q || (node.name || "").toLowerCase().includes(q);

  // Check if any descendant matches (only among loaded children)
  const hasMatchingDescendant = useMemo(() => {
    if (!q || !node.children || node.children.length === 0) return false;
    return node.children.some((child) => nodeHasMatch(child, q));
  }, [node, q]);

  if (node.type === "directory") {
    const childrenLoaded = node.children !== undefined;
    const hasChildren = childrenLoaded && node.children!.length > 0;
    const isLoading = node.loading === true;

    if (q && !matchesSelf && !hasMatchingDescendant) {
      return null;
    }

    const isFolderOpen = q ? (hasMatchingDescendant || isManuallyExpanded) : isManuallyExpanded;
    const gitRollup = !isFolderOpen ? getDirectoryGitRollup(node, gitFilesMap) : null;

    const handleToggle = () => {
      onToggleExpand(normNodePath);
      if (!isManuallyExpanded && !childrenLoaded && !isLoading) {
        onLoadChildren(node.path);
      }
    };

    return (
      <div className="flex flex-col">
        <button
          type="button"
          onClick={handleToggle}
          onContextMenu={(e) => onContextMenu(e, node)}
          className="flex items-center gap-1.5 w-full text-left py-1 px-1.5 rounded-lg hover:bg-white/[0.06] text-slate-300 hover:text-white transition-colors cursor-pointer group select-none"
          style={{ paddingLeft: `${Math.max(6, depth * 12)}px` }}
        >
          {/* Rotating vector chevron */}
          {isLoading ? (
            <svg className="w-3 h-3 text-cyan-400 shrink-0 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
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
          )}

          {/* Dynamic Folder Icon (Open vs Closed) */}
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

        {isFolderOpen && (
          <div className="flex flex-col border-l border-white/[0.06] ml-2.5">
            {isLoading && !hasChildren && (
              <div className="flex items-center gap-1.5 py-1 px-1.5 text-[10px] text-slate-500 font-mono" style={{ paddingLeft: `${Math.max(6, (depth + 1) * 12)}px` }}>
                <svg className="w-3 h-3 animate-spin text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading...
              </div>
            )}
            {node.loadError && (
              <div className="flex items-center gap-1.5 py-1 px-1.5 text-[10px] text-rose-400 font-mono" style={{ paddingLeft: `${Math.max(6, (depth + 1) * 12)}px` }}>
                Error: {node.loadError}
              </div>
            )}
            {hasChildren && node.children!.map((child, idx) => (
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
                onLoadChildren={onLoadChildren}
              />
            ))}
            {childrenLoaded && !hasChildren && !isLoading && !node.loadError && (
              <div className="py-0.5 px-1.5 text-[10px] text-slate-600 font-mono italic" style={{ paddingLeft: `${Math.max(6, (depth + 1) * 12)}px` }}>
                (empty)
              </div>
            )}
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
  const isSelected = normActive.length > 0 && normPath === normActive;

  // Resolve Git status for this file
  const gitStatusRaw = gitFilesMap[normPath];
  let gitBadge: { label: string; color: string; title: string } | null = null;
  if (gitStatusRaw) {
    if (gitStatusRaw.includes("M")) {
      gitBadge = { label: "M", color: "text-cyan-400", title: "Modified" };
    } else if (gitStatusRaw.includes("A")) {
      gitBadge = { label: "A", color: "text-emerald-400", title: "Added" };
    } else if (gitStatusRaw === "??" || gitStatusRaw.includes("U")) {
      gitBadge = { label: "U", color: "text-amber-400", title: "Untracked" };
    } else if (gitStatusRaw.includes("D")) {
      gitBadge = { label: "D", color: "text-rose-400", title: "Deleted" };
    }
  }

  return (
    <button
      type="button"
      onClick={() => onOpenFileIDE?.(node.path, node.name)}
      onContextMenu={(e) => onContextMenu(e, node)}
      className={`flex items-center gap-2 w-full text-left py-1 px-1.5 rounded-lg text-xs transition-colors cursor-pointer group select-none ${
        isSelected
          ? "bg-cyan-500/15 text-white font-medium border-l-[3px] border-cyan-400 pl-1 rounded-l-none"
          : "hover:bg-white/[0.04] text-slate-300 hover:text-white"
      }`}
      style={{ paddingLeft: `${Math.max(6, depth * 12)}px` }}
      title={`${node.name} (${node.size_kb} KB)`}
    >
      <div className="shrink-0 flex items-center justify-center pointer-events-none">
        {renderFileSvgIcon(ext, isCode, isPdf, isImg)}
      </div>

      <span
        className={`truncate font-mono text-[11px] flex-1 ${
          isSelected
            ? "text-cyan-300 font-semibold"
            : gitBadge
            ? `${gitBadge.color} opacity-90 group-hover:opacity-100`
            : "text-slate-300 group-hover:text-white"
        }`}
      >
        {node.name}
      </span>

      {/* Git Status Badge */}
      {gitBadge && (
        <span
          className={`text-[9px] font-mono font-bold shrink-0 px-1 rounded ${gitBadge.color} bg-white/[0.04]`}
          title={gitBadge.title}
        >
          {gitBadge.label}
        </span>
      )}

      {/* File Size */}
      <span className="text-[9px] text-slate-600 font-mono shrink-0 group-hover:text-slate-400 group-hover:opacity-100 opacity-0 transition-opacity">
        {node.size_kb}k
      </span>
    </button>
  );
}
