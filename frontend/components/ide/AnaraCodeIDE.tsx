"use client";

import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";
import CodeMirror, { ReactCodeMirrorRef, Extension } from "@uiw/react-codemirror";
import { EditorView } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { syntaxHighlighting } from "@codemirror/language";
import {
  search,
  SearchQuery,
  setSearchQuery as setCmSearchQuery,
  findNext,
  findPrevious,
  replaceNext,
  replaceAll,
} from "@codemirror/search";
import { unifiedMergeView } from "@codemirror/merge";
import AgentMarkdown from "../chat/AgentMarkdown";
import { getBackendUrl } from "@/lib/apiClient";
import {
  getLanguageExtension,
  anaraObsidianTheme,
  vsCodeDarkPlusHighlightStyle,
} from "./editorTheme";
import { IdeTabBar } from "./IdeTabBar";
import { IdeToolbar } from "./IdeToolbar";

export interface IdeTabFile {
  filePath: string;
  fileName: string;
  fileExt: string;
  fileSizeKb: number;
  content: string;
  originalContent?: string;
  isDirty?: boolean;
}

export interface AnaraCodeIDEProps {
  isOpen: boolean;
  onClose: () => void;
  fileName: string;
  filePath: string;
  fileExt: string;
  fileSizeKb: number;
  content: string;
  originalContent?: string;
  onAskAnara?: (filePath: string, fileName: string) => void;
  embedded?: boolean;
  isTerminalOpen?: boolean;
  onToggleTerminal?: () => void;
  tabs?: IdeTabFile[];
  onSelectTab?: (filePath: string, fileName: string) => void;
  onCloseTab?: (filePath: string) => void;
  onSaveFile?: (filePath: string, newContent: string) => Promise<boolean>;
}

