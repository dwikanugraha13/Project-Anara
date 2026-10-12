"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { BACKEND_URL } from "../types";

export interface ConnectorItem {
  id: string;
  name: string;
  slug: string;
  description: string;
  source?: string;
  transport_type: "stdio" | "http" | "sse" | "gateway";
  transport_url?: string;
  auth_type: string;
  category: string;
  installed?: boolean;
  connected?: boolean;
  tools_count?: number;
  post_install?: string;
}

export interface McpServerConfig {
  name: string;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  transport: "stdio" | "http" | "sse";
  enabled: boolean;
  connected: boolean;
  tools_count: number;
  tools?: string[];
}

export type ConnectorSegment = "all" | "connected" | "local" | "available";

export interface DraftValue {
  id: number;
  value: string;
}

export interface DraftPair {
  id: number;
  key: string;
  value: string;
}

export type CustomMcpTransport = "stdio" | "http";
export type CustomMcpAuth = "none" | "oauth" | "bearer";

export interface CustomMcpDraft {
  pasteSnippet: string;
  name: string;
  transport: CustomMcpTransport;
  command: string;
  args: DraftValue[];
  env: DraftPair[];
  passthrough: DraftValue[];
  cwd: string;
  url: string;
  headers: DraftPair[];
  auth: CustomMcpAuth;
  bearer: string;
}

let rowCounter = 0;
const nextRowId = (): number => ++rowCounter;
const createDraftValue = (val = ""): DraftValue => ({ id: nextRowId(), value: val });
const createDraftPair = (k = "", v = ""): DraftPair => ({ id: nextRowId(), key: k, value: v });

const DEFAULT_MCP_DRAFT: CustomMcpDraft = {
  pasteSnippet: "",
  name: "",
  transport: "stdio",
  command: "",
  args: [],
  env: [],
  passthrough: [],
  cwd: "",
  url: "",
  headers: [],
  auth: "none",
  bearer: "",
};

function cleanupName(base: string): string {
  const stripped = base
    .replace(/\.(cjs|js|mjs|py|ts)$/i, "")
    .replace(/^(mcp-server-|server-|mcp-)/, "")
    .replace(/(-mcp-server|-mcp|-server)$/, "");
  return stripped || base;
}

function nameFromUrl(raw: string): string {
  try {
    const labels = new URL(raw).hostname.split(".").filter(Boolean);
    while (labels.length > 1 && ["api", "mcp", "www"].includes(labels[0])) {
      labels.shift();
    }
    return cleanupName(labels[0] || "server");
  } catch {
    return "server";
  }
}

function tokenizeShell(line: string): string[] | null {
  const tokens: string[] = [];
  let current = "";
  let sawQuote = false;
  let quote: '"' | "'" | null = null;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quote) {
      if (ch === quote) {
        quote = null;
      } else if (ch === "\\" && quote === '"' && i + 1 < line.length) {
        current += line[++i];
      } else {
        current += ch;
      }
    } else if (ch === '"' || ch === "'") {
      quote = ch;
      sawQuote = true;
    } else if (/\s/.test(ch)) {
      if (current || sawQuote) {
        tokens.push(current);
        current = "";
        sawQuote = false;
      }
    } else {
      current += ch;
    }
  }

  if (quote) return null;
  if (current || sawQuote) tokens.push(current);
  return tokens;
}

function inferCommandName(command: string, args: string[]): string {
  if (command === "docker") {
    let i = args[0] === "run" ? 1 : 0;
    for (; i < args.length; i++) {
      const arg = args[i];
      if (arg.startsWith("-")) continue;
      return cleanupName((arg.split("/").pop() ?? arg).split(":")[0]);
    }
    return "docker";
  }
  if (command === "node") {
    const script = args.find((a) => !a.startsWith("-"));
    return script ? cleanupName(script.split(/[/\\]/).pop() ?? script) : "node";
  }
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith("-")) {
      if (["--from", "--package", "-p"].includes(arg)) i++;
      continue;
    }
    let bare = arg.split("==")[0];
    const at = bare.lastIndexOf("@");
    if (at > 0) bare = bare.slice(0, at);
    return cleanupName(bare.split("/").pop() ?? bare);
  }
  return cleanupName(command);
}

function draftFromRawEntry(name: string, raw: Record<string, unknown>, prev: CustomMcpDraft): CustomMcpDraft {
  const url = typeof raw.url === "string" ? raw.url : "";
  const named = name && name !== "server" ? name : prev.name || "server";

  if (url) {
    const headersList: DraftPair[] = [];
    if (raw.headers && typeof raw.headers === "object") {
      for (const [k, v] of Object.entries(raw.headers as Record<string, unknown>)) {
        headersList.push(createDraftPair(k, String(v)));
      }
    }
    const authVal: CustomMcpAuth =
      raw.auth === "oauth" ? "oauth" : raw.auth === "bearer" ? "bearer" : "none";
    return {
      ...DEFAULT_MCP_DRAFT,
      name: named !== "server" ? named : nameFromUrl(url),
      transport: "http",
      url,
      headers: headersList,
      auth: authVal,
      bearer: prev.bearer,
    };
  }

  const cmd = typeof raw.command === "string" ? raw.command : "";
  const argsList: DraftValue[] = Array.isArray(raw.args)
    ? raw.args.map((a: unknown) => createDraftValue(String(a)))
    : [];
  const envPairs: DraftPair[] = [];
  const passthroughList: DraftValue[] = [];

  if (raw.env && typeof raw.env === "object") {
    for (const [k, v] of Object.entries(raw.env as Record<string, unknown>)) {
      const valStr = String(v);
      if (valStr === `\${${k}}`) {
        passthroughList.push(createDraftValue(k));
      } else {
        envPairs.push(createDraftPair(k, valStr));
      }
    }
  }

  const cwdStr = typeof raw.cwd === "string" ? raw.cwd : "";

  return {
    ...DEFAULT_MCP_DRAFT,
    name:
      named !== "server"
        ? named
        : cmd
        ? inferCommandName(
            cmd,
            argsList.map((a) => a.value)
          )
        : "server",
    transport: "stdio",
    command: cmd,
    args: argsList,
    env: envPairs,
    passthrough: passthroughList,
    cwd: cwdStr,
  };
}

function parseMcpImportSnippet(text: string, prev: CustomMcpDraft): CustomMcpDraft | null {
  const trimmed = text.trim();
  if (!trimmed) return null;

  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const wrapper = parsed.mcpServers ?? parsed.mcp_servers ?? parsed;
      if (typeof wrapper === "object" && !Array.isArray(wrapper)) {
        if ("command" in wrapper || "url" in wrapper) {
          return draftFromRawEntry("server", wrapper as Record<string, unknown>, prev);
        }
        const entries = Object.entries(wrapper).filter(
          ([k]) => !["mcpServers", "mcp_servers"].includes(k)
        );
        if (entries.length > 0) {
          const [name, config] = entries[0];
          if (config && typeof config === "object" && !Array.isArray(config)) {
            return draftFromRawEntry(name, config as Record<string, unknown>, prev);
          }
        }
      }
    }
  } catch {
    // Continue
  }

  if (/^https?:\/\/\S+$/i.test(trimmed)) {
    return {
      ...DEFAULT_MCP_DRAFT,
      name: nameFromUrl(trimmed),
      transport: "http",
      url: trimmed,
    };
  }

  const folded = trimmed.replace(/\\\r?\n/g, " ");
  for (const line of folded.split("\n")) {
    const clean = line.trim();
    if (!clean) continue;
    const tokens = tokenizeShell(clean);
    if (!tokens || tokens.length === 0) continue;

    if (tokens[0] === "anara" && tokens[1] === "mcp" && tokens[2] === "add") {
      const name = tokens[3] || "server";
      const rest = tokens.slice(4);
      if (rest.length > 0 && /^https?:\/\/\S+$/i.test(rest[0])) {
        return { ...DEFAULT_MCP_DRAFT, name, transport: "http", url: rest[0] };
      }
      if (rest.length > 0) {
        return {
          ...DEFAULT_MCP_DRAFT,
          name,
          transport: "stdio",
          command: rest[0],
          args: rest.slice(1).map(createDraftValue),
        };
      }
    }

    const cmd = tokens[0];
    if (["npx", "bunx", "uvx", "node", "docker", "python", "python3"].includes(cmd)) {
      const args = tokens.slice(1);
      return {
        ...DEFAULT_MCP_DRAFT,
        name: inferCommandName(cmd, args),
        transport: "stdio",
        command: cmd,
        args: args.map(createDraftValue),
      };
    }
  }

  return null;
}

