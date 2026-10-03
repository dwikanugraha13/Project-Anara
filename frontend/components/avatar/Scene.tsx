"use client";

/**
 * Scene.tsx
 *
 * Cinematic Studio Rendering for Anara 3D Avatar:
 * - 85mm portrait camera focal framing (FOV 34) for photorealistic human proportions.
 * - 6-Point Warm Studio Portrait Lighting Setup.
 * - Dual-layer Error Boundaries:
 *   1. CanvasErrorBoundary: Catches WebGL/GPU driver disablement cleanly (Zero Red Screen).
 *   2. AvatarErrorBoundary: Catches GLTF animation or mesh loading errors.
 */

import React, { Suspense, Component } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, ContactShadows, Preload } from "@react-three/drei";
import * as THREE from "three";
import Avatar3D, { type Avatar3DHandle } from "./Avatar3D";

// ── Outer Canvas Error Boundary (Catches WebGL Disabled / Driver Loss) ──────
class CanvasErrorBoundary extends Component<
  {
    children: React.ReactNode;
    onWebGLFailure?: () => void;
    isSpeaking?: boolean;
    audioIntensity?: number;
    avatarRef?: React.RefObject<Avatar3DHandle | null>;
  },
  { hasError: boolean; errorMessage: string }
> {
  private rejectionHandler: ((event: PromiseRejectionEvent) => void) | null = null;

  constructor(props: {
    children: React.ReactNode;
    onWebGLFailure?: () => void;
    isSpeaking?: boolean;
    audioIntensity?: number;
    avatarRef?: React.RefObject<Avatar3DHandle | null>;
  }) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, errorMessage: error.message || "WebGL context creation failed" };
  }

  componentDidCatch(error: Error) {
    console.warn("[CanvasErrorBoundary] WebGL GPU context unavailable:", error.message);
    this.props.onWebGLFailure?.();
  }

  componentDidMount() {
    this.rejectionHandler = (event: PromiseRejectionEvent) => {
      const reason = event?.reason?.message || String(event?.reason || "");
      if (
        reason.toLowerCase().includes("webgl") ||
        reason.toLowerCase().includes("context") ||
        reason.toLowerCase().includes("three.webglrenderer")
      ) {
        event.preventDefault();
        this.setState({ hasError: true, errorMessage: reason });
        this.props.onWebGLFailure?.();
      }
    };
    window.addEventListener("unhandledrejection", this.rejectionHandler);
  }

  componentWillUnmount() {
    if (this.rejectionHandler) {
      window.removeEventListener("unhandledrejection", this.rejectionHandler);
      this.rejectionHandler = null;
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <HolographicAvatarFallback
          isSpeaking={this.props.isSpeaking ?? false}
          audioIntensity={this.props.audioIntensity ?? 0}
          avatarRef={this.props.avatarRef}
          errorMessage={this.state.errorMessage}
          onRetry={() => this.setState({ hasError: false, errorMessage: "" })}
        />
      );
    }
    return this.props.children;
  }
}

