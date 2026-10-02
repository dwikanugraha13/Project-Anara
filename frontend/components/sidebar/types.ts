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
  const hasTz = /[Z+-]\d{2}(?::?\d{2})?$/i.test(normalized);
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

export interface SessionCategory {
  category: "pinned" | "home" | "project";
  label: string;
  /** All sessions in this category, sorted by recency (newest first). */
  items: ChatSession[];
  /** Workspace root path for project categories (used as unique key). */
  workspacePath?: string;
}

/** Preview count before "Show all N sessions" — matches preview count. */
export const SESSION_PREVIEW_COUNT = 3;

/**
 * Native session categorization by workspace:
 * 1. Pinned — all pinned sessions (regardless of workspace)
 * 2. Home — sessions WITHOUT a workspace (general chat / unattached code)
 * 3. Per-Project — sessions WITH a workspace, grouped by workspace root_path
 *
 * Each category carries a flat list sorted by recency. The renderer handles
 * the preview cap (SESSION_PREVIEW_COUNT) and "Show all N sessions" button.
 */
export function groupSessions(sessions: ChatSession[]): SessionCategory[] {
  const pinned: ChatSession[] = [];
  const homeSessions: ChatSession[] = [];
  const projectMap = new Map<string, { name: string; sessions: ChatSession[] }>();

  for (const s of sessions) {
    if (s.is_pinned === 1) {
      pinned.push(s);
      continue;
    }

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

  const byRecency = (a: ChatSession, b: ChatSession) => {
    const ta = toDate(a.updated_at)?.getTime() ?? 0;
    const tb = toDate(b.updated_at)?.getTime() ?? 0;
    return tb - ta;
  };

  pinned.sort(byRecency);
  homeSessions.sort(byRecency);

  const categories: SessionCategory[] = [];

  if (pinned.length > 0) {
    categories.push({ category: "pinned", label: "Pinned", items: pinned });
  }

  if (homeSessions.length > 0) {
    categories.push({ category: "home", label: "Home", items: homeSessions });
  }

  // Sort project groups by most recent session in each group
  const projectEntries = [...projectMap.entries()].map(([wp, data]) => {
    data.sessions.sort(byRecency);
    return { wp, ...data };
  });
  projectEntries.sort((a, b) => {
    const ta = toDate(a.sessions[0]?.updated_at)?.getTime() ?? 0;
    const tb = toDate(b.sessions[0]?.updated_at)?.getTime() ?? 0;
    return tb - ta;
  });

  for (const entry of projectEntries) {
    categories.push({
      category: "project",
      label: entry.name,
      items: entry.sessions,
      workspacePath: entry.wp,
    });
  }

  return categories;
}
