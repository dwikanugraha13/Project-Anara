"use client";

import React, { useState, useEffect } from "react";
import { BACKEND_URL } from "../../types";

interface CustomProviderModalProps {
  isOpen: boolean;
  onClose: () => void;
  providerType: "openai" | "anthropic";
  onSuccess: (providers?: any[]) => void;
}

export default function CustomProviderModal({
  isOpen,
  onClose,
  providerType,
  onSuccess,
}: CustomProviderModalProps) {
  const [nameInput, setNameInput] = useState("");
  const [prefixInput, setPrefixInput] = useState("");
  const [apiType, setApiType] = useState<"chat_completions" | "responses">("chat_completions");
  const [baseUrlInput, setBaseUrlInput] = useState("https://api.openai.com/v1");
  const [keyInput, setKeyInput] = useState("");
  const [modelIdInput, setModelIdInput] = useState("");
  const [checkLoading, setCheckLoading] = useState(false);
  const [checkMsg, setCheckMsg] = useState<{ status: "ok" | "error" | "warning"; text: string } | null>(null);

  useEffect(() => {
    if (isOpen) {
      if (providerType === "anthropic") {
        setBaseUrlInput("https://api.anthropic.com/v1");
      } else {
        setBaseUrlInput("https://api.openai.com/v1");
      }
      setCheckMsg(null);
    }
  }, [isOpen, providerType]);

  if (!isOpen) return null;

  const handleCheck = async () => {
    if (!baseUrlInput.trim()) {
      setCheckMsg({ status: "error", text: "Base URL wajib diisi" });
      return;
    }
    setCheckLoading(true);
    setCheckMsg(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/providers/custom/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: baseUrlInput.trim(),
          api_key: keyInput.trim(),
          api_type: apiType,
        }),
      });
      const data = await res.json();
      if (data.status === "ok") {
        setCheckMsg({ status: "ok", text: data.message });
      } else {
        setCheckMsg({ status: "error", text: data.message || "Gagal menghubungi endpoint" });
      }
    } catch (e: any) {
      setCheckMsg({ status: "error", text: `Koneksi gagal: ${e.message}` });
    } finally {
      setCheckLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!nameInput.trim() || !prefixInput.trim() || !baseUrlInput.trim()) {
      alert("Nama, Prefix, dan Base URL wajib diisi!");
      return;
    }
    try {
      const res = await fetch(`${BACKEND_URL}/api/providers/custom`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: nameInput.trim(),
          prefix: prefixInput.trim().toLowerCase(),
          api_type: apiType,
          base_url: baseUrlInput.trim(),
          api_key: keyInput.trim(),
          default_model: modelIdInput.trim(),
        }),
      });
      if (res.ok) {
        const data = await res.json();
        onClose();
        setNameInput("");
        setPrefixInput("");
        setKeyInput("");
        setModelIdInput("");
        setCheckMsg(null);
        onSuccess(data.providers);
      } else {
        const err = await res.json();
        alert(err.detail || "Gagal menyimpan custom provider");
      }
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xl animate-fade-in select-none">
      <div className="w-full max-w-md p-6 rounded-3xl liquid-glass-drawer border border-purple-400/40 shadow-2xl text-white space-y-4">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-purple-400 shadow-[0_0_8px_#c084fc]" />
            <h4 className="text-sm font-bold text-white font-mono">
              Add {providerType === "openai" ? "OpenAI" : "Anthropic"} Compatible
            </h4>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-white text-sm cursor-pointer p-1"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3 font-sans text-xs">
          <div>
            <label className="text-[11px] font-mono text-slate-300 block mb-1">
              Name <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              placeholder="OpenAI Compatible (Prod)"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-black/60 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-purple-400 font-mono"
            />
            <p className="text-[10px] text-slate-500 mt-1">Required. A friendly label for this node.</p>
          </div>

          <div>
            <label className="text-[11px] font-mono text-slate-300 block mb-1">
              Prefix <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              placeholder="oc-prod"
              value={prefixInput}
              onChange={(e) => setPrefixInput(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-black/60 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-purple-400 font-mono"
            />
            <p className="text-[10px] text-slate-500 mt-1">Required. Used as the provider prefix for model IDs.</p>
          </div>

          <div>
            <label className="text-[11px] font-mono text-slate-300 block mb-1">
              API Type
            </label>
            <select
              value={apiType}
              onChange={(e) => setApiType(e.target.value as any)}
              className="w-full px-3 py-2 rounded-xl bg-black/60 border border-white/20 text-xs text-white focus:outline-none focus:border-purple-400 font-mono cursor-pointer"
            >
              <option value="chat_completions" className="bg-slate-900">Chat Completions</option>
              <option value="responses" className="bg-slate-900">Responses API</option>
            </select>
          </div>

          <div>
            <label className="text-[11px] font-mono text-slate-300 block mb-1">
              Base URL <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              placeholder="https://api.openai.com/v1"
              value={baseUrlInput}
              onChange={(e) => setBaseUrlInput(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-black/60 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-purple-400 font-mono"
            />
            <p className="text-[10px] text-slate-500 mt-1">Use the base URL (ending in /v1) for your OpenAI-compatible API.</p>
          </div>

          <div>
            <label className="text-[11px] font-mono text-slate-300 block mb-1">
              API Key (for Check)
            </label>
            <input
              type="password"
              placeholder="sk-..."
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-black/60 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-purple-400 font-mono"
            />
          </div>

          <div>
            <label className="text-[11px] font-mono text-slate-300 block mb-1">
              Model ID (optional)
            </label>
            <input
              type="text"
              placeholder="e.g. gpt-4, claude-3-opus"
              value={modelIdInput}
              onChange={(e) => setModelIdInput(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-black/60 border border-white/20 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-purple-400 font-mono"
            />
            <p className="text-[10px] text-slate-500 mt-1">If provider lacks /models endpoint, enter a model ID to validate via chat/completions instead.</p>
          </div>

          {checkMsg && (
            <div className={`p-2.5 rounded-xl border text-xs font-mono ${
              checkMsg.status === "ok"
                ? "bg-emerald-950/40 text-emerald-300 border-emerald-400/40"
                : "bg-rose-950/40 text-rose-300 border-rose-400/40"
            }`}>
              {checkMsg.text}
            </div>
          )}

          <div className="pt-3 border-t border-white/10 flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={handleCheck}
              disabled={checkLoading}
              className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-200 border border-white/15 text-xs font-semibold font-mono cursor-pointer transition-all disabled:opacity-50"
            >
              {checkLoading ? "Memeriksa..." : "Check"}
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-2 text-xs text-slate-400 hover:text-white cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreate}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-purple-600/40 to-indigo-600/40 hover:from-purple-600/60 hover:to-indigo-600/60 border border-purple-400/50 text-xs font-bold text-white shadow-lg cursor-pointer transition-all"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
