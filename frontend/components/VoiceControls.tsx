"use client";

import React, { useRef, useEffect, useState } from "react";
import AnaraHUD, {
  type WeatherData,
  type CodeData,
  type SystemHudData,
  type KnowledgeCardData,
  type TodoData,
} from "./AnaraHUD";
import AnaraBrain from "./AnaraBrain";

export type AssistantStatus = "idle" | "listening" | "thinking" | "speaking";

export interface TranscriptItem {
  speaker: "input" | "output";
  text: string;
  visualType?: "image" | "weather" | "code" | "system_hud" | "knowledge_card" | "todo_list" | "none";
  imageUrl?: string;
  imagePrompt?: string;
  imageTitle?: string;
  sourceDomain?: string;
  sourceUrl?: string;
  weatherData?: WeatherData;
  codeData?: CodeData;
  systemHudData?: SystemHudData;
  knowledgeCardData?: KnowledgeCardData;
  todoData?: TodoData;
  images?: Array<{ image_url?: string; url?: string; title?: string; source_domain?: string; sourceDomain?: string; source_url?: string; sourceUrl?: string }>;
  mediaType?: "image" | "hud";
}

interface VoiceControlsProps {
  status: AssistantStatus;
  connectionStatus: "disconnected" | "connecting" | "connected" | "error";
  transcript: TranscriptItem[];
  isMicActive: boolean;
  isMuted: boolean;
  userIntensity: number;
  aiIntensity: number;
  interactionMode?: "voice" | "chat";
  onSetInteractionMode?: (mode: "voice" | "chat") => void;
  onStartSession: () => void;
  onSendText?: (text: string) => void;
  onToggleMute: () => void;
  onInterrupt: () => void;
  onClearTranscript: () => void;
  onTriggerAnimation?: (animName: string, emotion: string) => void;
  micDenied?: boolean;
  activeSpeaker?: string | null;
}

