import { getBackendUrl } from "@/lib/apiClient";

export const BACKEND_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  (typeof window !== "undefined" ? getBackendUrl() : "http://localhost:8000")
).replace(/\/+$/, "");

export const DEFAULT_SIDEBAR_WIDTH = 260;
export const MIN_SIDEBAR_WIDTH = 200;
export const MAX_SIDEBAR_WIDTH = 600;

export interface ChatSession {
  id: number;
  session_key?: string | null;
  session_mode?: string | null;
  title: string | null;
  speaker_name: string | null;
  session_type?: "chat" | "code";
  channel?: string | null;
  total_tokens?: number | null;
  status?: string | null;
  message_count: number;
  is_archived: number;
  is_pinned: number;
  created_at: string;
  updated_at: string;
  last_user_text?: string | null;
  workspace_info?: {
    name: string;
    root_path: string;
    is_external?: boolean;
  } | null;
}

export interface WorkspaceFile {
  name: string;
  path: string;
  ext: string;
  size_kb: number;
  is_pdf?: boolean;
  is_image?: boolean;
  is_code?: boolean;
}

export interface WorkspaceNode {
  name: string;
  path: string;
  type: "directory" | "file";
  ext?: string;
  size_kb?: number;
  is_pdf?: boolean;
  is_image?: boolean;
  is_code?: boolean;
  isDirectory?: boolean;
  /**
   * Lazy tree convention (Anara Parity):
   * - `undefined`  → children NOT loaded yet (directory not expanded)
   * - `[]`         → children loaded, directory is empty
   * - `[...nodes]` → children loaded with entries
   */
  children?: WorkspaceNode[];
  /** True while children are being fetched from the backend */
  loading?: boolean;
  /** Error message if children fetch failed */
  loadError?: string;
}

export interface WorkspaceTreeData {
  workspace_name: string;
  is_custom_folder: boolean;
  root_path: string;
  total_files: number;
  files: WorkspaceFile[];
  /** @deprecated Use `entries` for lazy tree (Anara Parity) */
  nested_tree?: WorkspaceNode[];
  /** Lazy tree root-level entries (shallow, 1 level only) */
  entries?: WorkspaceNode[];
}

export interface GitStatusData {
  is_git: boolean;
  branch?: string;
  changed_count: number;
  insertions: number;
  deletions: number;
  files: Array<{ path: string; status: string }>;
}

export interface ChatSessionSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  activeSessionId: number | null;
  activeSpeaker?: string | null;
  speakerRoster?: string[];
  isConnected?: boolean;
  connectionStatus?: string;
  onSelectSession: (id: number) => void;
  onNewSession: () => void;
  onOpenBrain?: () => void;
  onOpenMessaging?: () => void;
  onOpenScheduled?: () => void;
  onOpenProviders?: () => void;
  onOpenArtifacts?: () => void;
  onOpenFileIDE?: (filePath: string, fileName: string) => void;
  onOpenFolder?: () => void;
  refreshKey?: number;
  sidebarWidth?: number;
  onWidthChange?: (width: number) => void;
  activeIdeFile?: {
    isOpen: boolean;
    fileName: string;
    filePath: string;
    fileExt: string;
    fileSizeKb: number;
    content: string;
    originalContent?: string;
  } | null;
  ideTabs?: Array<{
    filePath: string;
    fileName: string;
    fileExt: string;
    fileSizeKb: number;
    content: string;
    originalContent?: string;
  }>;
  onSelectIdeTab?: (filePath: string, fileName: string) => void;
  onCloseIdeTab?: (filePath: string) => void;
  onSaveIdeFile?: (filePath: string, newContent: string) => Promise<boolean>;
  onCloseIDE?: () => void;
  isTerminalOpen?: boolean;
  onToggleTerminal?: (open: boolean) => void;
  onAskAnaraIDE?: (filePath: string, fileName: string) => void;
  onSendText?: (text: string, agentMode?: "plan" | "build") => void;
  agentMode?: "plan" | "build";
  status?: string;
  embedded?: boolean;
  initialSidebarTab?: "history" | "editor";
  sessionType?: "chat" | "code";
  onResetIDE?: () => void;
}

