"use client";

import React from "react";
import { ContextMenuState } from "./treeUtils";

export interface TreeContextMenuProps {
  contextMenu: ContextMenuState;
  onClose: () => void;
  onPromptNewFile: (targetFolder: string) => void;
  onUploadFiles: () => void;
  onCopyPath: (path: string) => void;
  onPromptDeleteFile: (path: string) => void;
}

/**
 * TreeContextMenu — Liquid Glass contextual right-click menu for Workspace Tree files and folders.
 */
export function TreeContextMenu({
  contextMenu,
  onClose,
  onPromptNewFile,
  onUploadFiles,
  onCopyPath,
  onPromptDeleteFile,
}: TreeContextMenuProps) {
  if (!contextMenu.isOpen) return null;

  return (
    <div
      style={{ top: `${contextMenu.y}px`, left: `${contextMenu.x}px` }}
      className="fixed z-50 w-48 rounded-xl bg-[#060913]/95 backdrop-blur-2xl border border-white/[0.10] shadow-[0_12px_36px_rgba(0,0,0,0.85)] p-1 text-xs font-sans text-slate-200 animate-in fade-in duration-100 select-none"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="px-2 py-1 text-[10px] font-mono text-slate-500 truncate border-b border-white/[0.06] mb-0.5">
        {contextMenu.targetNode ? contextMenu.targetNode.name : "Workspace"}
      </div>

      <button
        type="button"
        onClick={() => {
          onPromptNewFile(contextMenu.isFolder ? contextMenu.targetPath : "");
          onClose();
        }}
        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left hover:bg-white/[0.07] hover:text-white transition-colors cursor-pointer"
      >
        <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 4v16m8-8H4" />
        </svg>
        <span>New File...</span>
      </button>

      <button
        type="button"
        onClick={() => {
          onUploadFiles();
          onClose();
        }}
        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left hover:bg-white/[0.07] hover:text-white transition-colors cursor-pointer"
      >
        <svg className="w-3.5 h-3.5 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
        <span>Upload Files...</span>
      </button>

      {contextMenu.targetPath && (
        <button
          type="button"
          onClick={() => {
            onCopyPath(contextMenu.targetPath);
            onClose();
          }}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left hover:bg-white/[0.07] hover:text-white transition-colors cursor-pointer"
        >
          <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" />
          </svg>
          <span>Copy Path</span>
        </button>
      )}

      {contextMenu.targetNode && contextMenu.targetNode.type === "file" && (
        <>
          <div className="border-t border-white/[0.06] my-1" />
          <button
            type="button"
            onClick={() => {
              onPromptDeleteFile(contextMenu.targetPath);
              onClose();
            }}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-rose-300 hover:bg-rose-500/10 hover:text-rose-200 transition-colors cursor-pointer"
          >
            <svg className="w-3.5 h-3.5 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            <span>Delete File</span>
          </button>
        </>
      )}
    </div>
  );
}
