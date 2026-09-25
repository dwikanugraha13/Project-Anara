"use client";

import React, { useState, useEffect } from "react";
import { anaraApi } from "@/lib/apiClient";

function LockIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function KeyIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="7.5" cy="15.5" r="5.5" />
      <path d="m21 2-9.6 9.6" />
      <path d="m15.5 7.5 3 3L22 7l-3-3" />
    </svg>
  );
}

function ShieldCheckIcon({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function LaptopIcon({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 16V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v9m16 0H4m16 0 1.28 2.55a1 1 0 0 1-.9 1.45H3.62a1 1 0 0 1-.9-1.45L4 16" />
    </svg>
  );
}

function TerminalIcon({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 17 10 11 4 5" />
      <line x1="12" y1="19" x2="20" y2="19" />
    </svg>
  );
}

export function GatewayAuthModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await anaraApi.gateway.getStatus();
        if (res && res.auth_required && !res.authenticated) {
          setIsOpen(true);
        }
      } catch {
        // Ignored
      }
    };

    checkStatus();

    const handleUnauthorized = () => {
      setIsOpen(true);
      setErrorMsg("Session has expired or requires password authentication.");
    };

    window.addEventListener("anara_gateway_unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("anara_gateway_unauthorized", handleUnauthorized);
    };
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim()) return;

    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await anaraApi.gateway.login(password.trim());
      if (res && res.token) {
        localStorage.setItem("anara_gateway_token", res.token);
        setIsOpen(false);
        setPassword("");
        window.location.reload();
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Password gateway salah.");
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-300">
      <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-cyan-500/30 bg-slate-950/90 p-6 shadow-2xl shadow-cyan-950/50 backdrop-blur-xl">
        <div className="absolute -top-24 -left-24 h-48 w-48 rounded-full bg-cyan-500/20 blur-3xl" />
        <div className="absolute -bottom-24 -right-24 h-48 w-48 rounded-full bg-blue-600/20 blur-3xl" />

        <div className="relative z-10 flex flex-col items-center text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-400/40 bg-cyan-950/40 text-cyan-400 shadow-inner">
            <LockIcon className="h-8 w-8 animate-pulse" />
          </div>

          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <span>Anara Remote Gateway</span>
            <ShieldCheckIcon className="h-5 w-5 text-cyan-400" />
          </h2>
          <p className="mt-1.5 text-xs text-slate-400 leading-relaxed max-w-xs">
            Remote access detected. Enter Gateway Password to connect this browser to your laptop.
          </p>

          <form onSubmit={handleLogin} className="mt-6 w-full space-y-4">
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
                <KeyIcon className="h-4 w-4" />
              </span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter Gateway Password..."
                autoFocus
                className="w-full rounded-xl border border-slate-800 bg-slate-900/90 py-3 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/20 transition-all"
              />
            </div>

            {errorMsg && (
              <div className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-left text-xs text-red-400 animate-in fade-in">
                ⚠️ {errorMsg}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading || !password.trim()}
              className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 py-3 text-sm font-semibold text-white shadow-lg shadow-cyan-500/25 transition-all hover:opacity-90 active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none"
            >
              {isLoading ? "Verifying..." : "Open Gateway Access"}
            </button>
          </form>

          <div className="mt-6 flex items-center justify-between w-full pt-4 border-t border-slate-800/80 text-[11px] text-slate-500">
            <div className="flex items-center gap-1.5">
              <LaptopIcon className="h-3.5 w-3.5 text-cyan-400" />
              <span>Host: Laptop Utama</span>
            </div>
            <div className="flex items-center gap-1.5">
              <TerminalIcon className="h-3.5 w-3.5 text-slate-400" />
              <span>Port: 3000 / 8000</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