// ── Holographic Audio-Reactive Fallback Avatar (Zero Black Screen) ────────────
function HolographicAvatarFallback({
  isSpeaking,
  audioIntensity,
  avatarRef,
  errorMessage,
  onRetry,
}: {
  isSpeaking: boolean;
  audioIntensity: number;
  avatarRef?: React.RefObject<Avatar3DHandle | null>;
  errorMessage?: string;
  onRetry: () => void;
}) {
  const [showSettingsHelp, setShowSettingsHelp] = React.useState(false);

  React.useImperativeHandle(avatarRef, () => ({
    setAudioIntensity: () => {},
    resetLipSync: () => {},
    queueTranscriptVisemes: () => {},
    triggerTextMotion: () => {},
    setEmotion: () => {},
    triggerGesture: () => {},
    applyBackendEmotion: (emotion: string, gesture: string) => {
      console.log(`[HolographicAvatar] Received backend emotion: ${emotion}, gesture: ${gesture}`);
    },
    stopDance: () => {},
    playAnimation: () => {},
    registerClips: () => {},
  }), [avatarRef]);

  const pulseScale = 1 + Math.min(0.45, audioIntensity * 0.5);
  const ringOpacity = 0.35 + Math.min(0.55, audioIntensity * 0.65);

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center p-6 select-none pointer-events-auto z-10 overflow-hidden">
      {/* ── Background Subtle Cosmic Radial Glow ── */}
      <div
        className="absolute w-[600px] h-[600px] rounded-full pointer-events-none transition-all duration-300"
        style={{
          background: "radial-gradient(circle, rgba(34, 211, 238, 0.12) 0%, rgba(99, 102, 241, 0.06) 45%, transparent 70%)",
          transform: `scale(${pulseScale})`,
          opacity: ringOpacity,
        }}
      />

      {/* ── Center Holographic Voice Orb ── */}
      <div className="relative flex items-center justify-center mb-8">
        {/* Outer Pulsing Aura Ring */}
        <div
          className="absolute w-64 h-64 rounded-full border border-cyan-500/20 transition-all duration-300 animate-pulse pointer-events-none"
          style={{ transform: `scale(${pulseScale * 1.15})` }}
        />
        {/* Intermediate Specular Kinetic Ring */}
        <div
          className="absolute w-48 h-48 rounded-full border border-dashed border-cyan-400/30 transition-transform duration-500 pointer-events-none"
          style={{
            transform: `scale(${pulseScale}) rotate(${isSpeaking ? 45 : 0}deg)`,
            borderColor: isSpeaking ? "rgba(34, 211, 238, 0.6)" : "rgba(34, 211, 238, 0.25)",
          }}
        />
        {/* Core Glowing Hologram Sphere */}
        <div
          className="relative w-36 h-36 rounded-full flex flex-col items-center justify-center shadow-2xl backdrop-blur-3xl transition-all duration-200"
          style={{
            background: isSpeaking
              ? "radial-gradient(circle at 35% 35%, rgba(34, 211, 238, 0.55) 0%, rgba(99, 102, 241, 0.4) 60%, rgba(6, 9, 19, 0.95) 100%)"
              : "radial-gradient(circle at 35% 35%, rgba(34, 211, 238, 0.28) 0%, rgba(99, 102, 241, 0.2) 60%, rgba(6, 9, 19, 0.95) 100%)",
            boxShadow: isSpeaking
              ? "0 0 50px rgba(34, 211, 238, 0.45), inset 0 0 25px rgba(255, 255, 255, 0.3)"
              : "0 0 30px rgba(34, 211, 238, 0.2), inset 0 0 15px rgba(255, 255, 255, 0.15)",
            border: "1px solid rgba(255, 255, 255, 0.18)",
          }}
        >
          {/* Animated Waveform Visualizer inside Core */}
          <div className="flex items-center gap-1.5 h-8">
            {[0.4, 0.8, 1.2, 0.9, 0.5].map((factor, idx) => {
              const barHeight = isSpeaking
                ? Math.max(8, 28 * factor * (0.4 + audioIntensity * 0.8))
                : 6 + Math.sin(Date.now() / 300 + idx) * 2;
              return (
                <div
                  key={idx}
                  className="w-1.5 rounded-full bg-gradient-to-t from-cyan-400 to-indigo-300 transition-all duration-75"
                  style={{ height: `${barHeight}px` }}
                />
              );
            })}
          </div>
          <span className="text-[10px] font-mono tracking-widest text-cyan-300/80 uppercase mt-1">
            {isSpeaking ? "Speaking" : "Anara Core"}
          </span>
        </div>
      </div>

      {/* ── Status Pill Badge & Helper Controls ── */}
      <div className="max-w-md w-full px-5 py-4 rounded-2xl bg-[#060913]/90 border border-white/10 shadow-2xl backdrop-blur-xl text-center">
        <div className="flex items-center justify-center gap-2 mb-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
          <h4 className="text-xs font-semibold text-white tracking-wide font-sans">
            Mode Hologram Suara Aktif
          </h4>
        </div>
        <p className="text-[11px] text-slate-400 leading-relaxed mb-3 font-sans">
          Akselerasi grafis 3D WebGL dinonaktifkan di browser. Interaksi suara dan teks berjalan 100% normal.
        </p>

        <div className="flex items-center justify-center gap-2">
          <button
            type="button"
            onClick={() => setShowSettingsHelp(!showSettingsHelp)}
            className="px-3 py-1 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] text-slate-300 font-medium transition-colors cursor-pointer"
          >
            {showSettingsHelp ? "Tutup Panduan" : "Cara Aktifkan 3D"}
          </button>
          <button
            type="button"
            onClick={onRetry}
            className="px-3 py-1 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 text-[11px] text-cyan-300 font-medium transition-colors cursor-pointer"
          >
            Coba 3D Lagi
          </button>
          <a
            href="/code"
            className="px-3 py-1 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] text-slate-300 font-medium transition-colors"
          >
            Code Studio
          </a>
        </div>

        {/* Expandable Step-by-Step Guide */}
        {showSettingsHelp && (
          <div className="mt-3.5 pt-3 border-t border-white/10 text-left text-[11px] text-slate-300 space-y-1.5 font-sans leading-normal animate-fade-in">
            <p className="font-semibold text-white">Langkah mengaktifkan 3D di Brave / Chrome:</p>
            <ol className="list-decimal list-inside space-y-1 text-slate-400 pl-1">
              <li>Buka <code className="text-cyan-300 bg-white/5 px-1 py-0.5 rounded font-mono text-[10px]">brave://settings/system</code> (atau Chrome).</li>
              <li>Aktifkan opsi <span className="text-slate-200">"Gunakan akselerasi grafis jika tersedia"</span> (Hardware Acceleration).</li>
              <li>Jika pakai Brave Shields, pastikan Proteksi Sidik Jari tidak diset ke "Agresif".</li>
              <li>Klik <span className="text-cyan-300">Relaunch / Restart</span> browser.</li>
            </ol>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Inner Avatar Error Boundary (Catches Mesh / Rigging Runtime Errors) ──────
class AvatarErrorBoundary extends Component<
  { children: React.ReactNode; onError?: () => void },
  { hasError: boolean; error: string }
> {
  private retryTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(props: { children: React.ReactNode; onError?: () => void }) {
    super(props);
    this.state = { hasError: false, error: "" };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }
  componentDidCatch(error: Error) {
    console.error("[AvatarErrorBoundary] Avatar mesh failed:", error.message);
    this.props.onError?.();
    this.retryTimer = setTimeout(() => this.setState({ hasError: false, error: "" }), 5000);
  }
  componentWillUnmount() {
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
  }
  render() {
    if (this.state.hasError) {
      return null;
    }
    return this.props.children;
  }
}

export interface SceneProps {
  avatarUrl: string;
  isSpeaking: boolean;
  audioIntensity: number;
  avatarRef: React.RefObject<Avatar3DHandle | null>;
  onAvatarLoad?: () => void;
  onDanceStart?: () => void;
  onDanceEnd?: () => void;
  isVoiceMode?: boolean;
}

// ── In-Canvas Loading Indicator (visible while GLTF suspended) ───────────────
function AvatarLoadingIndicator() {
  React.useEffect(() => {
    console.log("[Scene] Avatar3D Suspense: GLTF loading in progress...");
    return () => console.log("[Scene] Avatar3D Suspense: resolved, GLTF loaded");
  }, []);
  return null;
}

// ── Stable constants (outside component to avoid re-render loops) ────────────
const CONTAINER_STYLE: React.CSSProperties = {
  position: "absolute",
  top: 0,
  left: 0,
  width: "100%",
  height: "100%",
  background: "transparent",
};

const CAMERA_CONFIG = {
  position: [0, -0.06, 1.82] as [number, number, number],
  fov: 34,
  near: 0.1,
  far: 100,
};

function checkWebGLSupport(): { supported: boolean; reason?: string } {
  if (typeof window === "undefined") return { supported: true };
  try {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl2", { powerPreference: "default" }) ||
      canvas.getContext("webgl", { powerPreference: "default" }) ||
      canvas.getContext("experimental-webgl");
    if (!gl) {
      return { supported: false, reason: "WebGL context creation failed (hardware acceleration disabled in browser)." };
    }
    return { supported: true };
  } catch (e: any) {
    return { supported: false, reason: e?.message || "WebGL initialization error" };
  }
}

const GL_CONFIG = {
  antialias: true,
  powerPreference: "default" as const,
  toneMapping: THREE.ACESFilmicToneMapping,
  toneMappingExposure: 1.05,
  outputColorSpace: THREE.SRGBColorSpace,
  failIfMajorPerformanceCaveat: false,
};

const SHADOWS_CONFIG = { type: THREE.PCFSoftShadowMap } as const;

export default function Scene({
  avatarUrl,
  isSpeaking,
  audioIntensity,
  avatarRef,
  onAvatarLoad,
  onDanceStart,
  onDanceEnd,
  isVoiceMode = true,
}: SceneProps) {
  const [webglSupported, setWebglSupported] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    console.log("[Scene] Component mounted, checking WebGL support...");
    const res = checkWebGLSupport();
    console.log("[Scene] WebGL support check result:", res);
    if (!res.supported) {
      setWebglSupported(false);
      onAvatarLoad?.();
    } else {
      setWebglSupported(true);
    }
  }, [onAvatarLoad]);

  if (webglSupported === false) {
    return (
      <div style={CONTAINER_STYLE}>
        <HolographicAvatarFallback
          isSpeaking={isSpeaking}
          audioIntensity={audioIntensity}
          avatarRef={avatarRef}
          errorMessage="Browser WebGL context is currently unavailable."
          onRetry={() => {
            const res = checkWebGLSupport();
            setWebglSupported(res.supported);
          }}
        />
      </div>
    );
  }

  return (
    <div style={CONTAINER_STYLE}>
      <CanvasErrorBoundary
        onWebGLFailure={onAvatarLoad}
        isSpeaking={isSpeaking}
        audioIntensity={audioIntensity}
        avatarRef={avatarRef}
      >
        <Canvas
          id="avatar-canvas"
          camera={CAMERA_CONFIG}
          shadows={SHADOWS_CONFIG}
          gl={GL_CONFIG}
          dpr={[1, 1.5]}
          onCreated={({ gl }) => {
            gl.debug.checkShaderErrors = false;
          }}
        >
          {/* ── 6-Point Warm Studio Portrait Lighting Setup ── */}
          <ambientLight intensity={0.85} color="#fff8f0" />

          {/* 1. Key Light: Soft Warm Daylight Portrait Light */}
          <directionalLight
            position={[1.8, 2.2, 2.4]}
            intensity={1.35}
            color="#fff5ea"
          />

          {/* 2. Fill Light: Soft Warm Daylight */}
          <directionalLight
            position={[-1.8, 1.6, 2.2]}
            intensity={0.85}
            color="#fef3e8"
          />

          {/* 3. Front Beauty Glow: Soft Dewy Radiant Skin Light */}
          <pointLight position={[0, 0.45, 1.6]} intensity={0.65} color="#fff6ed" />

          {/* 4. Golden Rim Light (Right Back Shoulder/Hair Accent) */}
          <pointLight position={[2.4, 1.8, -1.6]} intensity={2.0} color="#fed7aa" />

          {/* 5. Soft Edge Light (Left Back Silhouette Definition) */}
          <pointLight position={[-2.4, 1.8, -1.6]} intensity={1.6} color="#e2e8f0" />

          {/* 6. Under-chin Bounce for Warm Radiant Skin Subsurface Glow */}
          <pointLight position={[0, -0.6, 1.1]} intensity={0.60} color="#fed7aa" />

          {/* Soft Contact Ground Shadow */}
          <ContactShadows
            position={[0, -1.48, 0]}
            opacity={0.65}
            scale={4.0}
            blur={2.2}
            far={2.5}
            resolution={512}
            frames={1}
          />

          {/* 3D Photorealistic Avatar */}
          <AvatarErrorBoundary onError={onAvatarLoad}>
            <Suspense fallback={<AvatarLoadingIndicator />}>
              <Avatar3D
                ref={avatarRef}
                url={avatarUrl}
                isSpeaking={isSpeaking}
                audioIntensity={audioIntensity}
                onLoad={onAvatarLoad}
                onDanceStart={onDanceStart}
                onDanceEnd={onDanceEnd}
                isVoiceMode={isVoiceMode}
              />
              <Preload all />
            </Suspense>
          </AvatarErrorBoundary>

          {/* Smooth Cinematic Orbit Controls */}
          <OrbitControls
            target={[0, 0.05, 0]}
            minDistance={0.8}
            maxDistance={2.6}
            minPolarAngle={Math.PI * 0.32}
            maxPolarAngle={Math.PI * 0.58}
            minAzimuthAngle={-Math.PI * 0.3}
            maxAzimuthAngle={Math.PI * 0.3}
            enablePan={false}
            enableDamping
            dampingFactor={0.05}
          />
        </Canvas>
      </CanvasErrorBoundary>
    </div>
  );
}
