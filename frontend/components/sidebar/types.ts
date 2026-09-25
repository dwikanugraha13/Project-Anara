export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export const DEFAULT_SIDEBAR_WIDTH = 380;
export const MIN_SIDEBAR_WIDTH = 380;
export const MAX_SIDEBAR_WIDTH = 1050;

export interface ChatSession {
  id: number;
  title: string | null;
  speaker_name: string | null;
  session_type?: "chat" | "code";
  message_count: number;
  is_archived: number;
  is_pinned: number;
  created_at: string;
  updated_at: string;
  last_user_text?: string | null;
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
  children?: WorkspaceNode[];
}

export interface WorkspaceTreeData {
  workspace_name: string;
  is_custom_folder: boolean;
  root_path: string;
  total_files: number;
  files: WorkspaceFile[];
  nested_tree?: WorkspaceNode[];
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
  const d = new Date(iso.includes("Z") || iso.includes("+") ? iso : iso + "Z");
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatFullDateTime(iso: string): string {
  const d = toDate(iso);
  if (!d) return "";
  const dateStr = d.toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const timeStr = d.toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${dateStr} • ${timeStr} WIB`;
}

export function groupSessions(sessions: ChatSession[]) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfYesterday = startOfToday - 86400_000;
  const sevenDaysAgo = startOfToday - 7 * 86400_000;

  const buckets: { label: string; items: ChatSession[] }[] = [
    { label: "Pinned", items: [] },
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Last 7 days", items: [] },
    { label: "Older", items: [] },
  ];

  for (const s of sessions) {
    if (s.is_pinned === 1) {
      buckets[0].items.push(s);
      continue;
    }
    const t = toDate(s.updated_at)?.getTime() ?? 0;
    if (t >= startOfToday) buckets[1].items.push(s);
    else if (t >= startOfYesterday) buckets[2].items.push(s);
    else if (t >= sevenDaysAgo) buckets[3].items.push(s);
    else buckets[4].items.push(s);
  }

  return buckets.filter((b) => b.items.length > 0);
}