function entryOfDraft(draft: CustomMcpDraft): Record<string, unknown> {
  if (draft.transport === "http") {
    const headers: Record<string, string> = {};
    draft.headers.forEach((h) => {
      if (h.key.trim()) headers[h.key.trim()] = h.value;
    });
    if (draft.auth === "bearer" && draft.bearer.trim()) {
      headers["Authorization"] = `Bearer ${draft.bearer.trim()}`;
    }
    const entry: Record<string, unknown> = {
      url: draft.url.trim(),
    };
    if (Object.keys(headers).length > 0) {
      entry.headers = headers;
    }
    if (draft.auth === "oauth") {
      entry.auth = "oauth";
    }
    return entry;
  }

  const env: Record<string, string> = {};
  draft.env.forEach((e) => {
    if (e.key.trim()) env[e.key.trim()] = e.value;
  });
  draft.passthrough.forEach((p) => {
    if (p.value.trim()) env[p.value.trim()] = `\${${p.value.trim()}}`;
  });

  const args = draft.args.map((a) => a.value.trim()).filter(Boolean);
  const entry: Record<string, unknown> = {
    command: draft.command.trim(),
  };
  if (args.length > 0) entry.args = args;
  if (Object.keys(env).length > 0) entry.env = env;
  if (draft.cwd.trim()) entry.cwd = draft.cwd.trim();
  return entry;
}

