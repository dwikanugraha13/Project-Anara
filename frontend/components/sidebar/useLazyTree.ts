import { useState, useRef, useEffect, useCallback } from "react";
import { WorkspaceNode, WorkspaceTreeData } from "./types";
import { normalizePath } from "./treeUtils";
import { anaraApi } from "@/lib/apiClient";

export interface UseLazyTreeReturn {
  treeNodes: WorkspaceNode[];
  setTreeNodes: React.Dispatch<React.SetStateAction<WorkspaceNode[]>>;
  handleLoadChildren: (dirPath: string) => Promise<void>;
  updateNodeAtPath: (
    nodes: WorkspaceNode[],
    targetPath: string,
    updater: (node: WorkspaceNode) => WorkspaceNode
  ) => WorkspaceNode[];
}

/**
 * useLazyTree — Custom hook managing shallow root entries and on-demand lazy expansion
 * for nested directory nodes without eager deep recursion.
 */
export function useLazyTree(workspaceTree: WorkspaceTreeData | null | undefined): UseLazyTreeReturn {
  const [treeNodes, setTreeNodes] = useState<WorkspaceNode[]>([]);
  const inFlightRef = useRef<Set<string>>(new Set());

  // Sync root entries from workspaceTree prop into treeNodes
  useEffect(() => {
    const rootEntries = workspaceTree?.entries ?? workspaceTree?.nested_tree ?? [];
    const mapped: WorkspaceNode[] = rootEntries.map((entry) => ({
      ...entry,
      children:
        entry.type === "directory"
          ? entry.children !== undefined
            ? entry.children
            : undefined
          : undefined,
    }));
    setTreeNodes(mapped);
  }, [workspaceTree]);

  /** Recursively find and update a node by path in the tree */
  const updateNodeAtPath = useCallback(
    (
      nodes: WorkspaceNode[],
      targetPath: string,
      updater: (node: WorkspaceNode) => WorkspaceNode
    ): WorkspaceNode[] => {
      return nodes.map((node) => {
        const normNode = normalizePath(node.path);
        const normTarget = normalizePath(targetPath);
        if (normNode === normTarget) {
          return updater(node);
        }
        if (node.children && node.type === "directory") {
          const updatedChildren = updateNodeAtPath(node.children, targetPath, updater);
          if (updatedChildren !== node.children) {
            return { ...node, children: updatedChildren };
          }
        }
        return node;
      });
    },
    []
  );

  /** Lazy-load children for a directory node */
  const handleLoadChildren = useCallback(
    async (dirPath: string) => {
      const normDir = normalizePath(dirPath);
      if (inFlightRef.current.has(normDir)) return;
      inFlightRef.current.add(normDir);

      // Optimistic: set loading flag
      setTreeNodes((prev) =>
        updateNodeAtPath(prev, dirPath, (node) => ({
          ...node,
          loading: true,
          loadError: undefined,
        }))
      );

      try {
        const result = await anaraApi.workspace.getTreeChildren(dirPath);
        const childEntries: WorkspaceNode[] = (result.entries || []).map((entry: any) => ({
          ...entry,
          children: entry.type === "directory" ? undefined : undefined,
        }));

        setTreeNodes((prev) =>
          updateNodeAtPath(prev, dirPath, (node) => ({
            ...node,
            children: childEntries,
            loading: false,
            loadError: undefined,
          }))
        );
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load";
        setTreeNodes((prev) =>
          updateNodeAtPath(prev, dirPath, (node) => ({
            ...node,
            loading: false,
            loadError: msg,
            children: [],
          }))
        );
      } finally {
        inFlightRef.current.delete(normDir);
      }
    },
    [updateNodeAtPath]
  );

  return {
    treeNodes,
    setTreeNodes,
    handleLoadChildren,
    updateNodeAtPath,
  };
}
