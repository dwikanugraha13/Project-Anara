"use client";

import React, { useState, useEffect, useRef } from "react";

export interface TerminalTab {
  id: string;
  name: string;
  lines: string[];
}

export interface WorkbenchTerminalProps {
  logs?: string[];
  activeTask?: string;
  onExecuteCommand?: (cmd: string) => void;
  onClose?: () => void;
  embedded?: boolean;
}

export default function WorkbenchTerminal({
  logs = [],
  activeTask,
  onExecuteCommand,
  onClose,
  embedded = true,
}: WorkbenchTerminalProps) {
  const [tabs, setTabs] = useState<TerminalTab[]>([
    {
      id: "term-1",
      name: "Terminal 1",
      lines: [
        "[anara-agent] Initializing autonomous workbench...",
        "[system] Workspace mounted. Ready for plan & build execution.",
      ],
    },
    {
      id: "term-2",
      name: "Terminal 2",
      lines: [
        "[worker] Sub-agent background daemon listening on WebSocket...",
      ],
    },
  ]);
  const [activeTabId, setActiveTabId] = useState<string>("term-1");
  const [commandInput, setCommandInput] = useState<string>("");
  const [isExecuting, setIsExecuting] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const processedLogIndexRef = useRef<number>(0);

  // Strip ANSI escape codes safely for clean visual rendering
  const stripAnsi = (text: string) =>
    text.replace(/[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g, "");

  // Auto-append incoming live agent tool/build logs without dropping duplicates
  useEffect(() => {
    if (logs.length > processedLogIndexRef.current) {
      const newLines = logs.slice(processedLogIndexRef.current).map(stripAnsi);
      processedLogIndexRef.current = logs.length;
      if (newLines.length > 0) {
        setTabs((prev) =>
          prev.map((t) => {
            if (t.id === "term-1") {
              return { ...t, lines: [...t.lines, ...newLines].slice(-1000) };
            }
            return t;
          })
        );
      }
    }
  }, [logs]);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [tabs, activeTabId]);

  const activeTab = tabs.find((t) => t.id === activeTabId) || tabs[0];

  const handleRunCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commandInput.trim()) return;
    const cmd = commandInput.trim();
    setCommandInput("");
    setIsExecuting(true);

    setTabs((prev) =>
      prev.map((t) =>
        t.id === activeTabId
          ? {
              ...t,
              lines: [...t.lines, `PS> ${cmd}`],
            }
          : t
      )
    );

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    const controller = new AbortController();
    abortControllerRef.current = controller;

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

          const newLines: string[] = [];
          for (const part of parts) {
            const line = part.trim();
            if (line.startsWith("data:")) {
              try {
                const parsed = JSON.parse(line.slice(5).trim());
                if (parsed.line !== undefined) {
                  newLines.push(stripAnsi(parsed.line));
                } else if (parsed.done) {
                  newLines.push(`[Process finished with exit code ${parsed.returncode}]`);
                } else if (parsed.error) {
                  newLines.push(`[error]: ${parsed.error}`);
                }
              } catch {}
            }
          }

          if (newLines.length > 0) {
            setTabs((prev) =>
              prev.map((t) =>
                t.id === activeTabId
                  ? {
                      ...t,
                      lines: [...t.lines, ...newLines].slice(-1000),
                    }
                  : t
              )
            );
          }
        }

        // Flush trailing chunk if present
        if (buffer.trim()) {
          const line = buffer.trim();
          if (line.startsWith("data:")) {
            try {
              const parsed = JSON.parse(line.slice(5).trim());
              const trailing: string[] = [];
              if (parsed.line !== undefined) {
                trailing.push(stripAnsi(parsed.line));
              } else if (parsed.done) {
                trailing.push(`[Process finished with exit code ${parsed.returncode}]`);
              }
              if (trailing.length > 0) {
                setTabs((prev) =>
                  prev.map((t) =>
                    t.id === activeTabId
                      ? { ...t, lines: [...t.lines, ...trailing].slice(-1000) }
                      : t
                  )
                );
              }
            } catch {}
          }
        }
      } else {
        setTabs((prev) =>
          prev.map((t) =>
            t.id === activeTabId
              ? {
                  ...t,
                  lines: [...t.lines, `[HTTP Error]: ${res.status} ${res.statusText}`],
                }
              : t
          )
        );
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        setTabs((prev) =>
          prev.map((t) =>
            t.id === activeTabId
              ? {
                  ...t,
                  lines: [...t.lines, `[error]: ${err.message || String(err)}`],
                }
              : t
          )
        );
      } else {
        setTabs((prev) =>
          prev.map((t) =>
            t.id === activeTabId
              ? {
                  ...t,
                  lines: [...t.lines, "[Process cancelled by user]"],
                }
              : t
          )
        );
      }
    } finally {
      setIsExecuting(false);
      abortControllerRef.current = null;
      onExecuteCommand?.(cmd);
    }
  };

  const handleStopExecution = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const handleAddTab = () => {
    const nextIdx = tabs.length + 1;
    const newTab: TerminalTab = {
      id: `term-${nextIdx}`,
      name: `Terminal ${nextIdx}`,
      lines: [`[terminal] Spawned session ${nextIdx}...`],
    };
    setTabs((prev) => [...prev, newTab]);
    setActiveTabId(newTab.id);
  };

  const handleCloseTab = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (tabs.length <= 1) return;
    setTabs((prev) => prev.filter((t) => t.id !== id));
    if (activeTabId === id) {
      const remaining = tabs.filter((t) => t.id !== id);
      setActiveTabId(remaining[0].id);
    }
  };

  return (
    <div
      className={`w-full h-full flex flex-col bg-[#050811] overflow-hidden font-mono text-xs select-text ${
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
                    className="text-slate-500 hover:text-rose-400 text-[10px] ml-0.5 cursor-pointer"
                  >
                    ✕
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
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
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
              <span>✕</span>
              <span>Close</span>
            </button>
          )}
        </div>
      </div>

      {/* Terminal Output Body */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-1 text-slate-300 font-mono text-[11.5px] leading-relaxed">
        {activeTab.lines.map((line, idx) => {
          const isCmd = line.startsWith("$") || line.startsWith("PS >") || line.startsWith("PS>");
          const isWarn = line.includes("WARNING") || line.includes("warn") || line.includes("503");
          const isErr = line.includes("ERROR") || line.includes("Error") || line.includes("400") || line.includes("429");
          const isOk = line.includes("SUCCESS") || line.includes("200") || line.includes("✓");

          return (
            <div
              key={idx}
              className={`leading-relaxed whitespace-pre-wrap break-all ${
                isCmd
                  ? "text-cyan-300 font-bold"
                  : isErr
                  ? "text-rose-300"
                  : isWarn
                  ? "text-amber-300"
                  : isOk
                  ? "text-emerald-300"
                  : "text-slate-400"
              }`}
            >
              {line}
            </div>
          );
        })}
        <div ref={terminalEndRef} />
      </div>

      {/* Terminal Command Input Prompt */}
      <form
        onSubmit={handleRunCommand}
        className="flex items-center gap-2 px-3 py-1.5 bg-[#060913]/95 border-t border-white/[0.08]"
      >
        <span className="text-cyan-400 font-bold text-[11px] shrink-0 font-mono">anara &gt;</span>
        <input
          type="text"
          value={commandInput}
          onChange={(e) => setCommandInput(e.target.value)}
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
            <span className="w-1.5 h-1.5 rounded-xs bg-rose-400" />
            <span>Cancel</span>
          </button>
        ) : commandInput ? (
          <button
            type="submit"
            className="px-2 py-0.5 rounded bg-cyan-500/20 hover:bg-cyan-500/40 text-cyan-200 border border-cyan-400/40 text-[10px] cursor-pointer"
          >
            Enter ↵
          </button>
        ) : null}
      </form>
    </div>
  );
}
