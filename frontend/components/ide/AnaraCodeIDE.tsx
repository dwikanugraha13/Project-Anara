"use client";

import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";
import CodeMirror, { ReactCodeMirrorRef, Extension } from "@uiw/react-codemirror";
import { EditorView } from "@codemirror/view";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";
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
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { php } from "@codemirror/lang-php";
import { json } from "@codemirror/lang-json";
import { html } from "@codemirror/lang-html";
import { css } from "@codemirror/lang-css";

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

function getLanguageExtension(ext: string): Extension {
  const clean = (ext || "").toLowerCase().replace(/^\./, "");
  switch (clean) {
    case "js":
    case "jsx":
    case "mjs":
    case "cjs":
      return javascript({ jsx: true, typescript: false });
    case "ts":
    case "tsx":
      return javascript({ jsx: true, typescript: true });
    case "py":
      return python();
    case "php":
      return php();
    case "json":
      return json();
    case "html":
    case "htm":
      return html();
    case "css":
    case "scss":
    case "less":
      return css();
    default:
      return [];
  }
}

// ── Anara Dark Obsidian Liquid Glass Theme for CodeMirror 6 ──
const anaraObsidianTheme = EditorView.theme(
  {
    "&": {
      color: "#f1f5f9",
      backgroundColor: "#070c18",
      height: "100%",
      fontSize: "12.5px",
      fontFamily: "var(--font-mono), 'JetBrains Mono', Consolas, monospace",
    },
    // Standard professional neutral cursor
    ".cm-content": {
      caretColor: "#f8fafc",
      fontFamily: "var(--font-mono), 'JetBrains Mono', Consolas, monospace",
      lineHeight: "20px",
      padding: "8px 0",
    },
    "&.cm-focused .cm-cursor": {
      borderLeftColor: "#f8fafc !important",
      borderLeftWidth: "1.5px !important",
    },
    "&.cm-focused .cm-selectionBackground, ::selection": {
      backgroundColor: "rgba(255, 255, 255, 0.16) !important",
    },
    // Gutter & Line Numbers seamless Anara Obsidian #070c18
    ".cm-gutters": {
      backgroundColor: "#070c18 !important",
      color: "#475569 !important",
      borderRight: "1px solid rgba(255, 255, 255, 0.08) !important",
      fontSize: "12px",
    },
    ".cm-gutter": {
      backgroundColor: "#070c18 !important",
    },
    ".cm-lineNumbers": {
      backgroundColor: "#070c18 !important",
    },
    ".cm-gutterElement": {
      color: "#475569 !important",
    },
    ".cm-activeLineGutter, .cm-activeLineGutter .cm-gutterElement": {
      backgroundColor: "rgba(255, 255, 255, 0.04) !important",
      color: "#f8fafc !important",
      fontWeight: "600 !important",
    },
    ".cm-activeLine": {
      backgroundColor: "rgba(255, 255, 255, 0.03) !important",
    },
    // Minimalist Obsidian Scrollbar
    ".cm-scroller": {
      overflow: "auto",
      fontFamily: "var(--font-mono), 'JetBrains Mono', Consolas, monospace",
      scrollbarWidth: "thin",
      scrollbarColor: "rgba(255, 255, 255, 0.18) transparent",
    },
    ".cm-scroller::-webkit-scrollbar": {
      width: "6px",
      height: "6px",
    },
    ".cm-scroller::-webkit-scrollbar-track": {
      background: "#070c18 !important",
    },
    ".cm-scroller::-webkit-scrollbar-thumb": {
      background: "rgba(255, 255, 255, 0.16) !important",
      borderRadius: "9999px !important",
    },
    ".cm-scroller::-webkit-scrollbar-thumb:hover": {
      background: "rgba(34, 211, 238, 0.45) !important",
    },
    // Clean search highlights in text
    ".cm-searchMatch": {
      backgroundColor: "rgba(255, 215, 0, 0.25) !important",
      outline: "1px solid rgba(255, 215, 0, 0.4) !important",
      borderRadius: "2px",
    },
    ".cm-searchMatch.cm-searchMatch-selected": {
      backgroundColor: "rgba(255, 255, 255, 0.25) !important",
      outline: "1px solid rgba(255, 255, 255, 0.5) !important",
    },
  },
  { dark: true }
);

