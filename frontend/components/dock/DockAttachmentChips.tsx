import React from "react";
import type { AttachedItem } from "./BottomDock";

export interface DockAttachmentChipsProps {
  attachedFiles: AttachedItem[];
  onRemove: (index: number) => void;
}

export function DockAttachmentChips({ attachedFiles, onRemove }: DockAttachmentChipsProps) {
  if (!attachedFiles || attachedFiles.length === 0) {
    return null;
  }

  return (
    <div className="w-full flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-1.5 pt-0.5 px-0.5 shrink-0">
      {attachedFiles.map((file, idx) => (
        <div
          key={idx}
          className="flex items-center gap-2 pl-2.5 pr-1.5 py-1 rounded-xl bg-white/[0.06] hover:bg-white/[0.09] border border-white/10 text-xs text-slate-200 transition-all shrink-0 max-w-[220px] sm:max-w-[260px] group shadow-sm"
        >
          <span className="truncate font-mono font-medium text-[11px] text-white">
            {file.name}
          </span>
          <button
            type="button"
            onClick={() => onRemove(idx)}
            className="w-4 h-4 rounded-full flex items-center justify-center text-slate-400 hover:text-rose-300 hover:bg-rose-500/20 transition-all text-[10px] cursor-pointer shrink-0"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
