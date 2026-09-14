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
}

export default function WorkbenchTerminal({
  logs = [],
  activeTask,
  onExecuteCommand,
  onClose,
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

  // Auto-append incoming live agent tool/build logs
  useEffect(() => {
    if (logs.length > 0) {
      setTabs((prev) =>
        prev.map((t) => {
          if (t.id === "term-1") {
            const existing = new Set(t.lines);
            const newLines = logs.filter((l) => !existing.has(l));
            if (newLines.length > 0) {
              return { ...t, lines: [...t.lines, ...newLines] };
            }
          }
          return t;
        })
      );
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
                  newLines.push(parsed.line);
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
                      lines: [...t.lines, ...newLines].slice(-300),
                    }
                  : t
              )
            );
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
    <div className="w-full h-full flex flex-col bg-slate-950/90 rounded-2xl border border-white/10 overflow-hidden font-mono text-xs shadow-xl select-text">
      {/* Terminal Tab Bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-black/50 border-b border-white/10 select-none">
        <div className="flex items-center gap-1 overflow-x-auto custom-scrollbar">
          {tabs.map((tab) => {
            const isActive = tab.id === activeTabId;
            return (
              <div
                key={tab.id}
                onClick={() => setActiveTabId(tab.id)}
                className={`flex items-center gap-2 px-2.5 py-1 rounded-lg text-[11px] transition-all cursor-pointer border ${
                  isActive
                    ? "bg-white/10 text-cyan-200 border-cyan-400/40 shadow-[0_0_8px_rgba(34,211,238,0.15)]"
                    : "text-slate-400 hover:text-slate-200 border-transparent hover:bg-white/[0.04]"
                }`}
              >
                <span>{tab.name}</span>
                {tabs.length > 1 && (
                  <button
                    type="button"
                    onClick={(e) => handleCloseTab(tab.id, e)}
                    className="text-slate-500 hover:text-rose-400 text-[10px]"
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
            className="p-1 px-2 rounded-lg text-slate-500 hover:text-white hover:bg-white/10 text-xs transition-colors"
            title="Buka tab terminal baru"
          >
            ＋
          </button>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {activeTask && (
            <div className="flex items-center gap-1.5 text-[10px] text-amber-300 bg-amber-500/15 border border-amber-400/30 px-2 py-0.5 rounded-md truncate max-w-[200px]">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
              <span className="truncate">{activeTask}</span>
            </div>
          )}

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="px-2 py-0.5 rounded-md bg-white/5 hover:bg-white/15 text-slate-400 hover:text-white border border-white/10 text-[10px] font-mono transition-all cursor-pointer flex items-center gap-1"
              title="Tutup Panel Terminal"
            >
              <span>✕</span>
              <span>Tutup</span>
            </button>
          )}
        </div>
      </div>

      {/* Terminal Output Body */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-1 text-slate-300">
        {activeTab.lines.map((line, idx) => {
          const isCmd = line.startsWith("$");
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
        className="flex items-center gap-2 px-3 py-1.5 bg-black/60 border-t border-white/10"
      >
        <span className="text-cyan-400 font-bold text-[11px] shrink-0 font-mono">PS &gt;</span>
        <input
          type="text"
          value={commandInput}
          onChange={(e) => setCommandInput(e.target.value)}
          placeholder={isExecuting ? "Menjalankan perintah..." : "Ketik perintah terminal atau instruksi build..."}
          disabled={isExecuting}
          className="flex-1 bg-transparent border-none text-xs text-white placeholder:text-slate-600 focus:outline-none font-mono disabled:opacity-50"
        />
        {isExecuting ? (
          <button
            type="button"
            onClick={handleStopExecution}
            className="px-2.5 py-0.5 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 text-[10px] cursor-pointer flex items-center gap-1 font-mono"
            title="Batalkan proses terminal"
          >
            <span>■</span>
            <span>Batal</span>
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
