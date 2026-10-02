"use client";

import React, { useState, useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";
import { getBackendUrl } from "@/lib/apiClient";

export interface TerminalTab {
  id: string;
  name: string;
}

export interface WorkbenchTerminalProps {
  logs?: string[];
  activeTask?: string;
  onExecuteCommand?: (cmd: string) => void;
  onClose?: () => void;
  embedded?: boolean;
  isVisible?: boolean;
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

export default function WorkbenchTerminal({
  logs = [],
  activeTask,
  onExecuteCommand,
  onClose,
  embedded = false,
  isVisible = true,
}: WorkbenchTerminalProps) {
  const [tabs, setTabs] = useState<TerminalTab[]>([
    { id: "term-1", name: "Terminal 1" },
  ]);
  const [activeTabId, setActiveTabId] = useState<string>("term-1");
  const [commandInput, setCommandInput] = useState<string>("");
  const [executingTabs, setExecutingTabs] = useState<Record<string, boolean>>({});
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState<number>(-1);

  const terminalContainerRef = useRef<HTMLDivElement>(null);
  const termInstanceRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const abortControllersRef = useRef<Record<string, AbortController>>({});
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const processedLogIndexRef = useRef<number>(0);
  const tabCounterRef = useRef<number>(2);

  const isExecuting = Boolean(executingTabs[activeTabId]);

  // ── Initialize Native Xterm.js Instance (Liquid Glass Theme) ──
  useEffect(() => {
    if (!terminalContainerRef.current) return;

    const term = new Terminal({
      theme: COSMIC_OBSIDIAN_PALETTE,
      fontFamily: "var(--font-mono), 'JetBrains Mono', Consolas, monospace",
      fontSize: 12,
      lineHeight: 1.4,
      cursorBlink: true,
      cursorStyle: "bar",
      scrollback: 5000,
      allowTransparency: true,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    term.open(terminalContainerRef.current);

    try {
      fitAddon.fit();
    } catch {}

    term.writeln("\x1b[38;2;34;211;238m[anara-terminal]\x1b[0m Session initialized. Cosmic Obsidian PTY ready.");

    termInstanceRef.current = term;
    fitAddonRef.current = fitAddon;

    // Debounced Resize Observer to prevent PTY wrapping corruption
    let resizeTimer: NodeJS.Timeout;
    const ro = new ResizeObserver(() => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        try {
          fitAddon.fit();
        } catch {}
      }, 50);
    });
    ro.observe(terminalContainerRef.current);
    resizeObserverRef.current = ro;

    return () => {
      clearTimeout(resizeTimer);
      ro.disconnect();
      term.dispose();
      // Terminate any running tab sub-processes on unmount
      Object.values(abortControllersRef.current).forEach((ctrl) => ctrl.abort());
    };
  }, []);

  // Auto-fit xterm canvas whenever visibility is restored (Hermes Desktop keep-alive parity)
  useEffect(() => {
    if (isVisible && fitAddonRef.current) {
      const timer = setTimeout(() => {
        try {
          fitAddonRef.current?.fit();
        } catch {}
      }, 60);
      return () => clearTimeout(timer);
    }
  }, [isVisible]);

  // Append external agent/tool execution logs with pure ANSI escapes
  useEffect(() => {
    if (!termInstanceRef.current) return;
    if (logs.length < processedLogIndexRef.current) {
      processedLogIndexRef.current = 0;
    }
    if (logs.length > processedLogIndexRef.current) {
      const newLines = logs.slice(processedLogIndexRef.current);
      processedLogIndexRef.current = logs.length;
      newLines.forEach((line) => {
        termInstanceRef.current?.writeln(`\x1b[90m[agent]\x1b[0m ${line}`);
      });
    }
  }, [logs]);

  const handleRunCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commandInput.trim()) return;
    const cmd = commandInput.trim();
    const currentTabId = activeTabId;
    const term = termInstanceRef.current;

    setHistory((prev) => [cmd, ...prev.filter((c) => c !== cmd)].slice(0, 50));
    setHistoryIdx(-1);
    setCommandInput("");
    setExecutingTabs((prev) => ({ ...prev, [currentTabId]: true }));

    term?.writeln(`
\n\x1b[38;2;34;211;238manara\x1b[0m \x1b[90m>\x1b[0m ${cmd}`);

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || (typeof window !== "undefined" ? getBackendUrl() : "http://localhost:8000");
    const controller = new AbortController();
    abortControllersRef.current[currentTabId] = controller;

    try {
      const res = await fetch(`${backendUrl}/api/agent/terminal/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmd }),
        signal: controller.signal,
      });

      if (res.ok && res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";

          for (const part of parts) {
            const line = part.trim();
            if (line.startsWith("data:")) {
              try {
                const parsed = JSON.parse(line.slice(5).trim());
                if (parsed.line !== undefined) {
                  term?.writeln(parsed.line);
                } else if (parsed.done) {
                  term?.writeln(`\x1b[90m[Process finished with exit code ${parsed.returncode}]\x1b[0m`);
                } else if (parsed.error) {
                  term?.writeln(`\x1b[38;2;244;63;94m[error]: ${parsed.error}\x1b[0m`);
                }
              } catch {}
            }
          }
        }

        // Flush trailing chunk if present
        if (buffer.trim()) {
          const line = buffer.trim();
          if (line.startsWith("data:")) {
            try {
              const parsed = JSON.parse(line.slice(5).trim());
              if (parsed.line !== undefined) {
                term?.writeln(parsed.line);
              } else if (parsed.done) {
                term?.writeln(`\x1b[90m[Process finished with exit code ${parsed.returncode}]\x1b[0m`);
              }
            } catch {}
          }
        }
      } else {
        term?.writeln(`\x1b[38;2;244;63;94m[HTTP Error]: ${res.status} ${res.statusText}\x1b[0m`);
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        term?.writeln(`\x1b[38;2;244;63;94m[error]: ${err.message || String(err)}\x1b[0m`);
      } else {
        term?.writeln(`\x1b[90m[Process cancelled by user]\x1b[0m`);
      }
    } finally {
      setExecutingTabs((prev) => {
        const copy = { ...prev };
        delete copy[currentTabId];
        return copy;
      });
      delete abortControllersRef.current[currentTabId];
      onExecuteCommand?.(cmd);
    }
  };

  const handleStopExecution = () => {
    const currentController = abortControllersRef.current[activeTabId];
    if (currentController) {
      currentController.abort();
    }
  };

  const handleAddTab = () => {
    const nextIdx = tabCounterRef.current++;
    const newTab: TerminalTab = {
      id: `term-${nextIdx}`,
      name: `Terminal ${nextIdx}`,
    };
    setTabs((prev) => [...prev, newTab]);
    setActiveTabId(newTab.id);
    termInstanceRef.current?.writeln(`
\n\x1b[38;2;34;211;238m[terminal]\x1b[0m Spawned ${newTab.name}.`);
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (history.length === 0) return;
      const nextIdx = Math.min(history.length - 1, historyIdx + 1);
      setHistoryIdx(nextIdx);
      setCommandInput(history[nextIdx] || "");
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIdx <= 0) {
        setHistoryIdx(-1);
        setCommandInput("");
      } else {
        const nextIdx = historyIdx - 1;
        setHistoryIdx(nextIdx);
        setCommandInput(history[nextIdx] || "");
      }
    }
  };

  const handleCloseTab = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (tabs.length <= 1) return;
    if (abortControllersRef.current[id]) {
      abortControllersRef.current[id].abort();
      delete abortControllersRef.current[id];
    }
    setTabs((prev) => prev.filter((t) => t.id !== id));
    if (activeTabId === id) {
      const remaining = tabs.filter((t) => t.id !== id);
      setActiveTabId(remaining[0].id);
    }
  };

  return (
    <div
      className={`w-full h-full flex flex-col bg-[#060913] overflow-hidden font-mono text-xs select-text ${
        embedded ? "rounded-none border-none shadow-none" : "rounded-xl border border-white/[0.08] shadow-xl"
      }`}
    >
      {/* Terminal Tab Bar */}
      <div className="flex items-center justify-between px-3 py-1 bg-[#060913]/95 border-b border-white/[0.08] select-none shrink-0">
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
          {tabs.map((tab) => {
            const isActive = tab.id === activeTabId;
            return (
              <div
                key={tab.id}
                onClick={() => setActiveTabId(tab.id)}
                className={`flex items-center gap-2 px-2.5 py-1 rounded-lg text-[11px] font-mono transition-all cursor-pointer border ${
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
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
            );
          })}
          <button
            type="button"
            onClick={handleAddTab}
            className="p-1 px-1.5 rounded-md text-slate-500 hover:text-white hover:bg-white/10 text-xs transition-colors cursor-pointer"
            title="New Terminal Tab"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {activeTask && (
            <div className="flex items-center gap-1.5 text-[10px] text-cyan-300 bg-cyan-500/10 border border-cyan-400/25 px-2 py-0.5 rounded-md truncate max-w-[200px]">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
              <span className="truncate">{activeTask}</span>
            </div>
          )}
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" title="PTY Connected" />

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

      {/* Native Xterm.js Canvas Host */}
      <div className="flex-1 min-h-0 relative p-2 overflow-hidden bg-[#060913]">
        <div ref={terminalContainerRef} className="w-full h-full" />
      </div>

      {/* Interactive Prompt Command Input */}
      <form
        onSubmit={handleRunCommand}
        className="flex items-center gap-2 px-3 py-2 bg-[#060913]/95 border-t border-white/[0.08]"
      >
        <span className="text-cyan-400 font-bold text-[11px] shrink-0 font-mono">anara &gt;</span>
        <input
          type="text"
          value={commandInput}
          onChange={(e) => setCommandInput(e.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder={isExecuting ? "Executing command..." : "Type terminal command or build script..."}
          disabled={isExecuting}
          className="flex-1 bg-transparent border-none text-xs text-white placeholder:text-slate-600 focus:outline-none font-mono disabled:opacity-50"
        />
        {isExecuting ? (
          <button
            type="button"
            onClick={handleStopExecution}
            className="px-2.5 py-0.5 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 text-[10px] cursor-pointer flex items-center gap-1.5 font-mono"
            title="Cancel terminal process"
          >
            <span className="w-1.5 h-1.5 rounded-sm bg-rose-400" />
            <span>Cancel</span>
          </button>
        ) : commandInput ? (
          <button
            type="submit"
            className="px-2 py-0.5 rounded bg-cyan-500/20 hover:bg-cyan-500/40 text-cyan-200 border border-cyan-400/40 text-[10px] cursor-pointer"
          >
            Enter
          </button>
        ) : null}
      </form>
    </div>
  );
}