export function toDate(iso: string): Date | null {
  if (!iso) return null;
  // Normalize SQLite space separator "YYYY-MM-DD HH:MM:SS" -> "YYYY-MM-DDTHH:MM:SS"
  const normalized = iso.trim().replace(/^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})/, "$1T$2");
  const hasTz = /(?:Z|[+-]\d{2}(?::?\d{2})?)$/i.test(normalized);
  const d = new Date(hasTz ? normalized : normalized + "Z");
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatFullDateTime(iso: string): string {
  const d = toDate(iso);
  if (!d) return "";
  const dateStr = d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const timeStr = d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${dateStr} • ${timeStr}`;
}

export function formatSmartDateTime(iso: string): string {
  const d = toDate(iso);
  if (!d) return "";
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfYesterday = startOfToday - 86400_000;
  const time = d.getTime();

  const timeStr = d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  if (time >= startOfToday) {
    return timeStr;
  }
  if (time >= startOfYesterday) {
    return `Yesterday, ${timeStr}`;
  }
  const dateStr = d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });
  return `${dateStr}, ${timeStr}`;
}

export function formatRelativeTime(iso: string): string {
  const d = toDate(iso);
  if (!d) return "";
  const diffSec = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  if (diffSec < 60) return "now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d`;
  const diffMonths = Math.floor(diffDays / 30);
  return `${diffMonths}mo`;
}

/**
 * Format token counts into human-readable compact representations (e.g. 1.2k, 18k, 1.4M).
 */
export function formatTokens(tokens?: number | null): string {
  if (tokens === undefined || tokens === null || Number.isNaN(tokens)) return "0";
  const num = Math.max(0, Math.round(tokens));
  if (num < 1000) return `${num}`;
  if (num < 10_000) {
    const val = (num / 1000).toFixed(1).replace(/\.0$/, "");
    return `${val}k`;
  }
  if (num < 1_000_000) {
    return `${Math.round(num / 1000)}k`;
  }
  if (num < 10_000_000) {
    const val = (num / 1_000_000).toFixed(1).replace(/\.0$/, "");
    return `${val}M`;
  }
  return `${Math.round(num / 1_000_000)}M`;
}

export interface SessionDisplayInfo {
  title: string;
  subtitle: string;
  channel: "telegram" | "cli" | "whatsapp" | "web";
  speaker: string;
}

export function resolveSessionDisplay(s: ChatSession): SessionDisplayInfo {
  const rawTitle = (s.title || "").trim();
  const tgMatch = rawTitle.match(/Telegram Chat \((.*?)\)(?:\s*\[.*?\])?/i);
  const waMatch = rawTitle.match(/Whatsapp Chat \((.*?)\)(?:\s*\[.*?\])?/i);
  const cliMatch = rawTitle.match(/Cli Chat \((.*?)\)(?:\s*\[.*?\])?/i);

  let channel: "telegram" | "cli" | "whatsapp" | "web" = "web";
  let speaker = s.speaker_name || "User";

  if (tgMatch) {
    channel = "telegram";
    speaker = tgMatch[1] || speaker;
  } else if (waMatch) {
    channel = "whatsapp";
    speaker = waMatch[1] || speaker;
  } else if (cliMatch || rawTitle.toLowerCase().includes("anara cli") || rawTitle.toLowerCase().includes("cli session")) {
    channel = "cli";
    if (cliMatch) speaker = cliMatch[1] || speaker;
  } else if (s.channel === "telegram" || s.channel === "whatsapp" || s.channel === "cli") {
    channel = s.channel;
  }

  const isGenericTitle =
    !rawTitle ||
    rawTitle === "New Chat" ||
    rawTitle === "New Project" ||
    rawTitle.startsWith("Conversation #") ||
    tgMatch !== null ||
    waMatch !== null ||
    cliMatch !== null;

  let title = rawTitle.replace(/\s*\[.*?:.*?\]/g, "").replace(/\s*\[.*?\]/g, "").trim();
  let subtitle = "";
  let usedLastUserTextForTitle = false;

  if (isGenericTitle && s.last_user_text) {
    title = s.last_user_text.trim().replace(/\n+/g, " ");
    if (title.length > 46) {
      title = title.substring(0, 44).trim() + "…";
    }
    usedLastUserTextForTitle = true;
  } else if (!title || isGenericTitle) {
    title = s.session_type === "code" ? "Coding Workspace" : "New Chat";
  }

  if (!usedLastUserTextForTitle && s.last_user_text && title !== s.last_user_text.trim()) {
    subtitle = s.last_user_text.trim().replace(/\n+/g, " ");
    if (subtitle.length > 55) {
      subtitle = subtitle.substring(0, 52).trim() + "…";
    }
  }

  return { title, subtitle, channel, speaker };
}