// ── 100% Faithful VS Code Dark+ TextMate Syntax Highlighting Palette ──
const vsCodeDarkPlusHighlightStyle = HighlightStyle.define([
  // Keywords (function, class, public, private, static, use, var, const, let, etc.) -> VS Code Blue
  { tag: [t.keyword, t.modifier, t.processingInstruction, t.meta, t.definitionKeyword], color: "#569cd6" },
  // Control flow keywords (if, else, return, for, while, do, switch, case, break, namespace) -> VS Code Purple
  { tag: [t.controlKeyword, t.moduleKeyword], color: "#c586c0" },
  // Functions & Methods (get, post, group, render, execute, etc.) -> VS Code Soft Yellow
  { tag: [t.function(t.variableName), t.function(t.propertyName), t.function(t.definition(t.variableName)), t.function(t.name)], color: "#dcdcaa" },
  // Variables & Properties ($routes, $var, object.property) -> VS Code Light Sky Blue
  { tag: [t.definition(t.variableName), t.variableName, t.propertyName, t.attributeName, t.special(t.propertyName)], color: "#9cdcfe" },
  // Strings ('auth/login', "text", template strings) -> VS Code Warm Terracotta Amber
  { tag: [t.string, t.special(t.string), t.docString, t.character, t.attributeValue], color: "#ce9178" },
  // Numbers (100, 3.14, 0) -> VS Code Pale Sage Green
  { tag: [t.number, t.integer, t.float], color: "#b5cea8" },
  // Booleans & Null (true, false, null) -> VS Code Blue
  { tag: [t.bool, t.null], color: "#569cd6" },
  // Classes, Types, Interfaces, Namespaces & Names (RouteCollection, BaseFilters, string, array) -> VS Code Teal
  { tag: [t.typeName, t.className, t.namespace, t.standard(t.typeName), t.name], color: "#4ec9b0" },
  // Comments (// Auth, /** @var ... */) -> VS Code Forest Green Italic
  { tag: [t.comment, t.lineComment, t.blockComment, t.docComment], color: "#6a9955", fontStyle: "italic" },
  // Operators & Punctuation (->, =>, ::, =, ;, ,, .) -> VS Code Off-White
  { tag: [t.operator, t.punctuation, t.derefOperator, t.separator, t.updateOperator, t.arithmeticOperator, t.compareOperator, t.definitionOperator, t.logicOperator, t.bitwiseOperator], color: "#d4d4d4" },
  // Brackets, Parentheses & Braces -> VS Code Bracket Gold
  { tag: [t.paren, t.brace, t.squareBracket, t.bracket], color: "#ffd700" },
]);

