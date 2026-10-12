"use client";

import React, { useState, useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { SearchAddon } from "@xterm/addon-search";
import "@xterm/xterm/css/xterm.css";
import { getBackendUrl } from "@/lib/apiClient";

export interface TerminalTab {
  id: string;
  name: string;
  shell: string;
  cwd?: string;
}

export interface WorkbenchTerminalProps {
  logs?: string[];
  activeTask?: string;
  onExecuteCommand?: (cmd: string) => void;
  onAskAnara?: (prompt: string) => void;
  onClose?: () => void;
  embedded?: boolean;
  isVisible?: boolean;
  cwd?: string;
}

const COSMIC_OBSIDIAN_PALETTE = {
  background: "#060913",
  foreground: "#e2e8f0",
  cursor: "#22d3ee",
  cursorAccent: "#060913",
  selectionBackground: "rgba(34, 211, 238, 0.25)",
  black: "#0f172a",
  red: "#f43f5e",
  green: "#10b981",
  yellow: "#f59e0b",
  blue: "#38bdf8",
  magenta: "#c084fc",
  cyan: "#22d3ee",
  white: "#f8fafc",
  brightBlack: "#475569",
  brightRed: "#fb7185",
  brightGreen: "#34d399",
  brightYellow: "#fbbf24",
  brightBlue: "#60a5fa",
  brightMagenta: "#e879f9",
  brightCyan: "#67e8f9",
  brightWhite: "#ffffff",
};

interface TerminalInstanceProps {
  tab: TerminalTab;
  isActive: boolean;
  isVisible: boolean;
  logs?: string[];
  pendingCommand?: string | null;
  onCommandConsumed?: () => void;
  onStatusUpdate?: (status: { connected: boolean; pid?: number; conpty?: boolean }) => void;
  onAskAnara?: (prompt: string) => void;
  restartSignal?: number;
}

function TerminalInstance({
  tab,
  isActive,
  isVisible,
  logs = [],
  pendingCommand,
  onCommandConsumed,
  onStatusUpdate,
  onAskAnara,
  restartSignal = 0,
}: TerminalInstanceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const searchAddonRef = useRef<SearchAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [pid, setPid] = useState<number | null>(null);
  const [isConpty, setIsConpty] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const processedLogsIndexRef = useRef(0);

  // Initialize Isolated Terminal and WebSocket PTY connection
  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      theme: COSMIC_OBSIDIAN_PALETTE,
      fontFamily: "var(--font-mono), 'JetBrains Mono', Consolas, monospace",
      fontSize: 12,
      lineHeight: 1.4,
      cursorBlink: true,
      cursorStyle: "bar",
      scrollback: 5000,
      allowTransparency: true,
      minimumContrastRatio: 4.5,
      logLevel: "off",
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    const searchAddon = new SearchAddon();

    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    term.loadAddon(searchAddon);

    term.open(containerRef.current);
    termRef.current = term;
    fitAddonRef.current = fitAddon;
    searchAddonRef.current = searchAddon;

    try {
      fitAddon.fit();
    } catch {}

    // Resolve WebSocket URL
    const rawBackend = process.env.NEXT_PUBLIC_BACKEND_URL || (typeof window !== "undefined" ? getBackendUrl() : "http://127.0.0.1:8000");
    const wsBase = rawBackend.replace(/^http/, "ws");
    const wsUrl = `${wsBase}/ws/terminal/${tab.id}?shell=${tab.shell}&cwd=${encodeURIComponent(tab.cwd || "")}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (evt) => {
      if (typeof evt.data === "string") {
        if (evt.data.startsWith("{") && evt.data.endsWith("}")) {
          try {
            const parsed = JSON.parse(evt.data);
            if (parsed.type === "ready") {
              setIsConnected(true);
              setPid(parsed.pid || null);
              setIsConpty(Boolean(parsed.conpty));
              onStatusUpdate?.({ connected: true, pid: parsed.pid, conpty: Boolean(parsed.conpty) });
              return;
            }
          } catch {}
        }
        try {
          term.write(evt.data);
        } catch {}
      } else if (evt.data instanceof Blob) {
        evt.data.text().then((text) => {
          try {
            term.write(text);
          } catch {}
        });
      }
    };

    ws.onerror = () => {
      setIsConnected(false);
      onStatusUpdate?.({ connected: false });
      term.writeln("\x1b[38;2;244;63;94m[anara-terminal] Shell connection offline. Connecting fallback...\x1b[0m");
    };

    ws.onclose = () => {
      setIsConnected(false);
      onStatusUpdate?.({ connected: false });
      term.writeln("\x1b[90m[anara-terminal] Process terminated.\x1b[0m");
    };

    // Direct Stdin Piping: Every keypress streams directly into the PTY
    const onDataDisposable = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "input", data }));
      }
    });

    // Intelligent Keyboard Shortcut Handling (Terminal Parity)
    term.attachCustomKeyEventHandler((event) => {
      // Ctrl+C / Cmd+C: Copy if selection exists; send SIGINT (\x03) if no selection
      if (event.ctrlKey && event.key.toLowerCase() === "c") {
        if (term.hasSelection()) {
          navigator.clipboard.writeText(term.getSelection());
          return false;
        }
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "input", data: "\x03" }));
          return false;
        }
      }

      // Ctrl+Shift+V or Ctrl+V: Paste from clipboard
      if ((event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "v") || (event.ctrlKey && event.key.toLowerCase() === "v")) {
        navigator.clipboard.readText().then((text) => {
          if (text && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "input", data: text }));
          }
        });
        return false;
      }

      // Ctrl+F: Open In-Terminal Search
      if (event.ctrlKey && event.key.toLowerCase() === "f") {
        event.preventDefault();
        setIsSearchOpen(true);
        return false;
      }

      // Ctrl+K or Ctrl+L: Clear terminal screen and buffer without triggering browser address bar
      if (event.ctrlKey && (event.key.toLowerCase() === "k" || event.key.toLowerCase() === "l")) {
        event.preventDefault();
        term.clear();
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "input", data: "\x0c" }));
        }
        return false;
      }

      return true;
    });

    // Debounced Resize Observer
    let resizeTimer: NodeJS.Timeout;
    const ro = new ResizeObserver(() => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        try {
          fitAddon.fit();
          if (ws.readyState === WebSocket.OPEN && term.cols && term.rows) {
            ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
          }
        } catch {}
      }, 50);
    });
    ro.observe(containerRef.current);

    return () => {
      clearTimeout(resizeTimer);
      ro.disconnect();
      onDataDisposable.dispose();
      ws.close();
      term.dispose();
    };
  }, [tab.id, tab.shell, tab.cwd, restartSignal]);

  // Execute pending command dispatched from parent toolbar
  useEffect(() => {
    if (pendingCommand && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "input", data: `${pendingCommand}
\n` }));
      onCommandConsumed?.();
    }
  }, [pendingCommand, onCommandConsumed]);

  // Re-fit canvas on visibility restore (Keep-Alive Parity)
  useEffect(() => {
    if (isVisible && isActive && fitAddonRef.current) {
      const timer = setTimeout(() => {
        try {
          fitAddonRef.current?.fit();
        } catch {}
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isVisible, isActive]);

  // Stream external logs if provided
  useEffect(() => {
    if (!termRef.current) return;
    if (logs.length > processedLogsIndexRef.current) {
      const newItems = logs.slice(processedLogsIndexRef.current);
      processedLogsIndexRef.current = logs.length;
      newItems.forEach((line) => {
        termRef.current?.writeln(`\x1b[90m[agent]\x1b[0m ${line}`);
      });
    }
  }, [logs]);

  // Search actions
  const handleFindNext = () => {
    if (searchQuery && searchAddonRef.current) {
      searchAddonRef.current.findNext(searchQuery);
    }
  };

  const handleFindPrev = () => {
    if (searchQuery && searchAddonRef.current) {
      searchAddonRef.current.findPrevious(searchQuery);
    }
  };

  // Context Menu Handlers
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY });
  };

  const handleCopy = () => {
    if (termRef.current && termRef.current.hasSelection()) {
      navigator.clipboard.writeText(termRef.current.getSelection());
    }
    setContextMenu(null);
  };

  const handlePaste = () => {
    navigator.clipboard.readText().then((text) => {
      if (text && wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "input", data: text }));
      }
    });
    setContextMenu(null);
  };

  const handleClear = () => {
    termRef.current?.clear();
    setContextMenu(null);
  };

  const handleKill = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "kill" }));
    }
    setContextMenu(null);
  };

  const handleSelectAll = () => {
    termRef.current?.selectAll();
    setContextMenu(null);
  };

  return (
    <div
      className="w-full h-full relative"
      onContextMenu={handleContextMenu}
      onClick={() => {
        if (contextMenu) setContextMenu(null);
        termRef.current?.focus();
      }}
    >
      <div ref={containerRef} className="w-full h-full" />

      {/* In-Terminal Floating Search Bar (Ctrl+F) */}
      {isSearchOpen && (
        <div
          className="absolute top-2 right-4 z-40 flex items-center gap-1.5 p-1 px-2 rounded-lg bg-[#0e1219]/95 border border-white/20 backdrop-blur-xl shadow-2xl text-xs font-mono select-none"
          onClick={(e) => e.stopPropagation()}
        >
          <input
            autoFocus
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              searchAddonRef.current?.findNext(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                if (e.shiftKey) handleFindPrev();
                else handleFindNext();
              }
              if (e.key === "Escape") setIsSearchOpen(false);
            }}
            placeholder="Find in terminal..."
            className="w-40 bg-black/40 border border-white/10 rounded px-2 py-0.5 text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-400"
          />
          <button
            type="button"
            onClick={handleFindPrev}
            className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white cursor-pointer"
            title="Previous (Shift+Enter)"
          >
            ↑
          </button>
          <button
            type="button"
            onClick={handleFindNext}
            className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white cursor-pointer"
            title="Next (Enter)"
          >
            ↓
          </button>
          <button
            type="button"
            onClick={() => setIsSearchOpen(false)}
            className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white cursor-pointer"
            title="Close (Esc)"
          >
            ✕
          </button>
        </div>
      )}

      {/* Floating Right-Click Context Menu */}
      {contextMenu && (
        <div
          style={{ top: contextMenu.y, left: contextMenu.x }}
          className="fixed z-50 w-44 p-1 rounded-xl bg-[#0e1219]/95 border border-white/15 backdrop-blur-2xl shadow-2xl text-xs font-mono text-slate-200 select-none animate-in fade-in zoom-in-95 duration-100"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            onClick={handleCopy}
            className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-white/10 text-left hover:text-white transition-colors cursor-pointer"
          >
            <span>Copy</span>
            <span className="text-[10px] text-slate-500">Ctrl+C</span>
          </button>
          <button
            type="button"
            onClick={handlePaste}
            className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-white/10 text-left hover:text-white transition-colors cursor-pointer"
          >
            <span>Paste</span>
            <span className="text-[10px] text-slate-500">Ctrl+V</span>
          </button>
          <button
            type="button"
            onClick={handleSelectAll}
            className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-white/10 text-left hover:text-white transition-colors cursor-pointer"
          >
            <span>Select All</span>
          </button>
          <div className="h-px bg-white/[0.08] my-1" />
          <button
            type="button"
            onClick={handleClear}
            className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-white/10 text-left hover:text-white transition-colors cursor-pointer"
          >
            <span>Clear Buffer</span>
            <span className="text-[10px] text-slate-500">Ctrl+K</span>
          </button>
          <button
            type="button"
            onClick={handleKill}
            className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-rose-500/20 text-left text-rose-300 hover:text-rose-100 transition-colors cursor-pointer"
          >
            <span>Kill Process</span>
            <span className="text-[10px] text-rose-400">SIGINT</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default function WorkbenchTerminal({
  logs = [],
  activeTask,
  onExecuteCommand,
  onAskAnara,
  onClose,
  embedded = false,
  isVisible = true,
  cwd,
}: WorkbenchTerminalProps) {
  const [tabs, setTabs] = useState<TerminalTab[]>([
    { id: "term-1", name: "PowerShell 1", shell: "powershell", cwd },
  ]);
  const [activeTabId, setActiveTabId] = useState<string>("term-1");
  const [isShellMenuOpen, setIsShellMenuOpen] = useState(false);
  const [pendingCommand, setPendingCommand] = useState<string | null>(null);
  const [statusMap, setStatusMap] = useState<Record<string, { connected: boolean; pid?: number; conpty?: boolean }>>({});
  const [restartSignals, setRestartSignals] = useState<Record<string, number>>({});
  const tabCounterRef = useRef<number>(2);

  const [availableShells, setAvailableShells] = useState<{ id: string; name: string }[]>([
    { id: "powershell", name: "PowerShell" },
    { id: "bash", name: "Git Bash" },
    { id: "cmd", name: "CMD" },
  ]);

  // Discover real installed shells from backend API
  useEffect(() => {
    try {
      fetch(`${getBackendUrl()}/api/agent/terminal/shells`)
        .then((res) => res.json())
        .then((data) => {
          if (data.shells && Array.isArray(data.shells) && data.shells.length > 0) {
            setAvailableShells(data.shells);
          }
        })
        .catch(() => {});
    } catch {}
  }, []);

  // Add new terminal tab
  const handleAddTab = (shell = "powershell") => {
    const id = `term-${Date.now()}`;
    const shellObj = availableShells.find((s) => s.id === shell);
    const shellName = shellObj ? shellObj.name : shell === "bash" ? "Git Bash" : shell === "cmd" ? "CMD" : "PowerShell";
    const name = `${shellName} ${tabCounterRef.current++}`;
    setTabs((prev) => [...prev, { id, name, shell, cwd }]);
    setActiveTabId(id);
    setIsShellMenuOpen(false);
  };

  // Close terminal tab
  const handleCloseTab = (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (tabs.length === 1) {
      onClose?.();
      return;
    }
    const idx = tabs.findIndex((t) => t.id === id);
    const remaining = tabs.filter((t) => t.id !== id);
    setTabs(remaining);
    if (activeTabId === id) {
      const nextActive = remaining[Math.max(0, idx - 1)];
      setActiveTabId(nextActive.id);
    }
  };

  const activeTab = tabs.find((t) => t.id === activeTabId);
  const activeStatus = statusMap[activeTabId];

  return (
    <div
      className={`w-full h-full flex flex-col bg-[#060913] overflow-hidden font-mono text-xs select-text ${
        embedded ? "rounded-none border-none shadow-none" : "rounded-xl border border-white/[0.08] shadow-xl"
      }`}
    >
      {/* ── Terminal Tab Bar Header ── */}
      <div className="flex items-center justify-between px-3 py-1 bg-[#080B11] border-b border-white/[0.08] select-none shrink-0">
        {/* Left Tabs with Shell Selector */}
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
          {tabs.map((tab) => {
            const isActive = tab.id === activeTabId;
            return (
              <div
                key={tab.id}
                onClick={() => setActiveTabId(tab.id)}
                className={`flex items-center gap-2 px-2.5 py-1 rounded-md text-[11px] font-mono transition-all cursor-pointer border ${
                  isActive
                    ? "bg-white/[0.08] text-white border-white/[0.12] shadow-sm font-semibold"
                    : "text-slate-400 hover:text-slate-200 border-transparent hover:bg-white/[0.03]"
                }`}
              >
                <svg className="w-3 h-3 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <span>{tab.name}</span>
                {tabs.length > 1 && (
                  <button
                    type="button"
                    onClick={(e) => handleCloseTab(tab.id, e)}
                    className="text-slate-500 hover:text-rose-400 p-0.5 rounded transition-colors cursor-pointer"
                    title="Close tab"
                  >
                    <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
            );
          })}

          {/* New Tab Button with Shell Dropdown */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsShellMenuOpen((v) => !v)}
              className="p-1 px-1.5 rounded-md text-slate-500 hover:text-white hover:bg-white/10 text-xs transition-colors cursor-pointer flex items-center gap-0.5"
              title="Add Terminal (Select Shell)"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span className="text-[9px]">▾</span>
            </button>

            {isShellMenuOpen && (
              <div
                className="absolute top-7 left-0 z-50 w-40 p-1 rounded-xl bg-[#0e1219]/95 border border-white/15 backdrop-blur-xl shadow-2xl text-[11px] font-mono space-y-0.5"
                onClick={(e) => e.stopPropagation()}
              >
                {availableShells.map((sh) => (
                  <button
                    key={sh.id}
                    type="button"
                    onClick={() => handleAddTab(sh.id)}
                    className="w-full text-left px-2 py-1 rounded hover:bg-white/10 text-slate-300 hover:text-white flex items-center gap-1.5 cursor-pointer"
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        sh.id === "bash" ? "bg-amber-400" : sh.id === "cmd" ? "bg-emerald-400" : "bg-cyan-400"
                      }`}
                    />
                    <span className="truncate">{sh.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Toolbar Actions */}
        <div className="flex items-center gap-2 shrink-0">
          {activeTask && (
            <div className="flex items-center gap-1.5 text-[10px] text-cyan-300 bg-cyan-500/10 border border-cyan-400/25 px-2 py-0.5 rounded-md truncate max-w-[200px]">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
              <span className="truncate">{activeTask}</span>
            </div>
          )}

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="px-2 py-0.5 rounded-md bg-white/[0.04] hover:bg-white/[0.10] text-slate-400 hover:text-white border border-white/[0.08] text-[10px] font-mono transition-all cursor-pointer flex items-center gap-1"
              title="Close Terminal Panel"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              <span>Close</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Quick Command Presets & Agent Integration Toolbar ── */}
      <div className="flex items-center justify-between px-3 py-1 bg-[#060913] border-b border-white/[0.06] text-[10.5px] select-none shrink-0 overflow-x-auto no-scrollbar gap-2">
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-slate-500 font-sans uppercase tracking-wider text-[9px] mr-0.5">Preset:</span>
          <button
            type="button"
            onClick={() => setPendingCommand("git status")}
            className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-slate-300 hover:text-cyan-300 border border-white/[0.06] transition-colors cursor-pointer"
          >
            git status
          </button>
          <button
            type="button"
            onClick={() => setPendingCommand(activeTab?.shell === "bash" ? "python run_tests.py" : "cmd.exe /c \"backend\\venv\\Scripts\\python.exe run_tests.py\"")}
            className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-slate-300 hover:text-cyan-300 border border-white/[0.06] transition-colors cursor-pointer"
          >
            run tests
          </button>
          <button
            type="button"
            onClick={() => setPendingCommand("clear")}
            className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-slate-300 hover:text-cyan-300 border border-white/[0.06] transition-colors cursor-pointer"
          >
            clear
          </button>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {onAskAnara && (
            <button
              type="button"
              onClick={() => {
                onAskAnara("Diagnose the active terminal session or recent test/build output.");
              }}
              className="px-2 py-0.5 rounded bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 transition-all cursor-pointer flex items-center gap-1 font-semibold"
              title="Ask Anara to analyze terminal"
            >
              <svg className="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>Ask Anara</span>
            </button>
          )}

          {/* Restart Shell Session */}
          <button
            type="button"
            onClick={() => {
              setRestartSignals((prev) => ({ ...prev, [activeTabId]: (prev[activeTabId] || 0) + 1 }));
            }}
            className="p-1 px-1.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-slate-400 hover:text-white border border-white/[0.06] transition-colors cursor-pointer flex items-center gap-1"
            title="Restart Active Shell Session"
          >
            <span>↺</span>
            <span className="text-[9.5px]">Reset</span>
          </button>

          {/* Live Status Indicator */}
          <div className="flex items-center gap-1.5 pl-1.5 border-l border-white/[0.08]">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                activeStatus?.connected
                  ? "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                  : "bg-amber-400 animate-pulse"
              }`}
            />
            <span className="text-[10px] text-slate-400 font-mono">
              {activeStatus?.connected
                ? `${activeTab?.name} ${activeStatus.pid ? `[PID ${activeStatus.pid}]` : ""} ${activeStatus.conpty ? "(ConPTY)" : ""}`
                : "Connecting..."}
            </span>
          </div>
        </div>
      </div>

      {/* ── Absolute-Stacked Isolated Terminal Hosts (Keep-Alive Lifecycle) ── */}
      <div className="flex-1 min-h-0 relative p-1.5 overflow-hidden bg-[#060913]">
        {tabs.map((tab) => (
          <div
            key={tab.id}
            style={{ display: tab.id === activeTabId ? "block" : "none" }}
            className="w-full h-full relative"
          >
            <TerminalInstance
              tab={tab}
              isActive={tab.id === activeTabId}
              isVisible={isVisible}
              logs={tab.id === activeTabId ? logs : undefined}
              pendingCommand={tab.id === activeTabId ? pendingCommand : null}
              onCommandConsumed={() => setPendingCommand(null)}
              onStatusUpdate={(st) => setStatusMap((prev) => ({ ...prev, [tab.id]: st }))}
              onAskAnara={onAskAnara}
              restartSignal={restartSignals[tab.id] || 0}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
