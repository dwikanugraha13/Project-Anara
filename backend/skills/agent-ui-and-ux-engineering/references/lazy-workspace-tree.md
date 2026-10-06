# Lazy Workspace Tree Architecture (Anara Desktop Parity)

Reference for implementing on-demand directory expansion in agent IDE file explorers,
mirroring the pattern used by Anara Desktop (`use-project-tree.ts`, `tree.tsx`, `ipc.ts`).

## Core Convention: `children === undefined` means not-loaded

```typescript
interface WorkspaceNode {
  name: string;
  path: string;
  type: "directory" | "file";
  // Lazy tree convention:
  // - undefined  → children NOT loaded yet (directory not expanded)
  // - []         → children loaded, directory is empty
  // - [...nodes] → children loaded with entries
  children?: WorkspaceNode[];
  loading?: boolean;    // true while fetching
  loadError?: string;   // error message if fetch failed
}
```

## Backend API Shape

| Endpoint | Returns | Purpose |
|---|---|---|
| `GET /api/agent/workspace/tree` | `{ entries: Node[], files: File[], workspace_name, root_path }` | Root-level entries only (shallow, 1 level) |
| `GET /api/agent/workspace/tree/children?path=<abs>` | `{ path, entries: Node[] }` | Children of one directory |

Backend uses `os.scandir()` for single-level listing — no recursion. Entries sorted
directories-first, then case-insensitive name. Ignored dirs list filters `.git`, `node_modules`,
`__pycache__`, `.next`, `venv`, etc.

## Frontend State Management

1. **Root sync**: `useEffect` maps `workspaceTree.entries` into `treeNodes` state.
   Directories get `children: undefined` (not-loaded). Legacy `nested_tree` with
   pre-populated children is preserved if present.

2. **Immutable recursive updater**: `updateNodeAtPath(nodes, targetPath, updater)` walks
   the tree and returns a new array reference only for the changed branch.

3. **In-flight dedup**: `inFlightRef = useRef<Set<string>>()` prevents duplicate fetches
   for the same directory when the user rapidly clicks.

4. **Expand triggers fetch**: `handleToggle` calls `onToggleExpand(path)` for UI state,
   then if `!childrenLoaded && !isLoading`, calls `onLoadChildren(dirPath)`.

5. **Loading states**: Spinner replaces chevron during fetch. Placeholder row
   "Loading..." shown inside expanded empty container. Error row on failure.
   Empty `(empty)` indicator for loaded directories with zero children.

## Pitfalls

- **Never return full recursive tree from API** — a project with `node_modules` can
  produce 3.9MB+ JSON that causes MemoryError and event loop starvation.
- **Backward compat**: Backend returns both `entries` (new) and `files` (flat list for
  PromptAssembler). Frontend checks `entries ?? nested_tree` for graceful migration.
- **Expand-all only walks loaded nodes** — it expands what's cached, not the entire
  filesystem. Users can still expand individual deep folders on demand.
- **Filter/search only matches loaded children** — `nodeHasMatch()` cannot see into
  unexpanded directories. This is the same trade-off Anara makes.
- **localStorage expand cache** uses normalized forward-slash paths to avoid
  Windows/POSIX mismatch (`normalizePath()` strips backslashes and leading slashes).