export default function BrainConnectorsTab() {
  const [catalog, setCatalog] = useState<ConnectorItem[]>([]);
  const [mcpServers, setMcpServers] = useState<Record<string, McpServerConfig>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [segment, setSegment] = useState<ConnectorSegment>("all");
  const [isLoading, setIsLoading] = useState(false);
  const [isConnectingAll, setIsConnectingAll] = useState(false);

  // Add Server Dialog state
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [draft, setDraft] = useState<CustomMcpDraft>(DEFAULT_MCP_DRAFT);
  const [isRawJson, setIsRawJson] = useState(false);
  const [rawJsonText, setRawJsonText] = useState("");
  const [rawJsonError, setRawJsonError] = useState<string | null>(null);
  const [isSavingServer, setIsSavingServer] = useState(false);
  const [pasteSnippetText, setPasteSnippetText] = useState("");
  const [pasteStatus, setPasteStatus] = useState<"matched" | "unmatched" | null>(null);

  // Inspector / Config Dialog state
  const [inspectingServer, setInspectingServer] = useState<McpServerConfig | null>(null);
  const [selectedCatalogItem, setSelectedCatalogItem] = useState<ConnectorItem | null>(null);

  // Toast notices
  const [notice, setNotice] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);
  const [busyActionKey, setBusyActionKey] = useState<string | null>(null);

  const showNotice = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 3500);
  };

  const showError = (msg: string) => {
    setErrorNotice(msg);
    setTimeout(() => setErrorNotice(null), 4500);
  };

  const fetchCatalogAndServers = useCallback(async () => {
    setIsLoading(true);
    try {
      const [catRes, srvRes] = await Promise.allSettled([
        fetch(`${BACKEND_URL}/api/brain/connectors/catalog`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${BACKEND_URL}/api/brain/mcp/servers`).then((r) => (r.ok ? r.json() : null)),
      ]);

      const srvMap: Record<string, McpServerConfig> =
        (srvRes.status === "fulfilled" && srvRes.value?.servers) || {};
      setMcpServers(srvMap);

      if (catRes.status === "fulfilled" && catRes.value?.catalog) {
        const rawCatalog: ConnectorItem[] = catRes.value.catalog;
        const merged = rawCatalog.map((item) => {
          const srv = srvMap[item.slug] || srvMap[item.id] || srvMap[item.name.toLowerCase()];
          return {
            ...item,
            installed: Boolean(srv),
            connected: srv?.connected || false,
            tools_count: srv?.tools_count || 0,
          };
        });
        setCatalog(merged);
      }
    } catch (e) {
      console.warn("[BrainConnectors] Fetch error:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCatalogAndServers();
  }, [fetchCatalogAndServers]);

  // Reconnect all servers
  const handleReconnectAll = async () => {
    setIsConnectingAll(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/mcp/servers/connect`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        showNotice(`Reconnected ${data.connected_servers ?? 0} active MCP servers.`);
      } else {
        showError("Failed to reconnect servers.");
      }
      await fetchCatalogAndServers();
    } catch (e) {
      showError(`Reconnect error: ${String(e)}`);
    } finally {
      setIsConnectingAll(false);
    }
  };

  // Toggle local MCP server
  const handleToggleServer = async (serverName: string, currentEnabled: boolean) => {
    setBusyActionKey(`toggle-${serverName}`);
    const nextEnabled = !currentEnabled;

    // Optimistic update
    setMcpServers((prev) => ({
      ...prev,
      [serverName]: {
        ...prev[serverName],
        enabled: nextEnabled,
        connected: nextEnabled ? prev[serverName].connected : false,
      },
    }));

    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/mcp/servers/${encodeURIComponent(serverName)}/toggle`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: nextEnabled }),
      });
      if (res.ok) {
        showNotice(`Server '${serverName}' ${nextEnabled ? "enabled" : "disabled"}.`);
      } else {
        showError(`Failed to toggle server '${serverName}'.`);
      }
      await fetchCatalogAndServers();
    } catch (e) {
      showError(`Toggle error: ${String(e)}`);
      await fetchCatalogAndServers();
    } finally {
      setBusyActionKey(null);
    }
  };

  // Connect single server
  const handleConnectSingle = async (serverName: string) => {
    setBusyActionKey(`connect-${serverName}`);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/mcp/servers/${encodeURIComponent(serverName)}/connect`, {
        method: "POST",
      });
      if (res.ok) {
        showNotice(`Connected to server '${serverName}'.`);
      } else {
        showError(`Failed to connect server '${serverName}'.`);
      }
      await fetchCatalogAndServers();
    } catch (e) {
      showError(`Connection error: ${String(e)}`);
    } finally {
      setBusyActionKey(null);
    }
  };

  // Disconnect single server
  const handleDisconnectSingle = async (serverName: string) => {
    setBusyActionKey(`disconnect-${serverName}`);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/mcp/servers/${encodeURIComponent(serverName)}/disconnect`, {
        method: "POST",
      });
      if (res.ok) {
        showNotice(`Disconnected server '${serverName}'.`);
        if (inspectingServer && inspectingServer.name === serverName) {
          setInspectingServer((prev) => (prev ? { ...prev, connected: false } : null));
        }
      } else {
        showError(`Failed to disconnect server '${serverName}'.`);
      }
      await fetchCatalogAndServers();
    } catch (e) {
      showError(`Disconnect error: ${String(e)}`);
    } finally {
      setBusyActionKey(null);
    }
  };

  // Remove server
  const handleRemoveServer = async (serverName: string) => {
    if (!confirm(`Are you sure you want to remove the MCP server '${serverName}'?`)) {
      return;
    }
    setBusyActionKey(`remove-${serverName}`);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/mcp/servers/${encodeURIComponent(serverName)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        showNotice(`Server '${serverName}' removed.`);
        if (inspectingServer?.name === serverName) {
          setInspectingServer(null);
        }
      } else {
        showError(`Failed to remove server '${serverName}'.`);
      }
      await fetchCatalogAndServers();
    } catch (e) {
      showError(`Remove error: ${String(e)}`);
    } finally {
      setBusyActionKey(null);
    }
  };

  const nameTaken = useMemo(() => {
    const n = draft.name.trim();
    return Boolean(n && mcpServers[n]);
  }, [draft.name, mcpServers]);

  const isDraftComplete = useMemo(() => {
    const hasName = draft.name.trim().length > 0;
    if (!hasName) return false;
    return draft.transport === "stdio" ? draft.command.trim().length > 0 : draft.url.trim().length > 0;
  }, [draft]);

  const handlePasteSnippetChange = (text: string) => {
    setPasteSnippetText(text);
    if (!text.trim()) {
      setPasteStatus(null);
      return;
    }
    const matched = parseMcpImportSnippet(text, draft);
    if (matched) {
      setDraft((prev) => ({
        ...prev,
        ...matched,
        pasteSnippet: text,
      }));
      setPasteStatus("matched");
    } else {
      setPasteStatus("unmatched");
    }
  };

  const handleOpenAddServer = () => {
    setDraft(DEFAULT_MCP_DRAFT);
    setPasteSnippetText("");
    setPasteStatus(null);
    setIsRawJson(false);
    setRawJsonError(null);
    setIsAddOpen(true);
  };

  const handleOpenRawJson = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/mcp/raw-config`);
      let baseJson: Record<string, any> = { mcpServers: {} };
      if (res.ok) {
        const data = await res.json();
        if (data.parsed && typeof data.parsed === "object" && !Array.isArray(data.parsed)) {
          baseJson = data.parsed;
        }
      }
      if (!baseJson.mcpServers && !baseJson.mcp_servers) {
        baseJson = { mcpServers: baseJson };
      }
      const serverKey = baseJson.mcpServers ? "mcpServers" : "mcp_servers";
      const serverName = draft.name.trim() || "my-server";

      if (draft.command.trim() || draft.url.trim() || draft.name.trim()) {
        baseJson[serverKey] = {
          ...baseJson[serverKey],
          [serverName]: entryOfDraft(draft),
        };
      }
      setRawJsonText(JSON.stringify(baseJson, null, 2));
      setRawJsonError(null);
    } catch {
      const fallback = {
        mcpServers: {
          [draft.name.trim() || "my-server"]: entryOfDraft(draft),
        },
      };
      setRawJsonText(JSON.stringify(fallback, null, 2));
      setRawJsonError(null);
    }
    setIsRawJson(true);
  };

  const handleLeaveRawJson = () => {
    try {
      const parsed = JSON.parse(rawJsonText);
      const wrapper = parsed.mcpServers ?? parsed.mcp_servers ?? (
        !("mcpServers" in parsed || "mcp_servers" in parsed) ? parsed : {}
      );
      if (wrapper && typeof wrapper === "object") {
        const validKeys = Object.keys(wrapper).filter(
          (k) => !["mcpServers", "mcp_servers"].includes(k)
        );
        const serverName = draft.name.trim();
        const targetKey = (serverName && wrapper[serverName]) ? serverName : validKeys[0];
        if (targetKey && typeof wrapper[targetKey] === "object") {
          const updated = draftFromRawEntry(targetKey, wrapper[targetKey] as Record<string, unknown>, draft);
          setDraft(updated);
        }
      }
    } catch {
      // Keep existing draft if raw JSON invalid
    }
    setIsRawJson(false);
    setRawJsonError(null);
  };

  const handleSaveRawJson = async () => {
    try {
      const parsed = JSON.parse(rawJsonText);
      setIsSavingServer(true);
      const res = await fetch(`${BACKEND_URL}/api/brain/mcp/raw-config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_json: rawJsonText, config: parsed }),
      });
      if (res.ok) {
        showNotice("Saved mcp.json configuration successfully.");
        setIsAddOpen(false);
        setIsRawJson(false);
        await fetchCatalogAndServers();
      } else {
        const err = await res.json().catch(() => ({}));
        setRawJsonError(err.detail || "Failed to save mcp.json.");
      }
    } catch (e: any) {
      setRawJsonError(`Invalid JSON: ${e.message}`);
    } finally {
      setIsSavingServer(false);
    }
  };

  const handleSaveForm = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanName = draft.name.trim();
    if (!cleanName) {
      showError("Server name is required.");
      return;
    }
    if (nameTaken) {
      showError(`Server '${cleanName}' already exists.`);
      return;
    }
    if (draft.transport === "stdio" && !draft.command.trim()) {
      showError("Command to launch is required for STDIO transport.");
      return;
    }
    if (draft.transport === "http" && !draft.url.trim()) {
      showError("Endpoint URL is required for Streamable HTTP transport.");
      return;
    }

    const envObj: Record<string, string> = {};
    draft.env.forEach((r) => {
      if (r.key.trim()) envObj[r.key.trim()] = r.value;
    });
    draft.passthrough.forEach((r) => {
      if (r.value.trim()) envObj[r.value.trim()] = `\${${r.value.trim()}}`;
    });

    const headerObj: Record<string, string> = {};
    draft.headers.forEach((r) => {
      if (r.key.trim()) headerObj[r.key.trim()] = r.value;
    });
    if (draft.transport === "http" && draft.auth === "bearer" && draft.bearer.trim()) {
      headerObj["Authorization"] = `Bearer ${draft.bearer.trim()}`;
    }

    const payload = {
      name: cleanName,
      transport: draft.transport,
      command: draft.transport === "stdio" ? draft.command.trim() : "",
      args: draft.transport === "stdio" ? draft.args.map((a) => a.value.trim()).filter(Boolean) : [],
      url: draft.transport === "http" ? draft.url.trim() : "",
      env: envObj,
      headers: headerObj,
      cwd: draft.cwd.trim(),
      auth: draft.auth,
    };

    setIsSavingServer(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/mcp/servers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        showNotice(`Server '${cleanName}' registered and connected.`);
        setIsAddOpen(false);
        setDraft(DEFAULT_MCP_DRAFT);
        setPasteSnippetText("");
        setPasteStatus(null);
        await fetchCatalogAndServers();
      } else {
        const errData = await res.json().catch(() => ({}));
        showError(errData.detail || `Failed to add server '${cleanName}'.`);
      }
    } catch (err) {
      showError(`Save error: ${String(err)}`);
    } finally {
      setIsSavingServer(false);
    }
  };

  // Open install modal prefilled with catalog item
  const handleCatalogInstallClick = (item: ConnectorItem) => {
    setSelectedCatalogItem(item);
  };

  // Pre-fill Add Server dialog from catalog item
  const handlePromoteCatalogToAdd = (item: ConnectorItem) => {
    setSelectedCatalogItem(null);
    setDraft({
      ...DEFAULT_MCP_DRAFT,
      name: item.slug,
      transport: item.transport_type === "http" ? "http" : "stdio",
      command: item.transport_type === "stdio" ? "npx" : "",
      args:
        item.transport_type === "stdio"
          ? [createDraftValue("-y"), createDraftValue(`@modelcontextprotocol/server-${item.slug}`)]
          : [],
      url: item.transport_url || "",
      auth: item.auth_type === "oauth" ? "oauth" : "none",
    });
    setPasteSnippetText("");
    setPasteStatus(null);
    setIsRawJson(false);
    setRawJsonError(null);
    setIsAddOpen(true);
  };

  // Partitioned datasets
  const serverList = useMemo(() => {
    return Object.values(mcpServers).filter(
      (s) => s.name && !["mcpServers", "mcp_servers"].includes(s.name)
    );
  }, [mcpServers]);

  const connectedServers = useMemo(() => {
    return serverList.filter((s) => s.connected);
  }, [serverList]);

  const localMcpServers = useMemo(() => {
    return serverList;
  }, [serverList]);

  const availableCatalog = useMemo(() => {
    return catalog.filter((c) => !c.installed);
  }, [catalog]);

  // Search filtering
  const q = searchQuery.toLowerCase().trim();

  const filteredConnected = useMemo(() => {
    if (!q) return connectedServers;
    return connectedServers.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.command && s.command.toLowerCase().includes(q)) ||
        (s.url && s.url.toLowerCase().includes(q))
    );
  }, [connectedServers, q]);

  const filteredLocal = useMemo(() => {
    if (!q) return localMcpServers;
    return localMcpServers.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.command && s.command.toLowerCase().includes(q)) ||
        (s.url && s.url.toLowerCase().includes(q))
    );
  }, [localMcpServers, q]);

  const filteredAvailable = useMemo(() => {
    if (!q) return availableCatalog;
    return availableCatalog.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.slug.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q) ||
        c.category.toLowerCase().includes(q)
    );
  }, [availableCatalog, q]);

  // Dynamic segments (matching reference derivePage 1:1 — only categories with >0 items earn a tab)
  const segments = useMemo(() => {
    const totalCount = filteredConnected.length + filteredLocal.length + filteredAvailable.length;
    const list: { id: "all" | "connected" | "local" | "available"; label: string; count: number; dot?: string }[] = [
      { id: "all", label: "All", count: totalCount },
    ];
    if (filteredConnected.length > 0) {
      list.push({ id: "connected", label: "Connected", count: filteredConnected.length, dot: "bg-emerald-400" });
    }
    if (filteredLocal.length > 0) {
      list.push({ id: "local", label: "Local MCP", count: filteredLocal.length });
    }
    if (filteredAvailable.length > 0) {
      list.push({ id: "available", label: "Available", count: filteredAvailable.length });
    }
    return list;
  }, [filteredConnected.length, filteredLocal.length, filteredAvailable.length]);

  const activeSegment = useMemo(() => {
    return segments.some((s) => s.id === segment) ? segment : "all";
  }, [segments, segment]);

  return (
    <div className="h-full w-full flex flex-col overflow-hidden select-none font-sans bg-[#030712] text-slate-200">
      {/* 1. Top Header Bar */}
      <div className="px-5 py-3.5 border-b border-white/[0.08] bg-[#050811]/95 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-white font-mono tracking-tight">
              Connectors &amp; MCP Integrations
            </h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/10 text-cyan-300 border border-cyan-400/20 font-semibold">
              {connectedServers.length} Active / {catalog.length} Available
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5 leading-relaxed font-sans">
            Connect external workspaces, SaaS tools, and local MCP subprocesses directly to Anara.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleReconnectAll}
            disabled={isConnectingAll}
            className="px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.1] text-slate-300 hover:text-white text-xs font-mono font-medium transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
          >
            <svg
              className={`w-3.5 h-3.5 ${isConnectingAll ? "animate-spin text-cyan-400" : "text-slate-400"}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>{isConnectingAll ? "Reconnecting..." : "Reconnect All"}</span>
          </button>

          <button
            type="button"
            onClick={handleOpenAddServer}
            className="px-3 py-1.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-400/30 text-cyan-200 text-xs font-mono font-medium transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
          >
            <svg className="w-3.5 h-3.5 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>+ Add Server</span>
          </button>
        </div>
      </div>

      {/* 2. Filter & Search Controls Bar */}
      <div className="px-5 py-2.5 border-b border-white/[0.06] bg-[#060913]/90 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 shrink-0">
        {/* Search Field */}
        <div className="relative flex-1 max-w-md">
          <svg
            className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search connectors, commands, or tools..."
            className="w-full py-1.5 pl-8 pr-3 rounded-lg bg-black/40 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-400/40 transition-colors font-sans"
          />
        </div>

        {/* Dynamic Segmented Control Buttons (1:1 Reference: Only shown when >2 segments exist and count > 0) */}
        {segments.length > 2 && (
          <div className="flex items-center gap-1 p-0.5 rounded-lg bg-black/40 border border-white/[0.08] text-xs font-mono">
            {segments.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setSegment(s.id)}
                className={`px-2.5 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                  activeSegment === s.id
                    ? "bg-white/[0.08] text-white font-medium border border-white/[0.12] shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {s.dot && <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />}
                <span>{s.label}</span>
                <span className="text-[10px] text-slate-500 font-semibold">{s.count}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 3. Main Body Scroll Container */}
      <div className="flex-1 min-h-0 overflow-y-auto p-5 custom-scrollbar font-sans space-y-6">
        {isLoading && serverList.length === 0 && catalog.length === 0 ? (
          <div className="p-16 text-center text-xs text-slate-500 font-mono flex items-center justify-center gap-2">
            <svg className="w-4 h-4 animate-spin text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>Loading connectors &amp; MCP registry...</span>
          </div>
        ) : null}

        {/* SECTION A: Connected Section */}
        {(activeSegment === "all" || activeSegment === "connected") && filteredConnected.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-center justify-between pb-1 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]" />
                <h4 className="text-xs font-bold text-white font-mono tracking-tight uppercase">
                  Connected Servers ({filteredConnected.length})
                </h4>
              </div>
              <span className="text-[10.5px] text-slate-500 font-mono">
                Active connections with registered core tools
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredConnected.map((srv) => (
                <div
                  key={srv.name}
                  className="p-3.5 rounded-xl border border-emerald-500/25 bg-[#070e20]/90 shadow-[0_0_15px_rgba(16,185,129,0.06)] flex flex-col justify-between transition-all hover:border-emerald-500/40"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-400/25 flex items-center justify-center text-emerald-300 font-mono font-bold text-xs shrink-0">
                          {srv.name.charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <h5 className="text-xs font-bold text-white truncate font-sans">
                              {srv.name}
                            </h5>
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399] shrink-0" />
                          </div>
                          <span className="text-[10px] text-slate-400 font-mono block truncate">
                            {srv.transport.toUpperCase()} · {srv.command || srv.url || "local subprocess"}
                          </span>
                        </div>
                      </div>

                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 border border-emerald-400/20 text-emerald-300 font-semibold shrink-0">
                        {srv.tools_count} {srv.tools_count === 1 ? "tool" : "tools"}
                      </span>
                    </div>

                    {srv.tools && srv.tools.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap gap-1">
                        {srv.tools.slice(0, 4).map((tool) => (
                          <span
                            key={tool}
                            className="px-1.5 py-0.5 rounded text-[9.5px] font-mono bg-white/[0.04] border border-white/[0.07] text-slate-300 truncate max-w-[140px]"
                            title={tool}
                          >
                            {tool}
                          </span>
                        ))}
                        {srv.tools.length > 4 && (
                          <span className="px-1.5 py-0.5 rounded text-[9.5px] font-mono text-slate-500">
                            +{srv.tools.length - 4} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="mt-3.5 pt-2.5 border-t border-white/[0.06] flex items-center justify-between">
                    <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                      <span className="w-1 h-1 rounded-full bg-emerald-400" />
                      Live Handshake
                    </span>

                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => setInspectingServer(srv)}
                        className="px-2.5 py-1 rounded-md text-xs font-mono bg-white/[0.05] hover:bg-white/[0.1] text-slate-200 border border-white/[0.1] transition-colors cursor-pointer"
                      >
                        Configure
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDisconnectSingle(srv.name)}
                        disabled={busyActionKey === `disconnect-${srv.name}`}
                        className="px-2.5 py-1 rounded-md text-xs font-mono bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-400/20 transition-colors cursor-pointer"
                      >
                        Disconnect
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* SECTION B: Local MCP Section */}
        {(activeSegment === "all" || activeSegment === "local") && filteredLocal.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-center justify-between pb-1 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                <h4 className="text-xs font-bold text-white font-mono tracking-tight uppercase">
                  Local MCP Servers ({filteredLocal.length})
                </h4>
              </div>
              <span className="text-[10.5px] text-slate-500 font-mono">
                stdio &amp; sse daemon MCP subprocesses
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredLocal.map((srv) => (
                <div
                  key={srv.name}
                  className={`p-3.5 rounded-xl border flex flex-col justify-between transition-all ${
                    srv.enabled
                      ? "bg-[#060913]/90 border-white/[0.08] hover:border-white/[0.15]"
                      : "bg-[#04060c]/80 border-white/[0.04] opacity-75"
                  }`}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-slate-300 font-mono font-bold text-xs shrink-0">
                          {srv.name.charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <h5 className="text-xs font-bold text-white truncate font-sans">
                              {srv.name}
                            </h5>
                            <span
                              className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                                srv.connected
                                  ? "bg-emerald-400 shadow-[0_0_6px_#34d399]"
                                  : srv.enabled
                                  ? "bg-amber-400"
                                  : "bg-rose-400/80"
                              }`}
                              title={srv.connected ? "Connected" : srv.enabled ? "Disconnected" : "Disabled"}
                            />
                          </div>
                          <span className="text-[10px] text-slate-400 font-mono block truncate">
                            {srv.transport.toUpperCase()} · {srv.command || srv.url || "custom server"}
                          </span>
                        </div>
                      </div>

                      {/* Toggle Switch */}
                      <div
                        className="shrink-0 cursor-pointer"
                        onClick={() => handleToggleServer(srv.name, srv.enabled)}
                        title={srv.enabled ? "Disable server" : "Enable server"}
                      >
                        <div
                          className={`w-8 h-4.5 rounded-full p-0.5 transition-colors duration-200 ease-in-out relative ${
                            srv.enabled ? "bg-cyan-500" : "bg-slate-700/80"
                          } ${busyActionKey === `toggle-${srv.name}` ? "opacity-50" : ""}`}
                        >
                          <div
                            className={`w-3.5 h-3.5 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                              srv.enabled ? "translate-x-3.5" : "translate-x-0"
                            }`}
                          />
                        </div>
                      </div>
                    </div>

                    {/* Subcommand / Arguments Preview */}
                    <div className="mt-2.5 p-2 rounded-lg bg-black/40 border border-white/[0.06] font-mono text-[10px] text-slate-400 truncate">
                      {srv.args && srv.args.length > 0 ? (
                        <span>
                          <span className="text-slate-500">{srv.command} </span>
                          <span className="text-slate-300">{srv.args.join(" ")}</span>
                        </span>
                      ) : (
                        <span className="text-slate-300">{srv.command || srv.url || "No arguments"}</span>
                      )}
                    </div>
                  </div>

                  <div className="mt-3.5 pt-2.5 border-t border-white/[0.06] flex items-center justify-between">
                    <span className="text-[10px] font-mono text-slate-500">
                      {srv.tools_count ? (
                        <span className="text-cyan-400 font-semibold">{srv.tools_count} tools registered</span>
                      ) : srv.connected ? (
                        "Connected (0 tools)"
                      ) : srv.enabled ? (
                        "Ready to handshake"
                      ) : (
                        "Disabled"
                      )}
                    </span>

                    <div className="flex items-center gap-1.5">
                      {!srv.connected && srv.enabled && (
                        <button
                          type="button"
                          onClick={() => handleConnectSingle(srv.name)}
                          disabled={busyActionKey === `connect-${srv.name}`}
                          className="px-2 py-1 rounded-md text-xs font-mono bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-400/30 transition-colors cursor-pointer"
                        >
                          Connect
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setInspectingServer(srv)}
                        className="px-2 py-1 rounded-md text-xs font-mono bg-white/[0.05] hover:bg-white/[0.1] text-slate-300 transition-colors cursor-pointer"
                      >
                        Inspect
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemoveServer(srv.name)}
                        disabled={busyActionKey === `remove-${srv.name}`}
                        className="p-1 rounded-md text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
                        title="Remove Server"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* SECTION C: Available Catalog Section */}
        {(activeSegment === "all" || activeSegment === "available") && filteredAvailable.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-center justify-between pb-1 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-purple-400" />
                <h4 className="text-xs font-bold text-white font-mono tracking-tight uppercase">
                  Available Catalog ({filteredAvailable.length})
                </h4>
              </div>
              <span className="text-[10.5px] text-slate-500 font-mono">
                Installable MCP connectors and SaaS integrations
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredAvailable.map((item) => (
                <div
                  key={item.id}
                  className="p-3.5 rounded-xl border border-white/[0.08] bg-[#060913]/80 hover:bg-[#080d1a] hover:border-white/[0.14] flex flex-col justify-between transition-all"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-slate-200 font-mono font-bold text-xs shrink-0">
                          {item.name.charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <h5 className="text-xs font-bold text-white tracking-tight truncate font-sans">
                            {item.name}
                          </h5>
                          <span className="text-[10px] text-slate-500 font-mono block truncate">
                            {item.category}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1 shrink-0">
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase bg-white/[0.04] border border-white/[0.08] text-slate-400">
                          {item.transport_type}
                        </span>
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase bg-purple-500/10 border border-purple-400/20 text-purple-300">
                          {item.auth_type}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-slate-300 mt-2 leading-relaxed font-sans line-clamp-2">
                      {item.description}
                    </p>
                  </div>

                  <div className="mt-3.5 pt-2.5 border-t border-white/[0.06] flex items-center justify-between">
                    <span className="text-[10px] font-mono text-slate-500">
                      Catalog integration
                    </span>

                    <button
                      type="button"
                      onClick={() => handleCatalogInstallClick(item)}
                      className="px-3 py-1 rounded-md text-xs font-mono font-medium bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-400/30 transition-colors cursor-pointer"
                    >
                      + Connect
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Empty Search Result Fallback */}
        {((activeSegment === "connected" && filteredConnected.length === 0) ||
          (activeSegment === "local" && filteredLocal.length === 0) ||
          (activeSegment === "available" && filteredAvailable.length === 0) ||
          (activeSegment === "all" && filteredConnected.length === 0 && filteredLocal.length === 0 && filteredAvailable.length === 0)) && (
          <div className="p-16 text-center text-xs text-slate-500 font-mono space-y-2">
            <div>No matching connectors found for the active filter.</div>
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="text-cyan-400 hover:underline cursor-pointer"
              >
                Clear search query
              </button>
            )}
          </div>
        )}
      </div>

      {/* 4. Connect to a custom MCP Modal (1:1 Parity) */}
      {isAddOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div
            className={`w-full ${
              isRawJson ? "max-w-2xl" : "max-w-xl"
            } rounded-2xl bg-[#070c18] border border-white/[0.12] text-white font-sans shadow-2xl flex flex-col max-h-[88vh] overflow-hidden`}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-3.5 shrink-0 bg-[#050811]">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-400/25 flex items-center justify-center text-cyan-300 font-bold text-xs font-mono">
                  +
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white font-mono">Connect to a custom MCP</h3>
                  <p className="text-[10px] text-slate-400 font-mono">
                    Configure command-line subprocess or remote Streamable HTTP endpoint
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsAddOpen(false)}
                className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-white/[0.05] transition-colors cursor-pointer"
                aria-label="Close dialog"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Body */}
            {isRawJson ? (
              /* Raw mcp.json View */
              <div className="flex-1 p-5 space-y-3 overflow-y-auto custom-scrollbar flex flex-col min-h-0 bg-[#030712]">
                <div className="flex items-center justify-between text-xs font-mono text-slate-400 pb-1">
                  <span className="flex items-center gap-1.5 text-cyan-300">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                    mcp.json
                  </span>
                  <span className="text-[10px] text-slate-500">Edit raw MCP configuration</span>
                </div>

                <textarea
                  value={rawJsonText}
                  onChange={(e) => {
                    setRawJsonText(e.target.value);
                    setRawJsonError(null);
                  }}
                  rows={16}
                  className="w-full flex-1 min-h-[18rem] font-mono text-xs bg-black/60 border border-white/[0.08] focus:border-cyan-400/40 rounded-xl p-3.5 text-slate-200 resize-none leading-relaxed custom-scrollbar outline-none"
                  placeholder='{"mcpServers": {}}'
                  spellCheck={false}
                />

                {rawJsonError && (
                  <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs font-mono">
                    {rawJsonError}
                  </div>
                )}
              </div>
            ) : (
              /* Form View */
              <form onSubmit={handleSaveForm} className="flex-1 p-5 space-y-4 overflow-y-auto custom-scrollbar min-h-0 bg-[#050811]">
                {/* 1. Paste a command or a snippet */}
                <div>
                  <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                    Paste a command or a snippet
                  </label>
                  <textarea
                    rows={2}
                    value={pasteSnippetText}
                    onChange={(e) => handlePasteSnippetChange(e.target.value)}
                    placeholder="npx -y @modelcontextprotocol/server-filesystem /path/to/dir"
                    className="w-full py-2 px-3 rounded-xl bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono custom-scrollbar resize-none transition-colors"
                  />
                  {pasteStatus === "matched" && (
                    <p className="text-[10px] text-cyan-400 font-mono flex items-center gap-1 mt-1">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      Configuration recognized and loaded
                    </p>
                  )}
                  {pasteStatus === "unmatched" && (
                    <p className="text-[10px] text-slate-500 font-mono mt-1">
                      No valid server configuration recognized in pasted text
                    </p>
                  )}
                </div>

                {/* 2. Name */}
                <div>
                  <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                    Name <span className="text-cyan-400">*</span>
                  </label>
                  <input
                    required
                    value={draft.name}
                    onChange={(e) => setDraft((prev) => ({ ...prev, name: e.target.value }))}
                    placeholder="e.g. filesystem"
                    className="w-full py-1.5 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                  />
                  {nameTaken && (
                    <p className="text-[10px] text-rose-400 font-mono mt-1">
                      A server with this name already exists
                    </p>
                  )}
                </div>

                {/* 3. Type */}
                <div>
                  <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                    Type
                  </label>
                  <div className="grid grid-cols-2 gap-1 p-1 bg-black/60 rounded-xl border border-white/[0.08]">
                    <button
                      type="button"
                      onClick={() => setDraft((prev) => ({ ...prev, transport: "stdio" }))}
                      className={`py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer ${
                        draft.transport === "stdio"
                          ? "bg-white/[0.08] text-cyan-300 border border-cyan-400/30 shadow-sm"
                          : "text-slate-400 hover:text-white"
                      }`}
                    >
                      STDIO
                    </button>
                    <button
                      type="button"
                      onClick={() => setDraft((prev) => ({ ...prev, transport: "http" }))}
                      className={`py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer ${
                        draft.transport === "http"
                          ? "bg-white/[0.08] text-cyan-300 border border-cyan-400/30 shadow-sm"
                          : "text-slate-400 hover:text-white"
                      }`}
                    >
                      Streamable HTTP
                    </button>
                  </div>
                </div>

                {/* Conditional Fields: STDIO vs HTTP */}
                {draft.transport === "stdio" ? (
                  <>
                    {/* 4. Command to launch */}
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                        Command to launch <span className="text-cyan-400">*</span>
                      </label>
                      <input
                        required
                        value={draft.command}
                        onChange={(e) => setDraft((prev) => ({ ...prev, command: e.target.value }))}
                        placeholder="e.g. npx"
                        className="w-full py-1.5 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                      />
                    </div>

                    {/* 5. Arguments */}
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                        Arguments
                      </label>
                      <div className="space-y-1.5">
                        {draft.args.map((arg) => (
                          <div key={arg.id} className="flex items-center gap-1.5">
                            <input
                              value={arg.value}
                              onChange={(e) => {
                                const nextVal = e.target.value;
                                setDraft((prev) => ({
                                  ...prev,
                                  args: prev.args.map((candidate) =>
                                    candidate.id === arg.id ? { ...candidate, value: nextVal } : candidate
                                  ),
                                }));
                              }}
                              placeholder="e.g. -y or @modelcontextprotocol/server-filesystem"
                              className="flex-1 py-1 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                            />
                            <button
                              type="button"
                              onClick={() =>
                                setDraft((prev) => ({
                                  ...prev,
                                  args: prev.args.filter((candidate) => candidate.id !== arg.id),
                                }))
                              }
                              className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-white/[0.04] rounded transition-colors shrink-0 cursor-pointer"
                              aria-label="Remove argument"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() =>
                            setDraft((prev) => ({
                              ...prev,
                              args: [...prev.args, createDraftValue()],
                            }))
                          }
                          className="text-xs font-mono text-cyan-400 hover:text-cyan-300 font-medium inline-flex items-center gap-1 transition-colors cursor-pointer py-1"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                          </svg>
                          <span>Add argument</span>
                        </button>
                      </div>
                    </div>

                    {/* 6. Environment variables */}
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                        Environment variables
                      </label>
                      <div className="space-y-1.5">
                        {draft.env.map((row) => (
                          <div key={row.id} className="flex items-center gap-1.5">
                            <input
                              value={row.key}
                              onChange={(e) => {
                                const nextKey = e.target.value;
                                setDraft((prev) => ({
                                  ...prev,
                                  env: prev.env.map((candidate) =>
                                    candidate.id === row.id ? { ...candidate, key: nextKey } : candidate
                                  ),
                                }));
                              }}
                              placeholder="KEY"
                              className="flex-1 py-1 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                            />
                            <input
                              value={row.value}
                              onChange={(e) => {
                                const nextVal = e.target.value;
                                setDraft((prev) => ({
                                  ...prev,
                                  env: prev.env.map((candidate) =>
                                    candidate.id === row.id ? { ...candidate, value: nextVal } : candidate
                                  ),
                                }));
                              }}
                              placeholder="VALUE"
                              className="flex-1 py-1 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                            />
                            <button
                              type="button"
                              onClick={() =>
                                setDraft((prev) => ({
                                  ...prev,
                                  env: prev.env.filter((candidate) => candidate.id !== row.id),
                                }))
                              }
                              className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-white/[0.04] rounded transition-colors shrink-0 cursor-pointer"
                              aria-label="Remove environment variable"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() =>
                            setDraft((prev) => ({
                              ...prev,
                              env: [...prev.env, createDraftPair()],
                            }))
                          }
                          className="text-xs font-mono text-cyan-400 hover:text-cyan-300 font-medium inline-flex items-center gap-1 transition-colors cursor-pointer py-1"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                          </svg>
                          <span>Add environment variable</span>
                        </button>
                      </div>
                    </div>

                    {/* 7. Environment variable passthrough */}
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                        Environment variable passthrough
                      </label>
                      <div className="space-y-1.5">
                        {draft.passthrough.map((pt) => (
                          <div key={pt.id} className="flex items-center gap-1.5">
                            <input
                              value={pt.value}
                              onChange={(e) => {
                                const nextVal = e.target.value;
                                setDraft((prev) => ({
                                  ...prev,
                                  passthrough: prev.passthrough.map((candidate) =>
                                    candidate.id === pt.id ? { ...candidate, value: nextVal } : candidate
                                  ),
                                }));
                              }}
                              placeholder="VARIABLE_NAME"
                              className="flex-1 py-1 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                            />
                            <button
                              type="button"
                              onClick={() =>
                                setDraft((prev) => ({
                                  ...prev,
                                  passthrough: prev.passthrough.filter((candidate) => candidate.id !== pt.id),
                                }))
                              }
                              className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-white/[0.04] rounded transition-colors shrink-0 cursor-pointer"
                              aria-label="Remove passthrough variable"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() =>
                            setDraft((prev) => ({
                              ...prev,
                              passthrough: [...prev.passthrough, createDraftValue()],
                            }))
                          }
                          className="text-xs font-mono text-cyan-400 hover:text-cyan-300 font-medium inline-flex items-center gap-1 transition-colors cursor-pointer py-1"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                          </svg>
                          <span>Add variable</span>
                        </button>
                      </div>
                    </div>

                    {/* 8. Working directory */}
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                        Working directory
                      </label>
                      <input
                        value={draft.cwd}
                        onChange={(e) => setDraft((prev) => ({ ...prev, cwd: e.target.value }))}
                        placeholder="e.g. /path/to/dir or C:\path\to\dir"
                        className="w-full py-1.5 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    {/* Streamable HTTP: URL */}
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                        URL <span className="text-cyan-400">*</span>
                      </label>
                      <input
                        required
                        value={draft.url}
                        onChange={(e) => setDraft((prev) => ({ ...prev, url: e.target.value }))}
                        placeholder="https://mcp.linear.app/mcp"
                        className="w-full py-1.5 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                      />
                    </div>

                    {/* Streamable HTTP: Headers */}
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                        Headers
                      </label>
                      <div className="space-y-1.5">
                        {draft.headers.map((header) => (
                          <div key={header.id} className="flex items-center gap-1.5">
                            <input
                              value={header.key}
                              onChange={(e) => {
                                const nextKey = e.target.value;
                                setDraft((prev) => ({
                                  ...prev,
                                  headers: prev.headers.map((candidate) =>
                                    candidate.id === header.id ? { ...candidate, key: nextKey } : candidate
                                  ),
                                }));
                              }}
                              placeholder="Header"
                              className="flex-1 py-1 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                            />
                            <input
                              value={header.value}
                              onChange={(e) => {
                                const nextVal = e.target.value;
                                setDraft((prev) => ({
                                  ...prev,
                                  headers: prev.headers.map((candidate) =>
                                    candidate.id === header.id ? { ...candidate, value: nextVal } : candidate
                                  ),
                                }));
                              }}
                              placeholder="Value"
                              className="flex-1 py-1 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                            />
                            <button
                              type="button"
                              onClick={() =>
                                setDraft((prev) => ({
                                  ...prev,
                                  headers: prev.headers.filter((candidate) => candidate.id !== header.id),
                                }))
                              }
                              className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-white/[0.04] rounded transition-colors shrink-0 cursor-pointer"
                              aria-label="Remove header"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() =>
                            setDraft((prev) => ({
                              ...prev,
                              headers: [...prev.headers, createDraftPair()],
                            }))
                          }
                          className="text-xs font-mono text-cyan-400 hover:text-cyan-300 font-medium inline-flex items-center gap-1 transition-colors cursor-pointer py-1"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                          </svg>
                          <span>Add header</span>
                        </button>
                      </div>
                    </div>

                    {/* Streamable HTTP: Auth */}
                    <div>
                      <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                        Auth
                      </label>
                      <div className="grid grid-cols-3 gap-1 p-1 bg-black/60 rounded-xl border border-white/[0.08]">
                        {(["none", "oauth", "bearer"] as const).map((authMode) => (
                          <button
                            key={authMode}
                            type="button"
                            onClick={() => setDraft((prev) => ({ ...prev, auth: authMode }))}
                            className={`py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer ${
                              draft.auth === authMode
                                ? "bg-white/[0.08] text-cyan-300 border border-cyan-400/30 shadow-sm"
                                : "text-slate-400 hover:text-white"
                            }`}
                          >
                            {authMode === "none" ? "None" : authMode === "oauth" ? "OAuth" : "Bearer token"}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Streamable HTTP: Bearer Token input */}
                    {draft.auth === "bearer" && (
                      <div>
                        <label className="block text-[11px] font-mono text-slate-400 mb-1.5 font-medium">
                          Bearer token <span className="text-cyan-400">*</span>
                        </label>
                        <input
                          type="password"
                          value={draft.bearer}
                          onChange={(e) => setDraft((prev) => ({ ...prev, bearer: e.target.value }))}
                          placeholder="Enter bearer token"
                          className="w-full py-1.5 px-3 rounded-lg bg-black/50 border border-white/[0.08] text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400/50 font-mono transition-colors"
                        />
                      </div>
                    )}
                  </>
                )}
              </form>
            )}

            {/* Modal Footer */}
            <div className="flex items-center justify-between border-t border-white/[0.08] px-5 py-3 shrink-0 bg-[#050811]">
              {isRawJson ? (
                <>
                  <button
                    type="button"
                    onClick={handleLeaveRawJson}
                    className="px-3.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/[0.08] text-slate-300 hover:text-white text-xs font-mono transition-colors cursor-pointer"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveRawJson}
                    disabled={isSavingServer}
                    className="px-4 py-1.5 rounded-lg bg-cyan-400 hover:bg-cyan-300 text-black font-semibold text-xs font-mono transition-colors cursor-pointer shadow-sm disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
                  >
                    {isSavingServer && (
                      <svg className="w-3.5 h-3.5 animate-spin text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    )}
                    <span>{isSavingServer ? "Saving..." : "Save"}</span>
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={handleOpenRawJson}
                    className="px-3.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/[0.08] text-slate-300 hover:text-white text-xs font-mono transition-colors cursor-pointer"
                  >
                    Edit mcp.json
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSaveForm()}
                    disabled={isSavingServer || nameTaken || !isDraftComplete}
                    className="px-4 py-1.5 rounded-lg bg-cyan-400 hover:bg-cyan-300 text-black font-semibold text-xs font-mono transition-colors cursor-pointer shadow-sm disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
                  >
                    {isSavingServer && (
                      <svg className="w-3.5 h-3.5 animate-spin text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    )}
                    <span>{isSavingServer ? "Saving..." : "Save"}</span>
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 5. Server Details & Tools Inspector Modal */}
      {inspectingServer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="w-full max-w-xl p-5 rounded-2xl bg-[#070c18] border border-white/[0.15] text-white space-y-4 font-sans shadow-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-400/25 flex items-center justify-center text-cyan-300 font-bold text-xs font-mono">
                  {inspectingServer.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-white font-mono">{inspectingServer.name}</h3>
                    <span
                      className={`px-2 py-0.2 rounded-full text-[10px] font-mono font-semibold ${
                        inspectingServer.connected
                          ? "bg-emerald-500/15 text-emerald-300 border border-emerald-400/30"
                          : "bg-rose-500/15 text-rose-300 border border-rose-400/30"
                      }`}
                    >
                      {inspectingServer.connected ? "CONNECTED" : "DISCONNECTED"}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-400 uppercase">
                    Transport: {inspectingServer.transport}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setInspectingServer(null)}
                className="text-slate-400 hover:text-white font-mono text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Server Specs */}
            <div className="space-y-3 shrink-0">
              <div className="p-3 rounded-xl bg-black/50 border border-white/[0.08] space-y-1.5 font-mono text-xs">
                {inspectingServer.command && (
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-slate-500 text-[11px]">Command:</span>
                    <span className="text-slate-300 text-[11px] font-semibold break-all text-right">
                      {inspectingServer.command}
                    </span>
                  </div>
                )}
                {inspectingServer.args && inspectingServer.args.length > 0 && (
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-slate-500 text-[11px]">Args:</span>
                    <span className="text-slate-300 text-[11px] break-all text-right">
                      {inspectingServer.args.join(" ")}
                    </span>
                  </div>
                )}
                {inspectingServer.url && (
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-slate-500 text-[11px]">URL:</span>
                    <span className="text-slate-300 text-[11px] break-all text-right">
                      {inspectingServer.url}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Registered Tools List */}
            <div className="flex-1 min-h-0 overflow-y-auto space-y-2 custom-scrollbar">
              <div className="flex items-center justify-between pb-1 border-b border-white/[0.06]">
                <span className="text-[11px] font-mono text-slate-400 uppercase font-semibold">
                  Discovered Tools ({inspectingServer.tools_count || 0})
                </span>
                <span className="text-[10px] font-mono text-slate-500">
                  Dynamic tool injection
                </span>
              </div>

              {inspectingServer.tools && inspectingServer.tools.length > 0 ? (
                <div className="space-y-1.5">
                  {inspectingServer.tools.map((toolName) => (
                    <div
                      key={toolName}
                      className="p-2.5 rounded-lg bg-black/40 border border-white/[0.06] flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                        <span className="text-xs font-mono text-cyan-200 font-semibold">{toolName}</span>
                      </div>
                      <span className="text-[10px] font-mono text-slate-500">Active handler</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center text-xs font-mono text-slate-500">
                  {inspectingServer.connected
                    ? "No tools reported by this MCP server."
                    : "Server is disconnected. Connect to discover registered tools."}
                </div>
              )}
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-3 border-t border-white/[0.08] font-mono text-xs shrink-0">
              <button
                type="button"
                onClick={() => handleRemoveServer(inspectingServer.name)}
                className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-400/25 transition-colors cursor-pointer"
              >
                Delete Server
              </button>

              <div className="flex items-center gap-2">
                {inspectingServer.connected ? (
                  <button
                    type="button"
                    onClick={() => handleDisconnectSingle(inspectingServer.name)}
                    className="px-3.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 transition-colors cursor-pointer"
                  >
                    Disconnect
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleConnectSingle(inspectingServer.name)}
                    className="px-3.5 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-400/30 transition-colors cursor-pointer"
                  >
                    Connect
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setInspectingServer(null)}
                  className="px-3.5 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-white transition-colors cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 6. Catalog Item Preview & Connect Modal */}
      {selectedCatalogItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="w-full max-w-lg p-5 rounded-2xl bg-[#070c18] border border-white/[0.15] text-white space-y-4 font-sans shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-purple-500/15 border border-purple-400/25 flex items-center justify-center text-purple-300 font-bold text-xs font-mono">
                  {selectedCatalogItem.name.charAt(0)}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white font-mono">{selectedCatalogItem.name}</h3>
                  <span className="text-[10px] font-mono text-slate-400">{selectedCatalogItem.category}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedCatalogItem(null)}
                className="text-slate-400 hover:text-white font-mono text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              {selectedCatalogItem.description}
            </p>

            <div className="p-3 rounded-xl bg-black/50 border border-white/[0.08] space-y-2 font-mono text-xs">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500">Identifier Slug:</span>
                <span className="text-slate-300 font-semibold">{selectedCatalogItem.slug}</span>
              </div>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500">Transport Protocol:</span>
                <span className="text-slate-300 font-semibold uppercase">{selectedCatalogItem.transport_type}</span>
              </div>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500">Authentication:</span>
                <span className="text-slate-300 font-semibold uppercase">{selectedCatalogItem.auth_type}</span>
              </div>
            </div>

            {selectedCatalogItem.post_install && (
              <div className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-500/20 text-xs font-mono text-cyan-200 whitespace-pre-wrap leading-relaxed">
                {selectedCatalogItem.post_install}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/[0.08] font-mono text-xs">
              <button
                type="button"
                onClick={() => setSelectedCatalogItem(null)}
                className="px-3.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 transition-colors cursor-pointer"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => handlePromoteCatalogToAdd(selectedCatalogItem)}
                className="px-4 py-1.5 rounded-lg bg-cyan-400 text-black font-semibold hover:bg-cyan-300 transition-colors cursor-pointer shadow-sm"
              >
                Configure &amp; Connect
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 7. Toast Notices */}
      {notice && (
        <div className="fixed bottom-6 right-6 z-50 p-3 px-4 rounded-xl bg-emerald-500/15 border border-emerald-400/30 text-emerald-200 text-xs font-mono shadow-2xl backdrop-blur-xl animate-fade-in flex items-center gap-2">
          <span>✓</span>
          <span>{notice}</span>
        </div>
      )}

      {errorNotice && (
        <div className="fixed bottom-6 right-6 z-50 p-3 px-4 rounded-xl bg-rose-500/15 border border-rose-400/30 text-rose-200 text-xs font-mono shadow-2xl backdrop-blur-xl animate-fade-in flex items-center gap-2">
          <span>✕</span>
          <span>{errorNotice}</span>
        </div>
      )}
    </div>
  );
}
