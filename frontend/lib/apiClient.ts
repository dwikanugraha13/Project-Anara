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
  if (typeof window !== "undefined" && window.location) {
    const protocol = window.location.protocol === "https:" ? "https:" : "http:";
    const host = window.location.hostname || "localhost";

    // Comprehensive RFC 1918, Carrier-Grade NAT (Tailscale 100.64.0.0/10), Loopback, and mDNS detection
    const isLocal =
      host === "localhost" ||
      host === "127.0.0.1" ||
      host === "::1" ||
      host === "[::1]" ||
      host.endsWith(".local") ||
      host.startsWith("192.168.") ||
      host.startsWith("10.") ||
      /^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(host) ||
      /^100\.(6[4-9]|[7-9][0-9]|1[0-1][0-9]|12[0-7])\./.test(host);

    const currentPort = window.location.port;
    const isWebDevPort =
      /^300\d$/.test(currentPort) ||
      currentPort === "5173" ||
      currentPort === "4173" ||
      currentPort === "8080";
    const configuredPort = process.env.NEXT_PUBLIC_BACKEND_PORT;

    let port = currentPort;
    if (isLocal) {
      port = configuredPort || (isWebDevPort ? "8000" : currentPort);
    }
    return port ? `${protocol}//${host}:${port}` : `${protocol}//${host}`;
  }
  const defaultPort = process.env.NEXT_PUBLIC_BACKEND_PORT || "8000";
  return `http://localhost:${defaultPort}`;
}

export function getWebSocketUrl(): string {
  let wsUrl = "";
  if (process.env.NEXT_PUBLIC_WS_URL) {
    wsUrl = process.env.NEXT_PUBLIC_WS_URL;
  } else if (typeof window !== "undefined" && window.location) {
    const backendUrl = getBackendUrl();
    const wsProtocol = backendUrl.startsWith("https:") ? "wss:" : "ws:";
    wsUrl = `${backendUrl.replace(/^https?:/, wsProtocol)}/ws`;
  } else {
    const defaultPort = process.env.NEXT_PUBLIC_BACKEND_PORT || "8000";
    wsUrl = `ws://localhost:${defaultPort}/ws`;
  }

  // Attach token from localStorage for remote gateway authentication
  if (typeof window !== "undefined") {
    try {
      const token = localStorage.getItem("anara_gateway_token");
      if (token && !wsUrl.includes("token=")) {
        const delimiter = wsUrl.includes("?") ? "&" : "?";
        wsUrl = `${wsUrl}${delimiter}token=${encodeURIComponent(token)}`;
      }
    } catch {}
  }

  return wsUrl;
}

export const BACKEND_URL =
  typeof window !== "undefined"
    ? getBackendUrl()
    : process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/+$/, "") ||
      `http://localhost:${process.env.NEXT_PUBLIC_BACKEND_PORT || "8000"}`;

export const WS_URL =
  typeof window !== "undefined"
    ? getWebSocketUrl()
    : process.env.NEXT_PUBLIC_WS_URL ||
      `ws://localhost:${process.env.NEXT_PUBLIC_BACKEND_PORT || "8000"}/ws`;

export interface ApiRequestOptions extends RequestInit {
  timeout?: number;
  retry?: number;
  retryDelay?: number;
  skipAuth?: boolean;
}

/**
 * Generic typed HTTP request dispatcher for Anara backend API.
 * Features:
 * - Dynamic URL resolution (localhost, LAN IP, remote gateway)
 * - Request timeouts via AbortSignal.timeout & composite signals
 * - Automatic gateway bearer token injection
 * - Resilient exponential backoff retry for network drops & transient 502/503/504 errors
 * - Graceful 204 No Content & JSON parsing
 */
