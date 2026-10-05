"use client";

import React, { useState, useEffect, useRef } from "react";
import ApprovalModePopover, { ApprovalMode, normalizeApprovalMode } from "../statusbar/ApprovalModePopover";
import { BACKEND_URL } from "@/lib/apiClient";

export interface ApprovalModePillProps {
  disabled?: boolean;
  compact?: boolean;
}

export default function ApprovalModePill({ disabled = false, compact = false }: ApprovalModePillProps) {
  const [isOpen, setIsOpen] = useState(false);
  const pillRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<"plan" | "auto" | "off">("auto");

  // Load initial mode from localStorage & backend config
  useEffect(() => {
    try {
      const saved = localStorage.getItem("anara_approval_mode");
      if (saved) {
        setMode(normalizeApprovalMode(saved));
      }
    } catch {}

    fetch(`${BACKEND_URL}/api/config/full`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.config?.approvals?.mode) {
          const mapped = normalizeApprovalMode(data.config.approvals.mode);
          setMode(mapped);
          try {
            localStorage.setItem("anara_approval_mode", mapped);
          } catch {}
        }
      })
      .catch(() => {});
  }, []);

  // Synchronize across windows/tabs
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === "anara_approval_mode" && e.newValue) {
        setMode(normalizeApprovalMode(e.newValue));
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  // Handle outside click & escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (pillRef.current && !pillRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [isOpen]);

  const handleModeChange = (newMode: "plan" | "auto" | "off") => {
    setMode(newMode);
    try {
      localStorage.setItem("anara_approval_mode", newMode);
    } catch {}
    fetch(`${BACKEND_URL}/api/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ "approvals.mode": newMode }),
    }).catch(() => {});
  };

  const MODE_PILL_STYLES: Record<string, { active: string; idle: string; icon: string }> = {
    plan: {
      active: "bg-amber-500/15 border-amber-400/35 text-amber-200",
      idle: "bg-amber-500/8 border-amber-400/20 hover:border-amber-400/35 hover:bg-amber-500/12 text-amber-300 hover:text-amber-200",
      icon: "text-amber-400/70",
    },
    manual: {
      active: "bg-amber-500/15 border-amber-400/35 text-amber-200",
      idle: "bg-amber-500/8 border-amber-400/20 hover:border-amber-400/35 hover:bg-amber-500/12 text-amber-300 hover:text-amber-200",
      icon: "text-amber-400/70",
    },
    auto: {
      active: "bg-sky-500/15 border-sky-400/35 text-sky-200",
      idle: "bg-sky-500/8 border-sky-400/20 hover:border-sky-400/35 hover:bg-sky-500/12 text-sky-300 hover:text-sky-200",
      icon: "text-sky-400/70",
    },
    smart: {
      active: "bg-sky-500/15 border-sky-400/35 text-sky-200",
      idle: "bg-sky-500/8 border-sky-400/20 hover:border-sky-400/35 hover:bg-sky-500/12 text-sky-300 hover:text-sky-200",
      icon: "text-sky-400/70",
    },
    off: {
      active: "bg-rose-500/15 border-rose-400/35 text-rose-200",
      idle: "bg-rose-500/8 border-rose-400/20 hover:border-rose-400/35 hover:bg-rose-500/12 text-rose-300 hover:text-rose-200",
      icon: "text-rose-400/70",
    },
    yolo: {
      active: "bg-rose-500/15 border-rose-400/35 text-rose-200",
      idle: "bg-rose-500/8 border-rose-400/20 hover:border-rose-400/35 hover:bg-rose-500/12 text-rose-300 hover:text-rose-200",
      icon: "text-rose-400/70",
    },
  };

  const currentStyle = MODE_PILL_STYLES[mode] || {
    active: "bg-white/[0.08] border-white/20 text-white",
    idle: "bg-white/[0.03] border-white/[0.08] hover:border-white/[0.16] hover:bg-white/[0.06] text-zinc-300 hover:text-white",
    icon: "text-zinc-500",
  };

  return (
    <div className="relative shrink-0" ref={pillRef}>
      <button
        type="button"
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          e.nativeEvent?.stopImmediatePropagation?.();
          setIsOpen((prev) => !prev);
        }}
        title={`Approval Mode: ${mode.toUpperCase()} (Click to change)`}
        className={`flex items-center gap-1 py-1 rounded-lg border text-[11px] font-medium font-mono transition-colors cursor-pointer select-none ${
          compact ? "px-1.5 text-[10.5px]" : "px-2.5"
        } ${
          isOpen ? currentStyle.active : currentStyle.idle
        }`}
      >
        <span className="font-semibold tracking-tight capitalize">
          {mode}
        </span>
        <svg
          className={`w-3 h-3 transition-transform shrink-0 ${isOpen ? "rotate-180" : ""} ${currentStyle.icon}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      <ApprovalModePopover
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        mode={mode}
        onChange={handleModeChange}
        anchored={true}
        align="right"
      />
    </div>
  );
}