export type SidebarGrouping = "project" | "date" | "status" | "none";
export type SidebarOrdering = "updated" | "created" | "tokens" | "status";

export interface SidebarFilterState {
  grouping: SidebarGrouping;
  ordering: SidebarOrdering;
  showTokens: boolean;
  showUpdated: boolean;
  showChannel: boolean;
  channelFilter: "all" | "web" | "cli" | "telegram" | "whatsapp";
  showArchived: boolean;
  projectFilter?: string[];
}

export const SIDEBAR_FILTER_STORAGE_KEYS = {
  grouping: "anara.sidebar.grouping",
  ordering: "anara.sidebar.ordering",
  showTokens: "anara.sidebar.showTokens",
  showUpdated: "anara.sidebar.showUpdated",
  showChannel: "anara.sidebar.showChannel",
  channelFilter: "anara.sidebar.channelFilter",
  showArchived: "anara.sidebar.showArchived",
  projectFilter: "anara.sidebar.projectFilter",
} as const;

export const DEFAULT_SIDEBAR_FILTER_STATE: SidebarFilterState = {
  grouping: "project",
  ordering: "updated",
  showTokens: false,
  showUpdated: true,
  showChannel: true,
  channelFilter: "all",
  showArchived: false,
  projectFilter: [],
};

export function loadSidebarFilterState(): SidebarFilterState {
  if (typeof window === "undefined") {
    return { ...DEFAULT_SIDEBAR_FILTER_STATE };
  }
  try {
    const rawGrouping = localStorage.getItem(SIDEBAR_FILTER_STORAGE_KEYS.grouping);
    const grouping: SidebarGrouping =
      rawGrouping === "project" || rawGrouping === "date" || rawGrouping === "status" || rawGrouping === "none"
        ? rawGrouping
        : DEFAULT_SIDEBAR_FILTER_STATE.grouping;

    const rawOrdering = localStorage.getItem(SIDEBAR_FILTER_STORAGE_KEYS.ordering);
    const ordering: SidebarOrdering =
      rawOrdering === "updated" || rawOrdering === "created" || rawOrdering === "tokens" || rawOrdering === "status"
        ? rawOrdering
        : DEFAULT_SIDEBAR_FILTER_STATE.ordering;

    const rawShowTokens = localStorage.getItem(SIDEBAR_FILTER_STORAGE_KEYS.showTokens);
    const showTokens = rawShowTokens !== null ? rawShowTokens === "true" : DEFAULT_SIDEBAR_FILTER_STATE.showTokens;

    const rawShowUpdated = localStorage.getItem(SIDEBAR_FILTER_STORAGE_KEYS.showUpdated);
    const showUpdated = rawShowUpdated !== null ? rawShowUpdated === "true" : DEFAULT_SIDEBAR_FILTER_STATE.showUpdated;

    const rawShowChannel = localStorage.getItem(SIDEBAR_FILTER_STORAGE_KEYS.showChannel);
    const showChannel = rawShowChannel !== null ? rawShowChannel === "true" : DEFAULT_SIDEBAR_FILTER_STATE.showChannel;

    const rawChannelFilter = localStorage.getItem(SIDEBAR_FILTER_STORAGE_KEYS.channelFilter);
    const channelFilter =
      rawChannelFilter === "web" ||
      rawChannelFilter === "cli" ||
      rawChannelFilter === "telegram" ||
      rawChannelFilter === "whatsapp" ||
      rawChannelFilter === "all"
        ? rawChannelFilter
        : DEFAULT_SIDEBAR_FILTER_STATE.channelFilter;

    const rawShowArchived = localStorage.getItem(SIDEBAR_FILTER_STORAGE_KEYS.showArchived);
    const showArchived = rawShowArchived !== null ? rawShowArchived === "true" : DEFAULT_SIDEBAR_FILTER_STATE.showArchived;

    const rawProjectFilter = localStorage.getItem(SIDEBAR_FILTER_STORAGE_KEYS.projectFilter);
    let projectFilter: string[] = DEFAULT_SIDEBAR_FILTER_STATE.projectFilter || [];
    if (rawProjectFilter) {
      try {
        const parsed = JSON.parse(rawProjectFilter);
        if (Array.isArray(parsed)) projectFilter = parsed;
      } catch {}
    }

    return {
      grouping,
      ordering,
      showTokens,
      showUpdated,
      showChannel,
      channelFilter,
      showArchived,
      projectFilter,
    };
  } catch {
    return { ...DEFAULT_SIDEBAR_FILTER_STATE };
  }
}

