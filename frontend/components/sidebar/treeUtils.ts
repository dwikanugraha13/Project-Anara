import { WorkspaceNode } from "./types";

export const EXPANDED_STORAGE_KEY = "anara_tree_expanded_paths";

/** Normalizes OS file paths to clean forward-slash relative/canonical paths */
export function normalizePath(p: string = ""): string {
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
export function getDirectoryGitRollup(
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

export interface ContextMenuState {
  isOpen: boolean;
  x: number;
  y: number;
  targetNode: WorkspaceNode | null;
  targetPath: string;
  isFolder: boolean;
}

export function getProjectBadge(name: string): { icon?: string; letter: string; color: string } {
  const n = (name || "").toLowerCase();
  if (n.includes("next") || n.includes("react") || n.includes("frontend")) {
    return { letter: "TS", color: "text-sky-400 bg-sky-500/10 border-sky-400/20" };
  }
  if (n.includes("python") || n.includes("backend") || n.includes("api") || n.includes("anara")) {
    return { letter: "PY", color: "text-amber-400 bg-amber-500/10 border-amber-400/20" };
  }
  if (n.includes("rust") || n.includes("cargo")) {
    return { letter: "RS", color: "text-orange-400 bg-orange-500/10 border-orange-400/20" };
  }
  if (n.includes("go")) {
    return { letter: "GO", color: "text-cyan-400 bg-cyan-500/10 border-cyan-400/20" };
  }
  const initial = (name || "W").charAt(0).toUpperCase();
  return { letter: initial, color: "text-violet-400 bg-violet-500/10 border-violet-400/20" };
}
