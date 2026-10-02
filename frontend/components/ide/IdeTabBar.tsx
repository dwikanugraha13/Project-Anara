"use client";

import React from "react";
import type { IdeTabFile } from "./AnaraCodeIDE";

export interface IdeTabBarProps {
  tabs?: IdeTabFile[];
  activeFilePath: string;
  editedContents: Record<string, string>;
  onSelectTab?: (filePath: string, fileName: string) => void;
  onCloseTab?: (filePath: string) => void;
  unsavedCloseTab: IdeTabFile | null;
  onConfirmSaveAndClose: () => void;
  onConfirmDiscardAndClose: () => void;
  onCancelCloseModal: () => void;
  onTabCloseClick: (e: React.MouseEvent, tab: IdeTabFile) => void;
}

/**
 * IdeTabBar — Multi-file tab strip with obsidian styling, active indicator,
 * unsaved dirty state, and tab closure confirmation dialog.
 */
export function IdeTabBar({
  tabs,
  activeFilePath,
  editedContents,
  onSelectTab,
  unsavedCloseTab,
  onConfirmSaveAndClose,
  onConfirmDiscardAndClose,
  onCancelCloseModal,
  onTabCloseClick,
}: IdeTabBarProps) {
  return (
    <>
      {/* ── Confirmation Modal: Unsaved Changes on Tab Close ── */}
      {unsavedCloseTab && (
        <div
          role="dialog"
          aria-modal="true"
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.stopPropagation();
              onCancelCloseModal();
            } else if (e.key === "Enter") {
              e.stopPropagation();
              onConfirmSaveAndClose();
            }
          }}
          tabIndex={-1}
          className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in select-none"
        >
          <div className="w-full max-w-sm p-4.5 rounded-2xl liquid-glass border border-white/15 shadow-2xl space-y-3 font-sans">
            <div className="flex items-start gap-3">
              <span className="w-6 h-6 rounded-full bg-amber-500/20 text-amber-300 border border-amber-400/40 flex items-center justify-center shrink-0 font-bold text-xs mt-0.5 font-mono">
                !
              </span>
              <div className="space-y-1 min-w-0">
                <h4 className="text-xs font-semibold text-white leading-snug">
                  Save changes to <span className="font-mono text-white font-bold">{unsavedCloseTab.fileName}</span>?
                </h4>
                <p className="text-[11px] text-slate-400 leading-relaxed font-sans">
                  Your changes will be lost if you don&apos;t save them.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/10 font-mono text-xs">
              <button
                type="button"
                onClick={onConfirmSaveAndClose}
                className="px-3 py-1.5 rounded-xl bg-cyan-500/25 hover:bg-cyan-500/40 border border-cyan-400/50 text-cyan-100 font-semibold cursor-pointer transition-all active:scale-95"
              >
                Save
              </button>
              <button
                type="button"
                onClick={onConfirmDiscardAndClose}
                className="px-3 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 cursor-pointer transition-all active:scale-95"
              >
                Don&apos;t Save
              </button>
              <button
                type="button"
                onClick={onCancelCloseModal}
                className="px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-slate-400 hover:text-white transition-all cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Multi-File Tab Strip ── */}
      {tabs && tabs.length > 0 && (
        <div className="flex items-center gap-0.5 px-2 pt-1 bg-[#060913]/90 backdrop-blur-2xl border-b border-white/[0.08] overflow-x-auto no-scrollbar font-mono text-xs select-none shrink-0">
          {tabs.map((tab) => {
            const isTabActive = tab.filePath === activeFilePath;
            const tabExt = (tab.fileExt || "").toLowerCase().replace(/^\./, "");
            const tabCode =
              editedContents[tab.filePath] !== undefined
                ? editedContents[tab.filePath]
                : tab.content || "";
            const tabIsDirty = Boolean(tab.isDirty) || tabCode !== (tab.content || "");

            return (
              <div
                key={tab.filePath}
                onClick={() => onSelectTab?.(tab.filePath, tab.fileName)}
                className={`group/tab relative flex items-center gap-2 px-3 py-1.5 rounded-t-md border-t border-x cursor-pointer transition-all duration-150 ${
                  isTabActive
                    ? "bg-[#070b16] border-white/[0.12] text-white font-medium shadow-sm"
                    : "bg-white/[0.02] border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                }`}
                title={tab.filePath}
              >
                {isTabActive && (
                  <div className="absolute top-0 inset-x-0 h-0.5 bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
                )}
                <span className={`text-[9px] font-bold uppercase ${isTabActive ? "text-cyan-400" : "text-slate-500"}`}>
                  {tabExt || "FILE"}
                </span>
                <span className="truncate max-w-[140px] text-[11px]">{tab.fileName}</span>

                <button
                  type="button"
                  onClick={(e) => onTabCloseClick(e, tab)}
                  className="w-4 h-4 rounded flex items-center justify-center hover:bg-white/10 transition-colors cursor-pointer text-[10px] group/tabbtn ml-0.5"
                  title={tabIsDirty ? "Unsaved changes (Click to close)" : "Close tab"}
                >
                  {tabIsDirty ? (
                    <>
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 group-hover/tabbtn:hidden shadow-sm" />
                      <svg className="w-2.5 h-2.5 hidden group-hover/tabbtn:inline text-slate-300 hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </>
                  ) : (
                    <svg className="w-2.5 h-2.5 text-slate-500 hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
