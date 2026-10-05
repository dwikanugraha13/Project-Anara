"use client";

import React, { useRef, useLayoutEffect, useEffect } from "react";
import { DockAttachmentChips } from "./DockAttachmentChips";
import DockTriggerPopover, { TriggerItem } from "./DockTriggerPopover";
import type { AttachedItem } from "./BottomDock";

export interface DockComposerInputProps {
  inputMessage: string;
  setInputMessage: (val: string) => void;
  attachedFiles: AttachedItem[];
  setAttachedFiles: React.Dispatch<React.SetStateAction<AttachedItem[]>>;
  isInputExpanded: boolean;
  setIsInputExpanded: React.Dispatch<React.SetStateAction<boolean>>;
  isInputOverflowed: boolean;
  setIsInputOverflowed: React.Dispatch<React.SetStateAction<boolean>>;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  onSubmit: (e?: React.FormEvent) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onPaste: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void;
  triggerKind: "@" | "/" | null;
  triggerQuery: string;
  triggerSelectedIndex: number;
  setTriggerSelectedIndex: (idx: number) => void;
  isTriggerPopoverOpen: boolean;
  onSelectTriggerItem: (item: TriggerItem) => void;
  onCloseTriggerPopover: () => void;
  workspaceFiles: Array<{ path: string; name: string; isDir?: boolean }>;
  onClearAttachments: () => void;
  handleTextareaChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
}

const useIsomorphicLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

/**
 * DockComposerInput — Auto-resizing textarea with multimodal autocomplete (@ and / triggers),
 * attachment preview chips, and fullscreen expand toggle.
 */
export function DockComposerInput({
  inputMessage,
  setInputMessage,
  attachedFiles,
  setAttachedFiles,
  isInputExpanded,
  setIsInputExpanded,
  isInputOverflowed,
  setIsInputOverflowed,
  textareaRef,
  onSubmit,
  onKeyDown,
  onPaste,
  triggerKind,
  triggerQuery,
  triggerSelectedIndex,
  setTriggerSelectedIndex,
  isTriggerPopoverOpen,
  onSelectTriggerItem,
  onCloseTriggerPopover,
  workspaceFiles,
  onClearAttachments,
  handleTextareaChange,
}: DockComposerInputProps) {
  // Single-pass layout auto-resize
  useIsomorphicLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el || isInputExpanded) return;
    if (!inputMessage) {
      el.style.height = "26px";
      el.style.overflowY = "hidden";
      setIsInputOverflowed(false);
      return;
    }
    el.style.height = "auto";
    const scrollH = el.scrollHeight;
    const nextH = Math.min(scrollH, 180);
    el.style.height = `${nextH}px`;
    el.style.overflowY = scrollH > 180 ? "auto" : "hidden";
    setIsInputOverflowed(scrollH > 180);
  }, [inputMessage, isInputExpanded, textareaRef, setIsInputOverflowed]);

  return (
    <div className={`w-full flex flex-col gap-1.5 relative ${isInputExpanded ? "h-full flex-1 min-h-0" : ""}`}>
      {/* Attachment Previews */}
      <DockAttachmentChips
        attachedFiles={attachedFiles}
        onRemove={(idx) => setAttachedFiles((prev) => prev.filter((_, i) => i !== idx))}
      />

      {/* Multimodal Trigger Popover (@ Mentions & / Slash Commands) */}
      <DockTriggerPopover
        isOpen={isTriggerPopoverOpen}
        triggerKind={triggerKind}
        query={triggerQuery}
        onSelect={onSelectTriggerItem}
        onClose={onCloseTriggerPopover}
        workspaceFiles={workspaceFiles}
        selectedIndex={triggerSelectedIndex}
        onSelectedIndexChange={setTriggerSelectedIndex}
      />

      {/* Textarea Form */}
      <form
        onSubmit={onSubmit}
        className={`w-full flex ${isInputExpanded ? "h-full flex-1 min-h-0 items-stretch" : "items-stretch"} gap-1.5`}
      >
        <div className={`flex-1 min-w-0 flex flex-col ${isInputExpanded ? "h-full min-h-0" : ""}`}>
          <textarea
            ref={textareaRef as any}
            rows={1}
            value={inputMessage}
            onChange={handleTextareaChange}
            onKeyDown={onKeyDown}
            onPaste={onPaste}
            placeholder="Start with a goal... (type '/' for commands, '@' for files)"
            className={`w-full bg-transparent border-none py-0.5 px-1 text-xs sm:text-[13px] text-white placeholder:text-slate-500 focus:outline-none font-sans resize-none custom-scrollbar leading-relaxed ${
              isInputOverflowed || isInputExpanded ? "overflow-y-auto" : "overflow-hidden"
            } ${isInputExpanded ? "flex-1 h-full max-h-none" : ""}`}
            style={isInputExpanded ? { minHeight: "140px" } : { maxHeight: "180px", minHeight: "26px" }}
            autoFocus
          />
        </div>

        {/* Fullscreen Expand / Clear buttons */}
        {(isInputOverflowed || isInputExpanded || inputMessage) && (
          <div className={`shrink-0 flex flex-col items-center ${isInputOverflowed || isInputExpanded ? "justify-between" : "justify-end"} py-0.5`}>
            {(isInputOverflowed || isInputExpanded) && (
              <button
                type="button"
                onClick={() => setIsInputExpanded((v) => !v)}
                className="w-6 h-6 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer active:scale-95"
                title={isInputExpanded ? "Collapse input" : "Expand input"}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  {isInputExpanded ? (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9L4 4m0 0l5 0m-5 0l0 5m6 6l5 5m0 0l-5 0m5 0l0-5" />
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5m-6 6l-5 5m0 0h4m-4 0v-4m16 4l-5-5m5 5v-4m0 4h-4" />
                  )}
                </svg>
              </button>
            )}
            {inputMessage && (
              <button
                type="button"
                onClick={() => {
                  setInputMessage("");
                  onClearAttachments();
                  if (textareaRef.current) textareaRef.current.style.height = "auto";
                  setIsInputExpanded(false);
                }}
                className="w-6 h-6 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-200 hover:bg-white/10 transition-all text-xs cursor-pointer active:scale-95"
                title="Clear message"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        )}
      </form>
    </div>
  );
}
