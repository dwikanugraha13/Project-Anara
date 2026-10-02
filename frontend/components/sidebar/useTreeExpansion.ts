import { useState, useCallback } from "react";
import { WorkspaceNode, WorkspaceTreeData } from "./types";
import { normalizePath, EXPANDED_STORAGE_KEY } from "./treeUtils";

export interface UseTreeExpansionReturn {
  expandedPaths: Set<string>;
  setExpandedPaths: React.Dispatch<React.SetStateAction<Set<string>>>;
  togglePathExpanded: (path: string) => void;
  expandAllFolders: () => void;
  collapseAllFolders: () => void;
}

/**
 * useTreeExpansion — Custom hook managing folder expand/collapse state, localStorage caching,
 * and bulk expand/collapse actions.
 */
export function useTreeExpansion(
  workspaceTree: WorkspaceTreeData | null | undefined,
  treeNodes: WorkspaceNode[]
): UseTreeExpansionReturn {
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
    const rootEntries = workspaceTree?.entries ?? workspaceTree?.nested_tree;
    if (rootEntries) {
      for (const node of rootEntries) {
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
          if (n.children && n.children.length > 0) {
            collect(n.children);
          }
        }
      }
    };
    collect(treeNodes);
    setExpandedPaths(all);
    try {
      localStorage.setItem(EXPANDED_STORAGE_KEY, JSON.stringify(Array.from(all)));
    } catch {}
  }, [treeNodes]);

  const collapseAllFolders = useCallback(() => {
    setExpandedPaths(new Set());
    try {
      localStorage.setItem(EXPANDED_STORAGE_KEY, JSON.stringify([]));
    } catch {}
  }, []);

  return {
    expandedPaths,
    setExpandedPaths,
    togglePathExpanded,
    expandAllFolders,
    collapseAllFolders,
  };
}
