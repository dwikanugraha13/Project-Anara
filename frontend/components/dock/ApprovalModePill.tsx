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
        className={`flex items-center gap-1.5 py-1 px-2.5 rounded-lg border text-[11px] font-medium transition-colors cursor-pointer select-none ${
          isOpen
            ? "bg-white/[0.08] border-white/20 text-white"
            : isManual
            ? "bg-amber-500/10 hover:bg-amber-500/15 border-amber-400/25 text-amber-300 hover:text-amber-200"
            : isOff
            ? "bg-emerald-500/10 hover:bg-emerald-500/15 border-emerald-400/25 text-emerald-300 hover:text-emerald-200"
            : "bg-white/[0.04] hover:bg-white/[0.07] border-white/[0.08] hover:border-white/[0.15] text-zinc-300 hover:text-white"
        }`}
      >
        {isManual ? (
          <svg className="w-3.5 h-3.5 text-amber-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.8}
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
            />
          </svg>
        ) : isOff ? (
          <svg className="w-3.5 h-3.5 text-emerald-400 shrink-0" fill="currentColor" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={0} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        ) : (
          <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.8}
              d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"
            />
          </svg>
        )}
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
