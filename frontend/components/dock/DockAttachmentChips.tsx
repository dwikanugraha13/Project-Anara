"use client";

import React, { useEffect } from "react";
import type { AttachedItem } from "./BottomDock";

export interface DockAttachmentChipsProps {
  attachedFiles: AttachedItem[];
  onRemove: (index: number) => void;
}

export function DockAttachmentChips({ attachedFiles, onRemove }: DockAttachmentChipsProps) {
  // Cleanup orphaned blob URLs on unmount
  useEffect(() => {
    return () => {
      attachedFiles.forEach((item) => {
        if (item.previewUrl) {
          try {
            URL.revokeObjectURL(item.previewUrl);
          } catch {}
        }
      });
    };
  }, [attachedFiles]);

  if (!attachedFiles || attachedFiles.length === 0) {
    return null;
  }

  const handleRemove = (idx: number) => {
    const target = attachedFiles[idx];
    if (target?.previewUrl) {
      try {
        URL.revokeObjectURL(target.previewUrl);
      } catch {}
    }
    onRemove(idx);
  };

  return (
    <div className="w-full flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-1.5 pt-0.5 px-0.5 shrink-0">
      {attachedFiles.map((file, idx) => {
        const uniqueKey = `${file.name}-${file.sizeKb}-${idx}`;
        return (
          <div
            key={uniqueKey}
            className="flex items-center gap-2 pl-2 pr-1.5 py-1 rounded-xl bg-white/[0.06] hover:bg-white/[0.09] border border-white/10 text-xs text-slate-200 transition-all shrink-0 max-w-[240px] group shadow-sm"
          >
            {file.previewUrl ? (
              <img
                src={file.previewUrl}
                alt={file.name}
                className="w-4 h-4 rounded object-cover border border-white/20 shrink-0"
              />
            ) : (
              <span className="px-1 py-0.2 rounded bg-cyan-500/20 text-cyan-300 font-mono text-[9px] uppercase font-bold shrink-0">
                {file.ext || "FILE"}
              </span>
            )}

            <span className="truncate font-mono font-medium text-[11px] text-white">
              {file.name}
            </span>
            <span className="text-[10px] text-slate-400 font-mono shrink-0">
              {file.sizeKb > 1024 ? `${(file.sizeKb / 1024).toFixed(1)}MB` : `${file.sizeKb}KB`}
            </span>

            <button
              type="button"
              onClick={() => handleRemove(idx)}
              className="w-4 h-4 rounded-full flex items-center justify-center text-slate-400 hover:text-rose-300 hover:bg-rose-500/20 transition-all cursor-pointer shrink-0"
              title="Remove attachment"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        );
      })}
    </div>
  );
}