export async function apiRequest<T = any>(
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const baseUrl = getBackendUrl();
  const cleanPath = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${baseUrl}${cleanPath}`;

  const method = (options.method || "GET").toUpperCase();
  const isIdempotent = method === "GET" || method === "HEAD" || method === "OPTIONS";
  const maxRetries = options.retry !== undefined ? options.retry : isIdempotent ? 2 : 0;
  const baseDelay = options.retryDelay ?? 300;
  const timeoutMs =
    options.timeout ??
    (endpoint.includes("/workspace/") || endpoint.includes("/terminal/") ? 60000 : 15000);

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  // Attach gateway bearer token when available
  if (!options.skipAuth && typeof window !== "undefined") {
    try {
      const token = localStorage.getItem("anara_gateway_token");
      if (token && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
      }
    } catch {}
  }

  let attempt = 0;
  while (true) {
    let timeoutSignal: AbortSignal | undefined;
    let timerId: any = null;

    if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
      timeoutSignal = AbortSignal.timeout(timeoutMs);
    } else {
      const controller = new AbortController();
      timerId = setTimeout(
        () => controller.abort(new Error(`Request timeout after ${timeoutMs}ms`)),
        timeoutMs
      );
      timeoutSignal = controller.signal;
    }

    let effectiveSignal: AbortSignal | undefined;
    if (options.signal && timeoutSignal) {
      if (typeof (AbortSignal as any).any === "function") {
        effectiveSignal = (AbortSignal as any).any([options.signal, timeoutSignal]);
      } else {
        const composite = new AbortController();
        const onAbort = () => composite.abort(options.signal?.reason || timeoutSignal?.reason);
        if (options.signal.aborted) {
          composite.abort(options.signal.reason);
        } else if (timeoutSignal.aborted) {
          composite.abort(timeoutSignal.reason);
        } else {
          options.signal.addEventListener("abort", onAbort, { once: true });
          timeoutSignal.addEventListener("abort", onAbort, { once: true });
        }
        effectiveSignal = composite.signal;
      }
    } else {
      effectiveSignal = options.signal || timeoutSignal;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: effectiveSignal,
        credentials: options.credentials ?? "same-origin",
      });

      if (timerId) clearTimeout(timerId);

      // Retry on transient 502/503/504 gateway errors if retries remain
      if (
        (response.status === 502 || response.status === 503 || response.status === 504) &&
        attempt < maxRetries
      ) {
        attempt++;
        const backoff = baseDelay * Math.pow(2, attempt - 1) + Math.random() * 50;
        await new Promise((r) => setTimeout(r, backoff));
        continue;
      }

      if (!response.ok) {
        if (response.status === 401 && typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("anara_gateway_unauthorized"));
        }
        let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errJson = await response.json();
          errorDetail = errJson.detail || errJson.message || errorDetail;
        } catch {
          // Ignored
        }
        throw new Error(errorDetail);
      }

      if (response.status === 204) {
        return {} as T;
      }

      const text = await response.text();
      if (!text || !text.trim()) {
        return {} as T;
      }

      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        try {
          return JSON.parse(text) as T;
        } catch {
          return text as unknown as T;
        }
      }
      return text as unknown as T;
    } catch (err: any) {
      if (timerId) clearTimeout(timerId);

      // If explicitly aborted by caller, re-throw immediately without retrying
      if (options.signal?.aborted) {
        throw err;
      }

      // Check if network error (e.g. TypeError: Failed to fetch / socket drop)
      const isNetworkDrop =
        err instanceof TypeError ||
        err?.name === "TypeError" ||
        (err?.message &&
          /failed to fetch|network|load failed|econnrefused|econnreset/i.test(err.message));

      if (isNetworkDrop && attempt < maxRetries) {
        attempt++;
        const backoff = baseDelay * Math.pow(2, attempt - 1) + Math.random() * 50;
        await new Promise((r) => setTimeout(r, backoff));
        continue;
      }

      throw err;
    }
  }
}

/**
 * Enterprise typed API SDK for Project Anara frontend.
 */
export const anaraApi = {
  // ── Chat Sessions ────────────────────────────────────────────────────────
  sessions: {
    list: (
      optsOrType?:
        | string
        | { sessionType?: string; speaker?: string; includeArchived?: boolean }
    ) => {
      let q = "";
      if (typeof optsOrType === "string") {
        q = optsOrType ? `?session_type=${encodeURIComponent(optsOrType)}` : "";
      } else if (optsOrType) {
        const params = new URLSearchParams();
        if (optsOrType.sessionType) params.set("session_type", optsOrType.sessionType);
        if (optsOrType.speaker) params.set("speaker", optsOrType.speaker);
        if (optsOrType.includeArchived) params.set("include_archived", "true");
        const qs = params.toString();
        q = qs ? `?${qs}` : "";
      }
      return apiRequest<any[]>(`/api/chat/sessions${q}`);
    },
    get: (id: number | string) => apiRequest<any>(`/api/chat/sessions/${id}`),
    create: (
      payloadOrTitle: { title?: string; session_type?: string; speaker_name?: string } | string,
      sessionType?: string
    ) => {
      const payload =
        typeof payloadOrTitle === "string"
          ? { title: payloadOrTitle, session_type: sessionType }
          : payloadOrTitle;
      return apiRequest<{ status: string; session: any }>("/api/chat/sessions", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    patch: (id: number | string, payload: Record<string, unknown>) =>
      apiRequest<{ status: string; session?: any }>(`/api/chat/sessions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    update: (id: number | string, payload: Record<string, unknown>) =>
      apiRequest<{ status: string; session?: any }>(`/api/chat/sessions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    fork: (id: number | string) =>
      apiRequest<{ status: string; session: any }>(`/api/chat/sessions/${id}/fork`, {
        method: "POST",
      }),
    delete: (id: number | string) =>
      apiRequest<{ status: string; session_id?: string }>(`/api/chat/sessions/${id}`, {
        method: "DELETE",
      }),
    clearMessages: (id: number | string) =>
      apiRequest<{ status: string; removed: number; session_id: string }>(
        `/api/chat/sessions/${id}/messages`,
        { method: "DELETE" }
      ),
    bulkDelete: (archivedOnly: boolean = true, keepPinned: boolean = true) =>
      apiRequest<{ status: string; deleted_count: number }>(
        `/api/chat/sessions?archived_only=${archivedOnly}&keep_pinned=${keepPinned}`,
        { method: "DELETE" }
      ),
    getPlan: (id: number | string) =>
      apiRequest<{ status: string; session_id: string; plan: any }>(
        `/api/chat/sessions/${id}/plan`
      ),
    savePlan: (
      id: number | string,
      payload: {
        title: string;
        summary: string;
        steps: string[];
        tech_stack?: string[];
        estimated_effort?: string;
      }
    ) =>
      apiRequest<{ status: string; plan: any }>(`/api/chat/sessions/${id}/plan`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    clearPlan: (id: number | string) =>
      apiRequest<{ status: string; session_id: string }>(`/api/chat/sessions/${id}/plan`, {
        method: "DELETE",
      }),
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
    uploadFolder: (formData: FormData, sessionId?: number) => {
      const q = sessionId !== undefined ? `?session_id=${sessionId}` : "";
      return apiRequest<any>(`/api/agent/upload-folder${q}`, {
        method: "POST",
        body: formData,
      });
    },
    initEmpty: (sessionId?: number) =>
      apiRequest<{ status: string; workspace_path: string }>("/api/agent/init-empty-workspace", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
      }),
    downloadArtifactUrl: (filename: string) =>
      `${getBackendUrl()}/api/agent/artifacts/download/${encodeURIComponent(filename)}`,
    deleteFile: (path: string, sessionId?: number) => {
      const q = sessionId !== undefined ? `&session_id=${sessionId}` : "";
      return apiRequest<{ status: string }>(`/api/agent/workspace/file?path=${encodeURIComponent(path)}${q}`, {
        method: "DELETE",
      });
    },
    clear: (sessionId?: number) => {
      const q = sessionId !== undefined ? `?session_id=${sessionId}` : "";
      return apiRequest<{ status: string }>(`/api/agent/workspace${q}`, { method: "DELETE" });
    },
    getGitStatus: (sessionId?: number) => {
      const q = sessionId !== undefined ? `?session_id=${sessionId}` : "";
      return apiRequest<any>(`/api/agent/git/status${q}`);
    },
    initGit: (sessionId?: number) =>
      apiRequest<any>("/api/agent/git/init", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
      }),
    rollbackGit: (targetCommit: string, sessionId?: number) =>
      apiRequest<any>("/api/agent/git/rollback", {
        method: "POST",
        body: JSON.stringify({ target_commit: targetCommit, session_id: sessionId }),
      }),
    getSkills: () => apiRequest<any[]>("/api/agent/skills"),
    createSkill: (payload: any) =>
      apiRequest<any>("/api/agent/skills", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    toggleSkill: (skillId: number | string) =>
      apiRequest<any>(`/api/agent/skills/${skillId}/toggle`, { method: "PATCH" }),
    deleteSkill: (skillId: number | string) =>
      apiRequest<{ status: string }>(`/api/agent/skills/${skillId}`, { method: "DELETE" }),
    getSubagentTasks: (sessionId?: number) => {
      const q = sessionId !== undefined ? `?session_id=${sessionId}` : "";
      return apiRequest<any[]>(`/api/agent/subagent/tasks${q}`);
    },
    getAutonomousTasks: () => apiRequest<any[]>("/api/agent/autonomous/tasks"),
    createAutonomousTask: (payload: any) =>
      apiRequest<any>("/api/agent/autonomous/tasks", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    deleteAutonomousTask: (taskId: string | number) =>
      apiRequest<{ status: string }>(`/api/agent/autonomous/tasks/${taskId}`, {
        method: "DELETE",
      }),
    triggerAutonomousTask: (taskId: string | number) =>
      apiRequest<{ status: string; result?: any }>(`/api/agent/autonomous/tasks/${taskId}/trigger`, {
        method: "POST",
      }),
    pauseAutonomousTask: (taskId: string | number) =>
      apiRequest<{ status: string }>(`/api/agent/autonomous/tasks/${taskId}/pause`, {
        method: "POST",
      }),
    resumeAutonomousTask: (taskId: string | number) =>
      apiRequest<{ status: string }>(`/api/agent/autonomous/tasks/${taskId}/resume`, {
        method: "POST",
      }),
  },

  // ── AI Models & Providers ────────────────────────────────────────────────
  models: {
    list: (refresh: boolean = false, signal?: AbortSignal) =>
      apiRequest<{ active_model_id: string; models: any[] }>(
        `/api/models${refresh ? "?refresh=true" : ""}`,
        { signal }
      ),
    getActive: () => apiRequest<{ active_model_id: string }>("/api/models/active"),
    setActive: (modelId: string) =>
      apiRequest<{ status: string }>("/api/models/active", {
        method: "POST",
        body: JSON.stringify({ model_id: modelId }),
      }),
    getSupported: (mode?: "voice" | "text" | "all", signal?: AbortSignal) =>
      apiRequest<{ mode: string; count: number; models: any[] }>(
        `/api/models/supported${mode ? `?mode=${mode}` : ""}`,
        { signal }
      ),
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
    restoreAllHidden: (provider?: string) => {
      const q = provider ? `?provider=${encodeURIComponent(provider)}` : "";
      return apiRequest<{ status: string }>(`/api/models/hidden/restore-all${q}`, {
        method: "POST",
      });
    },
    getTokenSummary: (signal?: AbortSignal) =>
      apiRequest<any>("/api/tokens/summary", { signal }),
    getTokenHistory: (limit: number = 50, signal?: AbortSignal) =>
      apiRequest<any[]>(`/api/tokens/history?limit=${limit}`, { signal }),
    getProviders: (refresh: boolean = false, signal?: AbortSignal) =>
      apiRequest<{ providers: any[]; active_model_id: string }>(
        `/api/providers${refresh ? "?refresh=true" : ""}`,
        { signal }
      ),
    getAccounts: (providerId: string, signal?: AbortSignal) =>
      apiRequest<any[]>(`/api/providers/${providerId}/accounts`, { signal }),
    addAccount: (providerName: string, accountLabel: string, apiKey: string) =>
      apiRequest<any>(`/api/providers/${providerName}/accounts`, {
        method: "POST",
        body: JSON.stringify({ account_label: accountLabel, api_key: apiKey }),
      }),
    toggleAccount: (providerId: string, accountId: number) =>
      apiRequest<{ status: string }>(`/api/providers/${providerId}/accounts/${accountId}/toggle`, {
        method: "PATCH",
      }),
    deleteAccount: (providerId: string, accountId: number) =>
      apiRequest<{ status: string }>(`/api/providers/${providerId}/accounts/${accountId}`, {
        method: "DELETE",
      }),
    refreshProvider: (providerName: string) =>
      apiRequest<any>(`/api/providers/${providerName}/refresh`, {
        method: "POST",
      }),
    getCustom: () => apiRequest<any[]>("/api/providers/custom"),
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
        method: "PATCH",
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
    saveKeys: (keys: Record<string, string>) =>
      apiRequest<{ status: string }>("/api/models/keys", {
        method: "POST",
        body: JSON.stringify(keys),
      }),
    getAuthorizeUrl: (providerId: string) =>
      apiRequest<{ authorize_url: string; session_id: string }>(`/api/auth/${providerId}/authorize-url`),
    getAuthStatus: (providerId: string) =>
      apiRequest<any>(`/api/auth/${providerId}/status`),
    exchangeToken: (providerId: string, payload: any) =>
      apiRequest<any>(`/api/auth/${providerId}/exchange`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    getChatDiagnostics: () => apiRequest<any>("/api/diagnostics/chat"),
    getActiveModelDiagnostics: () => apiRequest<any>("/api/diagnostics/active-model"),
    testModelDiagnostics: (modelId: string, prompt?: string) =>
      apiRequest<any>("/api/diagnostics/test-model", {
        method: "POST",
        body: JSON.stringify({ model_id: modelId, prompt }),
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
    getWhatsAppMessages: () => apiRequest<any[]>("/api/integrations/whatsapp/messages"),
    sendWhatsAppMessage: (payload: { to: string; message: string }) =>
      apiRequest<any>("/api/integrations/whatsapp/send", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    getTelegramStatus: () => apiRequest<any>("/api/integrations/telegram/status"),
    saveTelegramConfig: (config: any) =>
      apiRequest<any>("/api/integrations/telegram/config", {
        method: "POST",
        body: JSON.stringify(config),
      }),
    getTelegramMessages: () => apiRequest<any[]>("/api/integrations/telegram/messages"),
    sendTelegramMessage: (payload: { chat_id?: string | number; message: string }) =>
      apiRequest<any>("/api/integrations/telegram/send", {
        method: "POST",
        body: JSON.stringify(payload),
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
    getSystemStatus: () => apiRequest<any>("/api/brain/system-status"),
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
      apiRequest<any>(`/api/brain/notes/${id}/toggle`, { method: "PATCH" }),
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
    deleteSpeaker: (speakerName: string) =>
      apiRequest<{ status: string }>(`/api/brain/speakers/${encodeURIComponent(speakerName)}`, {
        method: "DELETE",
      }),
    getConversations: (limit: number = 60) =>
      apiRequest<any[]>(`/api/brain/conversations?limit=${limit}`),
    deleteConversation: (id: number) =>
      apiRequest<{ status: string }>(`/api/brain/conversations/${id}`, { method: "DELETE" }),
    clearConversations: () =>
      apiRequest<{ status: string }>("/api/brain/conversations", { method: "DELETE" }),
    getAnimations: () => apiRequest<any[]>("/api/brain/animations"),
    saveAnimation: (payload: any) =>
      apiRequest<any>("/api/brain/animations", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    deleteAnimation: (animationName: string) =>
      apiRequest<{ status: string }>(`/api/brain/animations/${encodeURIComponent(animationName)}`, {
        method: "DELETE",
      }),
    getProxyImageUrl: (url: string) =>
      `${getBackendUrl()}/api/proxy-image?url=${encodeURIComponent(url)}`,
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
    toggleSkillV2: (slug: string, enabled?: boolean) =>
      apiRequest<{ status: string; skill: any }>(`/api/brain/skills/v2/${slug}/toggle`, {
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      }),
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
    getTunnelStatus: () => apiRequest<any>("/api/gateway/tunnel"),
    startTunnel: () => apiRequest<any>("/api/gateway/tunnel/start", { method: "POST" }),
    stopTunnel: () => apiRequest<any>("/api/gateway/tunnel/stop", { method: "POST" }),
  },

  // ── Telemetry & Observability ─────────────────────────────────────────────
  telemetry: {
    getStreamUrl: (sessionId: number | string) =>
      `${getBackendUrl()}/api/telemetry/stream/${sessionId}`,
    getWebSocketUrl: (sessionId: number | string) => {
      const baseWs = getWebSocketUrl();
      return baseWs.replace(/\/ws(\?|$)/, `/ws/telemetry/${sessionId}$1`);
    },
  },
};
