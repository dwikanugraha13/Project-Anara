"use client";

import React, { useState, useEffect, useRef } from "react";
import { getBackendUrl } from "@/lib/apiClient";

export interface EmbeddedPreviewBrowserProps {
  url?: string;
  filePath?: string;
  fileName?: string;
  sessionId?: number | string | null;
  initialMode?: "preview" | "source";
  onClose?: () => void;
  onOpenFileInEditor?: (filePath: string, fileName?: string) => void;
}

export function EmbeddedPreviewBrowser({
  url: initialUrl,
  filePath,
  fileName,
  sessionId,
  initialMode = "preview",
  onClose,
  onOpenFileInEditor,
}: EmbeddedPreviewBrowserProps) {
  const backendUrl = typeof window !== "undefined" ? getBackendUrl() : "http://127.0.0.1:8000";

  // Compute initial target
  const defaultTarget = React.useMemo(() => {
    if (initialUrl && initialUrl.trim()) {
      return initialUrl.trim();
    }
    if (filePath && filePath.trim()) {
      const cleanP = filePath.replace(/\\/g, "/");
      return `${backendUrl}/api/agent/workspace/raw-preview?path=${encodeURIComponent(cleanP)}&session_id=${sessionId || ""}`;
    }
    return "about:blank";
  }, [initialUrl, filePath, sessionId, backendUrl]);

  const [currentUrl, setCurrentUrl] = useState<string>(defaultTarget);
  const [addressInput, setAddressInput] = useState<string>(
    initialUrl || (filePath ? `file:///${filePath.replace(/\\/g, "/")}` : "")
  );
  const [mode, setMode] = useState<"preview" | "source">(initialMode);
  const [isLoading, setIsLoading] = useState(false);
  const [sourceCode, setSourceCode] = useState<string>("");
  const [loadingSource, setLoadingSource] = useState(false);

  const iframeRef = useRef<HTMLIFrameElement>(null);
  const historyRef = useRef<string[]>([defaultTarget]);
  const historyIdxRef = useRef<number>(0);

  // Sync when props change
  useEffect(() => {
    if (defaultTarget && defaultTarget !== currentUrl) {
      setCurrentUrl(defaultTarget);
      setAddressInput(initialUrl || (filePath ? `file:///${filePath.replace(/\\/g, "/")}` : defaultTarget));
      historyRef.current = [defaultTarget];
      historyIdxRef.current = 0;
    }
  }, [defaultTarget, initialUrl, filePath]);

  // Fetch source code if in source mode or for file targets
  useEffect(() => {
    if (mode === "source" && filePath) {
      setLoadingSource(true);
      fetch(`${backendUrl}/api/agent/workspace/file-content?path=${encodeURIComponent(filePath)}&session_id=${sessionId || ""}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data?.content !== undefined) {
            setSourceCode(data.content);
          }
        })
        .catch(() => {})
        .finally(() => setLoadingSource(false));
    }
  }, [mode, filePath, sessionId, backendUrl]);

  const handleNavigate = (target: string) => {
    let clean = target.trim();
    if (!clean) return;

    if (clean.startsWith("file:///")) {
      const relPath = clean.replace(/^file:\/\/\//, "");
      clean = `${backendUrl}/api/agent/workspace/raw-preview?path=${encodeURIComponent(relPath)}&session_id=${sessionId || ""}`;
      setAddressInput(target);
    } else if (!clean.startsWith("http://") && !clean.startsWith("https://") && !clean.startsWith("about:")) {
      clean = `https://${clean}`;
      setAddressInput(clean);
    } else {
      setAddressInput(clean);
    }

    setCurrentUrl(clean);
    historyRef.current = [...historyRef.current.slice(0, historyIdxRef.current + 1), clean];
    historyIdxRef.current = historyRef.current.length - 1;
  };

  const handleBack = () => {
    if (historyIdxRef.current > 0) {
      historyIdxRef.current--;
      const target = historyRef.current[historyIdxRef.current];
      setCurrentUrl(target);
      setAddressInput(target.startsWith(backendUrl) && filePath ? `file:///${filePath}` : target);
    }
  };

  const handleForward = () => {
    if (historyIdxRef.current < historyRef.current.length - 1) {
      historyIdxRef.current++;
      const target = historyRef.current[historyIdxRef.current];
      setCurrentUrl(target);
      setAddressInput(target.startsWith(backendUrl) && filePath ? `file:///${filePath}` : target);
    }
  };

  const handleReload = () => {
    setIsLoading(true);
    if (iframeRef.current) {
      const src = iframeRef.current.src;
      iframeRef.current.src = "";
      setTimeout(() => {
        if (iframeRef.current) iframeRef.current.src = src;
        setIsLoading(false);
      }, 50);
    }
  };

  const canGoBack = historyIdxRef.current > 0;
  const canGoForward = historyIdxRef.current < historyRef.current.length - 1;

  const displayTitle = fileName || (filePath ? filePath.split(/[/\\]/).pop() : "") || "Browser Preview";

  return (
    <div className="flex flex-col h-full w-full bg-[#060913] select-none text-slate-300 font-sans">
      {/* ── TOP BROWSER BAR (Anara Desktop Parity) ── */}
      <div className="h-9 shrink-0 px-2.5 bg-[#080B11] border-b border-white/[0.08] flex items-center justify-between gap-2 z-10">
        {/* Left: Nav actions & Title */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={handleBack}
            disabled={!canGoBack}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:hover:bg-transparent transition-colors cursor-pointer"
            title="Back"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            type="button"
            onClick={handleForward}
            disabled={!canGoForward}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:hover:bg-transparent transition-colors cursor-pointer"
            title="Forward"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
          <button
            type="button"
            onClick={handleReload}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
            title="Reload"
          >
            <svg className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>

        {/* Center: Address Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleNavigate(addressInput);
          }}
          className="flex-1 max-w-xl mx-auto flex items-center"
        >
          <div className="w-full flex items-center h-6 px-2.5 rounded-md bg-white/[0.04] border border-white/[0.08] focus-within:border-cyan-400/50 focus-within:bg-white/[0.06] transition-all">
            <span className="text-slate-500 mr-1.5 text-[10px]">🔒</span>
            <input
              type="text"
              value={addressInput}
              onChange={(e) => setAddressInput(e.target.value)}
              placeholder="Enter URL or file path..."
              className="flex-1 bg-transparent text-[11px] font-mono text-slate-200 outline-none placeholder-slate-600 truncate"
            />
          </div>
        </form>

        {/* Right: Mode Switcher [PREVIEW | SOURCE] + Popout + Close */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Segmented Mode Switcher */}
          <div className="flex items-center p-0.5 rounded-md bg-white/[0.04] border border-white/[0.08] text-[10px] font-mono font-medium">
            <button
              type="button"
              onClick={() => setMode("preview")}
              className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
                mode === "preview"
                  ? "bg-white/[0.1] text-white font-semibold shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              PREVIEW
            </button>
            <button
              type="button"
              onClick={() => setMode("source")}
              className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
                mode === "source"
                  ? "bg-white/[0.1] text-white font-semibold shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              SOURCE
            </button>
          </div>

          {/* External Popout button */}
          <button
            type="button"
            onClick={() => {
              if (addressInput.startsWith("http")) {
                window.open(addressInput, "_blank");
              } else if (currentUrl) {
                window.open(currentUrl, "_blank");
              }
            }}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
            title="Open in default browser"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </button>

          {/* Close Pane */}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
              title="Close Preview Pane"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* ── CONTENT BODY ── */}
      <div className="flex-1 w-full h-full relative overflow-hidden bg-black/40">
        {mode === "preview" ? (
          <iframe
            ref={iframeRef}
            src={currentUrl}
            title={displayTitle}
            className="w-full h-full border-0 bg-white"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
            onLoad={() => setIsLoading(false)}
          />
        ) : (
          <div className="w-full h-full flex flex-col overflow-auto custom-scrollbar p-4 font-mono text-xs select-text bg-[#070B14]">
            {loadingSource ? (
              <div className="flex items-center justify-center h-full text-slate-500">
                <span>Loading source code...</span>
              </div>
            ) : sourceCode ? (
              <pre className="text-slate-200 leading-relaxed whitespace-pre-wrap font-mono">
                {sourceCode}
              </pre>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-2">
                <span>Source preview only available for workspace files.</span>
                {filePath && onOpenFileInEditor && (
                  <button
                    type="button"
                    onClick={() => onOpenFileInEditor(filePath, fileName)}
                    className="px-3 py-1 rounded bg-white/[0.06] hover:bg-white/[0.1] text-cyan-300 text-[11px] transition-colors"
                  >
                    Open in Code Studio
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default EmbeddedPreviewBrowser;