export function saveSidebarFilterState(partial: Partial<SidebarFilterState>): void {
  if (typeof window === "undefined") return;
  try {
    if (partial.grouping !== undefined) {
      localStorage.setItem(SIDEBAR_FILTER_STORAGE_KEYS.grouping, partial.grouping);
    }
    if (partial.ordering !== undefined) {
      localStorage.setItem(SIDEBAR_FILTER_STORAGE_KEYS.ordering, partial.ordering);
    }
    if (partial.showTokens !== undefined) {
      localStorage.setItem(SIDEBAR_FILTER_STORAGE_KEYS.showTokens, String(partial.showTokens));
    }
    if (partial.showUpdated !== undefined) {
      localStorage.setItem(SIDEBAR_FILTER_STORAGE_KEYS.showUpdated, String(partial.showUpdated));
    }
    if (partial.showChannel !== undefined) {
      localStorage.setItem(SIDEBAR_FILTER_STORAGE_KEYS.showChannel, String(partial.showChannel));
    }
    if (partial.channelFilter !== undefined) {
      localStorage.setItem(SIDEBAR_FILTER_STORAGE_KEYS.channelFilter, partial.channelFilter);
    }
    if (partial.showArchived !== undefined) {
      localStorage.setItem(SIDEBAR_FILTER_STORAGE_KEYS.showArchived, String(partial.showArchived));
    }
    if (partial.projectFilter !== undefined) {
      localStorage.setItem(SIDEBAR_FILTER_STORAGE_KEYS.projectFilter, JSON.stringify(partial.projectFilter));
    }
  } catch {}
}

export interface SessionCategory {
  category: "pinned" | "home" | "project" | "date" | "status" | "none" | string;
  label: string;
  /** All sessions in this category, sorted by the active ordering. */
  items: ChatSession[];
  /** Workspace root path for project categories (used as unique key). */
  workspacePath?: string;
}

/** Preview count before "Show all N sessions" */
export const SESSION_PREVIEW_COUNT = 3;

export function sortSessions(
  sessions: ChatSession[],
  ordering: SidebarOrdering = "updated"
): ChatSession[] {
  const sorted = [...sessions];
  sorted.sort((a, b) => {
    switch (ordering) {
      case "updated": {
        const ta = toDate(a.updated_at || a.created_at)?.getTime() ?? 0;
        const tb = toDate(b.updated_at || b.created_at)?.getTime() ?? 0;
        return tb - ta;
      }
      case "created": {
        const ta = toDate(a.created_at)?.getTime() ?? 0;
        const tb = toDate(b.created_at)?.getTime() ?? 0;
        return tb - ta;
      }
      case "tokens": {
        const tokA = a.total_tokens ?? 0;
        const tokB = b.total_tokens ?? 0;
        if (tokB !== tokA) return tokB - tokA;
        const ta = toDate(a.updated_at || a.created_at)?.getTime() ?? 0;
        const tb = toDate(b.updated_at || b.created_at)?.getTime() ?? 0;
        return tb - ta;
      }
      case "status": {
        const isDoneA = a.is_archived === 1 || a.status === "done" || a.status === "completed" ? 1 : 0;
        const isDoneB = b.is_archived === 1 || b.status === "done" || b.status === "completed" ? 1 : 0;
        if (isDoneA !== isDoneB) return isDoneA - isDoneB;
        const ta = toDate(a.updated_at || a.created_at)?.getTime() ?? 0;
        const tb = toDate(b.updated_at || b.created_at)?.getTime() ?? 0;
        return tb - ta;
      }
      default:
        return 0;
    }
  });
  return sorted;
}

/**
 * Dynamic session categorization supporting:
 * - project (workspace): Pinned, Home, Per-Project
 * - date: Today, Yesterday, Previous 7 days, Older
 * - status: Working, Done
 * - none: All sessions
 *
 * Inside each category, items are ordered by `ordering`:
 * - updated (most recently active first)
 * - created (most recently created first)
 * - tokens (highest token consumption first)
 * - status (working active sessions first, then done)
 */
