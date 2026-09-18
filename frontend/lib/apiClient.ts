/**
 * apiClient.ts — Centralized Dynamic API & WebSocket Client for Project Anara.
 * Anara Standard enterprise client architecture:
 * 1. Automatically resolves localhost, LAN IP (192.168.x.x), or domain name directly.
 * 2. Strongly-typed API client service methods (anaraApi.*) eliminating manual raw fetch calls.
 * 3. Graceful error handling, JSON parsing, and unified query string builder.
 */

export function getBackendUrl(): string {
  if (process.env.NEXT_PUBLIC_BACKEND_URL) {
    return process.env.NEXT_PUBLIC_BACKEND_URL.replace(/\/+$/, "");
  }
  const port = process.env.NEXT_PUBLIC_BACKEND_PORT || "8000";
  if (typeof window !== "undefined" && window.location) {
    const protocol = window.location.protocol === "https:" ? "https:" : "http:";
    const host = window.location.hostname || "localhost";
    return `${protocol}//${host}:${port}`;
  }
  return `http://localhost:${port}`;
}

export function getWebSocketUrl(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }
  const port = process.env.NEXT_PUBLIC_BACKEND_PORT || "8000";
  if (typeof window !== "undefined" && window.location) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname || "localhost";
    return `${protocol}//${host}:${port}/ws`;
  }
  return `ws://localhost:${port}/ws`;
}

export const BACKEND_URL = getBackendUrl();
export const WS_URL = getWebSocketUrl();

/**
 * Generic typed HTTP request dispatcher for Anara backend API.
 */
export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = getBackendUrl();
  const cleanPath = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${baseUrl}${cleanPath}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      // Ignored
    }
    throw new Error(errorDetail);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  return (await response.text()) as unknown as T;
}

/**
 * Enterprise typed API SDK for Project Anara frontend.
 */