export default function AnaraCodeIDE({
  isOpen,
  onClose,
  fileName,
  filePath,
  fileExt,
  content,
  originalContent,
  onAskAnara,
  embedded = false,
  isTerminalOpen = false,
  onToggleTerminal,
  tabs = [],
  onSelectTab,
  onCloseTab,
  onSaveFile,
}: AnaraCodeIDEProps) {
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<"code" | "diff" | "preview">("code");
  const [editedContents, setEditedContents] = useState<Record<string, string>>({});
  const isCodeHydratedRef = useRef(false);
  const [hasDiskConflict, setHasDiskConflict] = useState(false);
  const baselineSnapshotRef = useRef<string>(content || "");

  // Synchronize view mode on file switch (auto-preview for Markdown)
  useEffect(() => {
    const ext = (fileExt || "").toLowerCase();
    setViewMode(ext === ".md" || ext === "md" ? "preview" : "code");
    baselineSnapshotRef.current = content || "";
    setHasDiskConflict(false);
  }, [filePath, fileExt, content]);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("anara_ide_edited_contents");
      if (saved) {
        setEditedContents(JSON.parse(saved));
      }
    } catch {}
    isCodeHydratedRef.current = true;
  }, []);

  // Debounced non-blocking session storage persistence (1500ms delay) to prevent main-thread freeze
  useEffect(() => {
    if (!isCodeHydratedRef.current) return;
    const timer = setTimeout(() => {
      try {
        if (Object.keys(editedContents).length > 0) {
          sessionStorage.setItem("anara_ide_edited_contents", JSON.stringify(editedContents));
        } else {
          sessionStorage.removeItem("anara_ide_edited_contents");
        }
      } catch {}
    }, 1500);
    return () => clearTimeout(timer);
  }, [editedContents]);

  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [unsavedCloseTab, setUnsavedCloseTab] = useState<IdeTabFile | null>(null);

  // Floating Find & Replace State
  const [isFindOpen, setIsFindOpen] = useState(false);
  const [isReplaceOpen, setIsReplaceOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [replaceQuery, setReplaceQuery] = useState("");
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [wholeWord, setWholeWord] = useState(false);
  const [useRegex, setUseRegex] = useState(false);
  const [matchCount, setMatchCount] = useState(0);
  const [currentMatch, setCurrentMatch] = useState(0);

  const findInputRef = useRef<HTMLInputElement>(null);
  const cmRef = useRef<ReactCodeMirrorRef>(null);
  const editorContainerRef = useRef<HTMLDivElement>(null);

  // Active in-memory code buffer for current file
  const activeCode = editedContents[filePath] !== undefined ? editedContents[filePath] : (content || "");
  const isDirty = activeCode !== (content || "");

  // File path segmentation for breadcrumb
  const normPath = (filePath || fileName || "").replace(/\\/g, "/");
  const cleanName = normPath.split("/").pop() || fileName || "file";
  const dirPath = normPath.includes("/") ? normPath.substring(0, normPath.lastIndexOf("/")) : "";

  const handleCopy = () => {
    navigator.clipboard.writeText(activeCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Sync Search Query & Compute Matches
  const syncSearchQuery = useCallback(
    (customSearch?: string) => {
      const view = cmRef.current?.view;
      const targetQuery = customSearch !== undefined ? customSearch : searchQuery;
      if (!view) return;

      if (!targetQuery) {
        view.dispatch({ effects: setCmSearchQuery.of(new SearchQuery({ search: "" })) });
        setMatchCount(0);
        setCurrentMatch(0);
        return;
      }

      try {
        const query = new SearchQuery({
          search: targetQuery,
          replace: replaceQuery,
          caseSensitive,
          wholeWord,
          regexp: useRegex,
        });
        view.dispatch({ effects: setCmSearchQuery.of(query) });

        const cursor = query.getCursor(view.state);
        let count = 0;
        let currentIdx = 0;
        const curFrom = view.state.selection.main.from;
        let m;
        while (!(m = cursor.next()).done) {
          count++;
          if (m.value.from <= curFrom) {
            currentIdx = count;
          }
          if (count >= 1000) break;
        }
        setMatchCount(count);
        setCurrentMatch(count > 0 ? (currentIdx === 0 ? 1 : currentIdx) : 0);
      } catch (err) {
        setMatchCount(0);
        setCurrentMatch(0);
      }
    },
    [searchQuery, replaceQuery, caseSensitive, wholeWord, useRegex]
  );

  useEffect(() => {
    if (isFindOpen) {
      syncSearchQuery();
    }
  }, [isFindOpen, syncSearchQuery]);

  const handleOpenSearch = useCallback(
    (openReplace = false) => {
      setIsFindOpen(true);
      if (openReplace) setIsReplaceOpen(true);

      const view = cmRef.current?.view;
      if (view) {
        const sel = view.state.sliceDoc(view.state.selection.main.from, view.state.selection.main.to);
        if (sel && sel.trim().length > 0 && sel.length < 80) {
          setSearchQuery(sel);
          syncSearchQuery(sel);
        }
      }
      setTimeout(() => {
        findInputRef.current?.focus();
        findInputRef.current?.select();
      }, 50);
    },
    [syncSearchQuery]
  );

  const handleCloseSearch = useCallback(() => {
    setIsFindOpen(false);
    const view = cmRef.current?.view;
    if (view) {
      view.dispatch({ effects: setCmSearchQuery.of(new SearchQuery({ search: "" })) });
      view.focus();
    }
  }, []);

  const handleFindNext = useCallback(() => {
    const view = cmRef.current?.view;
    if (!view) return;
    findNext(view);
    syncSearchQuery();
  }, [syncSearchQuery]);

  const handleFindPrevious = useCallback(() => {
    const view = cmRef.current?.view;
    if (!view) return;
    findPrevious(view);
    syncSearchQuery();
  }, [syncSearchQuery]);

  const handleReplaceNext = useCallback(() => {
    const view = cmRef.current?.view;
    if (!view) return;
    replaceNext(view);
    syncSearchQuery();
  }, [syncSearchQuery]);

  const handleReplaceAll = useCallback(() => {
    const view = cmRef.current?.view;
    if (!view) return;
    replaceAll(view);
    syncSearchQuery();
  }, [syncSearchQuery]);

  const handleSave = useCallback(async (forceOverwrite?: boolean | unknown) => {
    if (!onSaveFile || !filePath) return;
    const isForce = forceOverwrite === true;

    // Stale-on-disk conflict guard
    if (!isForce) {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || (typeof window !== "undefined" ? getBackendUrl() : "http://localhost:8000");
        const checkRes = await fetch(`${backendUrl}/api/agent/workspace/file-content?path=${encodeURIComponent(filePath)}`);
        if (checkRes.ok) {
          const diskData = await checkRes.json();
          if (diskData.content !== undefined && baselineSnapshotRef.current && diskData.content !== baselineSnapshotRef.current) {
            setHasDiskConflict(true);
            return;
          }
        }
      } catch {}
    }

    setIsSaving(true);
    try {
      const ok = await onSaveFile(filePath, activeCode);
      if (ok) {
        setEditedContents((prev) => {
          const copy = { ...prev };
          delete copy[filePath];
          return copy;
        });
        baselineSnapshotRef.current = activeCode;
        setHasDiskConflict(false);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2500);
      }
    } finally {
      setIsSaving(false);
    }
  }, [activeCode, filePath, onSaveFile]);

  // Handle tab closing (with unsaved check)
  const handleTabClose = useCallback(
    (tab: IdeTabFile) => {
      const tabCode = editedContents[tab.filePath] !== undefined ? editedContents[tab.filePath] : (tab.content || "");
      const isDirtyTab = Boolean(tab.isDirty) || tabCode !== (tab.content || "");

      if (isDirtyTab) {
        setUnsavedCloseTab(tab);
      } else {
        setEditedContents((prev) => {
          if (prev[tab.filePath] === undefined) return prev;
          const copy = { ...prev };
          delete copy[tab.filePath];
          return copy;
        });
        onCloseTab?.(tab.filePath);
      }
    },
    [editedContents, onCloseTab]
  );

  // Global Keyboard shortcuts: Ctrl+F, Ctrl+H, Escape, Ctrl+S
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const activeEl = document.activeElement;
      const isInput = activeEl?.tagName === "INPUT" || activeEl?.tagName === "TEXTAREA";
      const isInsideIde = editorContainerRef.current?.contains(activeEl) || false;

      if (isInput && !isInsideIde && !isFindOpen) {
        return;
      }

      // Ctrl + F
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
        if (isInsideIde || isFindOpen) {
          e.preventDefault();
          handleOpenSearch(false);
          return;
        }
      }

      // Ctrl + H
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "h") {
        if (isInsideIde || isFindOpen) {
          e.preventDefault();
          handleOpenSearch(true);
          return;
        }
      }

      // Escape to close search
      if (e.key === "Escape" && isFindOpen) {
        e.preventDefault();
        handleCloseSearch();
        return;
      }

      // Ctrl + S to save
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        if (isInsideIde) {
          e.preventDefault();
          handleSave();
          return;
        }
      }

      // Ctrl + W to close current tab
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "w") {
        if (isInsideIde && filePath) {
          e.preventDefault();
          const activeTab = tabs?.find((t) => t.filePath === filePath);
          if (activeTab) {
            handleTabClose(activeTab);
          } else {
            onCloseTab?.(filePath);
          }
          return;
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isFindOpen, handleOpenSearch, handleCloseSearch, handleSave, filePath, tabs, handleTabClose]);

  const handleTabCloseClick = (e: React.MouseEvent, tab: IdeTabFile) => {
    e.stopPropagation();
    handleTabClose(tab);
  };

  const handleConfirmSaveAndClose = async () => {
    if (!unsavedCloseTab) return;
    const targetPath = unsavedCloseTab.filePath;
    const targetCode = editedContents[targetPath] !== undefined ? editedContents[targetPath] : (unsavedCloseTab.content || "");
    try {
      if (onSaveFile) {
        const ok = await onSaveFile(targetPath, targetCode);
        if (ok === false) return;
      }
      setEditedContents((prev) => {
        const copy = { ...prev };
        delete copy[targetPath];
        return copy;
      });
      const target = unsavedCloseTab;
      setUnsavedCloseTab(null);
      onCloseTab?.(target.filePath);
    } catch (err) {
      console.error("[IDE] Failed to save file before closing:", err);
    }
  };

  const handleConfirmDiscardAndClose = () => {
    if (!unsavedCloseTab) return;
    const targetPath = unsavedCloseTab.filePath;
    setEditedContents((prev) => {
      const copy = { ...prev };
      delete copy[targetPath];
      return copy;
    });
    const target = unsavedCloseTab;
    setUnsavedCloseTab(null);
    onCloseTab?.(target.filePath);
  };

  // SVG Language Icons
  const renderLanguageSvgIcon = () => {
    const ext = (fileExt || "").toLowerCase().replace(/^\./, "");
    if (ext === "py") {
      return (
        <svg className="w-3.5 h-3.5 text-amber-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
          <path d="M11.927 0c-3.414 0-5.467.568-5.467 2.457v2.107h5.467v.702h-7.66C1.94 5.266 0 7.37 0 9.873c0 2.502 1.637 4.545 4.267 4.545h1.2v-2.107c0-2.046 1.76-3.864 3.867-3.864h5.467V6.32c0-1.89-2.053-2.457-5.467-2.457h2.592V0h-2.592zm-2.07 1.405a.703.703 0 110 1.406.703.703 0 010-1.406zm2.143 14.05v2.107c0 2.046-1.76 3.864-3.867 3.864H2.666v2.126c0 1.889 2.053 2.457 5.467 2.457h2.592v3.864h-2.592c3.414 0 5.467-.568 5.467-2.457v-2.107H8.133v-.702h7.66c2.327 0 4.267-2.104 4.267-4.607 0-2.502-1.637-4.545-4.267-4.545h-1.2v2.107zm2.07 7.135a.703.703 0 110-1.406.703.703 0 010 1.406z" />
        </svg>
      );
    }
    if (ext === "php") {
      return (
        <span className="px-1 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono text-[9px] font-bold shrink-0">
          PHP
        </span>
      );
    }
    if (ext === "ts" || ext === "tsx") {
      return (
        <span className="px-1 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono text-[9px] font-bold shrink-0">
          TS
        </span>
      );
    }
    if (ext === "js" || ext === "jsx") {
      return (
        <span className="px-1 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono text-[9px] font-bold shrink-0">
          JS
        </span>
      );
    }
    return (
      <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    );
  };

  // Diff stats count
  const diffCounts = useMemo(() => {
    if (!originalContent || originalContent === activeCode) return { added: 0, deleted: 0 };
    const cr = String.fromCharCode(13);
    const origLines = originalContent.split("\n").map((l) => (l.endsWith(cr) ? l.slice(0, -1) : l));
    const currLines = activeCode.split("\n").map((l) => (l.endsWith(cr) ? l.slice(0, -1) : l));
    if (origLines.join("\n") === currLines.join("\n")) return { added: 0, deleted: 0 };

    const origFreq = new Map<string, number>();
    for (const l of origLines) origFreq.set(l, (origFreq.get(l) || 0) + 1);

    let added = 0;
    const origRemaining = new Map(origFreq);
    for (const l of currLines) {
      const c = origRemaining.get(l) || 0;
      if (c > 0) {
        origRemaining.set(l, c - 1);
      } else {
        added++;
      }
    }

    const currFreq = new Map<string, number>();
    for (const l of currLines) currFreq.set(l, (currFreq.get(l) || 0) + 1);

    let deleted = 0;
    const currRemaining = new Map(currFreq);
    for (const l of origLines) {
      const c = currRemaining.get(l) || 0;
      if (c > 0) {
        currRemaining.set(l, c - 1);
      } else {
        deleted++;
      }
    }
    return { added, deleted };
  }, [activeCode, originalContent]);

  // CodeMirror Extensions
  const extensions = useMemo<Extension[]>(() => {
    const list: Extension[] = [
      getLanguageExtension(fileExt),
      search({ top: true }),
      EditorView.lineWrapping,
    ];
    if (viewMode === "diff" && originalContent) {
      list.push(...unifiedMergeView({ original: originalContent, mergeControls: false }));
      list.push(EditorView.editable.of(false));
      list.push(EditorState.readOnly.of(true));
    }
    return list;
  }, [fileExt, viewMode, originalContent]);

  if (!isOpen && !embedded) return null;

  const editorContent = (
    <div
      ref={editorContainerRef}
      className={`w-full h-full overflow-hidden flex flex-col text-white relative ${
        embedded
          ? "rounded-none border-none shadow-none bg-transparent"
          : "rounded-2xl liquid-glass border border-white/10 shadow-[0_0_60px_rgba(0,0,0,0.9)] max-h-[850px]"
      }`}
    >
      {/* ── Multi-File Tab Strip & Unsaved Dialog ── */}
      <IdeTabBar
        tabs={tabs}
        activeFilePath={filePath}
        editedContents={editedContents}
        onSelectTab={onSelectTab}
        unsavedCloseTab={unsavedCloseTab}
        onConfirmSaveAndClose={handleConfirmSaveAndClose}
        onConfirmDiscardAndClose={handleConfirmDiscardAndClose}
        onCancelCloseModal={() => setUnsavedCloseTab(null)}
        onTabCloseClick={handleTabCloseClick}
      />

      {/* ── Antigravity Studio Clean Breadcrumbs & Toolbar ── */}
      <IdeToolbar
        filePath={filePath}
        cleanName={cleanName}
        dirPath={dirPath}
        fileExt={fileExt}
        isDirty={isDirty}
        originalContent={originalContent}
        activeCode={activeCode}
        viewMode={viewMode}
        setViewMode={setViewMode}
        diffCounts={diffCounts}
        saveSuccess={saveSuccess}
        isSaving={isSaving}
        handleSave={handleSave}
        onSaveFile={onSaveFile}
        onAskAnara={onAskAnara}
        isTerminalOpen={isTerminalOpen}
        onToggleTerminal={onToggleTerminal}
        isFindOpen={isFindOpen}
        handleOpenSearch={handleOpenSearch}
        handleCopy={handleCopy}
        copied={copied}
        embedded={embedded}
        onClose={onClose}
        renderLanguageSvgIcon={renderLanguageSvgIcon}
      />

      {/* ── Modern CodeMirror 6 Engine with Floating Professional Search Bar ── */}
      <div className="flex-1 w-full h-full overflow-hidden bg-[#070b16] relative">
        {/* Stale on Disk Conflict Warning */}
        {hasDiskConflict && (
          <div className="absolute top-0 inset-x-0 z-50 px-3 py-2 bg-amber-950/95 border-b border-amber-400/50 flex items-center justify-between text-xs text-amber-200 backdrop-blur-xl animate-fade-in font-mono">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-amber-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>File changed on disk by agent or external edit!</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleSave(true)}
                className="px-2.5 py-1 rounded-md bg-amber-500 hover:bg-amber-400 text-black font-semibold text-[11px] transition-colors cursor-pointer"
              >
                Overwrite
              </button>
              <button
                type="button"
                onClick={() => setHasDiskConflict(false)}
                className="px-2.5 py-1 rounded-md bg-white/10 hover:bg-white/20 text-white text-[11px] transition-colors cursor-pointer"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* ── Professional Floating Find & Replace Widget ── */}
        {isFindOpen && (
          <div className="absolute top-2 right-4 z-40 flex flex-col gap-1.5 p-2 rounded-xl bg-[#070b16]/95 backdrop-blur-2xl border border-white/15 shadow-[0_16px_40px_rgba(0,0,0,0.85)] font-mono text-xs animate-fade-in select-none max-w-md">
            {/* Row 1: Find input with option toggles, Count, Arrows, Close */}
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setIsReplaceOpen((prev) => !prev)}
                className="w-5 h-5 flex items-center justify-center rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer text-xs shrink-0"
                title={isReplaceOpen ? "Hide Replace row" : "Show Replace row"}
              >
                <svg className={`w-2.5 h-2.5 transform transition-transform ${isReplaceOpen ? "rotate-90" : ""}`} fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              </button>

              <div className="relative flex items-center bg-[#030712] border border-white/20 focus-within:border-white/50 focus-within:ring-1 focus-within:ring-white/20 rounded-lg px-2 py-1 transition-all">
                <input
                  ref={findInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      if (e.shiftKey) handleFindPrevious();
                      else handleFindNext();
                    } else if (e.key === "Escape") {
                      e.preventDefault();
                      handleCloseSearch();
                    }
                  }}
                  placeholder="Find text..."
                  className="bg-transparent text-slate-100 text-xs outline-none w-36 sm:w-44 pr-16 placeholder:text-slate-500 font-mono"
                />

                <div className="absolute right-1.5 flex items-center gap-0.5">
                  <button
                    type="button"
                    onClick={() => setCaseSensitive((c) => !c)}
                    className={`px-1 py-0.2 rounded text-[10px] font-bold transition-all cursor-pointer ${
                      caseSensitive ? "bg-white/20 text-white border border-white/40" : "text-slate-500 hover:text-slate-300"
                    }`}
                    title="Match Case (Aa)"
                  >
                    Aa
                  </button>
                  <button
                    type="button"
                    onClick={() => setWholeWord((w) => !w)}
                    className={`px-1 py-0.2 rounded text-[10px] font-bold transition-all cursor-pointer ${
                      wholeWord ? "bg-white/20 text-white border border-white/40" : "text-slate-500 hover:text-slate-300"
                    }`}
                    title="Match Whole Word (\\b)"
                  >
                    \b
                  </button>
                  <button
                    type="button"
                    onClick={() => setUseRegex((r) => !r)}
                    className={`px-1 py-0.2 rounded text-[10px] font-bold transition-all cursor-pointer ${
                      useRegex ? "bg-white/20 text-white border border-white/40" : "text-slate-500 hover:text-slate-300"
                    }`}
                    title="Use Regular Expression (.*)"
                  >
                    .*
                  </button>
                </div>
              </div>

              <span className="text-[11px] text-slate-400 min-w-[50px] text-center font-mono shrink-0">
                {searchQuery ? `${matchCount > 0 ? currentMatch : 0} of ${matchCount}` : "0 of 0"}
              </span>

              <button
                type="button"
                onClick={handleFindPrevious}
                className="w-6 h-6 flex items-center justify-center rounded-lg bg-white/[0.05] hover:bg-white/15 text-slate-300 hover:text-white border border-white/10 transition-colors cursor-pointer text-xs shrink-0"
                title="Previous (Shift + Enter)"
              >
                <svg className="w-3 h-3 text-current" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                </svg>
              </button>

              <button
                type="button"
                onClick={handleFindNext}
                className="w-6 h-6 flex items-center justify-center rounded-lg bg-white/[0.05] hover:bg-white/15 text-slate-300 hover:text-white border border-white/10 transition-colors cursor-pointer text-xs shrink-0"
                title="Next (Enter)"
              >
                <svg className="w-3 h-3 text-current" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              <button
                type="button"
                onClick={handleCloseSearch}
                className="w-6 h-6 flex items-center justify-center rounded-lg hover:bg-rose-500/25 hover:text-rose-200 text-slate-400 transition-colors cursor-pointer text-xs shrink-0 ml-0.5"
                title="Close (Escape)"
              >
                <svg className="w-3 h-3 text-current" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Row 2: Replace row */}
            {isReplaceOpen && (
              <div className="flex items-center gap-1.5 pl-6 pt-0.5 animate-fade-in">
                <input
                  type="text"
                  value={replaceQuery}
                  onChange={(e) => setReplaceQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleReplaceNext();
                    } else if (e.key === "Escape") {
                      e.preventDefault();
                      handleCloseSearch();
                    }
                  }}
                  placeholder="Replace with..."
                  className="bg-[#030712] border border-white/20 focus:border-white/50 focus:ring-1 focus:ring-white/20 rounded-lg px-2 py-1 text-slate-100 text-xs outline-none w-36 sm:w-44 placeholder:text-slate-500 font-mono"
                />

                <button
                  type="button"
                  onClick={handleReplaceNext}
                  className="px-2 py-1 rounded-lg bg-white/[0.06] hover:bg-white/15 text-slate-300 hover:text-white border border-white/10 text-[11px] font-medium transition-colors cursor-pointer"
                  title="Replace current match"
                >
                  Replace
                </button>

                <button
                  type="button"
                  onClick={handleReplaceAll}
                  className="px-2 py-1 rounded-lg bg-white/[0.06] hover:bg-white/15 text-slate-300 hover:text-white border border-white/10 text-[11px] font-medium transition-colors cursor-pointer"
                  title="Replace all matches in file"
                >
                  All
                </button>
              </div>
            )}
          </div>
        )}

        {/* Markdown Rendered Mode Viewport */}
        {viewMode === "preview" && (fileExt === ".md" || fileExt === "md") ? (
          <div className="h-full overflow-y-auto p-4 custom-scrollbar bg-[#070b16] text-slate-200">
            <AgentMarkdown content={activeCode} />
          </div>
        ) : (
          <CodeMirror
            key={filePath}
            ref={cmRef}
            value={activeCode}
            height="100%"
            className="h-full w-full"
            theme={[anaraObsidianTheme, syntaxHighlighting(vsCodeDarkPlusHighlightStyle)]}
            extensions={extensions}
            basicSetup={{
              lineNumbers: true,
              foldGutter: true,
              dropCursor: true,
              allowMultipleSelections: true,
              indentOnInput: true,
              bracketMatching: true,
              closeBrackets: true,
              autocompletion: true,
              rectangularSelection: true,
              crosshairCursor: true,
              highlightActiveLine: true,
              highlightSelectionMatches: true,
              closeBracketsKeymap: true,
              searchKeymap: false,
              foldKeymap: true,
              completionKeymap: true,
              lintKeymap: true,
            }}
            onChange={(val) => {
              setEditedContents((prev) => ({ ...prev, [filePath]: val ?? "" }));
            }}
          />
        )}
      </div>
    </div>
  );

  if (embedded) {
    return editorContent;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/75 backdrop-blur-xl animate-fade-in select-none">
      <div className="relative w-full max-w-5xl h-[85vh]">
        {editorContent}
      </div>
    </div>
  );
}
