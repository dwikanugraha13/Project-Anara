"use client";

import React, { useState } from "react";

export interface WeatherData {
  city: string;
  temp_c: number;
  condition: string;
  humidity: number;
  wind_kmh: number;
  uv_index?: number;
  forecast?: Array<{ day: string; temp_c: number; condition: string }>;
}

export interface CodeData {
  language: string;
  title: string;
  code: string;
  explanation?: string;
}

export interface SystemHudData {
  core_status: string;
  ai_model: string;
  active_keys: number;
  memory_nodes: number;
  latency_ms: number;
  uptime: string;
}

export interface KnowledgeCardData {
  title: string;
  category?: string;
  badge?: string;
  summary: string;
  specs?: Array<{ label: string; value: string }>;
}

export interface TodoData {
  items: Array<{
    id?: number;
    title: string;
    content?: string;
    category?: string;
    is_completed?: number | boolean;
    due_date?: string;
  }>;
}

export interface AnaraHUDProps {
  visualType?: "image" | "weather" | "code" | "system_hud" | "knowledge_card" | "todo_list" | "none";
  imageUrl?: string;
  imageTitle?: string;
  sourceDomain?: string;
  sourceUrl?: string;
  imagePrompt?: string;
  images?: Array<{
    image_url?: string;
    url?: string;
    title?: string;
    source_domain?: string;
    sourceDomain?: string;
    source_url?: string;
    sourceUrl?: string;
    prompt?: string;
  }>;
  weatherData?: WeatherData;
  codeData?: CodeData;
  systemHudData?: SystemHudData;
  knowledgeCardData?: KnowledgeCardData;
  todoData?: TodoData;
  compact?: boolean;
  onOpenLightbox?: (data: { url: string; title: string; sourceDomain?: string; sourceUrl?: string; prompt?: string }) => void;
}

