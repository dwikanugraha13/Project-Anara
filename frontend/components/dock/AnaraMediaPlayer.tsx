"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import type { MediaTrack } from "@/hooks/useWebSocket";

/**
 * AnaraMediaPlayer
 *
 * Holographic media surface for Anara. Playback runs through the OFFICIAL YouTube
 * IFrame Player API (ToS-compliant), while the chrome around it matches the
 * JARVIS-style neon HUD used elsewhere in the app.
 *
 * Two presentations:
 * - kind="music": compact player card (thumbnail + metadata + transport controls),
 *   the iframe itself stays hidden (audio only).
 * - kind="video": responsive 16:9 embed with the same header/controls.
 *
 * Audio ducking: when Anara talks (or dance mode runs) the volume automatically
 * drops so the music never bleeds into the microphone and triggers false VAD.
 */

export interface MediaSession {
  kind: "music" | "video";
  videoId: string;
  title: string;
  channel?: string;
  thumbnail?: string;
  duration?: string;
  queue?: MediaTrack[];
  /** Set when this track belongs to a saved playlist. */
  playlistName?: string;
  playlistIndex?: number;
  playlistTotal?: number;
  playlistTracks?: MediaTrack[];
}

export interface AnaraMediaPlayerProps {
  session: MediaSession;
  /** True while Anara is speaking / dance mode — triggers volume ducking. */
  ducked?: boolean;
  /** External control signal from voice commands. */
  controlSignal?: { action: "stop" | "pause" | "resume" | "next" | "prev"; nonce: number } | null;
  onClose: () => void;
  onTrackChange?: (track: MediaSession) => void;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    YT?: any;
    onYouTubeIframeAPIReady?: () => void;
  }
}

const NORMAL_VOLUME = 85;
const DUCKED_VOLUME = 15;

let ytApiPromise: Promise<void> | null = null;

/** Loads the YouTube IFrame API once and resolves when it is ready. */
function loadYouTubeApi(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.YT?.Player) return Promise.resolve();
  if (ytApiPromise) return ytApiPromise;

  ytApiPromise = new Promise<void>((resolve) => {
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      prev?.();
      resolve();
    };
    if (!document.querySelector('script[src*="youtube.com/iframe_api"]')) {
      const tag = document.createElement("script");
      tag.src = "https://www.youtube.com/iframe_api";
      tag.async = true;
      document.head.appendChild(tag);
    }
  });
  return ytApiPromise;
}

function normalizeTrack(t: MediaTrack): { videoId: string; title: string; channel?: string; thumbnail?: string; duration?: string } | null {
  const id = t.videoId || t.video_id;
  if (!id) return null;
  return {
    videoId: id,
    title: t.title || "Media",
    channel: t.channel,
    thumbnail: t.thumbnail,
    duration: t.duration,
  };
}

