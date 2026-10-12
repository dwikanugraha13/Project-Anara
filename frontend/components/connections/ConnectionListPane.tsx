"use client";

import React from "react";
import { ConnectionPlatform, ConnectionScope } from "./types";
import { ConnectionIcon } from "./ConnectionIcons";

interface ConnectionListPaneProps {
  platforms: ConnectionPlatform[];
  selectedPlatformId: string;
  onSelectPlatform: (id: string) => void;
  selectedScope: ConnectionScope;
  onSelectScope: (scope: ConnectionScope) => void;
}

const SCOPES: { id: ConnectionScope; label: string }[] = [
  { id: "all", label: "all" },
  { id: "default", label: "default" },
  { id: "architect", label: "architect" },
  { id: "backend", label: "backend" },
  { id: "frontend", label: "frontend" },
  { id: "tester", label: "tester" },
];

export function ConnectionListPane({
  platforms,
  selectedPlatformId,
  onSelectPlatform,
  selectedScope,
  onSelectScope,
}: ConnectionListPaneProps) {
  return (
    <aside className="w-72 sm:w-80 border-r border-white/[0.08] bg-[#070b16]/70 backdrop-blur-xl flex flex-col shrink-0 select-none overflow-hidden h-full">
      {/* ── Header: Applies to Pills ── */}
      <div className="p-3 border-b border-white/[0.08] space-y-2 shrink-0">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-mono uppercase text-slate-400 tracking-wider">
            Applies to
          </span>
          <span className="text-[10px] font-mono text-slate-500">
            {platforms.length} platforms
          </span>
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5">
          {SCOPES.map((scope) => {
            const isActive = selectedScope === scope.id;
            return (
              <button
                key={scope.id}
                type="button"
                onClick={() => onSelectScope(scope.id)}
                className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono transition-all cursor-pointer whitespace-nowrap ${
                  isActive
                    ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/40 shadow-[0_0_10px_rgba(6,182,212,0.15)] font-medium"
                    : "bg-white/[0.03] text-slate-400 border border-white/[0.06] hover:bg-white/[0.06] hover:text-slate-200"
                }`}
              >
                {scope.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Platform List ── */}
      <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-1 custom-scrollbar">
        {platforms.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-500 font-mono">
            No platforms found matching your filter.
          </div>
        ) : (
          platforms.map((p) => {
            const isSelected = p.id === selectedPlatformId;
            const isConnected = p.status === "connected";
            const isConnecting = p.status === "connecting";

            return (
              <button
                key={p.id}
                type="button"
                onClick={() => onSelectPlatform(p.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl transition-all cursor-pointer group text-left ${
                  isSelected
                    ? "bg-white/[0.08] border border-cyan-500/40 shadow-[0_0_16px_rgba(6,182,212,0.1)] text-white"
                    : "border border-transparent hover:bg-white/[0.03] text-slate-300 hover:text-white"
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
                      isSelected
                        ? "bg-cyan-500/20 text-cyan-300 border border-cyan-400/30"
                        : isConnected
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-400/20"
                        : "bg-white/[0.04] text-slate-400 group-hover:text-slate-200 border border-white/[0.06]"
                    }`}
                  >
                    <ConnectionIcon name={p.id} className="w-4 h-4" />
                  </div>
                  <span className="text-xs font-medium font-sans truncate">
                    {p.name}
                  </span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {isConnected && (
                    <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
                  )}
                  {isConnecting && (
                    <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                  )}
                  {!isConnected && !isConnecting && (
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-600 group-hover:bg-slate-500" />
                  )}
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
