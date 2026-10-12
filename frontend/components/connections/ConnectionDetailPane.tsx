"use client";

import React, { useState } from "react";
import { ConnectionPlatform } from "./types";
import { ConnectionIcon } from "./ConnectionIcons";

interface ConnectionDetailPaneProps {
  platform: ConnectionPlatform;
  onSaveConfig: (platformId: string, config: Record<string, unknown>, enabled: boolean) => Promise<void>;
  onTriggerQuickSetup: (platformId: string) => void;
  isSaving: boolean;
}

export function ConnectionDetailPane({
  platform,
  onSaveConfig,
  onTriggerQuickSetup,
  isSaving,
}: ConnectionDetailPaneProps) {
  const [formData, setFormData] = useState<Record<string, unknown>>(platform.config || {});
  const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [isEnabled, setIsEnabled] = useState<boolean>(platform.enabled ?? true);
  const [isSavedSuccess, setIsSavedSuccess] = useState(false);

  // New tag draft state
  const [newTagInput, setNewTagInput] = useState<Record<string, string>>({});
  const [showAddTag, setShowAddTag] = useState<Record<string, boolean>>({});

  const handleInputChange = (key: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  const handleCopy = (key: string, val: string) => {
    if (!val) return;
    navigator.clipboard?.writeText(val);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleRemoveTag = (fieldKey: string, indexToRemove: number) => {
    const raw = formData[fieldKey];
    let list: string[] = [];
    if (Array.isArray(raw)) {
      list = [...raw];
    } else if (typeof raw === "string") {
      list = raw.split(",").map((s) => s.trim()).filter(Boolean);
    }
    list.splice(indexToRemove, 1);
    handleInputChange(fieldKey, list.join(", "));
  };

  const handleAddTag = (fieldKey: string) => {
    const val = (newTagInput[fieldKey] || "").trim();
    if (!val) return;
    const raw = formData[fieldKey];
    let list: string[] = [];
    if (Array.isArray(raw)) {
      list = [...raw];
    } else if (typeof raw === "string" && raw.trim().length > 0) {
      list = raw.split(",").map((s) => s.trim()).filter(Boolean);
    }
    if (!list.includes(val)) {
      list.push(val);
    }
    handleInputChange(fieldKey, list.join(", "));
    setNewTagInput((prev) => ({ ...prev, [fieldKey]: "" }));
    setShowAddTag((prev) => ({ ...prev, [fieldKey]: false }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSaveConfig(platform.id, formData, isEnabled);
    setIsSavedSuccess(true);
    setTimeout(() => setIsSavedSuccess(false), 3000);
  };

  const isConnected = platform.status === "connected";

  return (
    <div className="flex-1 min-w-0 h-full flex flex-col bg-[#050812] select-text overflow-hidden font-sans">
      {/* ── Detail Header ── */}
      <div className="p-6 border-b border-white/[0.08] bg-[#070b16]/60 backdrop-blur-xl shrink-0 flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <div
            className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 shadow-lg border ${
              isConnected
                ? "bg-cyan-500/15 border-cyan-400/30 text-cyan-300"
                : "bg-white/[0.04] border-white/[0.08] text-slate-300"
            }`}
          >
            <ConnectionIcon name={platform.id} className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-bold text-white tracking-tight">
                {platform.name}
              </h2>
              <span
                className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-medium uppercase border flex items-center gap-1.5 ${
                  isConnected
                    ? "bg-cyan-500/10 text-cyan-300 border-cyan-400/30 shadow-[0_0_10px_rgba(6,182,212,0.15)]"
                    : "bg-white/[0.04] text-slate-400 border-white/10"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isConnected ? "bg-cyan-400" : "bg-slate-500"
                  }`}
                />
                {isConnected ? "Connected" : "Inactive"}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              {platform.description}
            </p>
          </div>
        </div>
      </div>

      {/* ── Scrollable Body ── */}
      <div className="flex-1 min-h-0 overflow-y-auto p-6 space-y-6 custom-scrollbar">
        {/* ── 1. QUICK SETUP (Recommended) ── */}
        {platform.quickSetupAvailable && (
          <div className="p-4 rounded-2xl bg-white/[0.025] border border-white/[0.08] relative overflow-hidden group">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono font-semibold text-white tracking-wide uppercase">
                Quick setup
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-400/30">
                Recommended
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed mb-4">
              {platform.quickSetupText || "Configure this integration instantly with automated handshake."}
            </p>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => onTriggerQuickSetup(platform.id)}
                className="px-4 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 border border-cyan-400/40 text-xs font-mono font-semibold transition-all cursor-pointer shadow-sm active:scale-98 flex items-center gap-2"
              >
                <span>{platform.quickSetupActionText || "Run Quick Setup"}</span>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* ── 2. GET YOUR CREDENTIALS ── */}
        {platform.guideSteps && platform.guideSteps.length > 0 && (
          <div className="p-4 rounded-2xl bg-white/[0.015] border border-white/[0.06] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wide">
                Get your credentials
              </span>
              {platform.guideUrl && (
                <a
                  href={platform.guideUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
                >
                  <span>Open setup guide</span>
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              )}
            </div>
            <ol className="list-decimal list-inside space-y-1.5 text-xs text-slate-400 leading-relaxed">
              {platform.guideSteps.map((step, idx) => (
                <li key={idx}>
                  <span className="text-slate-300">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* ── 3. REQUIRED FIELDS ── */}
        {platform.requiredFields && platform.requiredFields.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                Required
              </span>
            </div>

            <div className="space-y-4">
              {platform.requiredFields.map((field) => {
                const val = typeof formData[field.key] === "string" ? (formData[field.key] as string) : "";
                const isPassword = field.type === "password";
                const isRevealed = showPassword[field.key];
                const isSaved = Boolean(platform.config?.[field.key]);

                return (
                  <div
                    key={field.key}
                    className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.07] space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-mono font-medium text-slate-200">
                        {field.label}
                      </label>
                      {isSaved && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/10 text-cyan-300 border border-cyan-400/20">
                          Saved
                        </span>
                      )}
                    </div>

                    <div className="relative flex items-center">
                      <input
                        type={isPassword && !isRevealed ? "password" : "text"}
                        placeholder={field.placeholder}
                        value={val}
                        onChange={(e) => handleInputChange(field.key, e.target.value)}
                        className="w-full px-3.5 py-2.5 rounded-xl bg-black/40 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-400 font-mono transition-colors pr-20"
                      />
                      <div className="absolute right-2 flex items-center gap-1">
                        {isPassword && (
                          <button
                            type="button"
                            onClick={() =>
                              setShowPassword((prev) => ({
                                ...prev,
                                [field.key]: !prev[field.key],
                              }))
                            }
                            className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
                            title={isRevealed ? "Hide token" : "Show token"}
                          >
                            {isRevealed ? (
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                              </svg>
                            ) : (
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                              </svg>
                            )}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleCopy(field.key, val)}
                          className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
                          title="Copy to clipboard"
                        >
                          {copiedKey === field.key ? (
                            <span className="text-[10px] text-cyan-300 font-mono">✓</span>
                          ) : (
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                            </svg>
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleInputChange(field.key, "")}
                          className="p-1.5 text-slate-500 hover:text-rose-400 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
                          title="Clear field"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </div>

                    {field.helperText && (
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        {field.helperText}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── 4. RECOMMENDED FIELDS ── */}
        {platform.recommendedFields && platform.recommendedFields.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                Recommended
              </span>
            </div>

            <div className="space-y-4">
              {platform.recommendedFields.map((field) => {
                const rawVal = typeof formData[field.key] === "string" ? (formData[field.key] as string) : "";
                const isSaved = Boolean(platform.config?.[field.key]);

                if (field.type === "tags") {
                  let tagList: string[] = [];
                  if (Array.isArray(rawVal)) {
                    tagList = rawVal;
                  } else if (typeof rawVal === "string" && rawVal.trim().length > 0) {
                    tagList = rawVal.split(",").map((s) => s.trim()).filter(Boolean);
                  }

                  return (
                    <div
                      key={field.key}
                      className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.07] space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-mono font-medium text-slate-200">
                          {field.label}
                        </label>
                        {isSaved && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/10 text-cyan-300 border border-cyan-400/20">
                            Saved
                          </span>
                        )}
                      </div>

                      {field.helperText && (
                        <p className="text-[11px] text-slate-400 leading-relaxed">
                          {field.helperText}
                        </p>
                      )}

                      {/* Tag Chips Container */}
                      <div className="flex flex-wrap items-center gap-2">
                        {tagList.map((tag, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-white/[0.06] border border-white/10 text-xs font-mono text-slate-200"
                          >
                            <span>{tag}</span>
                            <button
                              type="button"
                              onClick={() => handleRemoveTag(field.key, idx)}
                              className="text-slate-400 hover:text-rose-400 cursor-pointer transition-colors"
                            >
                              ✕
                            </button>
                          </span>
                        ))}

                        {showAddTag[field.key] ? (
                          <div className="inline-flex items-center gap-1.5">
                            <input
                              type="text"
                              placeholder={field.placeholder}
                              value={newTagInput[field.key] || ""}
                              onChange={(e) =>
                                setNewTagInput((prev) => ({
                                  ...prev,
                                  [field.key]: e.target.value,
                                }))
                              }
                              onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                  e.preventDefault();
                                  handleAddTag(field.key);
                                } else if (e.key === "Escape") {
                                  setShowAddTag((prev) => ({
                                    ...prev,
                                    [field.key]: false,
                                  }));
                                }
                              }}
                              autoFocus
                              className="px-2.5 py-1 rounded-xl bg-black/50 border border-cyan-400 text-xs font-mono text-white focus:outline-none w-48"
                            />
                            <button
                              type="button"
                              onClick={() => handleAddTag(field.key)}
                              className="px-2 py-1 rounded-xl bg-cyan-500/20 text-cyan-200 border border-cyan-400/30 text-xs font-mono cursor-pointer"
                            >
                              Add
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() =>
                              setShowAddTag((prev) => ({
                                ...prev,
                                [field.key]: true,
                              }))
                            }
                            className="inline-flex items-center gap-1 px-3 py-1 rounded-xl bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.08] text-xs font-mono text-slate-300 hover:text-white transition-all cursor-pointer"
                          >
                            <span>+</span>
                            <span>Add another</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                }

                // Default text input
                return (
                  <div
                    key={field.key}
                    className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.07] space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-mono font-medium text-slate-200">
                        {field.label}
                      </label>
                      {isSaved && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/10 text-cyan-300 border border-cyan-400/20">
                          Saved
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      placeholder={field.placeholder}
                      value={rawVal}
                      onChange={(e) => handleInputChange(field.key, e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-black/40 border border-white/15 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-400 font-mono transition-colors"
                    />
                    {field.helperText && (
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        {field.helperText}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Footer Controls ── */}
      <footer className="p-4 border-t border-white/[0.08] bg-[#070b16]/90 backdrop-blur-2xl shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={isEnabled}
              onChange={(e) => setIsEnabled(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-500 relative border border-white/20" />
            <span className="text-xs font-mono font-medium text-slate-300">
              Enabled
            </span>
          </label>
          {isSavedSuccess && (
            <span className="text-xs font-mono text-cyan-300 animate-fade-in flex items-center gap-1">
              <span>✓</span>
              <span>Saved changes</span>
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={handleSubmit}
          disabled={isSaving}
          className="px-5 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black font-semibold text-xs font-mono transition-all cursor-pointer shadow-[0_0_20px_rgba(6,182,212,0.3)] active:scale-98 disabled:opacity-50 flex items-center gap-2"
        >
          {isSaving ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-black border-t-transparent rounded-full animate-spin" />
              <span>Saving...</span>
            </>
          ) : (
            <span>Save changes</span>
          )}
        </button>
      </footer>
    </div>
  );
}