export default function AnaraCodeIDE({
  isOpen,
  onClose,
  fileName,
  filePath,
  fileExt,
  fileSizeKb,
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
  const [viewMode, setViewMode] = useState<"code" | "diff">(originalContent ? "diff" : "code");
  const [editedContents, setEditedContents] = useState<Record<string, string>>({});
  const isCodeHydratedRef = useRef(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("anara_ide_edited_contents");
      if (saved) {
        setEditedContents(JSON.parse(saved));
      }
    } catch {}
    isCodeHydratedRef.current = true;
  }, []);

  useEffect(() => {
    if (!isCodeHydratedRef.current) return;
    try {
      if (Object.keys(editedContents).length > 0) {
        localStorage.setItem("anara_ide_edited_contents", JSON.stringify(editedContents));
      } else {
        localStorage.removeItem("anara_ide_edited_contents");
      }
    } catch {}
  }, [editedContents]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [unsavedCloseTab, setUnsavedCloseTab] = useState<IdeTabFile | null>(null);

  // Floating Professional Find & Replace State
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

  // Active in-memory code buffer for current file
  const activeCode = editedContents[filePath] !== undefined ? editedContents[filePath] : (content || "");
  const isDirty = activeCode !== (content || "");

  // File path segmentation for breadcrumb
  const normPath = (filePath || fileName || "").replace(/\\/g, "/");
  const cleanName = normPath.split("/").pop() || fileName || "berkas";
  const dirPath = normPath.includes("/") ? normPath.substring(0, normPath.lastIndexOf("/") + 1) : "";

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

  const handleSave = useCallback(async () => {
    if (!onSaveFile || !filePath) return;
    setIsSaving(true);
    try {
      const ok = await onSaveFile(filePath, activeCode);
      if (ok) {
        setEditedContents((prev) => {
          const copy = { ...prev };
          delete copy[filePath];
          return copy;
        });
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2500);
      }
    } finally {
      setIsSaving(false);
    }
  }, [activeCode, filePath, onSaveFile]);

  // Global Keyboard shortcuts: Ctrl+F, Ctrl+H, Escape, Ctrl+S
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Ctrl + F / Cmd + F
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        handleOpenSearch(false);
        return;
      }

      // Ctrl + H / Cmd + H
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "h") {
        e.preventDefault();
        handleOpenSearch(true);
        return;
      }

      // Escape to close search
      if (e.key === "Escape" && isFindOpen) {
        e.preventDefault();
        handleCloseSearch();
        return;
      }

      // Ctrl + S / Cmd + S to save
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        handleSave();
        return;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isFindOpen, handleOpenSearch, handleCloseSearch, handleSave]);

  // Handle click on tab close (✕) button
  const handleTabCloseClick = (e: React.MouseEvent, tab: IdeTabFile) => {
    e.stopPropagation();
    const tabCode = editedContents[tab.filePath] !== undefined ? editedContents[tab.filePath] : (tab.content || "");
    const isDirtyTab = tabCode !== (tab.content || "");

    if (isDirtyTab) {
      setUnsavedCloseTab(tab);
    } else {
      onCloseTab?.(tab.filePath);
    }
  };

  // Confirm Save and Close
  const handleConfirmSaveAndClose = async () => {
    if (!unsavedCloseTab) return;
    const targetPath = unsavedCloseTab.filePath;
    const targetCode = editedContents[targetPath] !== undefined ? editedContents[targetPath] : (unsavedCloseTab.content || "");
    if (onSaveFile) {
      await onSaveFile(targetPath, targetCode);
    }
    setEditedContents((prev) => {
      const copy = { ...prev };
      delete copy[targetPath];
      return copy;
    });
    const target = unsavedCloseTab;
    setUnsavedCloseTab(null);
    onCloseTab?.(target.filePath);
  };

  // Confirm Discard Changes and Close
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
        <span className="px-1 py-0.2 rounded bg-indigo-500/20 text-indigo-300 font-mono text-[9px] font-bold shrink-0">
          PHP
        </span>
      );
    }
    if (ext === "ts" || ext === "tsx") {
      return (
        <span className="px-1 py-0.2 rounded bg-blue-500/20 text-blue-300 font-mono text-[9px] font-bold shrink-0">
          TS
        </span>
      );
    }
    if (ext === "js" || ext === "jsx") {
      return (
        <span className="px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 font-mono text-[9px] font-bold shrink-0">
          JS
        </span>
      );
    }
    return (
      <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
      </svg>
    );
  };

  // Diff stats count
  const diffCounts = useMemo(() => {
    if (!originalContent) return { added: 0, deleted: 0 };
    const orig = originalContent.split("\n");
    const curr = activeCode.split("\n");
    let added = 0;
    let deleted = 0;
    const origSet = new Set(orig);
    const currSet = new Set(curr);
    for (const c of curr) {
      if (!origSet.has(c)) added++;
    }
    for (const o of orig) {
      if (!currSet.has(o)) deleted++;
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
    }
    return list;
  }, [fileExt, viewMode, originalContent]);

  if (!isOpen && !embedded) return null;

  const editorContent = (
    <div
      className={`w-full h-full overflow-hidden flex flex-col text-white relative ${
        embedded
          ? "rounded-none border-none shadow-none bg-transparent"
          : "rounded-2xl liquid-glass border border-white/10 shadow-[0_0_60px_rgba(0,0,0,0.9)] max-h-[850px]"
      }`}
    >
      {/* ── Confirmation Modal: Unsaved Changes on Tab Close ── */}
      {unsavedCloseTab && (
        <div className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in select-none">
          <div className="w-full max-w-sm p-4.5 rounded-2xl liquid-glass border border-white/15 shadow-2xl space-y-3 font-sans">
            <div className="flex items-start gap-3">
              <span className="w-6 h-6 rounded-full bg-amber-500/20 text-amber-300 border border-amber-400/40 flex items-center justify-center shrink-0 font-bold text-xs mt-0.5 font-mono">
                !
              </span>
              <div className="space-y-1 min-w-0">
                <h4 className="text-xs font-semibold text-white leading-snug">
                  Ingin menyimpan perubahan pada <span className="font-mono text-white font-bold">{unsavedCloseTab.fileName}</span>?
                </h4>
                <p className="text-[11px] text-slate-400 leading-relaxed font-sans">
                  Perubahan Anda akan hilang jika Anda tidak menyimpannya.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/10 font-mono text-xs">
              <button
                type="button"
                onClick={handleConfirmSaveAndClose}
                className="px-3 py-1.5 rounded-xl bg-cyan-500/25 hover:bg-cyan-500/40 border border-cyan-400/50 text-cyan-100 font-semibold cursor-pointer transition-all active:scale-95"
              >
                Simpan
              </button>
              <button
                type="button"
                onClick={handleConfirmDiscardAndClose}
                className="px-3 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 cursor-pointer transition-all active:scale-95"
              >
                Jangan Simpan
              </button>
              <button
                type="button"
                onClick={() => setUnsavedCloseTab(null)}
                className="px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-slate-400 hover:text-white transition-all cursor-pointer"
              >
                Batal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Multi-File Tab Strip (VS Code / OpenCode style) ── */}
      {tabs && tabs.length > 0 && (
        <div className="flex items-center gap-1 px-2 pt-1 bg-black/60 border-b border-white/10 overflow-x-auto no-scrollbar font-mono text-xs select-none shrink-0">
          {tabs.map((tab) => {
            const isTabActive = tab.filePath === filePath;
            const tabExt = (tab.fileExt || "").toLowerCase().replace(/^\./, "");
            const tabCode = editedContents[tab.filePath] !== undefined ? editedContents[tab.filePath] : (tab.content || "");
            const tabIsDirty = tabCode !== (tab.content || "");

            return (
              <div
                key={tab.filePath}
                onClick={() => onSelectTab?.(tab.filePath, tab.fileName)}
                className={`group/tab flex items-center gap-2 px-2.5 py-1 rounded-t-lg border-t border-x cursor-pointer transition-all duration-150 ${
                  isTabActive
                    ? "bg-slate-900/95 border-white/20 text-white font-medium shadow-inner"
                    : "bg-white/[0.02] border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                }`}
                title={tab.filePath}
              >
                <span className={`text-[9.5px] font-bold uppercase ${isTabActive ? "text-slate-400" : "text-slate-500"}`}>
                  {tabExt || "FILE"}
                </span>
                <span className="truncate max-w-[120px] text-[11px]">{tab.fileName}</span>

                {onCloseTab && (
                  <button
                    type="button"
                    onClick={(e) => handleTabCloseClick(e, tab)}
                    className="w-4 h-4 rounded flex items-center justify-center hover:bg-white/20 transition-colors cursor-pointer text-[10px] group/tabbtn ml-0.5"
                    title={tabIsDirty ? "Ada perubahan belum disimpan (Klik untuk tutup)" : "Tutup tab"}
                  >
                    {tabIsDirty ? (
                      <>
                        <span className="w-2 h-2 rounded-full bg-slate-300 group-hover/tabbtn:hidden shadow-sm" />
                        <span className="hidden group-hover/tabbtn:inline text-slate-300 hover:text-white">✕</span>
                      </>
                    ) : (
                      <span className="text-slate-500 hover:text-white">✕</span>
                    )}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── VS Code / OpenCode Clean Header: Breadcrumb, Diff Stats, Status ── */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-black/50 border-b border-white/10 font-mono text-xs select-none shrink-0">
        {/* Left: Status Badge M/A + Language Icon + File Name & Path */}
        <div className="flex items-center gap-2 min-w-0 flex-1 pr-2">
          <span
            className={`px-1 py-0.2 rounded font-bold text-[10px] shrink-0 ${
              isDirty
                ? "bg-amber-500/20 text-amber-300 border border-amber-400/40"
                : originalContent
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-400/40"
                : "bg-emerald-500/20 text-emerald-300 border border-emerald-400/40"
            }`}
          >
            {isDirty ? "M" : originalContent ? "M" : "A"}
          </span>

          {renderLanguageSvgIcon()}

          <div className="flex items-baseline gap-1.5 truncate">
            <span className="font-bold text-slate-100 text-xs truncate" title={cleanName}>
              {cleanName}
            </span>
            {dirPath && (
              <span className="text-[11px] text-slate-500 truncate" title={dirPath}>
                {dirPath}
              </span>
            )}
          </div>

          {/* Diff Stats (+X -Y) */}
          {originalContent && (diffCounts.added > 0 || diffCounts.deleted > 0) && (
            <div className="flex items-center gap-1.5 ml-2 font-mono text-[10.5px] shrink-0">
              <span className="text-emerald-400 font-bold">+{diffCounts.added}</span>
              <span className="text-rose-400 font-bold">-{diffCounts.deleted}</span>
            </div>
          )}

          {/* Save Status Notification */}
          {saveSuccess ? (
            <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold text-emerald-300 bg-emerald-500/15 border border-emerald-400/30 shrink-0 ml-1">
              ✓ Tersimpan
            </span>
          ) : isDirty ? (
            <span className="w-1.5 h-1.5 rounded-full bg-slate-300 shadow-sm shrink-0 ml-1" title="Perubahan belum disimpan (Ctrl+S untuk simpan)" />
          ) : null}
        </div>

        {/* Right: Search, Copy, Close */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={() => handleOpenSearch(false)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded-lg border text-xs font-medium font-mono cursor-pointer transition-all ${
              isFindOpen
                ? "bg-white/15 border-white/30 text-white shadow-[0_0_12px_rgba(255,255,255,0.1)]"
                : "bg-white/[0.04] hover:bg-white/10 border-white/10 text-slate-400 hover:text-white"
            }`}
            title="Cari kata / Cari & Ganti (Ctrl + F)"
          >
            <svg className="w-3 h-3 text-current" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="text-[10px]">Cari</span>
          </button>

          <button
            type="button"
            onClick={handleCopy}
            className="px-2 py-0.5 rounded-lg bg-white/[0.04] hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white text-xs font-medium font-mono cursor-pointer transition-all"
            title="Salin isi berkas"
          >
            {copied ? "✓ Tersalin" : "Salin"}
          </button>

          {!embedded && (
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-xl bg-white/10 hover:bg-rose-500/30 hover:text-rose-200 text-slate-400 border border-white/10 transition-all cursor-pointer ml-1"
              title="Tutup IDE Inspector"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* ── Modern CodeMirror 6 Engine with Floating Professional Search Bar ── */}
      <div className="flex-1 w-full h-full overflow-hidden bg-[#070c18] relative">
        {/* ── Professional Floating Find & Replace Widget ── */}
        {isFindOpen && (
          <div className="absolute top-2 right-4 z-40 flex flex-col gap-1.5 p-2 rounded-xl bg-[#070c18]/95 backdrop-blur-2xl border border-white/15 shadow-[0_16px_40px_rgba(0,0,0,0.85)] font-mono text-xs animate-fade-in select-none max-w-md">
            {/* Row 1: Chevron toggle, Find input with inline option toggles, Count, Arrows, Close */}
            <div className="flex items-center gap-1.5">
              {/* Toggle Expand Replace */}
              <button
                type="button"
                onClick={() => setIsReplaceOpen((prev) => !prev)}
                className="w-5 h-5 flex items-center justify-center rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer text-xs shrink-0"
                title={isReplaceOpen ? "Sembunyikan baris Ganti (Replace)" : "Tampilkan baris Ganti (Replace)"}
              >
                <span className={`transform transition-transform text-[10px] ${isReplaceOpen ? "rotate-90" : ""}`}>▶</span>
              </button>

              {/* Find Input with embedded option pills */}
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
                  placeholder="Cari kata..."
                  className="bg-transparent text-slate-100 text-xs outline-none w-36 sm:w-44 pr-16 placeholder:text-slate-500 font-mono"
                />

                {/* Option toggles (Aa, \\b, .*) inside the input */}
                <div className="absolute right-1.5 flex items-center gap-0.5">
                  <button
                    type="button"
                    onClick={() => setCaseSensitive((c) => !c)}
                    className={`px-1 py-0.2 rounded text-[10px] font-bold transition-all cursor-pointer ${
                      caseSensitive ? "bg-white/20 text-white border border-white/40" : "text-slate-500 hover:text-slate-300"
                    }`}
                    title="Cocokkan Huruf Besar/Kecil (Match Case - Aa)"
                  >
                    Aa
                  </button>
                  <button
                    type="button"
                    onClick={() => setWholeWord((w) => !w)}
                    className={`px-1 py-0.2 rounded text-[10px] font-bold transition-all cursor-pointer ${
                      wholeWord ? "bg-white/20 text-white border border-white/40" : "text-slate-500 hover:text-slate-300"
                    }`}
                    title="Cocokkan Seluruh Kata (Whole Word - \\b)"
                  >
                    \b
                  </button>
                  <button
                    type="button"
                    onClick={() => setUseRegex((r) => !r)}
                    className={`px-1 py-0.2 rounded text-[10px] font-bold transition-all cursor-pointer ${
                      useRegex ? "bg-white/20 text-white border border-white/40" : "text-slate-500 hover:text-slate-300"
                    }`}
                    title="Gunakan Regular Expression (.*)"
                  >
                    .*
                  </button>
                </div>
              </div>

              {/* Match count badge */}
              <span className="text-[11px] text-slate-400 min-w-[50px] text-center font-mono shrink-0">
                {searchQuery ? `${matchCount > 0 ? currentMatch : 0} of ${matchCount}` : "0 of 0"}
              </span>

              {/* Previous match (↑) */}
              <button
                type="button"
                onClick={handleFindPrevious}
                className="w-6 h-6 flex items-center justify-center rounded-lg bg-white/[0.05] hover:bg-white/15 text-slate-300 hover:text-white border border-white/10 transition-colors cursor-pointer text-xs shrink-0"
                title="Sebelumnya (Shift + Enter)"
              >
                ↑
              </button>

              {/* Next match (↓) */}
              <button
                type="button"
                onClick={handleFindNext}
                className="w-6 h-6 flex items-center justify-center rounded-lg bg-white/[0.05] hover:bg-white/15 text-slate-300 hover:text-white border border-white/10 transition-colors cursor-pointer text-xs shrink-0"
                title="Berikutnya (Enter)"
              >
                ↓
              </button>

              {/* Close button (✕) */}
              <button
                type="button"
                onClick={handleCloseSearch}
                className="w-6 h-6 flex items-center justify-center rounded-lg hover:bg-rose-500/25 hover:text-rose-200 text-slate-400 transition-colors cursor-pointer text-xs shrink-0 ml-0.5"
                title="Tutup (Escape)"
              >
                ✕
              </button>
            </div>

            {/* Row 2: Replace row (when expanded) */}
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
                  placeholder="Ganti dengan..."
                  className="bg-[#030712] border border-white/20 focus:border-white/50 focus:ring-1 focus:ring-white/20 rounded-lg px-2 py-1 text-slate-100 text-xs outline-none w-36 sm:w-44 placeholder:text-slate-500 font-mono"
                />

                <button
                  type="button"
                  onClick={handleReplaceNext}
                  className="px-2 py-1 rounded-lg bg-white/[0.06] hover:bg-white/15 text-slate-300 hover:text-white border border-white/10 text-[11px] font-medium transition-colors cursor-pointer"
                  title="Ganti satu kecocokan aktif"
                >
                  Ganti
                </button>

                <button
                  type="button"
                  onClick={handleReplaceAll}
                  className="px-2 py-1 rounded-lg bg-white/[0.06] hover:bg-white/15 text-slate-300 hover:text-white border border-white/10 text-[11px] font-medium transition-colors cursor-pointer"
                  title="Ganti semua kecocokan di berkas"
                >
                  Semua
                </button>
              </div>
            )}
          </div>
        )}

        <CodeMirror
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
            searchKeymap: false, // Use our floating professional UI instead of default panel
            foldKeymap: true,
            completionKeymap: true,
            lintKeymap: true,
          }}
          onChange={(val) => {
            setEditedContents((prev) => ({ ...prev, [filePath]: val ?? "" }));
          }}
        />
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
