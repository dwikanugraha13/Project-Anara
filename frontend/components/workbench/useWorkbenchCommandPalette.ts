"use client";

import { useMemo } from "react";
import type { CommandItem } from "@/components/command/CommandPalette";
import type { AIModelInfo } from "@/components/dock/ModelSelectorDropdown";

export interface UseWorkbenchCommandPaletteProps {
  activeIdeFile: {
    isOpen: boolean;
    fileName: string;
    filePath: string;
    fileExt: string;
    fileSizeKb: number;
    content: string;
    originalContent?: string;
  };
  setActiveIdeFile: React.Dispatch<React.SetStateAction<any>>;
  isTerminalOpen: boolean;
  handleToggleTerminal: (open: boolean) => void;
  interactionMode?: "voice" | "chat";
  onSetInteractionMode?: (mode: "voice" | "chat") => void;
  handleNewSession: () => void;
  setIsBrainDrawerOpen: (open: boolean) => void;
  onClearTranscript?: () => void;
  activeSessionId: number | null;
  models: AIModelInfo[];
  handleSelectModel: (id: string) => void;
  handleOpenFileIDE: (path: string, name: string) => void;
}

export function useWorkbenchCommandPalette({
  activeIdeFile,
  setActiveIdeFile,
  isTerminalOpen,
  handleToggleTerminal,
  interactionMode,
  onSetInteractionMode,
  handleNewSession,
  setIsBrainDrawerOpen,
  onClearTranscript,
  activeSessionId,
  models,
  handleSelectModel,
  handleOpenFileIDE,
}: UseWorkbenchCommandPaletteProps): CommandItem[] {
  return useMemo(() => {
    const items: CommandItem[] = [
      {
        id: "new-session",
        label: "New Chat Session",
        category: "Workstation",
        shortcut: "Ctrl+N",
        onSelect: () => handleNewSession(),
      },
      {
        id: "toggle-editor",
        label: activeIdeFile.isOpen ? "Close Context Editor" : "Open Context Editor",
        category: "Context Panes",
        sublabel: activeIdeFile.fileName || "Workspace code editor",
        shortcut: "Ctrl+\\",
        onSelect: () => {
          if (activeIdeFile.isOpen) {
            setActiveIdeFile((prev: any) => ({ ...prev, isOpen: false }));
          } else if (activeIdeFile.filePath) {
            setActiveIdeFile((prev: any) => ({ ...prev, isOpen: true }));
          } else {
            handleOpenFileIDE("README.md", "README.md");
          }
        },
      },
      {
        id: "toggle-terminal",
        label: isTerminalOpen ? "Hide Terminal Dock" : "Show Terminal Dock",
        category: "Context Panes",
        shortcut: "Ctrl+`",
        onSelect: () => handleToggleTerminal(!isTerminalOpen),
      },
      {
        id: "toggle-mode",
        label: interactionMode === "voice" ? "Switch to Chat Mode (Silent Text)" : "Switch to Voice Mode (3D Avatar)",
        category: "Workstation",
        shortcut: "Ctrl+M",
        onSelect: () => onSetInteractionMode?.(interactionMode === "voice" ? "chat" : "voice"),
      },
      {
        id: "open-brain",
        label: "Anara Brain (Memory, Skills & Providers)",
        category: "Workstation",
        onSelect: () => setIsBrainDrawerOpen(true),
      },
      {
        id: "clear-transcript",
        label: "Clear Conversation Transcript",
        category: "Chat",
        onSelect: () => onClearTranscript?.(),
      },
      {
        id: "open-code-studio",
        label: "Open Fullscreen Anara Code Studio (/code)",
        category: "Navigation",
        onSelect: () => {
          if (typeof window !== "undefined") {
            window.open(activeSessionId ? `/code?session_id=${activeSessionId}` : "/code", "_blank");
          }
        },
      },
    ];

    models.forEach((m) => {
      items.push({
        id: `model-${m.id}`,
        label: `Switch Model: ${m.name || m.id}`,
        category: "AI Models",
        sublabel: m.description,
        onSelect: () => handleSelectModel(m.id),
      });
    });

    return items;
  }, [
    activeIdeFile,
    isTerminalOpen,
    interactionMode,
    models,
    handleNewSession,
    handleToggleTerminal,
    onSetInteractionMode,
    onClearTranscript,
    handleSelectModel,
    handleOpenFileIDE,
    activeSessionId,
    setActiveIdeFile,
    setIsBrainDrawerOpen,
  ]);
}
