"use client";

import React, { useState, useMemo } from "react";
import { ImageItem, HudDismissButton } from "./types";

interface HudImageGalleryProps {
  images?: ImageItem[];
  imageUrl?: string;
  imageTitle?: string;
  sourceDomain?: string;
  sourceUrl?: string;
  imagePrompt?: string;
  onOpenLightbox?: (data: { url: string; title: string; sourceDomain?: string; sourceUrl?: string; prompt?: string }) => void;
  onDismiss?: () => void;
}

export default function HudImageGallery({
  images,
  imageUrl,
  imageTitle,
  sourceDomain,
  sourceUrl,
  imagePrompt,
  onOpenLightbox,
  onDismiss,
}: HudImageGalleryProps) {
  const [currentImageIndex, setCurrentImageIndex] = useState(0);

  const imageList = useMemo(() => {
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

  if (!currentImg) return null;

  const handlePrevImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentImageIndex((prev) => (prev > 0 ? prev - 1 : imageList.length - 1));
  };

  const handleNextImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentImageIndex((prev) => (prev < imageList.length - 1 ? prev + 1 : 0));
  };

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
      <div className="flex items-center justify-between px-4 py-2 bg-gradient-to-r from-cyan-950/90 via-slate-900/90 to-indigo-950/90 border-b border-cyan-400/30 text-[11px] font-mono text-cyan-300">
        <div className="flex items-center gap-2 truncate max-w-[70%]">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_#22d3ee] shrink-0" />
          <span className="font-bold tracking-widest uppercase truncate">
            Proyeksi Visual • {currentImg.sourceDomain || "Web Search"}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {imageList.length > 1 && (
            <span className="px-2 py-0.5 rounded bg-cyan-400/20 border border-cyan-400/40 text-cyan-200 text-[10px] font-bold">
              {activeIdx + 1} / {imageList.length} FOTO
            </span>
          )}
          <span className="text-[10px] text-cyan-400/90 hover:text-white transition-colors uppercase tracking-wider">Perbesar</span>
          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      {/* Image Canvas with Interactive Carousel */}
      <div className="relative w-full overflow-hidden bg-slate-950 h-[300px] sm:h-[340px]">
        {/* Blurred fill backdrop */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={currentImg.url}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 w-full h-full object-cover scale-110 blur-2xl opacity-40"
          loading="lazy"
          referrerPolicy="no-referrer"
        />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={currentImg.url}
          src={currentImg.url}
          alt={currentImg.title || "Foto Web"}
          className="relative w-full h-full object-contain transition-transform duration-500 group-hover:scale-[1.03]"
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
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-transparent pointer-events-none" />

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
        <div className="absolute bottom-3 inset-x-4 flex items-center justify-between pointer-events-none z-10">
          <p className="text-sm font-semibold text-white truncate max-w-[70%] drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)] font-sans">
            {currentImg.title || "Foto Asli Web"}
          </p>
          <span className="px-2.5 py-1 rounded-lg bg-cyan-500/40 backdrop-blur-md border border-cyan-400/60 text-cyan-200 text-[10px] font-mono font-medium shadow-lg pointer-events-auto">
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