export default function AnaraHUD({
  visualType = "image",
  imageUrl,
  imageTitle,
  sourceDomain,
  sourceUrl,
  imagePrompt,
  images,
  weatherData,
  codeData,
  systemHudData,
  knowledgeCardData,
  todoData,
  compact = false,
  onOpenLightbox,
}: AnaraHUDProps) {
  const [copiedCode, setCopiedCode] = useState(false);
  const [currentImageIndex, setCurrentImageIndex] = useState(0);

  const handleCopyCode = (text: string) => {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
    }
  };

  // Normalize Multi-Image List
  const imageList = React.useMemo(() => {
    if (images && images.length > 0) {
      return images
        .map((im) => ({
          url: im.image_url || im.url || "",
          title: im.title || imageTitle || "Foto Asli Web",
          sourceDomain: im.source_domain || im.sourceDomain || sourceDomain || "Web Search",
          sourceUrl: im.source_url || im.sourceUrl || sourceUrl || "",
          prompt: im.prompt || imagePrompt,
        }))
        .filter((im) => Boolean(im.url));
    }
    if (imageUrl) {
      return [{
        url: imageUrl,
        title: imageTitle || "Foto Asli Web",
        sourceDomain: sourceDomain || "Web Search",
        sourceUrl: sourceUrl || "",
        prompt: imagePrompt,
      }];
    }
    return [];
  }, [images, imageUrl, imageTitle, sourceDomain, sourceUrl, imagePrompt]);

  const activeIdx = Math.min(Math.max(0, currentImageIndex), Math.max(0, imageList.length - 1));
  const currentImg = imageList[activeIdx];

  const handlePrevImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentImageIndex((prev) => (prev > 0 ? prev - 1 : imageList.length - 1));
  };

  const handleNextImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentImageIndex((prev) => (prev < imageList.length - 1 ? prev + 1 : 0));
  };

  // ── 1. Real HD Web Photograph Projection (Multi-Image Carousel / Gallery) ──
  if (visualType === "image" && currentImg) {
    return (
      <div
        className="mt-2.5 rounded-2xl overflow-hidden border border-cyan-400/50 bg-black/70 shadow-[0_0_30px_rgba(34,211,238,0.25)] group relative cursor-pointer transition-all hover:border-cyan-300 hover:shadow-[0_0_40px_rgba(34,211,238,0.4)] select-none"
        onClick={() => onOpenLightbox?.({
          url: currentImg.url,
          title: currentImg.title,
          sourceDomain: currentImg.sourceDomain,
          sourceUrl: currentImg.sourceUrl,
          prompt: currentImg.prompt,
        })}
      >
        {/* HUD Top Bar */}
        <div className="flex items-center justify-between px-3.5 py-1.5 bg-gradient-to-r from-cyan-950/90 via-slate-900/90 to-indigo-950/90 border-b border-cyan-400/30 text-[10px] font-mono text-cyan-300">
          <div className="flex items-center gap-1.5 truncate max-w-[70%]">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_#22d3ee] shrink-0" />
            <span className="font-bold tracking-wider uppercase truncate">
              🔍 PROYEKSI VISUAL • {currentImg.sourceDomain || "WEB SEARCH"}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {imageList.length > 1 && (
              <span className="px-1.5 py-0.2 rounded bg-cyan-400/20 border border-cyan-400/40 text-cyan-200 text-[9px] font-bold">
                {activeIdx + 1} / {imageList.length} FOTO
              </span>
            )}
            <span className="text-[9px] text-cyan-400/90 hover:text-white transition-colors">Perbesar 🔍</span>
          </div>
        </div>

        {/* Image Canvas with Interactive Carousel */}
        <div className="relative aspect-video w-full overflow-hidden bg-slate-950 max-h-[230px]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            key={currentImg.url}
            src={currentImg.url}
            alt={currentImg.title || "Foto Web"}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
            referrerPolicy="no-referrer"
            crossOrigin="anonymous"
            onError={(e) => {
              const target = e.currentTarget;
              const proxyUrl = `http://localhost:8000/api/proxy-image?url=${encodeURIComponent(currentImg.url)}`;
              if (target.src !== proxyUrl && !target.src.includes("/api/proxy-image")) {
                target.src = proxyUrl;
              }
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-black/20 pointer-events-none" />

          {/* Navigation Arrows for Multi-Image (Prev / Next) */}
          {imageList.length > 1 && (
            <>
              <button
                type="button"
                onClick={handlePrevImage}
                className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/60 hover:bg-cyan-500/50 border border-white/20 hover:border-cyan-400 text-white flex items-center justify-center backdrop-blur-md transition-all shadow-lg active:scale-90 z-10"
                title="Foto Sebelumnya"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <button
                type="button"
                onClick={handleNextImage}
                className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/60 hover:bg-cyan-500/50 border border-white/20 hover:border-cyan-400 text-white flex items-center justify-center backdrop-blur-md transition-all shadow-lg active:scale-90 z-10"
                title="Foto Berikutnya"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </>
          )}

          {/* Floating Footer Banner */}
          <div className="absolute bottom-2.5 inset-x-3 flex items-center justify-between pointer-events-none z-10">
            <p className="text-[11px] font-semibold text-white truncate max-w-[70%] drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)] font-sans">
              {currentImg.title || "Foto Asli Web"}
            </p>
            <span className="px-2 py-0.8 rounded-lg bg-cyan-500/40 backdrop-blur-md border border-cyan-400/60 text-cyan-200 text-[9px] font-mono font-medium shadow-lg pointer-events-auto">
              Layar Penuh
            </span>
          </div>
        </div>

        {/* Multi-Image Thumbnail Selector Strip */}
        {imageList.length > 1 && (
          <div
            className="flex items-center gap-1.5 p-2 px-3 bg-black/90 border-t border-cyan-400/20 overflow-x-auto select-none"
            onClick={(e) => e.stopPropagation()}
          >
            {imageList.map((img, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setCurrentImageIndex(idx)}
                className={`relative w-12 h-8 rounded-lg overflow-hidden shrink-0 border transition-all ${
                  idx === activeIdx
                    ? "border-cyan-400 shadow-[0_0_8px_#22d3ee] scale-105"
                    : "border-white/20 opacity-60 hover:opacity-100 hover:border-white/50"
                }`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={img.url}
                  alt={img.title}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── 2. Holographic Weather Forecast HUD ───────────────────────────────────
  if (visualType === "weather" && weatherData) {
    const isRain = weatherData.condition.toLowerCase().includes("hujan");
    return (
      <div className="mt-2.5 rounded-2xl overflow-hidden border border-cyan-400/40 bg-slate-950/80 backdrop-blur-xl p-3.5 shadow-[0_0_30px_rgba(34,211,238,0.2)] text-white select-none">
        {/* HUD Header */}
        <div className="flex items-center justify-between pb-2 border-b border-cyan-400/20 text-[10px] font-mono text-cyan-300">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_#22d3ee]" />
            <span className="font-bold tracking-wider uppercase">ANARA ATMOSPHERE HUD</span>
          </div>
          <span className="text-[10px] text-cyan-400/80 font-mono">LIVE WIB</span>
        </div>

        {/* Main Weather Metric */}
        <div className="flex items-center justify-between py-3 px-1">
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider font-mono">{weatherData.city}</h4>
            <div className="flex items-baseline gap-1 mt-0.5">
              <span className="text-3xl sm:text-4xl font-extrabold text-white font-mono tracking-tight drop-shadow">
                {weatherData.temp_c}°
              </span>
              <span className="text-sm font-semibold text-cyan-300">C</span>
            </div>
            <p className="text-xs font-medium text-cyan-200 mt-0.5">{weatherData.condition}</p>
          </div>

          <div className="flex flex-col items-end gap-1.5">
            <div className="w-12 h-12 rounded-2xl bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center text-2xl shadow-[0_0_15px_rgba(34,211,238,0.3)]">
              {isRain ? "🌧️" : weatherData.temp_c > 30 ? "☀️" : "⛅"}
            </div>
            <div className="flex items-center gap-2 text-[10px] font-mono text-slate-300">
              <span>💧 {weatherData.humidity}%</span>
              <span>💨 {weatherData.wind_kmh} km/j</span>
            </div>
          </div>
        </div>

        {/* 2-Day Forecast Pills */}
        {weatherData.forecast && weatherData.forecast.length > 0 && (
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/10 text-[10px] font-mono">
            {weatherData.forecast.map((fc, idx) => (
              <div key={idx} className="flex items-center justify-between p-1.5 px-2.5 rounded-xl bg-black/40 border border-cyan-400/20">
                <span className="text-slate-400">{fc.day}</span>
                <span className="text-white font-bold">{fc.temp_c}°C • {fc.condition}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── 3. Holographic Sci-Fi Code Terminal ───────────────────────────────────
  if (visualType === "code" && codeData) {
    return (
      <div className="mt-2.5 rounded-2xl overflow-hidden border border-indigo-400/40 bg-slate-950/90 shadow-[0_0_30px_rgba(129,140,248,0.2)] text-white select-text">
        {/* Terminal Header */}
        <div className="flex items-center justify-between px-3.5 py-2 bg-slate-900/90 border-b border-indigo-400/20 text-[10px] font-mono">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
            </div>
            <span className="text-indigo-300 font-bold uppercase tracking-wider">
              {codeData.title || "TERMINAL KODE"}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-md bg-indigo-500/30 text-indigo-200 border border-indigo-400/30 font-bold uppercase text-[9px]">
              {codeData.language || "CODE"}
            </span>
            <button
              onClick={() => handleCopyCode(codeData.code)}
              className="px-2 py-0.5 rounded-md bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition-colors cursor-pointer text-[9px] font-mono"
            >
              {copiedCode ? "✓ Tersalin" : "Salin"}
            </button>
          </div>
        </div>

        {/* Code Content Viewport */}
        <div className="p-3 font-mono text-[11px] leading-relaxed overflow-x-auto max-h-[220px] bg-black/50 text-cyan-200">
          <pre className="whitespace-pre">{codeData.code}</pre>
        </div>

        {codeData.explanation && (
          <div className="px-3.5 py-1.5 bg-slate-900/60 border-t border-white/5 text-[10px] text-slate-400 font-sans">
            💡 {codeData.explanation}
          </div>
        )}
      </div>
    );
  }

  // ── 4. Anara Core Telemetry Diagnostics HUD ───────────────────────────────
  if (visualType === "system_hud" && systemHudData) {
    return (
      <div className="mt-2.5 rounded-2xl overflow-hidden border border-cyan-400/50 bg-slate-950/85 backdrop-blur-xl p-3.5 shadow-[0_0_30px_rgba(34,211,238,0.25)] text-white select-none">
        {/* Header */}
        <div className="flex items-center justify-between pb-2 border-b border-cyan-400/20 text-[10px] font-mono text-cyan-300">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]" />
            <span className="font-bold tracking-wider uppercase">ANARA CORE TELEMETRY</span>
          </div>
          <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-400/40 text-[9px] font-bold">
            {systemHudData.core_status || "ONLINE"}
          </span>
        </div>

        {/* Telemetry Metric Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 py-3 text-[10px] font-mono">
          <div className="p-2 rounded-xl bg-black/40 border border-cyan-400/20 flex flex-col">
            <span className="text-slate-400">AI MODEL</span>
            <span className="text-white font-bold mt-0.5 truncate">{systemHudData.ai_model || "Gemini Live"}</span>
          </div>
          <div className="p-2 rounded-xl bg-black/40 border border-cyan-400/20 flex flex-col">
            <span className="text-slate-400">KEY POOL</span>
            <span className="text-cyan-300 font-bold mt-0.5">{systemHudData.active_keys} Akun Aktif</span>
          </div>
          <div className="p-2 rounded-xl bg-black/40 border border-cyan-400/20 flex flex-col">
            <span className="text-slate-400">MEMORI NODES</span>
            <span className="text-purple-300 font-bold mt-0.5">{systemHudData.memory_nodes} Fakta SQLite</span>
          </div>
          <div className="p-2 rounded-xl bg-black/40 border border-cyan-400/20 flex flex-col">
            <span className="text-slate-400">LATENSI VAD</span>
            <span className="text-emerald-300 font-bold mt-0.5">{systemHudData.latency_ms}ms • {systemHudData.uptime}</span>
          </div>
        </div>
      </div>
    );
  }

  // ── 5. Knowledge & Schematic Infographic Card ──────────────────────────────
  if (visualType === "knowledge_card" && knowledgeCardData) {
    return (
      <div className="mt-2.5 rounded-2xl overflow-hidden border border-cyan-400/40 bg-slate-950/85 backdrop-blur-xl p-3.5 shadow-[0_0_30px_rgba(34,211,238,0.2)] text-white select-none">
        {/* Header */}
        <div className="flex items-center justify-between pb-2 border-b border-cyan-400/20 text-[10px] font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
            <span className="text-indigo-300 font-bold uppercase tracking-wider">
              {knowledgeCardData.category || "SKEMATIK PENGETAHUAN"}
            </span>
          </div>
          {knowledgeCardData.badge && (
            <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 text-[9px] font-bold">
              {knowledgeCardData.badge}
            </span>
          )}
        </div>

        {/* Title & Summary */}
        <div className="py-2.5">
          <h4 className="text-xs sm:text-sm font-bold text-white tracking-wide">{knowledgeCardData.title}</h4>
          <p className="text-[11px] text-slate-300 mt-1 leading-relaxed">{knowledgeCardData.summary}</p>
        </div>

        {/* Specs Grid */}
        {knowledgeCardData.specs && knowledgeCardData.specs.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-2 border-t border-white/10 text-[10px] font-mono">
            {knowledgeCardData.specs.map((sp, idx) => (
              <div key={idx} className="flex items-center justify-between p-1.5 px-2.5 rounded-lg bg-black/40 border border-cyan-400/15">
                <span className="text-slate-400">{sp.label}</span>
                <span className="text-cyan-200 font-semibold text-right">{sp.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── 6. Dynamic To-Do & Task Checklist Card ─────────────────────────────────
  if (visualType === "todo_list" && todoData && todoData.items) {
    return (
      <div className="mt-2.5 rounded-2xl overflow-hidden border border-purple-400/40 bg-slate-950/85 backdrop-blur-xl p-3.5 shadow-[0_0_30px_rgba(168,85,247,0.2)] text-white select-none">
        {/* Header */}
        <div className="flex items-center justify-between pb-2 border-b border-purple-400/20 text-[10px] font-mono text-purple-300">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            <span className="font-bold tracking-wider uppercase">ANARA TASK & TO-DO TRACKER</span>
          </div>
          <span className="text-purple-300/80">{todoData.items.length} Tugas</span>
        </div>

        {/* Items List */}
        <div className="py-2 space-y-1.5 max-h-[180px] overflow-y-auto pr-1">
          {todoData.items.length === 0 ? (
            <p className="text-[11px] text-slate-400 text-center py-2">Tidak ada tugas aktif di database.</p>
          ) : (
            todoData.items.map((td, idx) => (
              <div
                key={idx}
                className={`flex items-start gap-2.5 p-2 rounded-xl border text-xs transition-colors ${
                  td.is_completed
                    ? "bg-black/20 border-white/5 text-slate-500 line-through"
                    : "bg-black/40 border-purple-400/20 text-slate-100"
                }`}
              >
                <span className={`w-4 h-4 rounded-md flex items-center justify-center text-[10px] shrink-0 mt-0.5 border ${
                  td.is_completed ? "bg-emerald-500/20 border-emerald-400/40 text-emerald-300" : "border-purple-400/40 text-purple-300"
                }`}>
                  {td.is_completed ? "✓" : "○"}
                </span>
                <div className="truncate flex-1">
                  <p className="font-medium truncate">{td.title}</p>
                  {td.content && <p className="text-[10px] text-slate-400 truncate mt-0.5">{td.content}</p>}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    );
  }

  return null;
}
