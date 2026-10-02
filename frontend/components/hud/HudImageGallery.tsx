"use client";

import React, { useState, useMemo, useEffect, useCallback } from "react";
import { ImageItem, HudDismissButton } from "./types";
import { getBackendUrl } from "@/lib/apiClient";

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
  const [loadedUrls, setLoadedUrls] = useState<Record<string, boolean>>({});

  const imageList = useMemo(() => {
    if (images && images.length > 0) {
      return images
        .map((im) => ({
          url: im.image_url || im.url || "",
          title: im.title || imageTitle || "Web Visual Content",
          sourceDomain: im.source_domain || im.sourceDomain || sourceDomain || "Web Source",
          sourceUrl: im.source_url || im.sourceUrl || sourceUrl || "",
          prompt: im.prompt || imagePrompt,
        }))
        .filter((im) => Boolean(im.url));
    }
    if (imageUrl) {
      return [{
        url: imageUrl,
        title: imageTitle || "Web Visual Content",
        sourceDomain: sourceDomain || "Web Source",
        sourceUrl: sourceUrl || "",
        prompt: imagePrompt,
      }];
    }
    return [];
  }, [images, imageUrl, imageTitle, sourceDomain, sourceUrl, imagePrompt]);

  const activeIdx = Math.min(Math.max(0, currentImageIndex), Math.max(0, imageList.length - 1));
  const currentImg = imageList[activeIdx];

  const handlePrevImage = useCallback((e?: React.MouseEvent) => {
    e?.stopPropagation();
    setCurrentImageIndex((prev) => (prev > 0 ? prev - 1 : imageList.length - 1));
  }, [imageList.length]);

  const handleNextImage = useCallback((e?: React.MouseEvent) => {
    e?.stopPropagation();
    setCurrentImageIndex((prev) => (prev < imageList.length - 1 ? prev + 1 : 0));
  }, [imageList.length]);

  const triggerLightbox = useCallback(() => {
    if (!currentImg) return;
    onOpenLightbox?.({
      url: currentImg.url,
      title: currentImg.title,
      sourceDomain: currentImg.sourceDomain,
      sourceUrl: currentImg.sourceUrl,
      prompt: currentImg.prompt,
    });
  }, [currentImg, onOpenLightbox]);

  // Keyboard navigation for multi-image carousels with typable element guard & listener cleanup
  useEffect(() => {
    if (imageList.length <= 1) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target) {
        const tagName = target.tagName;
        if (tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT" || target.isContentEditable) {
          return;
        }
      }

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        setCurrentImageIndex((prev) => (prev > 0 ? prev - 1 : imageList.length - 1));
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        setCurrentImageIndex((prev) => (prev < imageList.length - 1 ? prev + 1 : 0));
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [imageList.length]);

  if (!currentImg) return null;

  const isCurrentLoaded = Boolean(loadedUrls[currentImg.url]);

  return (
    <div
      className="mt-2.5 rounded-2xl overflow-hidden border border-white/[0.08] bg-[#060913]/90 backdrop-blur-xl shadow-2xl shadow-black/80 group relative select-none"
      role="region"
      aria-roledescription="carousel"
      aria-label="Visual projection gallery"
    >
      {/* HUD Top Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-white/[0.03] border-b border-white/[0.08] text-[11px] font-mono">
        <div className="flex items-center gap-2 truncate max-w-[65%]">
          <span className="w-2 h-2 rounded-full bg-sky-400 shrink-0" />
          <span className="font-semibold tracking-wider uppercase truncate text-slate-200">
            Visual Projection
          </span>

          {/* Source domain & URL attribution */}
          {currentImg.sourceUrl ? (
            <a
              href={currentImg.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-[10px] font-mono text-slate-300 hover:text-white transition-all truncate shrink-0 cursor-pointer"
              title={`Source: ${currentImg.sourceUrl}`}
            >
              <span className="truncate max-w-[120px]">{currentImg.sourceDomain || "Source"}</span>
              <svg className="w-2.5 h-2.5 opacity-70 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          ) : (
            <span className="px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/[0.08] text-[10px] font-mono text-slate-400 shrink-0 truncate max-w-[120px]">
              {currentImg.sourceDomain || "Web Source"}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {imageList.length > 1 && (
            <span className="px-2 py-0.5 rounded-md bg-white/[0.05] border border-white/[0.08] text-slate-300 text-[10px] font-mono font-medium">
              {activeIdx + 1} / {imageList.length}
            </span>
          )}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              triggerLightbox();
            }}
            className="px-2 py-0.5 rounded-md bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.08] text-slate-300 hover:text-white text-[10px] font-mono font-medium uppercase tracking-wider transition-all cursor-pointer"
            title="Open fullscreen lightbox"
          >
            Expand
          </button>
          <HudDismissButton onDismiss={onDismiss} />
        </div>
      </div>

      {/* Image Canvas with Zero Layout Shift */}
      <div
        className="relative w-full overflow-hidden bg-[#030712] h-[300px] sm:h-[340px] flex items-center justify-center cursor-pointer"
        onClick={triggerLightbox}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            triggerLightbox();
          }
        }}
        aria-label={`View ${currentImg.title} in fullscreen`}
      >
        {/* Skeleton placeholder while image is loading */}
        {!isCurrentLoaded && (
          <div className="absolute inset-0 bg-white/[0.02] animate-pulse flex items-center justify-center">
            <div className="w-8 h-8 rounded-full border-2 border-white/20 border-t-white/80 animate-spin" />
          </div>
        )}

        {/* Blurred fill backdrop */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={currentImg.url}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 w-full h-full object-cover scale-110 blur-2xl opacity-25 pointer-events-none"
          loading="lazy"
          referrerPolicy="no-referrer"
        />

        {/* Main image */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={currentImg.url}
          src={currentImg.url}
          alt={currentImg.title || "Web Visual Content"}
          className={`relative w-full h-full object-contain transition-all duration-300 group-hover:scale-[1.02] ${
            isCurrentLoaded ? "opacity-100" : "opacity-0"
          }`}
          loading="lazy"
          referrerPolicy="no-referrer"
          crossOrigin="anonymous"
          onLoad={() => {
            setLoadedUrls((prev) => ({ ...prev, [currentImg.url]: true }));
          }}
          onError={(e) => {
            const target = e.currentTarget;
            const proxyUrl = `${getBackendUrl()}/api/proxy-image?url=${encodeURIComponent(currentImg.url)}`;
            if (target.src !== proxyUrl && !target.src.includes("/api/proxy-image")) {
              target.src = proxyUrl;
            }
          }}
        />

        {/* Bottom subtle shadow gradient */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent pointer-events-none" />

        {/* Navigation Arrows for Multi-Image */}
        {imageList.length > 1 && (
          <>
            <button
              type="button"
              onClick={handlePrevImage}
              className="absolute left-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/60 hover:bg-white/20 border border-white/10 hover:border-white/30 text-white flex items-center justify-center backdrop-blur-md transition-all shadow-lg active:scale-90 z-10 cursor-pointer"
              title="Previous image (ArrowLeft)"
              aria-label="Previous image"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              type="button"
              onClick={handleNextImage}
              className="absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/60 hover:bg-white/20 border border-white/10 hover:border-white/30 text-white flex items-center justify-center backdrop-blur-md transition-all shadow-lg active:scale-90 z-10 cursor-pointer"
              title="Next image (ArrowRight)"
              aria-label="Next image"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </>
        )}

        {/* Floating Footer Banner */}
        <div className="absolute bottom-3 inset-x-4 flex items-center justify-between pointer-events-none z-10">
          <p className="text-sm font-medium text-white truncate max-w-[70%] drop-shadow-md font-sans">
            {currentImg.title || "Web Visual Content"}
          </p>
          <span className="px-2.5 py-1 rounded-lg bg-black/60 hover:bg-black/80 backdrop-blur-md border border-white/[0.12] text-slate-200 text-[10px] font-mono font-medium shadow-lg pointer-events-auto transition-all">
            FULLSCREEN
          </span>
        </div>
      </div>

      {/* Multi-Image Thumbnail Selector Strip */}
      {imageList.length > 1 && (
        <div
          className="flex items-center gap-2 p-2 px-3 bg-black/50 border-t border-white/[0.08] overflow-x-auto custom-scrollbar select-none min-h-[52px]"
          onClick={(e) => e.stopPropagation()}
        >
          {imageList.map((img, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setCurrentImageIndex(idx)}
              className={`relative w-12 h-8 rounded-lg overflow-hidden shrink-0 border transition-all cursor-pointer bg-[#030712] ${
                idx === activeIdx
                  ? "border-white/60 ring-1 ring-white/30 scale-105 opacity-100"
                  : "border-white/10 opacity-50 hover:opacity-90 hover:border-white/30"
              }`}
              title={`View ${img.title || `image ${idx + 1}`}`}
              aria-label={`Switch to image ${idx + 1}`}
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
