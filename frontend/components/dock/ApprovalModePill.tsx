"use client";

import React, { useState, useEffect, useRef } from "react";
import ApprovalModePopover, { ApprovalMode } from "../statusbar/ApprovalModePopover";
import { BACKEND_URL } from "@/lib/apiClient";

export interface ApprovalModePillProps {
  disabled?: boolean;
}

export default function ApprovalModePill({ disabled = false }: ApprovalModePillProps) {
  const [isOpen, setIsOpen] = useState(false);
  const pillRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<ApprovalMode>("smart");

  // Load initial mode from localStorage & backend config
  useEffect(() => {
    try {
      const saved = localStorage.getItem("anara_approval_mode") as ApprovalMode | null;
      if (saved && (saved === "manual" || saved === "smart" || saved === "off")) {
        setMode(saved);
      }
    } catch {}

    fetch(`${BACKEND_URL}/api/config/full`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.config?.approvals?.mode) {
          const raw = String(data.config.approvals.mode).toLowerCase();
          const mapped: ApprovalMode =
            raw === "manual" || raw === "plan" ? "manual" : raw === "off" || raw === "yolo" ? "off" : "smart";
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
        if (e.newValue === "manual" || e.newValue === "smart" || e.newValue === "off") {
          setMode(e.newValue as ApprovalMode);
        }
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

  const handleModeChange = (newMode: ApprovalMode) => {
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

  const isManual = mode === "manual";
  const isOff = mode === "off";

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
        className={`flex items-center gap-1.5 py-1 px-2.5 rounded-lg border text-[11px] font-medium font-mono transition-colors cursor-pointer select-none ${
          isOpen
            ? "bg-white/[0.08] border-white/20 text-white"
            : "bg-white/[0.03] border-white/[0.08] hover:border-white/[0.16] hover:bg-white/[0.06] text-zinc-300 hover:text-white"
        }`}
      >
        <span className="font-semibold tracking-tight capitalize">
          {mode}
        </span>
        <svg
          className={`w-3 h-3 text-zinc-500 transition-transform shrink-0 ${isOpen ? "rotate-180 text-zinc-300" : ""}`}
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
      />
    </div>
  );
}