export const anaraApi = {
  // ── Chat Sessions ────────────────────────────────────────────────────────
  sessions: {
    list: (sessionType?: string) => {
      const q = sessionType ? `?session_type=${encodeURIComponent(sessionType)}` : "";
      return apiRequest<any[]>(`/api/chat/sessions${q}`);
    },
    get: (id: number) => apiRequest<any>(`/api/chat/sessions/${id}`),
    create: (payload: { title?: string; session_type?: string; speaker_name?: string }) =>
      apiRequest<{ status: string; session: any }>("/api/chat/sessions", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    delete: (id: number) =>
      apiRequest<{ status: string }>(`/api/chat/sessions/${id}`, { method: "DELETE" }),
  },

  // ── Agent Workspace & Files ──────────────────────────────────────────────
  workspace: {
    getTree: (sessionId?: number) => {
      const q = sessionId !== undefined ? `?session_id=${sessionId}` : "";
      return apiRequest<any>(`/api/agent/workspace/tree${q}`);
    },
    getFileContent: (path: string, sessionId?: number) => {
      const q = sessionId !== undefined ? `&session_id=${sessionId}` : "";
      return apiRequest<any>(`/api/agent/workspace/file-content?path=${encodeURIComponent(path)}${q}`);
    },
    saveFile: (path: string, content: string, sessionId?: number) =>
      apiRequest<{ status: string }>("/api/agent/workspace/save-file", {
        method: "POST",
        body: JSON.stringify({ path, content, session_id: sessionId }),
      }),
    importFolder: (folderPath: string, sessionId?: number) =>
      apiRequest<{ status: string; tree?: any }>("/api/agent/pick-local-folder", {
        method: "POST",
        body: JSON.stringify({ folder_path: folderPath, session_id: sessionId }),
      }),
    upload: (formData: FormData) =>
      apiRequest<any>("/api/agent/upload", {
        method: "POST",
        body: formData,
      }),
    clear: (sessionId?: number) => {
      const q = sessionId !== undefined ? `?session_id=${sessionId}` : "";
      return apiRequest<{ status: string }>(`/api/agent/workspace${q}`, { method: "DELETE" });
    },
    getGitStatus: (sessionId?: number) => {
      const q = sessionId !== undefined ? `?session_id=${sessionId}` : "";
      return apiRequest<any>(`/api/agent/git/status${q}`);
    },
  },

  // ── AI Models & Providers ────────────────────────────────────────────────
  models: {
    getActive: () => apiRequest<{ active_model_id: string }>("/api/models/active"),
    setActive: (modelId: string) =>
      apiRequest<{ status: string }>("/api/models/active", {
        method: "POST",
        body: JSON.stringify({ model_id: modelId }),
      }),
    getHidden: (signal?: AbortSignal) =>
      apiRequest<string[]>("/api/models/hidden", { signal }),
    hide: (modelId: string) =>
      apiRequest<{ status: string }>("/api/models/hide", {
        method: "POST",
        body: JSON.stringify({ model_id: modelId }),
      }),
    unhide: (modelId: string) =>
      apiRequest<{ status: string }>(`/api/models/hide/${encodeURIComponent(modelId)}`, {
        method: "DELETE",
      }),
    getTokenSummary: (signal?: AbortSignal) =>
      apiRequest<any>("/api/tokens/summary", { signal }),
    getTokenHistory: (limit: number = 50, signal?: AbortSignal) =>
      apiRequest<any[]>(`/api/tokens/history?limit=${limit}`, { signal }),
    getAccounts: (providerId: string, signal?: AbortSignal) =>
      apiRequest<any[]>(`/api/providers/${providerId}/accounts`, { signal }),
    toggleAccount: (providerId: string, accountId: number) =>
      apiRequest<{ status: string }>(`/api/providers/${providerId}/accounts/${accountId}/toggle`, {
        method: "POST",
      }),
    deleteAccount: (providerId: string, accountId: number) =>
      apiRequest<{ status: string }>(`/api/providers/${providerId}/accounts/${accountId}`, {
        method: "DELETE",
      }),
    checkCustom: (payload: any) =>
      apiRequest<any>("/api/providers/custom/check", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    addCustom: (payload: any) =>
      apiRequest<any>("/api/providers/custom", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    toggleCustom: (providerId: string) =>
      apiRequest<{ status: string }>(`/api/providers/custom/${providerId}/toggle`, {
        method: "POST",
      }),
    deleteCustom: (providerId: string) =>
      apiRequest<{ status: string }>(`/api/providers/custom/${providerId}`, {
        method: "DELETE",
      }),
    connectProvider: (providerId: string, payload: any) =>
      apiRequest<any>(`/api/providers/${providerId}/connect`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    disconnectProvider: (providerId: string) =>
      apiRequest<any>(`/api/providers/${providerId}/disconnect`, {
        method: "POST",
      }),
    getAuthorizeUrl: (providerId: string) =>
      apiRequest<{ authorize_url: string; session_id: string }>(`/api/auth/${providerId}/authorize-url`),
    exchangeToken: (providerId: string, payload: any) =>
      apiRequest<any>(`/api/auth/${providerId}/exchange`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  // ── Integrations ─────────────────────────────────────────────────────────
  integrations: {
    getAllStatus: () => apiRequest<any>("/api/integrations/status"),
    getWhatsAppStatus: () => apiRequest<any>("/api/integrations/whatsapp/status"),
    getWhatsAppConfig: () => apiRequest<any>("/api/integrations/whatsapp/config"),
    getWhatsAppQr: () => apiRequest<any>("/api/integrations/whatsapp/qr"),
    saveWhatsAppConfig: (config: any) =>
      apiRequest<any>("/api/integrations/whatsapp/config", {
        method: "POST",
        body: JSON.stringify(config),
      }),
    logoutWhatsApp: () =>
      apiRequest<any>("/api/integrations/whatsapp/logout", { method: "POST" }),
    getTelegramStatus: () => apiRequest<any>("/api/integrations/telegram/status"),
    saveTelegramConfig: (config: any) =>
      apiRequest<any>("/api/integrations/telegram/config", {
        method: "POST",
        body: JSON.stringify(config),
      }),
    getDiscordStatus: () => apiRequest<any>("/api/integrations/discord/status"),
    saveDiscordConfig: (config: any) =>
      apiRequest<any>("/api/integrations/discord/config", {
        method: "POST",
        body: JSON.stringify(config),
      }),
    getSlackStatus: () => apiRequest<any>("/api/integrations/slack/status"),
    saveSlackConfig: (config: any) =>
      apiRequest<any>("/api/integrations/slack/config", {
        method: "POST",
        body: JSON.stringify(config),
      }),
    getGoogleStatus: () => apiRequest<any>("/api/integrations/google/status"),
    saveGoogleConfig: (config: any) =>
      apiRequest<any>("/api/integrations/google/config", {
        method: "POST",
        body: JSON.stringify(config),
      }),
    disconnectGoogle: () =>
      apiRequest<any>("/api/integrations/google/disconnect", { method: "POST" }),
    getContacts: () => apiRequest<any[]>("/api/integrations/contacts"),
    saveContact: (contact: any) =>
      apiRequest<any>("/api/integrations/contacts", {
        method: "POST",
        body: JSON.stringify(contact),
      }),
    deleteContact: (id: number) =>
      apiRequest<{ status: string }>(`/api/integrations/contacts/${id}`, { method: "DELETE" }),
  },

  // ── Brain & Knowledge ────────────────────────────────────────────────────
  brain: {
    getOverview: () => apiRequest<any>("/api/brain/overview"),
    getMemories: () => apiRequest<any[]>("/api/brain/memories"),
    saveMemory: (payload: any) =>
      apiRequest<any>("/api/brain/memories", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    deleteMemory: (id: number) =>
      apiRequest<{ status: string }>(`/api/brain/memories/${id}`, { method: "DELETE" }),
    getTodos: () => apiRequest<any[]>("/api/brain/notes"),
    saveTodo: (payload: any) =>
      apiRequest<any>("/api/brain/notes", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    toggleTodo: (id: number) =>
      apiRequest<any>(`/api/brain/notes/${id}/toggle`, { method: "POST" }),
    deleteTodo: (id: number) =>
      apiRequest<{ status: string }>(`/api/brain/notes/${id}`, { method: "DELETE" }),
    getProjects: () => apiRequest<any[]>("/api/brain/projects"),
    saveProject: (payload: any) =>
      apiRequest<any>("/api/brain/projects", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    deleteProject: (id: number) =>
      apiRequest<{ status: string }>(`/api/brain/projects/${id}`, { method: "DELETE" }),
    getSpeakers: () => apiRequest<any[]>("/api/brain/speakers"),
    saveSpeaker: (payload: any) =>
      apiRequest<any>("/api/brain/speakers", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    updateSpeaker: (speakerName: string, payload: any) =>
      apiRequest<any>(`/api/brain/speakers/${encodeURIComponent(speakerName)}`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    calibrateSpeaker: (speakerName: string, payload: any) =>
      apiRequest<any>(`/api/brain/speakers/${encodeURIComponent(speakerName)}/calibrate`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    getConversations: (limit: number = 60) =>
      apiRequest<any[]>(`/api/brain/conversations?limit=${limit}`),
    deleteConversation: (id: number) =>
      apiRequest<{ status: string }>(`/api/brain/conversations/${id}`, { method: "DELETE" }),
    clearConversations: () =>
      apiRequest<{ status: string }>("/api/brain/conversations", { method: "DELETE" }),
    getAnimations: () => apiRequest<any[]>("/api/brain/animations"),
    getFileMemory: () => apiRequest<any>("/api/brain/file-memory"),
    updateFileMemory: (payload: { file_type: string; content: string }) =>
      apiRequest<any>("/api/brain/file-memory", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    getSkillsV2: (status?: string) => {
      const q = status ? `?status=${encodeURIComponent(status)}` : "";
      return apiRequest<any[]>(`/api/brain/skills/v2${q}`);
    },
    approveSkillV2: (slug: string) =>
      apiRequest<{ status: string }>(`/api/brain/skills/v2/${slug}/approve`, { method: "POST" }),
    deleteSkillV2: (slug: string) =>
      apiRequest<{ status: string }>(`/api/brain/skills/v2/${slug}`, { method: "DELETE" }),
    getSkillHubSources: () => apiRequest<any[]>("/api/brain/skills/hub/sources"),
    searchSkillHub: (query: string, source: string, limit: number = 40) =>
      apiRequest<any[]>(`/api/brain/skills/hub/search?q=${encodeURIComponent(query)}&source=${encodeURIComponent(source)}&limit=${limit}`),
    installSkillHub: (payload: any) =>
      apiRequest<any>("/api/brain/skills/hub/install", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    getTools: () => apiRequest<any[]>("/api/agent/tools"),
    getToolsets: () => apiRequest<any[]>("/api/agent/toolsets"),
    semanticSearch: (query: string, speakerName?: string) => {
      const spParam = speakerName ? `&speaker_name=${encodeURIComponent(speakerName)}` : "";
      return apiRequest<any[]>(`/api/brain/semantic-search?query=${encodeURIComponent(query)}${spParam}`);
    },
  },

  // ── Soul & Identity ──────────────────────────────────────────────────────
  soul: {
    get: () => apiRequest<any>("/api/agent/soul"),
    update: (content: string) =>
      apiRequest<any>("/api/agent/soul", {
        method: "POST",
        body: JSON.stringify({ content }),
      }),
  },

  // ── Terminal & Checkpoint ────────────────────────────────────────────────
  terminal: {
    execute: (command: string, sessionId?: number, workdir?: string) =>
      apiRequest<any>("/api/agent/terminal/execute", {
        method: "POST",
        body: JSON.stringify({ command, session_id: sessionId, workdir }),
      }),
    stream: (command: string, signal?: AbortSignal, sessionId?: number, workdir?: string) => {
      const baseUrl = getBackendUrl();
      return fetch(`${baseUrl}/api/agent/terminal/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, session_id: sessionId, workdir }),
        signal,
      });
    },
  },
  checkpoint: {
    revert: (checkpointId: string, sessionId?: number) =>
      apiRequest<any>("/api/agent/checkpoint/revert", {
        method: "POST",
        body: JSON.stringify({ checkpoint_id: checkpointId, session_id: sessionId }),
      }),
  },

  // ── Remote Gateway Authentication ─────────────────────────────────────────
  gateway: {
    getStatus: () =>
      apiRequest<{
        status: string;
        is_local: boolean;
        auth_required: boolean;
        authenticated: boolean;
        client_ip: string;
      }>("/api/gateway/status"),
    login: (password: string) =>
      apiRequest<{ status: string; token: string; message: string }>("/api/gateway/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      }),
    logout: () => apiRequest<{ status: string }>("/api/gateway/logout", { method: "POST" }),
  },
};