export default function VoiceControls({
  status,
  connectionStatus,
  transcript,
  isMicActive,
  isMuted,
  userIntensity,
  aiIntensity,
  interactionMode = "voice",
  activeSpeaker,
  onSetInteractionMode,
  onStartSession,
  onSendText,
  onToggleMute,
  onInterrupt,
  onClearTranscript,
  onTriggerAnimation,
  micDenied = false,
}: VoiceControlsProps) {
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const [inputMessage, setInputMessage] = useState("");
  const [isChatDrawerOpen, setIsChatDrawerOpen] = useState(false);
  const [isBrainDrawerOpen, setIsBrainDrawerOpen] = useState(false);
  const [selectedPreviewImage, setSelectedPreviewImage] = useState<{
    url: string;
    title: string;
    sourceDomain?: string;
    sourceUrl?: string;
    prompt?: string;
  } | null>(null);

  const isConnected = connectionStatus === "connected";
  const latestVisual = transcript.slice().reverse().find((t) => Boolean(t.visualType && t.visualType !== "none"));

  // Auto scroll transcript to latest
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, isChatDrawerOpen]);

  // ── Real-Time Streaming Running Subtitle ──
  const [displayedAiCharCount, setDisplayedAiCharCount] = useState(0);
  const latestAiMessage = transcript.filter((t) => t.speaker === "output").slice(-1)[0]?.text || "";
  const prevAiMessageRef = useRef("");

  useEffect(() => {
    if (latestAiMessage !== prevAiMessageRef.current) {
      if (!prevAiMessageRef.current || !latestAiMessage.startsWith(prevAiMessageRef.current)) {
        setDisplayedAiCharCount(1);
      }
      prevAiMessageRef.current = latestAiMessage;
    }
  }, [latestAiMessage]);

  useEffect(() => {
    if (!latestAiMessage) {
      setDisplayedAiCharCount(0);
      return;
    }

    if (displayedAiCharCount >= latestAiMessage.length) return;

    // Smooth real-time running typewriter effect
    const interval = setInterval(() => {
      setDisplayedAiCharCount((prev) => {
        if (prev >= latestAiMessage.length) {
          clearInterval(interval);
          return latestAiMessage.length;
        }
        return Math.min(latestAiMessage.length, prev + 2);
      });
    }, 20);

    return () => clearInterval(interval);
  }, [latestAiMessage, displayedAiCharCount]);

  // ── Holographic JARVIS HUD Timer ──
  const [activeTimer, setActiveTimer] = useState<{
    label: string;
    totalSeconds: number;
    remainingSeconds: number;
  } | null>(null);

  useEffect(() => {
    const handleTimerEvent = (e: any) => {
      const { durationSeconds, label } = e.detail || {};
      if (durationSeconds && durationSeconds > 0) {
        setActiveTimer({
          label: label || "Timer",
          totalSeconds: durationSeconds,
          remainingSeconds: durationSeconds,
        });
      }
    };

    window.addEventListener("anara-hud-timer", handleTimerEvent);
    return () => window.removeEventListener("anara-hud-timer", handleTimerEvent);
  }, []);

  useEffect(() => {
    if (!activeTimer) return;
    if (activeTimer.remainingSeconds <= 0) {
      const timeout = setTimeout(() => setActiveTimer(null), 8000);
      return () => clearTimeout(timeout);
    }
    const interval = setInterval(() => {
      setActiveTimer((prev) => {
        if (!prev) return null;
        if (prev.remainingSeconds <= 1) {
          return { ...prev, remainingSeconds: 0 };
        }
        return { ...prev, remainingSeconds: prev.remainingSeconds - 1 };
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [activeTimer]);

  // Combined visual intensity
  const activeIntensity = status === "speaking" ? aiIntensity : userIntensity;

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;
    if (onSendText) {
      onSendText(inputMessage);
    }
    setInputMessage("");
  };

  return (
    <div className="notranslate select-none" translate="no">
      {/* ── Top Floating Liquid Glass Header ── */}
      <header className="absolute top-5 inset-x-0 mx-auto max-w-5xl px-4 z-50 flex items-center justify-between pointer-events-none">
        {/* Brand Liquid Glass Capsule with Integrated Server Status */}
        <div className="liquid-glass flex items-center gap-3 px-3.5 py-2 rounded-2xl border border-white/20 shadow-2xl shadow-black/80 pointer-events-auto backdrop-blur-3xl transition-all hover:border-white/30">
          <div className="relative flex items-center justify-center">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/40 border border-white/30">
              <span className="text-xs font-black text-white tracking-widest font-mono">AN</span>
            </div>
            <span
              className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-slate-950 transition-all duration-300 ${
                isConnected
                  ? "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                  : connectionStatus === "connecting"
                  ? "bg-amber-400 animate-pulse shadow-[0_0_8px_#fbbf24]"
                  : "bg-rose-500 shadow-[0_0_8px_#f43f5e]"
              }`}
            />
          </div>

          <div className="flex flex-col">
            <h1
              className="text-xs font-bold text-white tracking-wider uppercase flex items-center gap-1.5 leading-tight"
              suppressHydrationWarning
            >
              Anara Asisten
            </h1>
            <p className="text-[10.5px] font-mono tracking-tight flex items-center gap-1.5 leading-tight pt-0.5" suppressHydrationWarning>
              <span
                className={`font-semibold ${
                  isConnected
                    ? "text-emerald-400"
                    : connectionStatus === "connecting"
                    ? "text-amber-400"
                    : "text-rose-400"
                }`}
              >
                {isConnected
                  ? "Server Terhubung Online"
                  : connectionStatus === "connecting"
                  ? "Server Menghubungkan..."
                  : "Server Terputus"}
              </span>
              {activeSpeaker ? (
                <span className="text-slate-400 font-normal flex items-center gap-1">
                  • <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_#22d3ee]" />
                  <span className="text-cyan-300 font-semibold">{activeSpeaker}</span>
                </span>
              ) : (
                <span className="text-slate-500 font-normal">
                  • <span className="text-slate-400">Tamu</span>
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Right Action Widgets: Symmetrical Luxury Glass Capsule */}
        <div className="liquid-glass flex items-center p-1 rounded-2xl border border-white/20 shadow-2xl shadow-black/80 pointer-events-auto backdrop-blur-3xl gap-1">
          {/* Anara Brain Database Drawer Button */}
          <button
            onClick={() => setIsBrainDrawerOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-200 hover:text-white hover:bg-white/[0.12] border border-transparent hover:border-white/15 transition-all duration-200 cursor-pointer active:scale-95 group"
            title="Buka Console Otak & Database SQLite Anara"
          >
            <div className="w-6 h-6 rounded-lg bg-gradient-to-tr from-purple-500/25 via-indigo-500/25 to-cyan-400/25 border border-white/20 flex items-center justify-center text-xs group-hover:scale-110 transition-transform shadow-inner">
              🧠
            </div>
            <span className="tracking-wide">Anara Brain</span>
          </button>

          <span className="w-px h-5 bg-white/15 mx-0.5" />

          {/* Chat history drawer button */}
          <button
            onClick={() => setIsChatDrawerOpen((prev) => !prev)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all duration-200 cursor-pointer active:scale-95 group ${
              isChatDrawerOpen
                ? "bg-white/[0.18] text-white border border-white/25 shadow-md"
                : "text-slate-200 hover:text-white hover:bg-white/[0.12] border border-transparent hover:border-white/15"
            }`}
            title="Buka Riwayat Percakapan"
          >
            <div className="w-6 h-6 rounded-lg bg-gradient-to-tr from-cyan-500/25 via-blue-500/25 to-indigo-400/25 border border-white/20 flex items-center justify-center text-xs group-hover:scale-110 transition-transform shadow-inner">
              <svg className="w-3.5 h-3.5 text-cyan-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <span className="tracking-wide">Chat</span>
            <span className="px-2 py-0.5 rounded-full bg-cyan-400/20 border border-cyan-400/35 text-cyan-300 text-[10.5px] font-bold font-mono leading-none shadow-[0_0_8px_rgba(34,211,238,0.25)]">
              {transcript.length}
            </span>
          </button>
        </div>
      </header>

      {/* ── Floating Holographic JARVIS HUD Timer ── */}
      {activeTimer && (
        <div className="fixed top-20 inset-x-0 mx-auto max-w-sm px-4 z-40 animate-fade-in pointer-events-auto">
          <div className="p-4 rounded-3xl bg-black/60 border border-cyan-400/40 backdrop-blur-2xl shadow-[0_0_30px_rgba(34,211,238,0.25)] flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-2xl flex items-center justify-center border font-mono text-base font-bold ${
                activeTimer.remainingSeconds <= 0
                  ? "bg-emerald-500/20 border-emerald-400 text-emerald-300 animate-bounce"
                  : "bg-cyan-500/20 border-cyan-400 text-cyan-300 animate-pulse"
              }`}>
                ⏱️
              </div>
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-300 font-semibold block">
                  {activeTimer.label}
                </span>
                <span className="text-xl font-bold font-mono text-white tracking-widest">
                  {Math.floor(activeTimer.remainingSeconds / 60).toString().padStart(2, "0")}:
                  {(activeTimer.remainingSeconds % 60).toString().padStart(2, "0")}
                </span>
              </div>
            </div>

            <button
              onClick={() => setActiveTimer(null)}
              className="p-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-400 hover:text-white transition-colors cursor-pointer"
              title="Tutup Timer"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* ── Liquid Glass Chat Drawer (Slide-over History Panel) ── */}
      {isChatDrawerOpen && (
        <aside className="fixed top-0 right-0 h-full w-full max-w-sm sm:max-w-md z-40 p-4 pt-20 animate-slide-in pointer-events-auto">
          <div className="h-full w-full liquid-glass rounded-3xl p-4 flex flex-col shadow-2xl border border-white/20 shadow-black/80">
            {/* Drawer Header */}
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
                <h2 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                  Riwayat Percakapan
                </h2>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-slate-300 font-mono">
                  {transcript.length}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {transcript.length > 0 && (
                  <button
                    onClick={onClearTranscript}
                    className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-rose-300 transition-colors"
                    title="Hapus riwayat"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                )}
                <button
                  onClick={() => setIsChatDrawerOpen(false)}
                  className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                  title="Tutup riwayat"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Drawer Message List */}
            <div className="flex-1 overflow-y-auto py-3 space-y-3 pr-1 text-xs select-text">
              {transcript.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
                  <div className="w-12 h-12 rounded-2xl bg-white/[0.05] border border-white/10 flex items-center justify-center mb-3">
                    <svg className="w-6 h-6 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </div>
                  <p className="text-xs font-semibold text-slate-300 font-mono">Belum Ada Percakapan</p>
                  <p className="text-[11px] text-slate-500 mt-1 max-w-[200px]">
                    Bicara lewat mic atau ketik pesan untuk mulai berinteraksi dengan Anara.
                  </p>
                </div>
              ) : (
                transcript.map((item, idx) => (
                  <div
                    key={idx}
                    className={`flex flex-col gap-1.5 ${
                      item.speaker === "input" ? "items-end" : "items-start"
                    }`}
                  >
                    <div
                      className={`max-w-[95%] p-3 rounded-2xl leading-relaxed shadow-lg ${
                        item.speaker === "input"
                          ? "liquid-glass-bubble-user text-white rounded-tr-sm"
                          : "liquid-glass-bubble-ai text-slate-100 rounded-tl-sm border border-cyan-400/20"
                      }`}
                    >
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span
                          className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded font-mono ${
                            item.speaker === "input"
                              ? "bg-indigo-500/40 text-indigo-200"
                              : "bg-cyan-500/30 text-cyan-200 border border-cyan-400/30"
                          }`}
                        >
                          {item.speaker === "input" ? "Anda" : "Anara"}
                        </span>
                        {item.visualType && item.visualType !== "none" && (
                          <span className="text-[9px] font-mono font-semibold px-1.5 py-0.2 rounded bg-cyan-400/20 text-cyan-300 border border-cyan-400/30 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                            HUD • {item.visualType.toUpperCase()}
                          </span>
                        )}
                      </div>
                      <p className="break-words font-normal mb-1">{item.text || "..."}</p>

                      {/* ── Holographic Anara HUD Component in Drawer ── */}
                      {item.visualType && item.visualType !== "none" && (
                        <AnaraHUD
                          visualType={item.visualType}
                          imageUrl={item.imageUrl}
                          imageTitle={item.imageTitle}
                          sourceDomain={item.sourceDomain}
                          sourceUrl={item.sourceUrl}
                          imagePrompt={item.imagePrompt}
                          images={item.images}
                          weatherData={item.weatherData}
                          codeData={item.codeData}
                          systemHudData={item.systemHudData}
                          knowledgeCardData={item.knowledgeCardData}
                          todoData={item.todoData}
                          onOpenLightbox={setSelectedPreviewImage}
                        />
                      )}
                    </div>
                  </div>
                ))
              )}
              <div ref={transcriptEndRef} />
            </div>
          </div>
        </aside>
      )}

      {/* ── Universal Sleek Liquid Glass Bottom Dock ── */}
      <footer className="fixed bottom-3 sm:bottom-4 inset-x-0 mx-auto max-w-xl sm:max-w-2xl px-4 z-30 flex flex-col items-center gap-2 pointer-events-none">
        {/* Floating Active Dialogue Bubbles (Strictly Chat Mode Only) */}
        {!isChatDrawerOpen && interactionMode === "chat" && transcript.length > 0 && (
          <div className="w-full flex flex-col gap-2 pointer-events-auto animate-fade-in transition-all duration-300">
            {transcript
              .filter((t, idx, arr) => {
                return Boolean(t.visualType && t.visualType !== "none") || Boolean(t.imageUrl) || Boolean(t.text) || idx === arr.length - 1;
              })
              .slice(-2)
              .map((item, idx, arr) => {
                const isAi = item.speaker === "output";
                const isLatestAi = isAi && idx === arr.length - 1;
                const isStreaming = isLatestAi && displayedAiCharCount < (item.text?.length || 0);
                const textToShow = !isLatestAi
                  ? item.text
                  : (item.text ? item.text.slice(0, Math.max(1, displayedAiCharCount)) : "");

                return (
                  <div
                    key={idx}
                    className={`max-w-[95%] sm:max-w-[90%] transition-all ${
                      item.speaker === "input" ? "self-end" : "self-start"
                    }`}
                  >
                    <div
                      className={`p-3.5 px-4.5 rounded-3xl text-xs sm:text-sm leading-relaxed shadow-2xl select-text flex flex-col gap-2 transition-all duration-200 ${
                        item.speaker === "input"
                          ? "liquid-glass-bubble-user text-white rounded-br-md"
                          : "liquid-glass-bubble-ai text-slate-100 rounded-bl-md"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <span
                          className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-lg shrink-0 mt-0.5 shadow-sm font-mono ${
                            item.speaker === "input"
                              ? "bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-sm"
                              : "bg-cyan-500/25 border border-cyan-400/40 text-cyan-300 shadow-[0_0_8px_rgba(34,211,238,0.25)]"
                          }`}
                        >
                          {item.speaker === "input" ? "Anda" : "Anara"}
                        </span>
                        <div className="break-words font-normal text-slate-100 leading-relaxed flex-1">
                          {!item.text ? (
                            <div className="flex items-center gap-1.5 py-1">
                              <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce [animation-delay:0ms]" />
                              <span className="w-1.5 h-1.5 bg-cyan-300 rounded-full animate-bounce [animation-delay:150ms]" />
                              <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce [animation-delay:300ms]" />
                            </div>
                          ) : (
                            <span>
                              {textToShow || item.text}
                              {isStreaming && (
                                <span className="inline-block w-1.5 h-3.5 bg-cyan-400 ml-1 align-middle animate-pulse shadow-[0_0_8px_#22d3ee] rounded-xs" />
                              )}
                            </span>
                          )}
                        </div>
                        {isLatestAi && (status === "speaking" || (!item.text && status === "thinking") || isStreaming) && (
                          <div className="flex items-center gap-0.5 shrink-0 mt-1" title="Sedang Berbicara">
                            <span className="w-1 h-3 bg-cyan-400 rounded-full animate-bounce [animation-delay:0ms]" />
                            <span className="w-1 h-4.5 bg-cyan-300 rounded-full animate-bounce [animation-delay:150ms]" />
                            <span className="w-1 h-2 bg-cyan-400 rounded-full animate-bounce [animation-delay:300ms]" />
                          </div>
                        )}
                      </div>

                      {/* ── Holographic Anara HUD in Active Floating Bubble ── */}
                      {item.visualType && item.visualType !== "none" && (
                        <AnaraHUD
                          visualType={item.visualType}
                          imageUrl={item.imageUrl}
                          imageTitle={item.imageTitle}
                          sourceDomain={item.sourceDomain}
                          sourceUrl={item.sourceUrl}
                          imagePrompt={item.imagePrompt}
                          images={item.images}
                          weatherData={item.weatherData}
                          codeData={item.codeData}
                          systemHudData={item.systemHudData}
                          knowledgeCardData={item.knowledgeCardData}
                          todoData={item.todoData}
                          onOpenLightbox={setSelectedPreviewImage}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
          </div>
        )}

        {/* Holographic Projection Card Only in Voice Mode (when explicit visual media is requested) */}
        {!isChatDrawerOpen && interactionMode === "voice" && latestVisual && (
          <div className="w-full flex flex-col gap-2 pointer-events-auto animate-fade-in transition-all duration-300 max-w-[95%] sm:max-w-[90%] self-center mb-1">
            <AnaraHUD
              visualType={latestVisual.visualType}
              imageUrl={latestVisual.imageUrl}
              imageTitle={latestVisual.imageTitle}
              sourceDomain={latestVisual.sourceDomain}
              sourceUrl={latestVisual.sourceUrl}
              imagePrompt={latestVisual.imagePrompt}
              images={latestVisual.images}
              weatherData={latestVisual.weatherData}
              codeData={latestVisual.codeData}
              systemHudData={latestVisual.systemHudData}
              knowledgeCardData={latestVisual.knowledgeCardData}
              todoData={latestVisual.todoData}
              onOpenLightbox={setSelectedPreviewImage}
            />
          </div>
        )}

        {/* Non-intrusive Mic Denied Alert Pill */}
        {micDenied && interactionMode === "voice" && (
          <div className="animate-fade-in pointer-events-auto bg-rose-500/20 border border-rose-500/40 text-rose-200 text-xs px-4 py-2 rounded-2xl backdrop-blur-xl shadow-lg flex items-center gap-2 font-mono">
            <svg className="w-4 h-4 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span suppressHydrationWarning>Akses mikrofon ditolak. Izinkan izin mikrofon di browser Anda.</span>
          </div>
        )}

        {/* Main Clean Liquid Glass Panel */}
        <div className="w-full liquid-glass rounded-2xl p-3 px-4 shadow-2xl flex flex-col gap-3 border border-white/20 shadow-black/70 pointer-events-auto">
          {/* Top Row: Clean Mode Switcher Tabs */}
          <div className="flex items-center justify-between gap-2 w-full pb-2 border-b border-white/10">
            <div className="flex items-center p-1 bg-black/40 border border-white/10 rounded-xl gap-1">
              <button
                type="button"
                onClick={() => onSetInteractionMode?.("voice")}
                className={`flex items-center gap-1.5 py-1 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer font-mono ${
                  interactionMode === "voice"
                    ? "bg-gradient-to-r from-indigo-500 to-cyan-500 text-white shadow-md shadow-cyan-500/25"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 02-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
                <span>Mode Suara (Mic)</span>
              </button>

              <button
                type="button"
                onClick={() => onSetInteractionMode?.("chat")}
                className={`flex items-center gap-1.5 py-1 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer font-mono ${
                  interactionMode === "chat"
                    ? "bg-gradient-to-r from-purple-500 to-indigo-500 text-white shadow-md shadow-indigo-500/25"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                <span>Mode Chat (Teks)</span>
              </button>
            </div>

            {/* Quick action utility buttons */}
            <div className="flex items-center gap-1.5">
              {/* Interrupt button (if AI is talking) */}
              {status === "speaking" && (
                <button
                  onClick={onInterrupt}
                  className="p-1.5 px-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 transition-all hover:scale-105 active:scale-95 cursor-pointer flex items-center gap-1 text-xs font-medium font-mono"
                  title="Sela AI"
                >
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                  <span className="hidden sm:inline">Sela</span>
                </button>
              )}

              {/* Clear transcript button */}
              {transcript.length > 0 && (
                <button
                  onClick={onClearTranscript}
                  className="p-1.5 rounded-xl bg-white/[0.06] text-slate-400 border border-white/10 hover:bg-white/[0.12] hover:text-white transition-all hover:scale-105 active:scale-95 cursor-pointer"
                  title="Bersihkan Layar"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* ── MODE 1: DEDICATED VOICE MODE ── */}
          {interactionMode === "voice" && (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 py-1">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                {/* Live soundwave equalizer */}
                <div className="flex items-center gap-1 h-6 shrink-0 px-2 py-1 bg-black/30 rounded-xl border border-white/10">
                  {[...Array(6)].map((_, i) => {
                    const barHeight = Math.max(
                      4,
                      Math.min(20, (activeIntensity * 35 * (1 + (i % 3) * 0.4)) + (status !== "idle" ? 6 : 4))
                    );
                    return (
                      <span
                        key={i}
                        className={`w-1 rounded-full transition-all duration-75 ${
                          status === "speaking"
                            ? "bg-cyan-400 shadow-[0_0_8px_#22d3ee]"
                            : status === "listening"
                            ? "bg-indigo-400 shadow-[0_0_8px_#818cf8]"
                            : "bg-slate-600"
                        }`}
                        style={{ height: `${barHeight}px` }}
                      />
                    );
                  })}
                </div>

                <div className="truncate">
                  <p className="text-xs font-semibold text-white truncate flex items-center gap-1.5" suppressHydrationWarning>
                    {status === "speaking"
                      ? "AI Sedang Berbicara..."
                      : status === "thinking"
                      ? "AI Sedang Berpikir & Menyiapkan..."
                      : isMuted
                      ? "Mikrofon Dibisukan"
                      : isMicActive
                      ? "Mendengarkan suara Anda..."
                      : "Mikrofon Siap"}
                  </p>
                  <p className="text-[11px] text-slate-400 truncate" suppressHydrationWarning>
                    {isMicActive
                      ? "Bicara bebas secara langsung (Anara smart auto-vad)"
                      : "Klik tombol aktifkan untuk mulai bicara"}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto">
                {!isMicActive ? (
                  <button
                    onClick={onStartSession}
                    disabled={!isConnected}
                    className={`py-2 px-4.5 rounded-xl font-semibold text-white text-xs transition-all duration-300 flex items-center justify-center gap-2 shadow-lg shrink-0 w-full sm:w-auto font-mono ${
                      isConnected
                        ? "bg-gradient-to-r from-indigo-500 via-purple-500 to-cyan-400 hover:opacity-95 hover:scale-105 active:scale-95 shadow-indigo-500/40 cursor-pointer"
                        : "bg-slate-800/80 text-slate-500 cursor-not-allowed border border-slate-700/50"
                    }`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 02-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                    </svg>
                    <span>Aktifkan Mic</span>
                  </button>
                ) : (
                  <button
                    onClick={onToggleMute}
                    className={`py-2 px-4 rounded-xl border transition-all hover:scale-105 active:scale-95 cursor-pointer flex items-center gap-2 text-xs font-semibold w-full sm:w-auto justify-center font-mono ${
                      isMuted
                        ? "bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-[0_0_10px_rgba(244,63,94,0.3)]"
                        : "bg-white/[0.06] text-slate-200 border-white/10 hover:bg-white/[0.12]"
                    }`}
                  >
                    {isMuted ? (
                      <>
                        <svg className="w-3.5 h-3.5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                        </svg>
                        <span>Unmute Mic</span>
                      </>
                    ) : (
                      <>
                        <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 02-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                        </svg>
                        <span>Mute Mic</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* ── MODE 2: DEDICATED TEXT CHAT MODE ── */}
          {interactionMode === "chat" && (
            <form onSubmit={handleFormSubmit} className="flex items-center gap-2 w-full pt-0.5">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  placeholder="Ketik pertanyaan atau minta visual (cth: 'cuaca jakarta', 'skrip python', 'foto monas')..."
                  className="w-full bg-black/40 border border-white/15 rounded-xl py-2.5 pl-4 pr-9 text-xs sm:text-sm text-white placeholder-slate-400 focus:outline-none focus:border-indigo-400/60 transition-all"
                  autoFocus
                />
                {inputMessage && (
                  <button
                    type="button"
                    onClick={() => setInputMessage("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs p-1 cursor-pointer"
                  >
                    ✕
                  </button>
                )}
              </div>

              <button
                type="submit"
                disabled={!inputMessage.trim()}
                className={`py-2.5 px-4.5 rounded-xl flex items-center justify-center gap-1.5 text-xs font-semibold text-white transition-all duration-200 shadow-md shrink-0 font-mono ${
                  inputMessage.trim()
                    ? "bg-gradient-to-r from-purple-500 via-indigo-500 to-cyan-400 hover:opacity-95 hover:scale-105 active:scale-95 shadow-indigo-500/40 cursor-pointer"
                    : "bg-white/[0.04] border border-white/10 text-slate-600 cursor-not-allowed"
                }`}
                title="Kirim Pesan"
              >
                <span>Kirim</span>
                <svg className="w-3.5 h-3.5 rotate-90" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                </svg>
              </button>
            </form>
          )}
        </div>
      </footer>

      {/* ── Real Web Photo Fullscreen Lightbox Modal ── */}
      {selectedPreviewImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/85 backdrop-blur-2xl animate-fade-in select-none"
          onClick={() => setSelectedPreviewImage(null)}
        >
          <div
            className="relative max-w-4xl w-full bg-slate-950/90 border border-cyan-400/50 rounded-3xl overflow-hidden shadow-[0_0_60px_rgba(34,211,238,0.3)] flex flex-col pointer-events-auto animate-scale-up"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3.5 bg-gradient-to-r from-cyan-950 via-slate-900 to-indigo-950 border-b border-cyan-400/30">
              <div className="flex items-center gap-2.5 max-w-[70%]">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee] shrink-0" />
                <div className="truncate">
                  <h3 className="text-xs sm:text-sm font-bold text-white tracking-wider font-mono uppercase truncate">
                    {selectedPreviewImage.title || "FOTO ASLI PENCARIAN WEB"}
                  </h3>
                  <p className="text-[10px] text-cyan-300/80 font-mono truncate">
                    Sumber: {selectedPreviewImage.sourceDomain || "Google / Web Search"}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {selectedPreviewImage.sourceUrl && (
                  <a
                    href={selectedPreviewImage.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 rounded-xl bg-indigo-500/20 hover:bg-indigo-500/40 border border-indigo-400/50 text-indigo-200 text-xs font-mono font-medium transition-all flex items-center gap-1.5 cursor-pointer shadow-lg hover:scale-105"
                    title="Kunjungi Sumber Web"
                  >
                    <span>Kunjungi Web</span>
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                )}

                <button
                  onClick={() => setSelectedPreviewImage(null)}
                  className="p-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition-all cursor-pointer"
                  title="Tutup (Esc)"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            <div className="relative w-full max-h-[70vh] overflow-hidden flex items-center justify-center bg-black/90 p-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={selectedPreviewImage.url}
                alt={selectedPreviewImage.title}
                className="max-h-[66vh] w-auto max-w-full object-contain rounded-2xl shadow-2xl"
                referrerPolicy="no-referrer"
                crossOrigin="anonymous"
                onError={(e) => {
                  const target = e.currentTarget;
                  const proxyUrl = `http://localhost:8000/api/proxy-image?url=${encodeURIComponent(selectedPreviewImage.url)}`;
                  if (target.src !== proxyUrl && !target.src.includes("/api/proxy-image")) {
                    target.src = proxyUrl;
                  }
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Anara Brain Console & SQLite Database Drawer ── */}
      <AnaraBrain
        isOpen={isBrainDrawerOpen}
        onClose={() => setIsBrainDrawerOpen(false)}
        onTriggerAnimation={onTriggerAnimation}
        activeSpeaker={activeSpeaker}
      />
    </div>
  );
}