export function groupSessionsDynamic(
  sessions: ChatSession[],
  grouping: SidebarGrouping = "project",
  ordering: SidebarOrdering = "updated"
): SessionCategory[] {
  const pinned: ChatSession[] = [];
  const unpinned: ChatSession[] = [];

  for (const s of sessions) {
    if (s.is_pinned === 1) {
      pinned.push(s);
    } else {
      unpinned.push(s);
    }
  }

  const categories: SessionCategory[] = [];

  // Pinned items always form a top category if any exist
  if (pinned.length > 0) {
    categories.push({
      category: "pinned",
      label: "Pinned",
      items: sortSessions(pinned, ordering),
    });
  }

  if (unpinned.length === 0) {
    return categories;
  }

  if (grouping === "project") {
    const homeSessions: ChatSession[] = [];
    const projectMap = new Map<string, { name: string; sessions: ChatSession[] }>();

    for (const s of unpinned) {
      const wp = s.workspace_info?.root_path;
      if (wp) {
        const existing = projectMap.get(wp);
        if (existing) {
          existing.sessions.push(s);
        } else {
          projectMap.set(wp, {
            name: s.workspace_info?.name || wp.split(/[\\/]/).filter(Boolean).pop() || "Project",
            sessions: [s],
          });
        }
      } else {
        homeSessions.push(s);
      }
    }

    if (homeSessions.length > 0) {
      categories.push({
        category: "home",
        label: "Home",
        items: sortSessions(homeSessions, ordering),
      });
    }

    const projectEntries = [...projectMap.entries()].map(([wp, data]) => {
      const sorted = sortSessions(data.sessions, ordering);
      return { wp, name: data.name, sessions: sorted };
    });

    // Sort project groups by their top session
    projectEntries.sort((a, b) => {
      const topA = a.sessions[0];
      const topB = b.sessions[0];
      if (!topA) return 1;
      if (!topB) return -1;
      return sortSessions([topA, topB], ordering)[0] === topA ? -1 : 1;
    });

    for (const entry of projectEntries) {
      categories.push({
        category: "project",
        label: entry.name,
        items: entry.sessions,
        workspacePath: entry.wp,
      });
    }
  } else if (grouping === "date") {
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const startOfYesterday = startOfToday - 86400_000;
    const startOfPrevious7Days = startOfToday - 7 * 86400_000;

    const buckets: Record<"Today" | "Yesterday" | "Previous 7 days" | "Older", ChatSession[]> = {
      Today: [],
      Yesterday: [],
      "Previous 7 days": [],
      Older: [],
    };

    for (const s of unpinned) {
      const d = toDate(s.updated_at || s.created_at);
      const t = d ? d.getTime() : 0;
      if (t >= startOfToday) {
        buckets["Today"].push(s);
      } else if (t >= startOfYesterday) {
        buckets["Yesterday"].push(s);
      } else if (t >= startOfPrevious7Days) {
        buckets["Previous 7 days"].push(s);
      } else {
        buckets["Older"].push(s);
      }
    }

    const bucketKeys: Array<"Today" | "Yesterday" | "Previous 7 days" | "Older"> = [
      "Today",
      "Yesterday",
      "Previous 7 days",
      "Older",
    ];

    for (const key of bucketKeys) {
      const items = buckets[key];
      if (items.length > 0) {
        categories.push({
          category: "date",
          label: key,
          items: sortSessions(items, ordering),
        });
      }
    }
  } else if (grouping === "status") {
    const working: ChatSession[] = [];
    const done: ChatSession[] = [];

    for (const s of unpinned) {
      const isDone = s.is_archived === 1 || s.status === "done" || s.status === "completed";
      if (isDone) {
        done.push(s);
      } else {
        working.push(s);
      }
    }

    if (working.length > 0) {
      categories.push({
        category: "status",
        label: "Working",
        items: sortSessions(working, ordering),
      });
    }

    if (done.length > 0) {
      categories.push({
        category: "status",
        label: "Done",
        items: sortSessions(done, ordering),
      });
    }
  } else {
    // none (All sessions)
    categories.push({
      category: "none",
      label: "All sessions",
      items: sortSessions(unpinned, ordering),
    });
  }

  return categories;
}

/**
 * Backward compatibility wrapper defaulting to project grouping and updated recency.
 */
export function groupSessions(sessions: ChatSession[]): SessionCategory[] {
  return groupSessionsDynamic(sessions, "project", "updated");
}