function formatTime(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return "0:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function AnaraMediaPlayer({
  session,
  ducked = false,
  controlSignal,
  onClose,
  onTrackChange,
}: AnaraMediaPlayerProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<any>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastNonceRef = useRef<number>(-1);
  // Guards against React Strict Mode double-mounting the player in dev
  const initializedRef = useRef(false);
  // Tracks the videoId actually loaded inside the iframe (metadata alone is not enough)
  const loadedVideoIdRef = useRef<string | null>(null);

  const [ready, setReady] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [position, setPosition] = useState(0);
  const [length, setLength] = useState(0);
  const [current, setCurrent] = useState(session);
  const [needsGesture, setNeedsGesture] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showPlaylist, setShowPlaylist] = useState(false);

  const isMusic = current.kind === "music";

  // Keep local state in sync when a brand new session arrives — and, crucially,
  // tell the existing player to LOAD the new video. Updating metadata alone left
  // the iframe playing the previous track ("ganti lagu" bug).
  useEffect(() => {
    setCurrent(session);

    if (!session?.videoId) return;
    if (loadedVideoIdRef.current === session.videoId) return; // same track — nothing to do

    const p = playerRef.current;
    if (p?.loadVideoById) {
      console.log(`[Media] Loading new track: ${session.videoId} — "${session.title}"`);
      loadedVideoIdRef.current = session.videoId;
      try {
        p.loadVideoById(session.videoId);
        p.setVolume?.(ducked ? DUCKED_VOLUME : NORMAL_VOLUME);
      } catch (err) {
        console.warn("[Media] loadVideoById failed:", err);
      }
      // Reset transport UI so progress/duration never mix across tracks
      setPosition(0);
      setLength(0);
      setIsPaused(false);
      setNeedsGesture(false);
      setLoadError(null);
    }
    // `ducked` intentionally excluded — volume has its own effect
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  const playNext = useCallback(() => {
    const queue = current.queue ?? [];
    const next = queue.map(normalizeTrack).find(Boolean);
    if (!next) {
      onClose();
      return;
    }
    const rest = queue.slice(queue.findIndex((q) => (q.videoId || q.video_id) === next.videoId) + 1);
    const updated: MediaSession = {
      kind: current.kind,
      videoId: next.videoId,
      title: next.title,
      channel: next.channel,
      thumbnail: next.thumbnail,
      duration: next.duration,
      queue: rest,
    };
    setCurrent(updated);
    onTrackChange?.(updated);
    if (playerRef.current?.loadVideoById) {
      loadedVideoIdRef.current = next.videoId;
      playerRef.current.loadVideoById(next.videoId);
      setIsPaused(false);
      setPosition(0);
      setLength(0);
    }
  }, [current, onClose, onTrackChange]);

  // ── Create / destroy the YouTube player ────────────────────────────────────
  useEffect(() => {
    if (initializedRef.current) return; // Strict Mode double-invoke guard
    initializedRef.current = true;

    let disposed = false;
    let readyTimer: ReturnType<typeof setTimeout> | null = null;

    loadYouTubeApi().then(async () => {
      if (disposed) return;

      if (!window.YT?.Player) {
        console.warn("[Media] YouTube IFrame API unavailable");
        setLoadError("API YouTube tidak dapat dimuat");
        return;
      }

      // The host div is rendered conditionally, so it may not be attached yet on
      // the first microtask — wait briefly for the ref to settle.
      for (let i = 0; i < 20 && !hostRef.current; i++) {
        await new Promise((r) => setTimeout(r, 50));
        if (disposed) return;
      }
      if (disposed || !hostRef.current) {
        console.warn("[Media] Host element never mounted");
        return;
      }

      // IMPORTANT: YT.Player REPLACES the element it is given with its own iframe.
      // Never hand it a React-managed node — create a throwaway child instead,
      // otherwise React loses the node and the whole card fails to render.
      const mountTarget = document.createElement("div");
      hostRef.current.appendChild(mountTarget);

      console.log(`[Media] Creating YT player for ${current.videoId} (${current.kind})`);
      loadedVideoIdRef.current = current.videoId;

      try {
        playerRef.current = new window.YT.Player(mountTarget, {
          videoId: current.videoId,
          playerVars: {
            autoplay: 1,
            // Native controls stay ENABLED for video so the ⚙️ quality menu works.
            // (setPlaybackQuality() has been ignored by YouTube since 2019, so the
            // native menu is the only way to genuinely let the user pick quality.)
            // They are visually hidden until hover via the CSS overlay below.
            controls: current.kind === "video" ? 1 : 0,
            disablekb: 0,
            modestbranding: 1,
            rel: 0,
            playsinline: 1,
            iv_load_policy: 3,
            cc_load_policy: 0,
            fs: 1,
            origin: typeof window !== "undefined" ? window.location.origin : undefined,
          },
          events: {
            onReady: (e: any) => {
              if (disposed) return;
              if (readyTimer) clearTimeout(readyTimer);
              console.log("[Media] Player ready");
              setReady(true);
              setLoadError(null);
              // Block Picture-in-Picture — YouTube's PiP button used to rip the
              // video out into a floating window on top of the whole UI.
              try {
                const frame: HTMLIFrameElement | undefined = e.target?.getIframe?.();
                if (frame) {
                  frame.setAttribute("allow", "autoplay; encrypted-media; fullscreen");
                  frame.setAttribute("disablepictureinpicture", "true");
                  frame.style.width = "100%";
                  frame.style.height = "100%";
                }
              } catch {
                /* iframe not reachable — non fatal */
              }
              try {
                e.target.setVolume(ducked ? DUCKED_VOLUME : NORMAL_VOLUME);
                e.target.playVideo();
                setLength(e.target.getDuration?.() ?? 0);
                // Autoplay may be silently blocked — detect and offer a gesture
                setTimeout(() => {
                  if (disposed) return;
                  try {
                    const st = e.target.getPlayerState?.();
                    // 1 = PLAYING, 3 = BUFFERING
                    if (st !== 1 && st !== 3) {
                      console.warn(`[Media] Autoplay blocked (state=${st}) — awaiting user gesture`);
                      setNeedsGesture(true);
                    }
                  } catch {
                    /* ignore */
                  }
                }, 1200);
              } catch (err) {
                console.warn("[Media] onReady error:", err);
              }
            },
            onStateChange: (e: any) => {
              if (disposed || !window.YT?.PlayerState) return;
              const S = window.YT.PlayerState;
              if (e.data === S.PLAYING) {
                setIsPaused(false);
                setNeedsGesture(false);
                setLength(playerRef.current?.getDuration?.() ?? 0);
              } else if (e.data === S.PAUSED) {
                setIsPaused(true);
              } else if (e.data === S.ENDED) {
                playNext();
              }
            },
            onError: (e: any) => {
              console.warn(`[Media] YouTube error code=${e?.data} — skipping track`);
              if (!disposed) playNext();
            },
          },
        });

        // If onReady never fires (blocked iframe, network), surface a manual control
        readyTimer = setTimeout(() => {
          if (!disposed && !playerRef.current?.getPlayerState) {
            console.warn("[Media] Player did not become ready within 5s");
            setNeedsGesture(true);
          }
        }, 5000);
      } catch (err) {
        console.error("[Media] Failed to create YT player:", err);
        setLoadError("Gagal membuat pemutar YouTube");
      }
    });

    return () => {
      disposed = true;
      if (readyTimer) clearTimeout(readyTimer);
      if (pollRef.current) clearInterval(pollRef.current);
      try {
        playerRef.current?.destroy?.();
      } catch {
        /* ignore */
      }
      playerRef.current = null;
    };
    // Player instance is created once; track swaps use loadVideoById()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Progress polling ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!ready) return;
    pollRef.current = setInterval(() => {
      try {
        const p = playerRef.current;
        if (!p?.getCurrentTime) return;
        setPosition(p.getCurrentTime() ?? 0);
        const d = p.getDuration?.() ?? 0;
        if (d && Math.abs(d - length) > 1) setLength(d);
      } catch {
        /* ignore transient errors */
      }
    }, 500);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [ready, length]);

  // ── Audio ducking while Anara speaks ──────────────────────────────────────
  useEffect(() => {
    if (!ready || !playerRef.current?.setVolume) return;
    try {
      playerRef.current.setVolume(ducked ? DUCKED_VOLUME : NORMAL_VOLUME);
    } catch {
      /* ignore */
    }
  }, [ducked, ready]);

  // ── Voice-command control signals ─────────────────────────────────────────
  useEffect(() => {
    if (!controlSignal || controlSignal.nonce === lastNonceRef.current) return;
    lastNonceRef.current = controlSignal.nonce;
    const p = playerRef.current;
    switch (controlSignal.action) {
      case "stop":
        try {
          p?.stopVideo?.();
        } catch {
          /* ignore */
        }
        onClose();
        break;
      case "pause":
        try {
          p?.pauseVideo?.();
        } catch {
          /* ignore */
        }
        break;
      case "resume":
        try {
          p?.playVideo?.();
        } catch {
          /* ignore */
        }
        break;
      case "next":
        playNext();
        break;
      case "prev":
        // Backend drives playlist prev; this is the standalone-track fallback
        try {
          p?.seekTo?.(0, true);
          p?.playVideo?.();
        } catch {
          /* ignore */
        }
        break;
    }
  }, [controlSignal, onClose, playNext]);

  const togglePlay = () => {
    const p = playerRef.current;
    if (!p) return;
    try {
      if (isPaused || needsGesture) {
        // A real user gesture — unlocks playback when autoplay was blocked
        p.setVolume?.(ducked ? DUCKED_VOLUME : NORMAL_VOLUME);
        p.playVideo?.();
        setNeedsGesture(false);
      } else {
        p.pauseVideo?.();
      }
    } catch (err) {
      console.warn("[Media] togglePlay failed:", err);
    }
  };

  const progressPct = length > 0 ? Math.min(100, (position / length) * 100) : 0;
  const hasQueue = (current.queue?.length ?? 0) > 0;

  // ── Playlist session info ────────────────────────────────────────────────
  const plTracks = current.playlistTracks ?? [];
  const isPlaylist = Boolean(current.playlistName) && plTracks.length > 0;
  const plIndex = current.playlistIndex ?? 0;
  const plTotal = current.playlistTotal ?? plTracks.length;

  /** Jumps straight to a track in the playlist (click on the list). */
  const jumpToTrack = (idx: number) => {
    const t = plTracks[idx];
    const vid = t?.videoId || t?.video_id;
    if (!vid || !playerRef.current?.loadVideoById) return;
    loadedVideoIdRef.current = vid;
    try {
      playerRef.current.loadVideoById(vid);
      playerRef.current.setVolume?.(ducked ? DUCKED_VOLUME : NORMAL_VOLUME);
    } catch (err) {
      console.warn("[Media] jumpToTrack failed:", err);
    }
    setCurrent((prev) => ({
      ...prev,
      videoId: vid,
      title: t.title || prev.title,
      channel: t.channel ?? prev.channel,
      thumbnail: t.thumbnail ?? prev.thumbnail,
      duration: t.duration ?? prev.duration,
      playlistIndex: idx,
      queue: plTracks.slice(idx + 1),
    }));
    setPosition(0);
    setLength(0);
    setIsPaused(false);
    setNeedsGesture(false);
  };

  return (
    <div className="relative rounded-2xl border border-cyan-400/40 bg-slate-950/90 backdrop-blur-xl shadow-[0_0_30px_rgba(34,211,238,0.22)] text-white select-none">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 rounded-t-2xl bg-gradient-to-r from-cyan-950/80 via-slate-900/80 to-indigo-950/80 border-b border-cyan-400/25 text-[11px] font-mono">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`w-2 h-2 rounded-full shrink-0 shadow-[0_0_6px_#22d3ee] ${
              isPaused ? "bg-slate-500" : "bg-cyan-400 animate-pulse"
            }`}
          />
          <span className="text-cyan-300 font-bold uppercase tracking-widest truncate">
            {isPlaylist ? current.playlistName : isMusic ? "Anara Music" : "Anara Video"}
            {ducked && !isPaused && <span className="ml-2 text-cyan-500/70 normal-case">· volume diturunkan</span>}
          </span>
          {isPlaylist && (
            <span className="px-2 py-0.5 rounded bg-indigo-500/20 border border-indigo-400/40 text-indigo-200 text-[10px] font-bold tabular-nums shrink-0">
              {plIndex + 1}/{plTotal}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isPlaylist && (
            <button
              type="button"
              onClick={() => setShowPlaylist((v) => !v)}
              title={showPlaylist ? "Sembunyikan daftar lagu" : "Lihat daftar lagu"}
              aria-label="Daftar lagu"
              className={`w-7 h-7 rounded-full border flex items-center justify-center transition-all active:scale-90 cursor-pointer ${
                showPlaylist
                  ? "bg-cyan-500/30 border-cyan-400/60 text-cyan-100"
                  : "bg-black/60 border-white/20 text-slate-300 hover:text-white hover:border-cyan-400/50"
              }`}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M4 6h16M4 12h16M4 18h10" />
              </svg>
            </button>
          )}
          {current.duration && (
            <span className="px-2 py-0.5 rounded bg-cyan-400/15 border border-cyan-400/30 text-cyan-200 text-[10px] font-bold">
              {current.duration}
            </span>
          )}
          <button
            type="button"
            aria-label="Tutup pemutar"
            title="Tutup (Esc)"
            onClick={onClose}
            className="w-7 h-7 rounded-full bg-black/60 hover:bg-rose-500/70 border border-white/20 hover:border-rose-300 text-slate-300 hover:text-white flex items-center justify-center backdrop-blur-md transition-all shadow-lg active:scale-90 cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Video surface.
          For music we still need a REAL-sized iframe (YouTube refuses to play in a
          0x0 player), so it is parked off-screen instead of being collapsed. */}
      {isMusic ? (
        <div
          aria-hidden="true"
          className="absolute -left-[9999px] top-0 w-[240px] h-[135px] opacity-0 pointer-events-none"
        >
          <div ref={hostRef} className="w-full h-full" />
        </div>
      ) : (
        <div className="group/video relative w-full aspect-video max-h-[40vh] bg-black overflow-hidden">
          {/* The iframe itself is always visible; YouTube auto-hides its own chrome
              when the pointer leaves, so hovering reveals controls + ⚙️ quality. */}
          <div ref={hostRef} className="w-full h-full" />
          {/* Hint, fades out once the user hovers (i.e. once controls are visible) */}
          <div className="pointer-events-none absolute bottom-2 right-3 opacity-90 group-hover/video:opacity-0 transition-opacity duration-200">
            <span className="px-2 py-1 rounded-md bg-black/70 border border-white/15 text-[10px] font-mono text-slate-300 backdrop-blur-sm">
              arahkan kursor untuk kontrol &amp; kualitas
            </span>
          </div>
        </div>
      )}

      {/* Body */}
      <div className="p-4 flex items-center gap-4">
        {isMusic && (
          <div className="relative w-16 h-16 rounded-xl overflow-hidden border border-cyan-400/30 bg-slate-900 shrink-0">
            {current.thumbnail ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={current.thumbnail}
                alt={current.title}
                className="w-full h-full object-cover"
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-cyan-400 text-xl">♪</div>
            )}
            {!isPaused && (
              <div className="absolute inset-0 bg-cyan-400/10 animate-pulse pointer-events-none" />
            )}
          </div>
        )}

        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-white truncate leading-snug">{current.title}</p>
          {current.channel && (
            <p className="text-xs text-slate-400 truncate mt-0.5">{current.channel}</p>
          )}
          {loadError && (
            <p className="text-[11px] text-rose-300 mt-1">{loadError}</p>
          )}
          {needsGesture && !loadError && (
            <p className="text-[11px] text-amber-300 mt-1">
              Browser memblokir putar otomatis — tekan tombol putar.
            </p>
          )}

          {/* Progress */}
          <div className="mt-2.5 flex items-center gap-2">
            <span className="text-[10px] font-mono text-cyan-300 tabular-nums w-9 shrink-0">
              {formatTime(position)}
            </span>
            <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-400 to-indigo-400 shadow-[0_0_8px_rgba(34,211,238,0.6)] transition-[width] duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-[10px] font-mono text-slate-500 tabular-nums w-9 shrink-0 text-right">
              {length ? formatTime(length) : current.duration || "--:--"}
            </span>
          </div>
        </div>

        {/* Transport controls */}
        <div className="flex items-center gap-2 shrink-0">
          {isPlaylist && plIndex > 0 && (
            <button
              type="button"
              onClick={() => jumpToTrack(plIndex - 1)}
              title="Sebelumnya"
              aria-label="Sebelumnya"
              className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 border border-white/20 text-slate-300 hover:text-white flex items-center justify-center transition-all active:scale-90 cursor-pointer"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M18 19l-9-7 9-7zM7 5h2v14H7z" />
              </svg>
            </button>
          )}
          <button
            type="button"
            onClick={togglePlay}
            title={isPaused || needsGesture ? "Putar" : "Jeda"}
            aria-label={isPaused || needsGesture ? "Putar" : "Jeda"}
            className={`w-10 h-10 rounded-full border flex items-center justify-center transition-all active:scale-90 cursor-pointer ${
              needsGesture
                ? "bg-amber-500/30 hover:bg-amber-500/50 border-amber-400/60 text-amber-100 shadow-[0_0_16px_rgba(251,191,36,0.45)] animate-pulse"
                : "bg-cyan-500/20 hover:bg-cyan-500/40 border-cyan-400/50 text-cyan-200 hover:text-white shadow-[0_0_12px_rgba(34,211,238,0.25)]"
            }`}
          >
            {isPaused || needsGesture ? (
              <svg className="w-4 h-4 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
              </svg>
            )}
          </button>

          {(hasQueue || (isPlaylist && plIndex < plTotal - 1)) && (
            <button
              type="button"
              onClick={() => (isPlaylist ? jumpToTrack(plIndex + 1) : playNext())}
              title="Berikutnya"
              aria-label="Berikutnya"
              className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 border border-white/20 text-slate-300 hover:text-white flex items-center justify-center transition-all active:scale-90 cursor-pointer"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 5l9 7-9 7zM17 5h2v14h-2z" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* ── Collapsible playlist track list ── */}
      {isPlaylist && showPlaylist && (
        <div className="border-t border-cyan-400/20 bg-black/40 rounded-b-2xl">
          <div className="max-h-[220px] overflow-y-auto py-2 px-2 space-y-1 [scrollbar-width:thin] [scrollbar-color:rgba(34,211,238,0.3)_transparent]">
            {plTracks.map((t, idx) => {
              const active = idx === plIndex;
              return (
                <button
                  key={(t.videoId || t.video_id || "") + idx}
                  type="button"
                  onClick={() => jumpToTrack(idx)}
                  className={`w-full flex items-center gap-3 py-2 px-2.5 rounded-xl text-left transition-all cursor-pointer border ${
                    active
                      ? "bg-cyan-500/15 border-cyan-400/40 shadow-[0_0_10px_rgba(34,211,238,0.18)]"
                      : "bg-transparent border-transparent hover:bg-white/[0.06] hover:border-white/10"
                  }`}
                >
                  <span
                    className={`w-6 h-6 rounded-full text-[11px] font-mono font-bold flex items-center justify-center shrink-0 border ${
                      active
                        ? "bg-cyan-400/25 border-cyan-400/50 text-cyan-100"
                        : "bg-white/[0.06] border-white/15 text-slate-400"
                    }`}
                  >
                    {active && !isPaused ? "♪" : idx + 1}
                  </span>
                  <span
                    className={`flex-1 min-w-0 text-xs truncate ${
                      active ? "text-cyan-100 font-semibold" : "text-slate-300"
                    }`}
                  >
                    {t.title || "Tanpa Judul"}
                  </span>
                  {t.duration && (
                    <span className="text-[10px] font-mono text-slate-500 tabular-nums shrink-0">
                      {t.duration}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
