"use client";

import React, { useState, useEffect } from "react";
import { BACKEND_URL, BrandIcon } from "../../types";

export interface OAuthSessionData {
  providerId: string;
  state: string;
  authUrl: string;
  codeVerifier?: string;
}

interface CodexOAuthModalProps {
  session: OAuthSessionData | null;
  onClose: () => void;
  onSuccess: (providers?: any[]) => void;
}

export default function CodexOAuthModal({
  session,
  onClose,
  onSuccess,
}: CodexOAuthModalProps) {
  const [manualCallbackInput, setManualCallbackInput] = useState("");
  const [isVerifyingManualCallback, setIsVerifyingManualCallback] = useState(false);

  // Polling loop while session is active
  useEffect(() => {
    if (!session) return;
    let isSubscribed = true;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(
          `${BACKEND_URL}/api/auth/${session.providerId}/status?state=${encodeURIComponent(session.state)}`
        );
        if (res.ok && isSubscribed) {
          const data = await res.json();
          if (data.status === "success") {
            onSuccess(data.providers);
            onClose();
          }
        }
      } catch {}
    }, 2000);

    // Cross-window postMessage listener
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === "CODEX_OAUTH_SUCCESS" && e.data?.state === session.state) {
        onSuccess();
        onClose();
      }
    };
    window.addEventListener("message", onMessage);

    const timeout = setTimeout(() => {
      clearInterval(interval);
    }, 300000);

    return () => {
      isSubscribed = false;
      clearInterval(interval);
      clearTimeout(timeout);
      window.removeEventListener("message", onMessage);
    };
  }, [session, onClose, onSuccess]);

  if (!session) return null;

  const handleManualCallbackSubmit = async () => {
    if (!manualCallbackInput.trim()) return;
    setIsVerifyingManualCallback(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/${session.providerId}/exchange`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: manualCallbackInput.trim(),
          state: session.state,
          code_verifier: session.codeVerifier,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setManualCallbackInput("");
        onSuccess(data.providers);
        onClose();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to verify callback URL");
      }
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setIsVerifyingManualCallback(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-xl animate-fade-in select-none">
      <div className="w-full max-w-lg p-6 rounded-3xl liquid-glass-drawer border border-emerald-500/40 shadow-2xl text-white space-y-5">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/20 border border-emerald-400/30 flex items-center justify-center text-emerald-300">
              <BrandIcon name="openai" className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white">Login OpenAI Codex (OAuth)</h4>
              <span className="text-[10px] font-mono text-emerald-400 font-semibold">
                PKCE Resmi (Codex CLI) · Port 1455 Active
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-white text-sm cursor-pointer p-1"
          >
            ✕
          </button>
        </div>

        {/* Status Indicator */}
        <div className="p-4 rounded-2xl bg-emerald-950/30 border border-emerald-500/25 flex items-start gap-3">
          <div className="w-4 h-4 mt-0.5 rounded-full border-2 border-emerald-400 border-t-transparent animate-spin shrink-0" />
          <div className="space-y-1">
            <p className="text-xs font-semibold text-emerald-200">
              Waiting for OpenAI account authorization in browser window...
            </p>
            <p className="text-[11px] text-slate-300 leading-relaxed">
              Sign in with your ChatGPT/OpenAI account in the opened window. The system will capture authorization automatically via port 1455.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              if (typeof window !== "undefined" && session.authUrl) {
                window.open(session.authUrl, "OpenAI_Codex_Login", "width=600,height=750,left=200,top=100");
              }
            }}
            className="px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 border border-white/15 text-xs font-mono text-slate-200 transition-all cursor-pointer flex items-center gap-1.5"
          >
            <span>↗ Reopen Login Window</span>
          </button>
        </div>

        {/* Manual Fallback Section */}
        <div className="space-y-2 pt-2 border-t border-white/10">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase text-slate-400 font-bold">
              Fallback Option (If redirect is blocked by browser):
            </span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            If your browser was redirected to <code className="text-cyan-300 font-mono text-[10px]">localhost:1455/auth/callback?code=...</code> but didn't close automatically, copy the entire URL from the address bar and paste it below:
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Paste callback URL (http://localhost:1455/auth/callback?code=...) or code..."
              value={manualCallbackInput}
              onChange={(e) => setManualCallbackInput(e.target.value)}
              className="flex-1 px-3 py-2 rounded-xl bg-black/60 border border-white/15 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-emerald-400 font-mono"
            />
            <button
              type="button"
              onClick={handleManualCallbackSubmit}
              disabled={isVerifyingManualCallback || !manualCallbackInput.trim()}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs font-mono transition-all cursor-pointer disabled:opacity-40"
            >
              {isVerifyingManualCallback ? "Verifying..." : "Verify"}
            </button>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white text-xs font-mono transition-all cursor-pointer border border-white/10"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
